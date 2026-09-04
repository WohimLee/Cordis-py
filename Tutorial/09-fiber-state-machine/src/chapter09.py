"""A complete, compact Fiber state machine for tutorial chapter 09."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import cast

Cleanup = Callable[[], object]
Plugin = Callable[[object], object]
Validator = Callable[[object], object]
StatusListener = Callable[["Fiber", "FiberState"], None]


class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


class FiberDisposedError(RuntimeError):
    pass


def identity(value: object) -> object:
    return value


class Fiber:
    """One Plugin mount driven by readiness and explicit lifecycle operations."""

    def __init__(
        self,
        plugin: Plugin,
        config: object = None,
        *,
        validator: Validator = identity,
        dependencies_ready: Callable[[], bool] = lambda: True,
    ) -> None:
        self.plugin = plugin
        self._raw_config = config
        self.config = config
        self.validator = validator
        self.dependencies_ready = dependencies_ready
        self.state = FiberState.PENDING
        self.error: BaseException | None = None
        self._cleanups: list[Cleanup] = []
        self._listeners: list[StatusListener] = []
        self._epoch: bool | None = None
        self._failed_epoch: bool | None = None
        self._force_restart = False
        self._dispose_requested = False
        self._refresh_requested = False
        self._refresh_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()

    def __await__(self):  # type: ignore[no-untyped-def]
        return self.wait().__await__()

    def on_status(self, listener: StatusListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def dispose() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return dispose

    def _set_state(self, state: FiberState) -> None:
        old_state = self.state
        if old_state is state:
            return
        self.state = state
        for listener in tuple(self._listeners):
            listener(self, old_state)

    def start(self) -> Fiber:
        self.request_refresh()
        return self

    def request_refresh(self) -> None:
        if self._dispose_requested:
            return
        self._refresh_requested = True
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def wait(self) -> Fiber:
        while self._refresh_task is not None:
            task = self._refresh_task
            await asyncio.shield(task)
            if task is self._refresh_task and not self._refresh_requested:
                break
        if self.error is not None:
            raise self.error
        return self

    async def _refresh_loop(self) -> None:
        while self._refresh_requested and not self._dispose_requested:
            self._refresh_requested = False
            async with self._lifecycle_lock:
                await self._refresh_once()

    async def _refresh_once(self) -> None:
        ready = self.dependencies_ready()
        if not ready:
            if self.state in {FiberState.ACTIVE, FiberState.FAILED}:
                await self._unload()
            return

        force_restart = self._force_restart
        self._force_restart = False
        if self.state is FiberState.ACTIVE and self._epoch is ready and not force_restart:
            return
        if self.state is FiberState.FAILED and self._failed_epoch is ready and not force_restart:
            return
        if self.state in {FiberState.ACTIVE, FiberState.FAILED}:
            await self._unload(settle_pending=False)
        if not self._dispose_requested:
            await self._activate(ready)

    async def _activate(self, epoch: bool) -> None:
        self._set_state(FiberState.LOADING)
        self.error = None
        self._cleanups = []
        try:
            self.config = self.validator(self._raw_config)
            result = self.plugin(self.config)
            if inspect.isawaitable(result):
                result = await cast(Awaitable[object], result)
            if result is not None:
                if not callable(result):
                    raise TypeError("plugin result must be a cleanup callable or None")
                self._cleanups.append(cast(Cleanup, result))
            self._epoch = epoch
            self._failed_epoch = None
            self._set_state(FiberState.ACTIVE)
        except BaseException as error:
            await self._cleanup()
            self.error = error
            self._epoch = None
            self._failed_epoch = epoch
            self._set_state(FiberState.FAILED)

    async def _cleanup(self) -> None:
        while self._cleanups:
            result = self._cleanups.pop()()
            if inspect.isawaitable(result):
                await cast(Awaitable[object], result)

    async def _unload(self, *, settle_pending: bool = True) -> None:
        self._set_state(FiberState.UNLOADING)
        try:
            await self._cleanup()
        finally:
            self._epoch = None
            self.error = None
            if self._dispose_requested:
                self._set_state(FiberState.DISPOSED)
            elif settle_pending:
                self._set_state(FiberState.PENDING)

    def _assert_live(self) -> None:
        if self._dispose_requested or self.state is FiberState.DISPOSED:
            raise FiberDisposedError("disposed Fiber cannot reactivate")

    async def restart(self) -> None:
        self._assert_live()
        self._force_restart = True
        self.error = None
        self.request_refresh()
        await self.wait()

    async def update(self, config: object) -> None:
        self._assert_live()
        if self.state is FiberState.ACTIVE:
            validated = self.validator(config)
            self._raw_config = validated
            await self.restart()
            return
        self._raw_config = config
        self.error = None
        self._force_restart = True
        self.request_refresh()

    async def dispose(self) -> None:
        if self.state is FiberState.DISPOSED:
            return
        self._dispose_requested = True
        async with self._lifecycle_lock:
            if self.state is FiberState.PENDING:
                self._set_state(FiberState.DISPOSED)
            else:
                await self._unload()
