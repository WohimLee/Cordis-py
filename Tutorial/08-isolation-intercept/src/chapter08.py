"""Isolation labels and intercept config for tutorial chapter 08."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

Cleanup = Callable[[], None]
DEFAULT_LABEL = object()


def _config(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("service config must be a mapping")
    result: dict[str, object] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str):
            raise TypeError("service config keys must be strings")
        result[key] = item
    return result


@dataclass(eq=False, slots=True)
class Impl:
    name: str
    value: object
    label: object


class ReflectService:
    def __init__(self) -> None:
        self._impls: list[Impl] = []

    def provide(self, context: Context, name: str, value: object) -> Cleanup:
        impl = Impl(name, value, context.label_for(name))
        self._impls.append(impl)
        disposed = False

        def dispose() -> None:
            nonlocal disposed
            if disposed:
                return
            disposed = True
            self._impls.remove(impl)

        return dispose

    def resolve(self, context: Context, name: str) -> Impl | None:
        label = context.label_for(name)
        return next(
            (impl for impl in reversed(self._impls) if impl.name == name and impl.label is label),
            None,
        )


class Context:
    def __init__(self) -> None:
        self._root = self
        self._reflect = ReflectService()
        self._labels: dict[str, object] = {}
        self._intercepts: dict[str, list[object]] = {}

    @classmethod
    def derive(cls, parent: Context) -> Context:
        child = cls.__new__(cls)
        child._root = parent._root
        child._reflect = parent._reflect
        child._labels = dict(parent._labels)
        child._intercepts = {name: list(configs) for name, configs in parent._intercepts.items()}
        return child

    def extend(self) -> Context:
        return Context.derive(self)

    def isolate(self, name: str, label: object | None = None) -> Context:
        child = self.extend()
        child._labels[name] = object() if label is None else label
        return child

    def intercept(self, name: str, config: object) -> Context:
        child = self.extend()
        child._intercepts.setdefault(name, []).append(config)
        return child

    def label_for(self, name: str) -> object:
        return self._labels.get(name, DEFAULT_LABEL)

    def intercepts_for(self, name: str) -> tuple[object, ...]:
        return tuple(self._intercepts.get(name, ()))

    def provide(self, name: str, value: object) -> Cleanup:
        return self._reflect.provide(self, name, value)

    def get(self, name: str) -> object | None:
        impl = self._reflect.resolve(self, name)
        return None if impl is None else impl.value


class Service:
    class _DefaultConfig:
        """Override ``merge`` here when shallow merge is not suitable."""

    Config: type[Any] = _DefaultConfig

    def __init__(self, name: str) -> None:
        self.name = name

    def resolve_config(
        self,
        context: Context,
        base: object | None = None,
        head: object | None = None,
    ) -> object:
        empty: dict[str, object] = {}
        values: list[object] = [empty if base is None else base]
        values.extend(context.intercepts_for(self.name))
        values.append(empty if head is None else head)
        configs = tuple(_config(value) for value in values)
        merge = getattr(self.Config, "merge", None)
        if callable(merge):
            return cast(Any, merge)(*configs)

        result: dict[str, object] = {}
        for config in configs:
            result.update(config)
        return result
