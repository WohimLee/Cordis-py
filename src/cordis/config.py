"""Plugin configuration validation contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class ConfigValidator(Protocol):
    """Synchronous adapter used to normalize plugin configuration."""

    def validate(self, value: object) -> object:
        """Return normalized configuration or raise an exception."""


class ValidationError(TypeError):
    """Configuration validation failed before plugin activation."""

    def __init__(self, plugin_name: str, reason: BaseException) -> None:
        self.plugin_name = plugin_name
        self.reason = reason
        super().__init__(f"invalid config for plugin {plugin_name!r}: {reason}")


def validate_config(validator: object | None, value: object, plugin_name: str) -> object:
    """Run a validator object or callable and normalize its error type."""

    if validator is None:
        return value
    try:
        method = getattr(validator, "validate", None)
        if callable(method):
            callback = cast(Callable[[object], object], method)
            return callback(value)
        if callable(validator):
            callback = cast(Callable[[object], object], validator)
            return callback(value)
        raise TypeError("Config must be callable or provide validate()")
    except ValidationError:
        raise
    except BaseException as error:
        raise ValidationError(plugin_name, error) from error
