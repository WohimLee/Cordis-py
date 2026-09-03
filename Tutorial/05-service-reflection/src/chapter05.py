"""Service implementation lookup for tutorial chapter 05."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

Cleanup = Callable[[], object]
AvailabilityCheck = Callable[["Context"], bool]
Watcher = Callable[[str], object]
DEFAULT_LABEL = object()


class FiberState(StrEnum):
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    DISPOSED = "DISPOSED"


class Fiber:
    """The smallest owner needed to demonstrate Reflect cleanup."""

    def __init__(self, root: Context, state: FiberState = FiberState.ACTIVE) -> None:
        self.state = state
        self._cleanups: list[Cleanup] = []
        self._dispose_task: asyncio.Task[None] | None = None
        self.ctx = Context.for_fiber(root, self)

    @classmethod
    def create_root(cls, context: Context) -> Fiber:
        fiber = cls.__new__(cls)
        fiber.state = FiberState.ACTIVE
        fiber._cleanups = []
        fiber._dispose_task = None
        fiber.ctx = context
        return fiber

    def own(self, cleanup: Cleanup) -> None:
        if self.state is FiberState.DISPOSED:
            raise RuntimeError("cannot own resource on disposed fiber")
        self._cleanups.append(cleanup)

    def dispose(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _dispose(self) -> None:
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
        self.state = FiberState.DISPOSED
        if errors:
            raise BaseExceptionGroup("fiber cleanup failed", errors)


@dataclass(slots=True)
class Impl:
    name: str
    fiber: Fiber
    value: object
    label: object
    check: AvailabilityCheck


class Context:
    def __init__(self) -> None:
        self._root = self
        self._labels: dict[str, object] = {}
        self._reflect_service = ReflectService(self)
        self._fiber = Fiber.create_root(self)

    @classmethod
    def _derive(cls, parent: Context, fiber: Fiber) -> Context:
        child = cls.__new__(cls)
        child._root = parent.root
        child._labels = dict(parent._labels)
        child._reflect_service = parent._reflect_service
        child._fiber = fiber
        return child

    @classmethod
    def for_fiber(cls, root: Context, fiber: Fiber) -> Context:
        return cls._derive(root, fiber)

    @property
    def root(self) -> Context:
        return self._root

    @property
    def fiber(self) -> Fiber:
        return self._fiber

    @property
    def reflect(self) -> ReflectServiceView:
        return ReflectServiceView(self._reflect_service, self)

    def extend(self) -> Context:
        return Context._derive(self, self.fiber)

    def isolate(self, name: str, label: object | None = None) -> Context:
        child = self.extend()
        child._labels[name] = object() if label is None else label
        return child

    def label_for(self, name: str) -> object:
        return self._labels.get(name, DEFAULT_LABEL)

    def get(self, name: str, strict: bool = True) -> object | None:
        return self.reflect.get(name, strict)

    def provide(
        self,
        name: str,
        value: object,
        check: AvailabilityCheck | None = None,
    ) -> Callable[[], bool]:
        return self.reflect.provide(name, value, check)


class ReflectService:
    def __init__(self, context: Context) -> None:
        self.ctx = context
        self._impls: dict[str, list[Impl]] = {}
        self._watchers: dict[str, list[Watcher]] = {}

    def _label(self, context: Context, name: str) -> object:
        return context.label_for(name)

    def get(self, context: Context, name: str, strict: bool = True) -> object | None:
        label = self._label(context, name)
        for impl in reversed(self._impls.get(name, [])):
            if impl.label is not label:
                continue
            if strict and (impl.fiber.state is not FiberState.ACTIVE or not impl.check(context)):
                return None
            return impl.value
        return None

    def provide(
        self,
        context: Context,
        name: str,
        value: object,
        check: AvailabilityCheck | None = None,
    ) -> Callable[[], bool]:
        impl = Impl(name, context.fiber, value, self._label(context, name), check or _available)
        self._impls.setdefault(name, []).append(impl)
        disposed = False

        def dispose() -> bool:
            nonlocal disposed
            if disposed:
                return False
            disposed = True
            implementations = self._impls[name]
            implementations.remove(impl)
            if not implementations:
                del self._impls[name]
            self.notify(name)
            return True

        context.fiber.own(dispose)
        self.notify(name)
        return dispose

    def watch(self, name: str, callback: Watcher) -> Callable[[], bool]:
        watchers = self._watchers.setdefault(name, [])
        watchers.append(callback)

        def dispose() -> bool:
            if callback not in watchers:
                return False
            watchers.remove(callback)
            return True

        return dispose

    def notify(self, name: str) -> None:
        for callback in tuple(self._watchers.get(name, [])):
            callback(name)


class ReflectServiceView:
    def __init__(self, service: ReflectService, context: Context) -> None:
        self.service = service
        self.ctx = context

    def get(self, name: str, strict: bool = True) -> object | None:
        return self.service.get(self.ctx, name, strict)

    def provide(
        self,
        name: str,
        value: object,
        check: AvailabilityCheck | None = None,
    ) -> Callable[[], bool]:
        return self.service.provide(self.ctx, name, value, check)

    def watch(self, name: str, callback: Watcher) -> Callable[[], bool]:
        return self.service.watch(name, callback)


def _available(_context: Context) -> bool:
    return True
