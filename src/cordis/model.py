"""Shared immutable runtime records."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

Plugin: TypeAlias = object
Inject: TypeAlias = list[str] | tuple[str, ...] | Mapping[str, object | None]


@dataclass(frozen=True, slots=True)
class PluginSpec:
    """Normalized plugin entrypoint and metadata."""

    callback: Plugin
    name: str
    inject: Mapping[str, object | None]
    validator: object | None = None


def normalize_inject(value: object) -> dict[str, object | None]:
    """Normalize array or mapping dependency metadata."""

    if value is None:
        return {}
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        if not all(isinstance(name, str) for name in mapping):
            raise TypeError("plugin inject mapping keys must be strings")
        return {cast(str, name): config for name, config in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(Sequence[object], value)
        if all(isinstance(name, str) for name in sequence):
            return {cast(str, name): None for name in sequence}
    raise TypeError("plugin inject must be a string sequence or mapping")


def inject(*names: str, **configs: object) -> Callable[[Any], Any]:
    """Declare service dependencies on a plugin."""

    dependencies = {name: None for name in names} | configs

    def decorate(plugin: Any) -> Any:
        plugin.inject = dependencies
        return plugin

    return decorate
