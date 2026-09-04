"""Unified Effect ownership for tutorial chapter 10."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from collections.abc import AsyncIterable, Awaitable, Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from typing import Protocol, cast

Cleanup = Callable[[], object]
Setup = Callable[[], object]


class Disposable(Protocol):
    def dispose(self) -> object: ...


class InactiveEffectError(RuntimeError):
    pass


@dataclass(slots=True)
class EffectMeta:
    label: str
    children: list[EffectMeta] = field(default_factory=lambda: list[EffectMeta]())


class Effect:
    def __init__(self, label: str) -> None:
        self.meta = EffectMeta(label)
        self._cleanups: list[Cleanup] = []
        self._setup_done = asyncio.Event()
        self._dispose_task: asyncio.Task[None] | None = None

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._wait().__await__()

    async def _wait(self) -> Effect:
        await self._setup_done.wait()
        return self

    def __call__(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    def attach(self, child: Effect) -> None:
        self.meta.children.append(child.meta)
        self._cleanups.append(child)

    async def start(self, setup: Setup) -> None:
        try:
            await self._collect(setup())
        except BaseException:
            self._setup_done.set()
            try:
                await self.dispose()
            except BaseExceptionGroup:
                pass
            raise
        finally:
            self._setup_done.set()

    async def _collect(self, result: object) -> None:
        if callable(result):
            self._cleanups.append(cast(Cleanup, result))
        elif inspect.isawaitable(result):
            await self._collect(await cast(Awaitable[object], result))
        elif result is None:
            return
        elif isinstance(result, AsyncIterable):
            async for cleanup in cast(AsyncIterable[object], result):
                self._append(cleanup)
        elif isinstance(result, Iterable) and not isinstance(result, (str, bytes, bytearray)):
            for cleanup in cast(Iterable[object], result):
                self._append(cleanup)
        else:
            raise TypeError("invalid Effect result")

    def _append(self, cleanup: object) -> None:
        if not callable(cleanup):
            raise TypeError("invalid Effect cleanup")
        self._cleanups.append(cast(Cleanup, cleanup))

    async def dispose(self) -> None:
        await asyncio.shield(self())

    async def _dispose(self) -> None:
        await self._setup_done.wait()
        errors: list[BaseException] = []
        while self._cleanups:
            try:
                result = self._cleanups.pop()()
                if inspect.isawaitable(result):
                    await cast(Awaitable[object], result)
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup(f"effect {self.meta.label!r} cleanup failed", errors)


_current_effect: contextvars.ContextVar[Effect | None] = contextvars.ContextVar(
    "tutorial_current_effect", default=None
)


class EffectScope:
    def __init__(self) -> None:
        self._effects: list[Effect] = []
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None

    @property
    def effects(self) -> tuple[EffectMeta, ...]:
        return tuple(effect.meta for effect in self._effects)

    async def install(self, setup: Setup, label: str = "anonymous") -> Effect:
        if self._closed:
            raise InactiveEffectError("closed scope cannot own a new Effect")
        effect = Effect(label)
        parent = _current_effect.get()
        if parent is not None:
            parent.attach(effect)
        self._effects.append(effect)
        token = _current_effect.set(effect)
        try:
            await effect.start(setup)
        except BaseException:
            self._effects.remove(effect)
            raise
        finally:
            _current_effect.reset(token)
        if self._closed:
            await effect.dispose()
            raise InactiveEffectError("scope closed during setup")
        return effect

    async def close(self) -> None:
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)

    async def _close(self) -> None:
        errors: list[BaseException] = []
        while self._effects:
            try:
                await self._effects.pop().dispose()
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("EffectScope cleanup failed", errors)


class ResourceContext:
    """Several resource APIs backed by one EffectScope."""

    def __init__(self) -> None:
        self.effects = EffectScope()
        self.services: dict[str, object] = {}
        self.listeners: dict[str, list[Callable[..., object]]] = {}

    async def effect(self, setup: Setup, label: str = "anonymous") -> Effect:
        return await self.effects.install(setup, label)

    async def provide(self, name: str, value: object) -> Effect:
        def setup() -> Cleanup:
            self.services[name] = value
            return lambda: self.services.pop(name, None)

        return await self.effect(setup, f"provide({name!r})")

    async def on(self, event: str, listener: Callable[..., object]) -> Effect:
        def setup() -> Cleanup:
            listeners = self.listeners.setdefault(event, [])
            listeners.append(listener)
            return lambda: listeners.remove(listener)

        return await self.effect(setup, f"on({event!r})")

    async def child(self, child: Disposable) -> Effect:
        return await self.effect(lambda: child.dispose, "child Fiber")

    async def task(self, coroutine: Coroutine[object, object, object]) -> Effect:
        task = asyncio.create_task(coroutine)

        async def cleanup() -> None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return await self.effect(lambda: cleanup, "background task")

    async def close(self) -> None:
        await self.effects.close()
