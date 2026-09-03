"""The intentionally limited plugin runtime used in tutorial chapter 00."""

from collections.abc import Callable

Plugin = Callable[[dict[str, object]], object]
Cleanup = Callable[[], object]


class NaiveRuntime:
    """Immediately execute plugins against one shared service dictionary."""

    def __init__(self) -> None:
        self.services: dict[str, object] = {}
        self.cleanups: list[Cleanup] = []

    def mount(self, plugin: Plugin) -> None:
        result = plugin(self.services)
        if callable(result):
            self.cleanups.append(result)

    def close(self) -> None:
        while self.cleanups:
            self.cleanups.pop()()
