"""Deterministic lifecycle race handling for tutorial chapter 11."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import cast

Cleanup = Callable[[], object]
Plugin = Callable[[int], object]


class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


async def run_cleanup(cleanup: Cleanup) -> None:
    result = cleanup()
    if inspect.isawaitable(result):
        await cast(Awaitable[object], result)


class SetupEffect:
    """An Effect that disposal can discover before setup has completed."""

    def __init__(self) -> None:
        self._cleanup: Cleanup | None = None
        self._setup_done = asyncio.Event()
        self._dispose_task: asyncio.Task[None] | None = None

    async def start(self, setup: Callable[[], object]) -> None:
        try:
            result = setup()
            if inspect.isawaitable(result):
                result = await cast(Awaitable[object], result)
            if result is not None and not callable(result):
                raise TypeError("invalid cleanup")
            self._cleanup = cast(Cleanup | None, result)
        finally:
            self._setup_done.set()

    async def dispose(self) -> None:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        await asyncio.shield(self._dispose_task)

    async def _dispose(self) -> None:
        await self._setup_done.wait()
        if self._cleanup is not None:
            cleanup, self._cleanup = self._cleanup, None
            await run_cleanup(cleanup)


class SetupScope:
    """The smallest scope needed to demonstrate setup/close ordering."""

    def __init__(self) -> None:
        self.effect: SetupEffect | None = None
        self.closed = False

    async def install(self, setup: Callable[[], object]) -> SetupEffect:
        if self.closed:
            raise RuntimeError("scope is closed")
        effect = self.effect = SetupEffect()
        await effect.start(setup)
        if self.closed:
            await effect.dispose()
            raise RuntimeError("scope closed during setup")
        return effect

    async def close(self) -> None:
        self.closed = True
        if self.effect is not None:
            await self.effect.dispose()


class RaceFiber:
    """A Fiber with a serialized runner and integer dependency epochs."""

    def __init__(self, plugin: Plugin) -> None:
        self.plugin = plugin
        self.desired_epoch: int | None = None
        self.active_epoch: int | None = None
        self.state = FiberState.PENDING
        self.removed = False
        self._cleanup: Cleanup | None = None
        self._refresh_requested = False
        self._refresh_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._dispose_requested = False
        self.dispose_started = asyncio.Event()

    def set_epoch(self, epoch: int | None) -> None:
        self.desired_epoch = epoch
        self.request_refresh()

    def request_refresh(self) -> None:
        if self._dispose_requested:
            return
        self._refresh_requested = True
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def wait(self) -> None:
        while self._refresh_task is not None:
            task = self._refresh_task
            await asyncio.shield(task)
            if task is self._refresh_task and not self._refresh_requested:
                return

    async def _refresh_loop(self) -> None:
        while self._refresh_requested and not self._dispose_requested:
            self._refresh_requested = False
            async with self._lock:
                await self._refresh_once()

    async def _refresh_once(self) -> None:
        desired = self.desired_epoch
        if self.state is FiberState.ACTIVE and desired == self.active_epoch:
            return
        if self.state is FiberState.ACTIVE:
            await self._unload()
        if self._dispose_requested or desired is None:
            return
        await self._activate(desired)

    async def _activate(self, epoch: int) -> None:
        self.state = FiberState.LOADING
        result = self.plugin(epoch)
        if inspect.isawaitable(result):
            result = await cast(Awaitable[object], result)
        if result is not None and not callable(result):
            raise TypeError("invalid cleanup")
        self._cleanup = cast(Cleanup | None, result)
        if self._dispose_requested or self.desired_epoch != epoch:
            await self._unload()
            return
        self.active_epoch = epoch
        self.state = FiberState.ACTIVE

    async def _unload(self) -> None:
        self.state = FiberState.UNLOADING
        cleanup, self._cleanup = self._cleanup, None
        try:
            if cleanup is not None:
                await run_cleanup(cleanup)
        finally:
            self.active_epoch = None
            self.state = FiberState.DISPOSED if self._dispose_requested else FiberState.PENDING

    async def dispose(self) -> None:
        if self.state is FiberState.DISPOSED:
            return
        self._dispose_requested = True
        self.dispose_started.set()
        failure: BaseException | None = None
        async with self._lock:
            try:
                if self.state is FiberState.PENDING:
                    self.state = FiberState.DISPOSED
                else:
                    await self._unload()
            except BaseException as error:
                failure = error
                self.state = FiberState.DISPOSED
            finally:
                self.removed = True
        if failure is not None:
            raise BaseExceptionGroup("Fiber cleanup failed", [failure])


class CleanupGroup:
    """Run every cleanup even when earlier ones fail."""

    def __init__(self, cleanups: list[Cleanup]) -> None:
        self.cleanups = cleanups

    async def close(self) -> None:
        errors: list[BaseException] = []
        while self.cleanups:
            try:
                await run_cleanup(self.cleanups.pop())
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("cleanup group failed", errors)
