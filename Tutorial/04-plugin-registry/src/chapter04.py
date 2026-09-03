"""Plugin normalization and Registry identity for tutorial chapter 04."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

Cleanup = Callable[[], object]
Setup = Callable[[], object]
Callback = Callable[["Context", object], object]
Plugin = object


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

    def dispose(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

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
    fibers: set[Fiber] = field(default_factory=lambda: set[Fiber]())


class Context:
    def __init__(self) -> None:
        self._root = self
        self._meta: dict[str, object] = {}
        self._registry = RegistryService(self)
        self._fiber = Fiber.create_root(self)

    @classmethod
    def derive(cls, parent: Context, fiber: Fiber) -> Context:
        child = cls.__new__(cls)
        child._root = parent.root
        child._meta = dict(parent._meta)
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

    def extend(self, meta: Mapping[str, object] | None = None) -> Context:
        child = Context.derive(self, self.fiber)
        child._meta.update({} if meta is None else meta)
        return child

    def effect(self, setup: Setup) -> Effect:
        return self.fiber.install_effect(setup)

    def plugin(self, plugin: Plugin, config: object = None) -> Fiber:
        return self.registry.plugin(self, plugin, config)

    async def aclose(self) -> None:
        if self is not self.root:
            raise RuntimeError("only the root context can close the runtime")
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
        self._effects: list[Effect] = []
        self._activation_task: asyncio.Task[None] | None = None
        self._dispose_task: asyncio.Task[None] | None = None

    @classmethod
    def create_root(cls, context: Context) -> Fiber:
        root = cls.__new__(cls)
        root.parent = root
        root.runtime = None
        root.config = None
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
        runtime = self.runtime
        if runtime is None:
            raise RuntimeError("root fiber cannot activate a plugin")
        effect = Effect()
        self._effects.append(effect)
        effect.start(lambda: runtime.callback(self.ctx, self.config))
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
        if self.runtime is not None:
            self.runtime.fibers.discard(self)
        self.state = FiberState.DISPOSED
        if errors:
            raise BaseExceptionGroup("fiber cleanup failed", errors)


def _plugin_name(plugin: Plugin) -> str:
    name = getattr(plugin, "name", None) or getattr(plugin, "__name__", None)
    return str(name or plugin.__class__.__name__)


def _invoke(callable_: Callable[..., object], context: Context, config: object) -> object:
    parameters = inspect.signature(callable_).parameters
    if len(parameters) == 1:
        return callable_(context)
    return callable_(context, config)


class RegistryService:
    def __init__(self, context: Context) -> None:
        self.ctx = context
        self._resolved: dict[int, tuple[Plugin, Callback]] = {}
        self._runtimes: dict[Callback, PluginRuntime] = {}

    @property
    def size(self) -> int:
        return len(self._runtimes)

    def resolve(self, plugin: Plugin) -> Callback:
        cached = self._resolved.get(id(plugin))
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

        self._resolved[id(plugin)] = (plugin, callback)
        return callback

    def get(self, plugin: Plugin) -> PluginRuntime | None:
        cached = self._resolved.get(id(plugin))
        if cached is None or cached[0] is not plugin:
            return None
        return self._runtimes.get(cached[1])

    def has(self, plugin: Plugin) -> bool:
        return self.get(plugin) is not None

    def plugin(self, context: Context, plugin: Plugin, config: object = None) -> Fiber:
        callback = self.resolve(plugin)
        runtime = self._runtimes.get(callback)
        if runtime is None:
            runtime = PluginRuntime(callback, _plugin_name(plugin))
            self._runtimes[callback] = runtime
        fiber = Fiber(context, runtime, config, context.fiber)
        runtime.fibers.add(fiber)
        context.fiber.install_effect(lambda: fiber.dispose)
        fiber.start()
        return fiber

    def delete(self, plugin: Plugin) -> PluginRuntime | None:
        runtime = self.get(plugin)
        if runtime is None:
            return None
        self._runtimes.pop(runtime.callback)
        for fiber in tuple(runtime.fibers):
            fiber.dispose()
        return runtime

    def keys(self) -> Iterator[Callback]:
        return iter(self._runtimes.keys())

    def values(self) -> Iterator[PluginRuntime]:
        return iter(self._runtimes.values())

    def entries(self) -> Iterator[tuple[Callback, PluginRuntime]]:
        return iter(self._runtimes.items())

    def forEach(self, callback: Callable[[PluginRuntime, Callback], object]) -> None:
        for key, value in tuple(self._runtimes.items()):
            callback(value, key)

    def clear(self) -> None:
        self._runtimes.clear()
