"""A minimal Fiber that owns Effects for tutorial chapter 03."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from enum import StrEnum
from typing import cast

Cleanup = Callable[[], object]
Setup = Callable[[], object]
Plugin = Callable[["Context"], object]


async def _run_cleanup(cleanup: Cleanup) -> None:
    result = cleanup()
    if inspect.isawaitable(result):
        await cast(Awaitable[object], result)


class Effect:
    def __init__(self, setup: Setup | None = None) -> None:
        self._cleanups: list[Cleanup] = []
        self._dispose_task: asyncio.Task[None] | None = None
        self._setup_task: asyncio.Task[None] | None = None
        self._setup_complete = asyncio.Event()
        self._setup_error: BaseException | None = None
        if setup is not None:
            self.start(setup)

    def start(self, setup: Setup) -> None:
        try:
            result = setup()
            if callable(result):
                self._cleanups.append(cast(Cleanup, result))
                self._setup_complete.set()
            elif inspect.isawaitable(result):
                self._setup_task = asyncio.create_task(
                    self._finish_setup(cast(Awaitable[object], result))
                )
            else:
                self._collect(result)
                self._setup_complete.set()
        except BaseException:
            self._setup_complete.set()
            raise

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._wait_setup().__await__()

    def __call__(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _wait_setup(self) -> Effect:
        await self._setup_complete.wait()
        if self._setup_error is not None:
            raise self._setup_error
        return self

    def _collect(self, result: object) -> None:
        if result is None:
            return
        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, bytearray)):
            cleanups = list(cast(Iterable[object], result))
            if not all(callable(cleanup) for cleanup in cleanups):
                raise TypeError("Invalid effect")
            self._cleanups.extend(cast(list[Cleanup], cleanups))
            return
        raise TypeError("Invalid effect")

    async def _finish_setup(self, result: Awaitable[object]) -> None:
        try:
            resolved = await result
            if callable(resolved):
                self._cleanups.append(cast(Cleanup, resolved))
            else:
                self._collect(resolved)
        except BaseException as error:
            self._setup_error = error
        finally:
            self._setup_complete.set()

    async def _dispose(self) -> None:
        await self._setup_complete.wait()
        errors: list[BaseException] = []
        while self._cleanups:
            try:
                await _run_cleanup(self._cleanups.pop())
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                errors.append(error)
        if self._setup_error is not None:
            raise self._setup_error
        if errors:
            raise BaseExceptionGroup("effect cleanup failed", errors)

    async def dispose(self) -> None:
        await self()


class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


class Context:
    def __init__(self) -> None:
        self._root = self
        self._meta: dict[str, object] = {}
        self._fiber = Fiber.create_root(self)

    @classmethod
    def derive(cls, parent: Context, fiber: Fiber) -> Context:
        child = cls.__new__(cls)
        child._root = parent.root
        child._meta = dict(parent._meta)
        child._fiber = fiber
        return child

    @property
    def root(self) -> Context:
        return self._root

    @property
    def fiber(self) -> Fiber:
        return self._fiber

    def __getattr__(self, name: str) -> object:
        try:
            return self._meta[name]
        except KeyError:
            raise AttributeError(name) from None

    def extend(self, meta: Mapping[str, object] | None = None) -> Context:
        child = Context.derive(self, self.fiber)
        child._meta.update({} if meta is None else meta)
        return child

    def effect(self, setup: Setup) -> Effect:
        return self.fiber.install_effect(setup)

    def plugin(self, callback: Plugin) -> Fiber:
        child = Fiber(self, callback, self.fiber)
        self.fiber.install_effect(lambda: child.dispose)
        child.start()
        return child

    async def aclose(self) -> None:
        if self is not self.root:
            raise RuntimeError("only the root context can close the runtime")
        await self.fiber.dispose()


class Fiber:
    def __init__(self, parent_context: Context, callback: Plugin, parent: Fiber) -> None:
        self.parent = parent
        self.callback = callback
        self.state = FiberState.PENDING
        self.ctx = Context.derive(parent_context, self)
        self._effects: list[Effect] = []
        self._activation_task: asyncio.Task[None] | None = None
        self._dispose_task: asyncio.Task[None] | None = None

    @classmethod
    def create_root(cls, context: Context) -> Fiber:
        root = cls.__new__(cls)
        root.parent = root

        def root_callback(_context: Context) -> None:
            return None

        root.callback = root_callback
        root.state = FiberState.ACTIVE
        root.ctx = context
        root._effects = []
        root._activation_task = None
        root._dispose_task = None
        return root

    def start(self) -> None:
        self._activation_task = asyncio.create_task(self._activate())

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._wait().__await__()

    async def _wait(self) -> Fiber:
        if self._activation_task is not None:
            await asyncio.shield(self._activation_task)
        return self

    async def _activate(self) -> None:
        self.state = FiberState.LOADING
        effect = Effect()
        self._effects.append(effect)
        effect.start(lambda: self.callback(self.ctx))
        try:
            await effect
        except BaseException:
            await effect.dispose()
            raise
        self.state = FiberState.ACTIVE

    def install_effect(self, setup: Setup) -> Effect:
        if self.state in (FiberState.UNLOADING, FiberState.DISPOSED):
            raise RuntimeError("cannot create effect on inactive fiber")
        effect = Effect(setup)
        self._effects.append(effect)
        return effect

    def dispose(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _dispose(self) -> None:
        if self._activation_task is not None:
            try:
                await asyncio.shield(self._activation_task)
            except BaseException:
                pass
        self.state = FiberState.UNLOADING
        errors: list[BaseException] = []
        while self._effects:
            try:
                await self._effects.pop().dispose()
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                errors.append(error)
        self.state = FiberState.DISPOSED
        if errors:
            raise BaseExceptionGroup("fiber cleanup failed", errors)
