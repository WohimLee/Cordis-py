"""A minimal Context built on chapter 00's naive runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping

Cleanup = Callable[[], object]
Plugin = Callable[["Context"], object]


class _Runtime:
    def __init__(self) -> None:
        self.services: dict[str, object] = {}
        self.cleanups: list[Cleanup] = []

    def mount(self, context: Context, plugin: Plugin) -> None:
        result = plugin(context)
        if callable(result):
            self.cleanups.append(result)

    def close(self) -> None:
        while self.cleanups:
            self.cleanups.pop()()


class Context:
    """A runtime-bound scope with inheritable metadata."""

    def __init__(self) -> None:
        self._runtime = _Runtime()
        self._root = self
        self._meta: dict[str, object] = {}

    @classmethod
    def _derive(cls, parent: Context, meta: Mapping[str, object]) -> Context:
        child = cls.__new__(cls)
        child._runtime = parent._runtime
        child._root = parent.root
        child._meta = parent._meta | dict(meta)
        return child

    @staticmethod
    def is_context(value: object) -> bool:
        return isinstance(value, Context)

    @property
    def root(self) -> Context:
        return self._root

    @property
    def services(self) -> dict[str, object]:
        """Temporary chapter-only access to the shared service dictionary."""

        return self._runtime.services

    def __getattr__(self, name: str) -> object:
        try:
            return self._meta[name]
        except KeyError:
            raise AttributeError(name) from None

    def extend(self, meta: Mapping[str, object] | None = None) -> Context:
        return Context._derive(self, {} if meta is None else meta)

    def plugin(self, callback: Plugin) -> None:
        self._runtime.mount(self, callback)

    def close(self) -> None:
        if self is not self.root:
            raise RuntimeError("only the root context can close the runtime")
        self._runtime.close()
