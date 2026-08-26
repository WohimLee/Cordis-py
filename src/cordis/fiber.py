"""Dependency-driven plugin lifecycle instances."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from .config import validate_config
from .effect import EffectScope
from .errors import CordisError, CordisErrorCode

if TYPE_CHECKING:
    from .context import Context
    from .reflect import Implementation
    from .registry import PluginRuntime


class FiberState(StrEnum):
    """Stable and transitional plugin lifecycle states."""

    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"


class RootFiber:
    """Permanent owner of top-level plugin Fibers until Context shutdown."""

    uid = 0
    name = "root"

    def __init__(self, context: Context) -> None:
        self.context = context
        self.state = FiberState.ACTIVE
        self.effects = EffectScope()
        self.dependencies: dict[str, Implementation] = {}
        self.provided_names: set[str] = set()

    @property
    def is_active(self) -> bool:
        return self.state is FiberState.ACTIVE

    def assert_active(self) -> None:
        if self.state is FiberState.DISPOSED:
            raise CordisError(CordisErrorCode.INACTIVE_EFFECT)

    def get_effects(self) -> tuple[object, ...]:
        """Return diagnostic metadata for live Effects."""

        return self.effects.effects

    async def dispose(self) -> None:
        if self.state is FiberState.DISPOSED:
            return
        self.state = FiberState.UNLOADING
        await self.effects.close()
        self.state = FiberState.DISPOSED


class Fiber:
    """One plugin mount and its dependency-controlled activation epochs."""

    def __init__(
        self,
        uid: int,
        parent: Context,
        runtime: PluginRuntime,
        config: object,
    ) -> None:
        from .context import Context

        self.uid = uid
        self.parent = parent
        self.runtime = runtime
        self.raw_config = config
        self.config = config
        self.context = Context.derive(parent, self)
        for name, intercept in runtime.spec.inject.items():
            if intercept is not None:
                self.context.intercepts.setdefault(name, []).append(intercept)
        self.state = FiberState.PENDING
        self.effects = EffectScope()
        self.dependencies: dict[str, Implementation] = {}
        self.provided_names: set[str] = set()
        self.error: BaseException | None = None
        self._epoch: tuple[int, ...] | None = None
        self._failed_epoch: tuple[int, ...] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_requested = False
        self._lifecycle_lock = asyncio.Lock()
        self._dispose_requested = False
        self._force_restart = False

    @property
    def name(self) -> str:
        """Diagnostic plugin name."""

        return self.runtime.spec.name

    @property
    def is_active(self) -> bool:
        """Whether this activation is visible to strict service consumers."""

        return self.state is FiberState.ACTIVE

    def assert_active(self) -> None:
        """Reject new owned resources after final disposal begins."""

        if self._dispose_requested or self.state is FiberState.DISPOSED:
            raise CordisError(CordisErrorCode.INACTIVE_EFFECT)

    def get_effects(self) -> tuple[object, ...]:
        """Return diagnostic metadata for live Effects."""

        return self.effects.effects

    def bootstrap(self) -> None:
        """Publish parent ownership and request initial dependency evaluation."""

        self.parent.fiber.effects.install_sync(
            lambda: self.dispose,
            f"ctx.plugin({self.name!r})",
        )
        self.request_refresh()

    def _set_state(self, state: FiberState) -> None:
        old_state = self.state
        if old_state is state:
            return
        self.state = state
        self.parent.root.events.emit_safe("internal/status", self, old_state)

    def request_refresh(self) -> None:
        """Schedule dependency evaluation, coalescing repeated notifications."""

        if self._dispose_requested:
            return
        self._refresh_requested = True
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def wait(self) -> Fiber:
        """Wait until all currently requested lifecycle work settles."""

        while self._refresh_task is not None:
            task = self._refresh_task
            await asyncio.shield(task)
            if task is self._refresh_task and not self._refresh_requested:
                break
        if self.error is not None:
            raise self.error
        return self

    async def _refresh_loop(self) -> None:
        while self._refresh_requested and not self._dispose_requested:
            self._refresh_requested = False
            async with self._lifecycle_lock:
                await self._refresh_once()

    def _resolve_dependencies(self) -> tuple[dict[str, Implementation], tuple[int, ...]] | None:
        resolved: dict[str, Implementation] = {}
        epoch: list[int] = []
        for name in self.runtime.spec.inject:
            implementation = self.parent.root.reflect.implementation(self.context, name)
            if implementation is None:
                return None
            resolved[name] = implementation
            epoch.append(implementation.fiber.uid)
        return resolved, tuple(epoch)

    async def _refresh_once(self) -> None:
        resolution = self._resolve_dependencies()
        if resolution is None:
            if self.state in {FiberState.ACTIVE, FiberState.FAILED}:
                await self._unload()
            return

        dependencies, epoch = resolution
        force_restart = self._force_restart
        self._force_restart = False
        if self.state is FiberState.ACTIVE and epoch == self._epoch and not force_restart:
            return
        if self.state is FiberState.FAILED and epoch == self._failed_epoch and not force_restart:
            return
        if self.state in {FiberState.ACTIVE, FiberState.FAILED}:
            await self._unload()
        if self._dispose_requested:
            return
        await self._activate(dependencies, epoch)

    async def _activate(
        self,
        dependencies: dict[str, Implementation],
        epoch: tuple[int, ...],
    ) -> None:
        self._set_state(FiberState.LOADING)
        self.dependencies = dependencies
        self._epoch = epoch
        self.error = None
        self.effects = EffectScope()
        try:
            self.config = await self.context.waterfall(
                "internal/config",
                self.raw_config,
                next_=lambda: validate_config(
                    self.runtime.spec.validator,
                    self.raw_config,
                    self.name,
                ),
            )
            result = self._invoke_plugin()
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                await self.effects.install(lambda: result, f"plugin({self.name!r})")
            if self._dispose_requested or self._resolve_dependencies_epoch() != epoch:
                await self._unload()
                return
            self._set_state(FiberState.ACTIVE)
            for name in tuple(self.provided_names):
                label = self.parent.root.reflect.label(self.context, name)
                self.parent.root.reflect.notify_soon(name, label)
        except BaseException as error:
            self.error = error
            self._failed_epoch = epoch
            try:
                await self.effects.close()
            except BaseException as cleanup_error:
                self.error = BaseExceptionGroup(
                    f"plugin {self.name!r} activation and rollback failed",
                    [error, cleanup_error],
                )
            self.dependencies = {}
            self._epoch = None
            self._set_state(FiberState.FAILED)

    def _resolve_dependencies_epoch(self) -> tuple[int, ...] | None:
        resolution = self._resolve_dependencies()
        return None if resolution is None else resolution[1]

    def _invoke_plugin(self) -> object:
        plugin = self.runtime.spec.callback
        if inspect.isclass(plugin):
            constructor = cast(Callable[[object, object], object], plugin)
            constructor(self.context, self.config)
            return None
        apply = getattr(plugin, "apply", None)
        if not inspect.isfunction(plugin) and callable(apply):
            return apply(self.context, self.config)
        if not callable(plugin):
            raise CordisError(CordisErrorCode.INVALID_PLUGIN)
        callback = cast(Callable[[object, object], object], plugin)
        return callback(self.context, self.config)

    async def _unload(self) -> None:
        self._set_state(FiberState.UNLOADING)
        try:
            await self.effects.close()
        finally:
            self.dependencies = {}
            self.provided_names.clear()
            self._epoch = None
            self.error = None
            self._set_state(FiberState.DISPOSED if self._dispose_requested else FiberState.PENDING)

    async def restart(self) -> None:
        """Force a new activation using the current raw configuration."""

        self.assert_active()
        self._force_restart = True
        self.error = None
        self.request_refresh()
        await self.wait()

    async def update(self, config: object, no_save: bool = False) -> object:
        """Validate and apply configuration through the update waterfall."""

        self.assert_active()
        validate_config(self.runtime.spec.validator, config, self.name)

        async def apply_update() -> None:
            self.raw_config = config
            await self.restart()

        return await self.context.waterfall(
            "internal/update",
            config,
            no_save,
            next_=apply_update,
        )

    async def dispose(self) -> None:
        """Permanently unload and remove this Fiber."""

        if self.state is FiberState.DISPOSED:
            return
        self._dispose_requested = True
        async with self._lifecycle_lock:
            if cast(FiberState, self.state) is not FiberState.DISPOSED:
                await self._unload()
            self.parent.root.registry.remove(self)
            self.parent.root.events.emit_safe("internal/plugin", self)
