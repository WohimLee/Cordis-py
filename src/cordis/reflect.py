"""Scoped service registration and dependency notification."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect import Effect
from .errors import CordisError, CordisErrorCode

if TYPE_CHECKING:
    from .context import Context
    from .fiber import Fiber, RootFiber


@dataclass(slots=True)
class Implementation:
    """A service value and the Fiber that owns it."""

    name: str
    label: object
    value: object
    fiber: Fiber | RootFiber
    check: Callable[[], bool] | None = None


@dataclass(frozen=True, slots=True)
class Accessor:
    """Computed Context property owned by a Fiber."""

    name: str
    getter: Callable[[Context], object]
    setter: Callable[[Context, object], None] | None
    fiber: Fiber | RootFiber


class ReflectService:
    """Store service implementations by isolation label."""

    def __init__(self, root: Context) -> None:
        self.root = root
        self._labels: dict[str, object] = {}
        self._implementations: dict[object, Implementation] = {}
        self._accessors: dict[str, Accessor] = {}

    def label(self, context: Context, name: str) -> object:
        """Resolve the isolation label for a service in a Context."""

        label = context.isolation.get(name)
        if label is not None:
            return label
        return self._labels.setdefault(name, object())

    def implementation(
        self, context: Context, name: str, *, strict: bool = True
    ) -> Implementation | None:
        """Resolve a scoped service implementation."""

        from .fiber import FiberState

        implementation = self._implementations.get(self.label(context, name))
        if implementation is None:
            return None
        if strict and implementation.fiber.state is not FiberState.ACTIVE:
            return None
        if strict and implementation.check is not None and not implementation.check():
            return None
        return implementation

    def get(self, context: Context, name: str, *, strict: bool = True) -> object:
        """Return a scoped service value or raise MISSING_SERVICE."""

        implementation = self.implementation(context, name, strict=strict)
        if implementation is None:
            raise CordisError(CordisErrorCode.MISSING_SERVICE, f"service {name!r} is unavailable")
        return implementation.value

    def set(self, context: Context, name: str, value: object) -> None:
        """Set an accessor or service implementation owned by the current Fiber."""

        accessor = self._accessors.get(name)
        if accessor is not None:
            if accessor.setter is None:
                raise AttributeError(f"Context accessor {name!r} is read-only")
            accessor.setter(context, value)
            return
        implementation = self.implementation(context, name, strict=False)
        if implementation is None:
            raise CordisError(CordisErrorCode.MISSING_SERVICE, f"service {name!r} is unavailable")
        if implementation.fiber is not context.fiber:
            raise PermissionError(f"service {name!r} is owned by another Fiber")
        implementation.value = value

    def provide(
        self,
        context: Context,
        name: str,
        value: object,
        check: Callable[[], bool] | None = None,
    ) -> Effect:
        """Register a service as a synchronous Effect owned by the current Fiber."""

        label = self.label(context, name)
        if name in self._accessors:
            raise TypeError(f"Context property {name!r} is already an accessor")
        implementation = Implementation(name, label, value, context.fiber, check)

        def setup() -> object:
            if label in self._implementations:
                raise CordisError(
                    CordisErrorCode.DUPLICATE_SERVICE,
                    f"service {name!r} already has a provider in this scope",
                )
            self._implementations[label] = implementation
            context.fiber.provided_names.add(name)

            async def cleanup() -> None:
                if self._implementations.get(label) is implementation:
                    del self._implementations[label]
                context.fiber.provided_names.discard(name)
                await self.notify(name, label)

            return cleanup

        effect = context.fiber.effects.install_sync(setup, f"ctx.provide({name!r})")
        if context.fiber.is_active:
            self.notify_soon(name, label)
        return effect

    def accessor_record(self, name: str) -> Accessor | None:
        """Return a declared accessor without invoking it."""

        return self._accessors.get(name)

    def accessor(
        self,
        context: Context,
        name: str,
        getter: Callable[[Context], object],
        setter: Callable[[Context, object], None] | None = None,
    ) -> Effect:
        """Register a computed Context property as an owned Effect."""

        record = Accessor(name, getter, setter, context.fiber)

        def setup() -> object:
            if name in self._accessors or name in self._labels:
                raise TypeError(f"Context property {name!r} is already declared")
            self._accessors[name] = record

            def cleanup() -> None:
                if self._accessors.get(name) is record:
                    del self._accessors[name]

            return cleanup

        return context.fiber.effects.install_sync(setup, f"ctx.accessor({name!r})")

    def mixin(
        self,
        context: Context,
        source: str | object,
        members: Sequence[str] | Mapping[str, str],
    ) -> Effect:
        """Register accessors that forward selected object members."""

        if isinstance(members, Mapping):
            entries = list(members.items())
        else:
            entries = [(name, name) for name in members]
        records: list[Accessor] = []
        for source_name, target_name in entries:

            def getter(receiver: Context, key: str = source_name) -> object:
                target = receiver.get(source) if isinstance(source, str) else source
                return getattr(target, key)

            def setter(receiver: Context, value: object, key: str = source_name) -> None:
                target = receiver.get(source) if isinstance(source, str) else source
                setattr(target, key, value)

            records.append(Accessor(target_name, getter, setter, context.fiber))

        def setup() -> object:
            names = [record.name for record in records]
            if len(set(names)) != len(names) or any(
                name in self._accessors or name in self._labels for name in names
            ):
                raise TypeError("mixin target property is already declared")
            self._accessors.update((record.name, record) for record in records)

            def cleanup() -> None:
                for record in records:
                    if self._accessors.get(record.name) is record:
                        del self._accessors[record.name]

            return cleanup

        return context.fiber.effects.install_sync(setup, "ctx.mixin()")

    def implementations(self) -> tuple[Implementation, ...]:
        """Return a side-effect-free snapshot for diagnostics."""

        return tuple(self._implementations.values())

    def notify_soon(self, name: str, label: object) -> None:
        """Schedule dependency refresh without blocking synchronous registration."""

        asyncio.get_running_loop().create_task(self.notify(name, label))

    async def notify(self, name: str, label: object) -> None:
        """Refresh and settle matching dependent Fibers."""

        fibers = [
            fiber
            for fiber in self.root.registry.dependents(name)
            if self.label(fiber.context, name) is label
        ]
        for fiber in fibers:
            fiber.request_refresh()
        if fibers:
            await asyncio.gather(*(fiber.wait() for fiber in fibers), return_exceptions=True)
        implementation = self._implementations.get(label)
        value = None if implementation is None else implementation.value
        self.root.events.emit_safe("internal/service", name, value)

    def bind(self, context: Context, callback: Callable[..., object]) -> Callable[..., object]:
        """Return a callback carrying its registration Context for diagnostics."""

        def bound(*args: object, **kwargs: object) -> object:
            return callback(*args, **kwargs)

        bound.__name__ = getattr(callback, "__name__", "bound")
        bound.__dict__["__cordis_context__"] = context
        return bound
