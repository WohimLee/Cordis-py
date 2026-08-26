"""Lifecycle-owned event hooks and dispatch modes."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .effect import Effect

if TYPE_CHECKING:
    from .context import Context

Listener = Callable[..., object]


def is_bailed(value: object) -> bool:
    """Return whether a listener result stops bail-style dispatch."""

    return value is not None and value is not False


@dataclass(frozen=True, slots=True)
class Hook:
    """One registered listener and its owning Context."""

    context: Context
    callback: Listener
    global_: bool = False


class EventsService:
    """Shared event bus for a root Context and all derived Contexts."""

    def __init__(self, root: Context) -> None:
        self.root = root
        self._hooks: dict[str, list[Hook]] = {}

    def on(
        self,
        context: Context,
        name: str,
        listener: Listener,
        *,
        prepend: bool = False,
        global_: bool = False,
    ) -> Effect:
        """Register a listener as an Effect owned by the calling Context."""

        self.emit_safe(
            "internal/listener",
            context,
            name,
            listener,
            {"prepend": prepend, "global": global_},
        )
        hook = Hook(context, listener, global_)
        hooks = self._hooks.setdefault(name, [])

        def setup() -> object:
            hooks.insert(0 if prepend else len(hooks), hook)

            def cleanup() -> None:
                try:
                    hooks.remove(hook)
                except ValueError:
                    return
                if not hooks:
                    self._hooks.pop(name, None)

            return cleanup

        return context.fiber.effects.install_sync(setup, f"ctx.on({name!r})")

    def once(
        self,
        context: Context,
        name: str,
        listener: Listener,
        *,
        prepend: bool = False,
        global_: bool = False,
    ) -> Effect:
        """Register a listener that removes itself before its first call."""

        self.emit_safe(
            "internal/listener",
            context,
            name,
            listener,
            {"prepend": prepend, "global": global_},
        )
        hooks = self._hooks.setdefault(name, [])
        hook: Hook

        def cleanup() -> None:
            try:
                hooks.remove(hook)
            except ValueError:
                return
            if not hooks:
                self._hooks.pop(name, None)

        def callback(*args: object) -> object:
            cleanup()
            return listener(*args)

        hook = Hook(context, callback, global_)

        def setup() -> object:
            hooks.insert(0 if prepend else len(hooks), hook)
            return cleanup

        return context.fiber.effects.install_sync(setup, f"ctx.once({name!r})")

    def _callbacks(self, name: str) -> tuple[Listener, ...]:
        return tuple(hook.callback for hook in self._hooks.get(name, ()))

    def emit_safe(self, name: str, *args: object) -> tuple[BaseException, ...]:
        """Notify observers without allowing them to interrupt framework cleanup."""

        errors: list[BaseException] = []
        for callback in self._callbacks(name):
            try:
                result = callback(*args)
                if inspect.isawaitable(result):
                    if inspect.iscoroutine(result):
                        result.close()
                    raise TypeError(f"safe event listener for {name!r} returned an awaitable")
            except BaseException as error:
                errors.append(error)
        return tuple(errors)

    def waterfall_sync(
        self,
        name: str,
        *args: object,
        next_: Callable[[], object],
    ) -> object:
        """Compose synchronous listeners around a final callback."""

        callbacks = self._callbacks(name)

        def dispatch(index: int) -> object:
            result = (
                next_()
                if index == len(callbacks)
                else callbacks[index](*args, lambda: dispatch(index + 1))
            )
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError(f"sync waterfall listener for {name!r} returned an awaitable")
            return result

        return dispatch(0)

    def emit(self, name: str, *args: object) -> None:
        """Synchronously notify every listener in registration order."""

        if not name.startswith("internal/"):
            self.emit_safe("internal/dispatch", "emit", name, args)
        for callback in self._callbacks(name):
            result = callback(*args)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError(f"emit listener for {name!r} returned an awaitable")

    def bail(self, name: str, *args: object) -> object:
        """Return the first synchronous bail value."""

        if not name.startswith("internal/"):
            self.emit_safe("internal/dispatch", "bail", name, args)
        for callback in self._callbacks(name):
            result = callback(*args)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError(f"bail listener for {name!r} returned an awaitable")
            if is_bailed(result):
                return result
        return None

    async def serial(self, name: str, *args: object) -> object:
        """Await listeners in order and return the first bail value."""

        if not name.startswith("internal/"):
            self.emit_safe("internal/dispatch", "serial", name, args)
        for callback in self._callbacks(name):
            result = callback(*args)
            if inspect.isawaitable(result):
                result = await cast(Awaitable[object], result)
            if is_bailed(result):
                return result
        return None

    async def parallel(self, name: str, *args: object) -> None:
        """Run all listeners concurrently and aggregate failures."""

        if not name.startswith("internal/"):
            self.emit_safe("internal/dispatch", "parallel", name, args)

        async def invoke(callback: Listener) -> None:
            result = callback(*args)
            if inspect.isawaitable(result):
                await cast(Awaitable[object], result)

        results = await asyncio.gather(
            *(invoke(callback) for callback in self._callbacks(name)),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, BaseException)]
        if errors:
            raise BaseExceptionGroup(f"parallel event {name!r} failed", errors)

    async def waterfall(
        self,
        name: str,
        *args: object,
        next_: Callable[[], object],
    ) -> object:
        """Compose listeners as async around-middleware."""

        if not name.startswith("internal/"):
            self.emit_safe("internal/dispatch", "waterfall", name, args)
        callbacks = self._callbacks(name)

        async def dispatch(index: int) -> object:
            if index == len(callbacks):
                result = next_()
            else:
                result = callbacks[index](*args, lambda: dispatch(index + 1))
            if inspect.isawaitable(result):
                return await cast(Awaitable[object], result)
            return result

        return await dispatch(0)
