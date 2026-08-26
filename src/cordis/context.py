"""Scoped dependency container presented to plugins."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from .effect import Effect, EffectSetup
from .events import Listener
from .model import Plugin

if TYPE_CHECKING:
    from .events import EventsService
    from .fiber import Fiber, RootFiber
    from .logger import Exporter, LoggerService
    from .reflect import ReflectService
    from .registry import RegistryService


class Context:
    """Root or derived view over a Cordis runtime."""

    def __init__(self) -> None:
        from .events import EventsService
        from .fiber import RootFiber
        from .logger import LoggerService
        from .reflect import ReflectService
        from .registry import RegistryService

        self.root = self
        self.isolation: dict[str, object] = {}
        self.intercepts: dict[str, list[object]] = {}
        self.fiber: Fiber | RootFiber = RootFiber(self)
        self.registry: RegistryService = RegistryService(self)
        self.reflect: ReflectService = ReflectService(self)
        self.events: EventsService = EventsService(self)
        self.logger: LoggerService = LoggerService(self)

    @classmethod
    def derive(cls, parent: Context, fiber: Fiber | None = None) -> Context:
        context = object.__new__(cls)
        context.root = parent.root
        context.isolation = dict(parent.isolation)
        context.intercepts = {name: list(values) for name, values in parent.intercepts.items()}
        context.fiber = fiber or parent.fiber
        context.registry = parent.root.registry
        context.reflect = parent.root.reflect
        context.events = parent.root.events
        context.logger = parent.root.logger
        return context

    def extend(self) -> Context:
        """Create a child Context that shares the current scope."""

        return self.derive(self)

    def isolate(self, name: str, label: object | None = None) -> Context:
        """Create a child Context with an independent service scope."""

        context = self.derive(self)
        context.isolation[name] = label if label is not None else object()
        return context

    def intercept(self, name: str, config: object) -> Context:
        """Create a child Context with additional service-specific configuration."""

        context = self.derive(self)
        context.intercepts.setdefault(name, []).append(config)
        return context

    def plugin(self, plugin: Plugin, config: object = None) -> Fiber:
        """Mount a plugin under this Context."""

        return self.root.registry.plugin(self, plugin, config)

    def get(self, name: str) -> object:
        """Resolve a service explicitly."""

        from .service import bind_service

        def resolve() -> object:
            accessor = self.root.reflect.accessor_record(name)
            if accessor is not None:
                return accessor.getter(self)
            implementation = self.fiber.dependencies.get(name)
            if implementation is not None:
                return bind_service(implementation.value, self)
            return bind_service(self.root.reflect.get(self, name), self)

        return self.events.waterfall_sync("internal/get", self, name, next_=resolve)

    def __getattr__(self, name: str) -> object:
        return self.get(name)

    def set(self, name: str, value: object) -> None:
        """Set a declared accessor or a service owned by this Fiber."""

        self.events.waterfall_sync(
            "internal/set",
            self,
            name,
            value,
            next_=lambda: self.root.reflect.set(self, name, value),
        )

    def provide(
        self,
        name: str,
        value: object,
        check: Callable[[], bool] | None = None,
    ) -> Effect:
        """Provide a service owned by the current Fiber."""

        return self.root.reflect.provide(self, name, value, check)

    def accessor(
        self,
        name: str,
        getter: Callable[[Context], object],
        setter: Callable[[Context, object], None] | None = None,
    ) -> Effect:
        """Declare a computed Context property."""

        return self.root.reflect.accessor(self, name, getter, setter)

    def mixin(
        self,
        source: str | object,
        members: Sequence[str] | Mapping[str, str],
    ) -> Effect:
        """Expose selected members of a service or object on Context."""

        return self.root.reflect.mixin(self, source, members)

    def bind(self, callback: Callable[..., object]) -> Callable[..., object]:
        """Bind callback diagnostics to this Context."""

        return self.root.reflect.bind(self, callback)

    def exporter(self, exporter: Exporter) -> Effect:
        """Register a lifecycle-owned log exporter."""

        return self.logger.exporter(self, exporter)

    def effect(self, setup: EffectSetup, label: str = "anonymous") -> Effect:
        """Install a synchronous-setup Effect on the current Fiber."""

        return self.fiber.effects.install_sync(setup, label)

    async def effect_async(self, setup: EffectSetup, label: str = "anonymous") -> Effect:
        """Install an Effect whose setup may be asynchronous."""

        return await self.fiber.effects.install(setup, label)

    def on(
        self,
        name: str,
        listener: Listener,
        *,
        prepend: bool = False,
        global_: bool = False,
    ) -> Effect:
        """Register a lifecycle-owned event listener."""

        return self.events.on(self, name, listener, prepend=prepend, global_=global_)

    def once(
        self,
        name: str,
        listener: Listener,
        *,
        prepend: bool = False,
        global_: bool = False,
    ) -> Effect:
        """Register a lifecycle-owned one-shot listener."""

        return self.events.once(self, name, listener, prepend=prepend, global_=global_)

    def emit(self, name: str, *args: object) -> None:
        """Synchronously notify all event listeners."""

        self.events.emit(name, *args)

    def bail(self, name: str, *args: object) -> object:
        """Return the first synchronous bail value."""

        return self.events.bail(name, *args)

    async def serial(self, name: str, *args: object) -> object:
        """Await listeners in order until one returns a bail value."""

        return await self.events.serial(name, *args)

    async def parallel(self, name: str, *args: object) -> None:
        """Run listeners concurrently and wait for completion."""

        await self.events.parallel(name, *args)

    async def waterfall(
        self,
        name: str,
        *args: object,
        next_: Listener,
    ) -> object:
        """Run async around-middleware around a final callback."""

        return await self.events.waterfall(name, *args, next_=next_)

    async def aclose(self) -> None:
        """Dispose the root Fiber and every owned child."""

        await self.root.fiber.dispose()
