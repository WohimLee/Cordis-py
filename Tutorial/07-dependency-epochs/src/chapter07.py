"""Dependency epochs and serialized Fiber lifecycle for tutorial chapter 07."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

Cleanup = Callable[[], object]
Callback = Callable[["Context", object], object]
InjectSpec = Sequence[str] | Mapping[str, object | None]
DEFAULT_LABEL = object()


def normalize_inject(value: object) -> dict[str, object | None]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(name): config for name, config in mapping.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        return {str(name): None for name in sequence}
    raise TypeError("invalid inject")


class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


@dataclass(eq=False, slots=True)
class Impl:
    name: str
    fiber: Fiber
    value: object
    label: object


@dataclass(eq=False)
class PluginRuntime:
    callback: Callback
    name: str
    inject: Mapping[str, object | None]
    fibers: set[Fiber] = field(default_factory=lambda: set[Fiber]())


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

    def label_for(self, name: str) -> object:
        return self._labels.get(name, DEFAULT_LABEL)

    def resolve_impl(self, name: str) -> Impl | None:
        return self._reflect.resolve(self, name, strict=True)

    def get(self, name: str) -> object | None:
        impl = self.resolve_impl(name)
        return None if impl is None else impl.value

    def provide(self, name: str, value: object) -> Cleanup:
        return self._reflect.provide(self, name, value)

    def plugin(self, plugin: Callback, config: object = None) -> Fiber:
        return self._registry.plugin(self, plugin, config)

    def notify_owned_services(self, fiber: Fiber) -> None:
        self._reflect.notify_owned_by(fiber)

    def remove_dependent(self, fiber: Fiber) -> None:
        self._registry.remove_dependent(fiber)

    async def aclose(self) -> None:
        await self.fiber.dispose()
        self._registry.clear()


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
        self.epoch: tuple[Impl, ...] | None = None
        self._cleanups: list[Cleanup] = []
        self._runner: asyncio.Task[None] | None = None
        self._dispose_task: asyncio.Task[None] | None = None
        self._disposed = False

    @classmethod
    def create_root(cls, context: Context) -> Fiber:
        root = cls.__new__(cls)
        root.parent = root
        root.runtime = None
        root.config = None
        root.state = FiberState.ACTIVE
        root.ctx = context
        root.epoch = ()
        root._cleanups = []
        root._runner = None
        root._dispose_task = None
        root._disposed = False
        return root

    def __await__(self):  # type: ignore[no-untyped-def]
        return self.wait().__await__()

    async def wait(self) -> Fiber:
        while self._runner is not None:
            task = self._runner
            await asyncio.shield(task)
            if self._runner is task:
                break
        return self

    def compute_epoch(self) -> tuple[Impl, ...] | None:
        runtime = self.runtime
        if runtime is None:
            return ()
        implementations: list[Impl] = []
        for name in runtime.inject:
            impl = self.ctx.resolve_impl(name)
            if impl is None:
                return None
            implementations.append(impl)
        return tuple(implementations)

    def refresh(self) -> None:
        if self._disposed:
            return
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while not self._disposed:
            desired = self.compute_epoch()
            if self.state is FiberState.ACTIVE:
                if desired == self.epoch:
                    return
                self.state = FiberState.UNLOADING
                self.ctx.notify_owned_services(self)
                await self._cleanup()
                self.epoch = None
                self.state = FiberState.PENDING
                continue

            if desired is None:
                self.state = FiberState.PENDING
                return

            activation_epoch = desired
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

            if self._disposed:
                await self._cleanup()
                return
            if self.compute_epoch() != activation_epoch:
                self.state = FiberState.UNLOADING
                await self._cleanup()
                self.state = FiberState.PENDING
                continue

            self.epoch = activation_epoch
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

    async def _cleanup(self) -> None:
        while self._cleanups:
            result = self._cleanups.pop()()
            if inspect.isawaitable(result):
                await cast(Awaitable[object], result)

    def dispose(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._disposed = True
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _dispose(self) -> None:
        if self.state is FiberState.ACTIVE:
            self.state = FiberState.UNLOADING
            self.ctx.notify_owned_services(self)
        runner = self._runner
        if runner is not None:
            try:
                await asyncio.shield(runner)
            except BaseException:
                pass
        await self._cleanup()
        runtime = self.runtime
        if runtime is not None:
            runtime.fibers.discard(self)
            self.ctx.remove_dependent(self)
        self.epoch = None
        self.state = FiberState.DISPOSED


class ReflectService:
    def __init__(self) -> None:
        self.registry: RegistryService | None = None
        self._impls: dict[str, list[Impl]] = {}

    def resolve(self, context: Context, name: str, strict: bool) -> Impl | None:
        label = context.label_for(name)
        for impl in reversed(self._impls.get(name, [])):
            if impl.label is not label:
                continue
            if strict and impl.fiber.state is not FiberState.ACTIVE:
                return None
            return impl
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


class RegistryService:
    def __init__(self, reflect: ReflectService) -> None:
        self.reflect = reflect
        self._runtimes: dict[int, tuple[object, PluginRuntime]] = {}
        self._dependents: dict[str, set[Fiber]] = {}

    def resolve(self, plugin: Callback) -> PluginRuntime:
        cached = self._runtimes.get(id(plugin))
        if cached is not None and cached[0] is plugin:
            return cached[1]
        runtime = PluginRuntime(
            plugin,
            getattr(plugin, "__name__", "plugin"),
            normalize_inject(getattr(plugin, "inject", None)),
        )
        self._runtimes[id(plugin)] = (plugin, runtime)
        return runtime

    def plugin(self, context: Context, plugin: Callback, config: object = None) -> Fiber:
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


def declare_inject(callback: Callback, dependencies: InjectSpec) -> Callback:
    cast(Any, callback).inject = dependencies
    return callback
