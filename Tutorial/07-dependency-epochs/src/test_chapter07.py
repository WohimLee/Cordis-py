"""Behavior checkpoints for tutorial chapter 07."""

import asyncio

import pytest
from chapter07 import Context, FiberState, declare_inject


def provider(value: str):  # type: ignore[no-untyped-def]
    def plugin(context: Context, _config: object) -> None:
        context.provide("database", value)

    return plugin


@pytest.mark.asyncio
async def test_service_loss_unloads_active_consumer() -> None:
    root = Context()
    trace: list[str] = []

    def consumer(context: Context, _config: object):  # type: ignore[no-untyped-def]
        value = str(context.get("database"))
        trace.append(f"activate:{value}")
        return lambda: trace.append(f"cleanup:{value}")

    declare_inject(consumer, ["database"])
    consumer_fiber = root.plugin(consumer)
    provider_fiber = root.plugin(provider("A"))
    await provider_fiber
    await consumer_fiber

    await provider_fiber.dispose()
    await consumer_fiber
    assert consumer_fiber.state is FiberState.PENDING
    assert trace == ["activate:A", "cleanup:A"]
    await root.aclose()


@pytest.mark.asyncio
async def test_restored_service_activates_new_epoch() -> None:
    root = Context()
    trace: list[str] = []

    def consumer(context: Context, _config: object):  # type: ignore[no-untyped-def]
        value = str(context.get("database"))
        trace.append(f"activate:{value}")
        return lambda: trace.append(f"cleanup:{value}")

    declare_inject(consumer, ["database"])
    consumer_fiber = root.plugin(consumer)
    first_provider = root.plugin(provider("A"))
    await first_provider
    await consumer_fiber
    first_epoch = consumer_fiber.epoch

    await first_provider.dispose()
    await consumer_fiber
    second_provider = root.plugin(provider("B"))
    await second_provider
    await consumer_fiber

    assert consumer_fiber.state is FiberState.ACTIVE
    assert consumer_fiber.epoch != first_epoch
    assert trace == ["activate:A", "cleanup:A", "activate:B"]
    await root.aclose()


@pytest.mark.asyncio
async def test_service_loss_during_loading_discards_stale_setup() -> None:
    root = Context()
    started = asyncio.Event()
    release = asyncio.Event()
    trace: list[str] = []

    async def consumer(context: Context, _config: object):  # type: ignore[no-untyped-def]
        value = str(context.get("database"))
        trace.append(f"setup-start:{value}")
        started.set()
        await release.wait()
        trace.append(f"setup-end:{value}")
        return lambda: trace.append(f"cleanup:{value}")

    declare_inject(consumer, ["database"])
    consumer_fiber = root.plugin(consumer)
    provider_fiber = root.plugin(provider("A"))
    await provider_fiber
    await started.wait()
    assert consumer_fiber.state is FiberState.LOADING

    await provider_fiber.dispose()
    release.set()
    await consumer_fiber

    assert consumer_fiber.state is FiberState.PENDING
    assert trace == ["setup-start:A", "setup-end:A", "cleanup:A"]
    await root.aclose()


@pytest.mark.asyncio
async def test_restoration_during_unloading_waits_for_old_cleanup() -> None:
    root = Context()
    cleanup_started = asyncio.Event()
    cleanup_release = asyncio.Event()
    trace: list[str] = []

    def consumer(context: Context, _config: object):  # type: ignore[no-untyped-def]
        value = str(context.get("database"))
        trace.append(f"activate:{value}")

        async def cleanup() -> None:
            trace.append(f"cleanup-start:{value}")
            cleanup_started.set()
            await cleanup_release.wait()
            trace.append(f"cleanup-end:{value}")

        return cleanup

    declare_inject(consumer, ["database"])
    consumer_fiber = root.plugin(consumer)
    first_provider = root.plugin(provider("A"))
    await first_provider
    await consumer_fiber

    disposing_first = first_provider.dispose()
    await cleanup_started.wait()
    second_provider = root.plugin(provider("B"))
    await second_provider
    assert "activate:B" not in trace

    cleanup_release.set()
    await disposing_first
    await consumer_fiber
    assert trace == [
        "activate:A",
        "cleanup-start:A",
        "cleanup-end:A",
        "activate:B",
    ]
    await root.aclose()


@pytest.mark.asyncio
async def test_disposed_fiber_never_reactivates() -> None:
    root = Context()
    activations = 0

    def consumer(_context: Context, _config: object) -> None:
        nonlocal activations
        activations += 1

    declare_inject(consumer, ["database"])
    consumer_fiber = root.plugin(consumer)
    first_provider = root.plugin(provider("A"))
    await first_provider
    await consumer_fiber
    await consumer_fiber.dispose()

    await first_provider.dispose()
    second_provider = root.plugin(provider("B"))
    await second_provider
    await consumer_fiber

    assert consumer_fiber.state is FiberState.DISPOSED
    assert activations == 1
    await root.aclose()
