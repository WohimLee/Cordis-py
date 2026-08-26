"""Plugin normalization and runtime registry."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .errors import CordisError, CordisErrorCode
from .model import Plugin, PluginSpec, normalize_inject

if TYPE_CHECKING:
    from .context import Context
    from .fiber import Fiber


def _new_fiber_set() -> set[Fiber]:
    return set()


@dataclass(slots=True)
class PluginRuntime:
    """Shared registry record for one normalized plugin callback."""

    spec: PluginSpec
    fibers: set[Fiber] = field(default_factory=_new_fiber_set)


class RegistryService:
    """Create Fibers and index mounted plugin definitions."""

    def __init__(self, root: Context) -> None:
        self.root = root
        self._counter = 0
        self._runtimes: dict[object, PluginRuntime] = {}
        self._dependents: dict[str, set[Fiber]] = {}

    @property
    def size(self) -> int:
        """Number of distinct mounted plugin definitions."""

        return len(self._runtimes)

    def resolve(self, plugin: Plugin) -> PluginSpec:
        """Normalize a function, class, or object-with-apply plugin."""

        if inspect.isclass(plugin) or inspect.isfunction(plugin):
            pass
        else:
            apply = getattr(plugin, "apply", None)
            if not callable(apply):
                raise CordisError(CordisErrorCode.INVALID_PLUGIN)
        raw_name = getattr(plugin, "name", None) or getattr(plugin, "__name__", None)
        name = raw_name if isinstance(raw_name, str) else plugin.__class__.__name__
        dependencies = normalize_inject(getattr(plugin, "inject", None))
        validator = getattr(plugin, "Config", None)
        return PluginSpec(plugin, name, dependencies, validator)

    def plugin(self, context: Context, plugin: Plugin, config: object = None) -> Fiber:
        """Mount a plugin under a Context and return its Fiber immediately."""

        from .fiber import Fiber

        context.fiber.assert_active()
        spec = self.resolve(plugin)
        runtime = self._runtimes.get(spec.callback)
        if runtime is None:
            runtime = PluginRuntime(spec)
            self._runtimes[spec.callback] = runtime
        self._counter += 1
        fiber = Fiber(self._counter, context, runtime, config)
        runtime.fibers.add(fiber)
        for name in spec.inject:
            self._dependents.setdefault(name, set()).add(fiber)
        fiber.bootstrap()
        context.root.events.emit_safe("internal/plugin", fiber)
        return fiber

    def dependents(self, name: str) -> tuple[Fiber, ...]:
        """Return a stable snapshot of Fibers depending on a service name."""

        return tuple(self._dependents.get(name, ()))

    def runtimes(self) -> tuple[PluginRuntime, ...]:
        """Return a side-effect-free runtime snapshot."""

        return tuple(self._runtimes.values())

    def remove(self, fiber: Fiber) -> None:
        """Remove a disposed Fiber from every registry index."""

        runtime = fiber.runtime
        runtime.fibers.discard(fiber)
        for name in runtime.spec.inject:
            fibers = self._dependents.get(name)
            if fibers is None:
                continue
            fibers.discard(fiber)
            if not fibers:
                del self._dependents[name]
        if not runtime.fibers:
            self._runtimes.pop(runtime.spec.callback, None)
