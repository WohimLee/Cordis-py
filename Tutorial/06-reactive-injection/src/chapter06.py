"""Delayed plugin activation through Inject for tutorial chapter 06."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar, cast

Cleanup = Callable[[], object]
Callback = Callable[["Context", object], object]
InjectSpec = Sequence[str] | Mapping[str, object | None]
Decorated = TypeVar("Decorated")
DEFAULT_LABEL = object()


def normalize_inject(value: object) -> dict[str, object | None]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        if not all(isinstance(name, str) for name in mapping):
            raise TypeError("inject mapping keys must be strings")
        return {cast(str, name): config for name, config in mapping.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        if all(isinstance(name, str) for name in sequence):
            return {cast(str, name): None for name in sequence}
    raise TypeError("inject must be a string sequence or mapping")


class Inject:
    def __init__(self, name: str, config: object = None) -> None:
        self.name = name
        self.config = config

    def __call__(self, value: Decorated) -> Decorated:
        if not isinstance(value, type):
            raise TypeError("this chapter uses Inject only on classes")
        target = cast(Any, value)
        inherited = normalize_inject(getattr(target, "inject", None))
        target.inject = inherited | {self.name: self.config}
        return value

    @staticmethod
    def resolve(value: object) -> dict[str, object | None]:
        return normalize_inject(value)


class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


@dataclass(eq=False)
class PluginRuntime:
    callback: Callback
    name: str
    inject: Mapping[str, object | None]
    fibers: set[Fiber] = field(default_factory=lambda: set[Fiber]())


@dataclass(slots=True)
class Impl:
    name: str
    fiber: Fiber
    value: object
    label: object


class Context:
    def __init__(self) -> None:
        self._root = self
        self._labels: dict[str, object] = {}
        self._reflect = ReflectService()
        self._registry = RegistryService(self._reflect)
        self._reflect.registry = self._registry
        self._fiber = Fiber.create_root(self)

    @classmethod
    def derive(cls, parent: Context, fiber: Fiber) -> Context:
        child = cls.__new__(cls)
        child._root = parent.root
        child._labels = dict(parent._labels)
        child._reflect = parent._reflect
        child._registry = parent._registry
        child._fiber = fiber
        return child

    @property
    def root(self) -> Context:
        return self._root

    @property
    def fiber(self) -> Fiber:
        return self._fiber

    @property
    def registry(self) -> RegistryService:
        return self._registry

    def label_for(self, name: str) -> object:
        return self._labels.get(name, DEFAULT_LABEL)

    def get(self, name: str, strict: bool = True) -> object | None:
        return self._reflect.get(self, name, strict)

    def provide(self, name: str, value: object) -> Cleanup:
        return self._reflect.provide(self, name, value)

    def notify_owned_services(self, fiber: Fiber) -> None:
        self._reflect.notify_owned_by(fiber)

    def remove_dependent(self, fiber: Fiber) -> None:
        self._registry.remove_dependent(fiber)

    def plugin(self, plugin: object, config: object = None) -> Fiber:
        return self.registry.plugin(self, plugin, config)

    def inject(self, dependencies: InjectSpec, callback: Callback) -> Fiber:
        cast(Any, callback).inject = dependencies
        return self.plugin(callback)

    async def aclose(self) -> None:
        await self.fiber.dispose()
        self.registry.clear()


class Fiber:
    def __init__(
        self,
        parent_context: Context,
        runtime: PluginRuntime,
        config: object,
        parent: Fiber,
    ) -> None:
        self.parent = parent
        self.runtime: PluginRuntime | None = runtime
        self.config = config
        self.state = FiberState.PENDING
        self.ctx = Context.derive(parent_context, self)
        self._cleanups: list[Cleanup] = []
        self._task: asyncio.Task[None] | None = None
        self._dispose_task: asyncio.Task[None] | None = None

    @classmethod
    def create_root(cls, context: Context) -> Fiber:
        root = cls.__new__(cls)
        root.parent = root
        root.runtime = None
        root.config = None
        root.state = FiberState.ACTIVE
        root.ctx = context
        root._cleanups = []
        root._task = None
        root._dispose_task = None
        return root

    def __await__(self):  # type: ignore[no-untyped-def]
        return self.wait().__await__()

    async def wait(self) -> Fiber:
        task = self._task
        if task is not None:
            await asyncio.shield(task)
        return self

    def refresh(self) -> None:
        if self.state in (FiberState.ACTIVE, FiberState.UNLOADING, FiberState.DISPOSED):
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._try_activate())

    def dependencies_ready(self) -> bool:
        runtime = self.runtime
        if runtime is None:
            return True
        return all(self.ctx.get(name) is not None for name in runtime.inject)

    async def _try_activate(self) -> None:
        if not self.dependencies_ready():
            self.state = FiberState.PENDING
            return
        runtime = self.runtime
        if runtime is None:
            return
        self.state = FiberState.LOADING
        try:
            result = runtime.callback(self.ctx, self.config)
            if inspect.isawaitable(result):
                result = await cast(Awaitable[object], result)
            self._collect(result)
        except BaseException:
            await self._cleanup()
            self.state = FiberState.PENDING
            raise
        self.state = FiberState.ACTIVE
        self.ctx.notify_owned_services(self)

    def _collect(self, result: object) -> None:
        if result is None:
            return
        if callable(result):
            self._cleanups.append(cast(Cleanup, result))
            return
        raise TypeError("Invalid effect")

    def own(self, cleanup: Cleanup) -> None:
        self._cleanups.append(cleanup)

    def dispose(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _cleanup(self) -> None:
        while self._cleanups:
            result = self._cleanups.pop()()
            if inspect.isawaitable(result):
                await cast(Awaitable[object], result)

    async def _dispose(self) -> None:
        task = self._task
        if task is not None:
            try:
                await asyncio.shield(task)
            except BaseException:
                pass
        self.state = FiberState.UNLOADING
        await self._cleanup()
        runtime = self.runtime
        if runtime is not None:
            runtime.fibers.discard(self)
            self.ctx.remove_dependent(self)
        self.state = FiberState.DISPOSED


class ReflectService:
    def __init__(self) -> None:
        self.registry: RegistryService | None = None
        self._impls: dict[str, list[Impl]] = {}

    def get(self, context: Context, name: str, strict: bool = True) -> object | None:
        label = context.label_for(name)
        for impl in reversed(self._impls.get(name, [])):
            if impl.label is not label:
                continue
            if strict and impl.fiber.state is not FiberState.ACTIVE:
                return None
            return impl.value
        return None

    def provide(self, context: Context, name: str, value: object) -> Cleanup:
        impl = Impl(name, context.fiber, value, context.label_for(name))
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

    def notify(self, name: str) -> None:
        if self.registry is not None:
            self.registry.refresh(name)

    def notify_owned_by(self, fiber: Fiber) -> None:
        for name, implementations in tuple(self._impls.items()):
            if any(impl.fiber is fiber for impl in implementations):
                self.notify(name)


def _invoke(callable_: Callable[..., object], context: Context, config: object) -> object:
    if len(inspect.signature(callable_).parameters) == 1:
        return callable_(context)
    return callable_(context, config)


class RegistryService:
    def __init__(self, reflect: ReflectService) -> None:
        self.reflect = reflect
        self._runtimes: dict[int, tuple[object, PluginRuntime]] = {}
        self._dependents: dict[str, set[Fiber]] = {}

    def resolve(self, plugin: object) -> PluginRuntime:
        cached = self._runtimes.get(id(plugin))
        if cached is not None and cached[0] is plugin:
            return cached[1]

        if isinstance(plugin, type):

            def callback(context: Context, config: object) -> object:
                _invoke(cast(Callable[..., object], plugin), context, config)
                return None

        elif callable(plugin):

            def callback(context: Context, config: object) -> object:
                return _invoke(plugin, context, config)

        else:
            apply = getattr(plugin, "apply", None)
            if not callable(apply):
                raise TypeError("invalid plugin")

            def callback(context: Context, config: object) -> object:
                return _invoke(apply, context, config)

        name = str(
            getattr(plugin, "name", None)
            or getattr(plugin, "__name__", None)
            or type(plugin).__name__
        )
        runtime = PluginRuntime(callback, name, Inject.resolve(getattr(plugin, "inject", None)))
        self._runtimes[id(plugin)] = (plugin, runtime)
        return runtime

    def plugin(self, context: Context, plugin: object, config: object = None) -> Fiber:
        runtime = self.resolve(plugin)
        fiber = Fiber(context, runtime, config, context.fiber)
        runtime.fibers.add(fiber)
        for name in runtime.inject:
            self._dependents.setdefault(name, set()).add(fiber)
        context.fiber.own(fiber.dispose)
        fiber.refresh()
        return fiber

    def refresh(self, name: str) -> None:
        for fiber in tuple(self._dependents.get(name, set())):
            fiber.refresh()

    def remove_dependent(self, fiber: Fiber) -> None:
        runtime = fiber.runtime
        if runtime is None:
            return
        for name in runtime.inject:
            dependents = self._dependents[name]
            dependents.discard(fiber)
            if not dependents:
                del self._dependents[name]

    def clear(self) -> None:
        self._runtimes.clear()
        self._dependents.clear()
