"""Behavior checkpoints for tutorial chapter 05."""

import pytest
from chapter05 import Context, Fiber, FiberState


def test_provide_and_get_service_implementation() -> None:
    root = Context()
    dispose = root.provide("message", "hello")

    assert root.get("message") == "hello"
    assert root.reflect.get("message") == "hello"
    assert root.reflect.ctx is root
    assert dispose()
    assert not dispose()
    assert root.get("message") is None


def test_strict_lookup_hides_loading_provider() -> None:
    root = Context()
    provider = Fiber(root, FiberState.LOADING)
    provider.ctx.provide("message", "loading")

    assert root.get("message", strict=True) is None
    assert root.get("message", strict=False) == "loading"

    provider.state = FiberState.ACTIVE
    assert root.get("message", strict=True) == "loading"


def test_availability_check_applies_only_to_strict_lookup() -> None:
    root = Context()
    ready = False
    root.provide("database", "db", check=lambda _context: ready)

    assert root.get("database") is None
    assert root.get("database", strict=False) == "db"
    ready = True
    assert root.get("database") == "db"


def test_disposing_shadowed_provider_restores_previous_value() -> None:
    root = Context()
    dispose_first = root.provide("message", "first")
    dispose_second = root.provide("message", "second")

    assert root.get("message") == "second"
    dispose_second()
    assert root.get("message") == "first"
    dispose_first()
    assert root.get("message") is None


def test_isolation_resolves_same_name_by_label_identity() -> None:
    root = Context()
    label_a = object()
    label_b = object()
    scope_a = root.isolate("database", label_a)
    scope_b = root.isolate("database", label_b)
    another_a = root.isolate("database", label_a)

    root.provide("database", "root-db")
    scope_a.provide("database", "a-db")
    scope_b.provide("database", "b-db")

    assert root.get("database") == "root-db"
    assert scope_a.get("database") == "a-db"
    assert another_a.get("database") == "a-db"
    assert scope_b.get("database") == "b-db"


@pytest.mark.asyncio
async def test_fiber_dispose_removes_owned_service() -> None:
    root = Context()
    provider = Fiber(root)
    provider.ctx.provide("message", "hello")
    assert root.get("message") == "hello"

    await provider.dispose()
    assert root.get("message") is None
    assert provider.state is FiberState.DISPOSED


def test_provide_and_dispose_notify_watchers() -> None:
    root = Context()
    changes: list[str] = []
    dispose_watch = root.reflect.watch("message", changes.append)

    dispose_service = root.provide("message", "hello")
    dispose_service()
    assert changes == ["message", "message"]

    assert dispose_watch()
    assert not dispose_watch()
    root.provide("message", "ignored")
    assert changes == ["message", "message"]
