"""Behavior checkpoints for tutorial chapter 06."""

from typing import Any, cast

import pytest
from chapter06 import Context, FiberState, Inject


def test_inject_metadata_normalizes_lists_mappings_and_inheritance() -> None:
    @Inject("database")
    class Base:
        pass

    @Inject("cache", {"timeout": 3})
    class Consumer(Base):
        pass

    assert Inject.resolve(["database", "cache"]) == {
        "database": None,
        "cache": None,
    }
    assert Inject.resolve(cast(Any, Consumer).inject) == {
        "database": None,
        "cache": {"timeout": 3},
    }


@pytest.mark.asyncio
async def test_consumer_waits_for_provider() -> None:
    root = Context()
    calls = 0

    def consumer(_context: Context) -> None:
        nonlocal calls
        calls += 1

    consumer.inject = ["database"]  # type: ignore[attr-defined]
    fiber = root.plugin(consumer)
    await fiber

    assert fiber.state is FiberState.PENDING
    assert calls == 0
    await root.aclose()


@pytest.mark.asyncio
async def test_late_provider_activates_pending_consumer() -> None:
    root = Context()
    seen: list[str] = []

    def consumer(context: Context) -> None:
        seen.append(str(context.get("database")))

    consumer.inject = ["database"]  # type: ignore[attr-defined]
    consumer_fiber = root.plugin(consumer)
    await consumer_fiber
    assert consumer_fiber.state is FiberState.PENDING

    def provider(context: Context) -> None:
        context.provide("database", "db")

    provider_fiber = root.plugin(provider)
    await provider_fiber
    await consumer_fiber

    assert provider_fiber.state is FiberState.ACTIVE
    assert consumer_fiber.state is FiberState.ACTIVE
    assert seen == ["db"]
    await root.aclose()


@pytest.mark.asyncio
async def test_consumer_waits_for_all_dependencies() -> None:
    root = Context()
    calls = 0

    def consumer(_context: Context) -> None:
        nonlocal calls
        calls += 1

    consumer.inject = ["database", "cache"]  # type: ignore[attr-defined]
    consumer_fiber = root.plugin(consumer)
    await consumer_fiber

    def database_provider(context: Context) -> object:
        return context.provide("database", "db")

    database = root.plugin(database_provider)
    await database
    await consumer_fiber
    assert consumer_fiber.state is FiberState.PENDING
    assert calls == 0

    def cache_provider(context: Context) -> object:
        return context.provide("cache", "cache")

    cache = root.plugin(cache_provider)
    await cache
    await consumer_fiber
    assert consumer_fiber.state is FiberState.ACTIVE
    assert calls == 1
    await root.aclose()


@pytest.mark.asyncio
async def test_context_inject_uses_normal_plugin_path() -> None:
    root = Context()
    seen: list[str] = []

    def callback(context: Context, _config: object) -> None:
        seen.append(str(context.get("ready")))

    consumer = root.inject(["ready"], callback)
    await consumer
    assert consumer.state is FiberState.PENDING

    def provider_plugin(context: Context) -> object:
        return context.provide("ready", "yes")

    provider = root.plugin(provider_plugin)
    await provider
    await consumer
    assert consumer.state is FiberState.ACTIVE
    assert seen == ["yes"]
    await root.aclose()


@pytest.mark.asyncio
async def test_service_loss_is_intentionally_deferred_to_next_chapter() -> None:
    root = Context()
    cleanups = 0

    def consumer(_context: Context):  # type: ignore[no-untyped-def]
        def cleanup() -> None:
            nonlocal cleanups
            cleanups += 1

        return cleanup

    consumer.inject = ["database"]  # type: ignore[attr-defined]
    consumer_fiber = root.plugin(consumer)

    def provider(context: Context) -> object:
        return context.provide("database", "db")

    provider_fiber = root.plugin(provider)
    await provider_fiber
    await consumer_fiber

    await provider_fiber.dispose()
    await consumer_fiber
    assert consumer_fiber.state is FiberState.ACTIVE
    assert cleanups == 0

    await root.aclose()
    assert cleanups == 1
