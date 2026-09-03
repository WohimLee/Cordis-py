"""Behavior checkpoints for tutorial chapter 02."""

import asyncio

import pytest
from chapter02 import Effect


def test_plain_cleanup_is_not_idempotent() -> None:
    trace: list[str] = []

    def setup():  # type: ignore[no-untyped-def]
        trace.append("open")
        return lambda: trace.append("close")

    cleanup = setup()
    cleanup()
    cleanup()
    assert trace == ["open", "close", "close"]


@pytest.mark.asyncio
async def test_effect_runs_setup_immediately() -> None:
    trace: list[str] = []
    effect = Effect(lambda: trace.append("setup"))
    assert trace == ["setup"]
    assert await effect is effect
    await effect()


def test_invalid_result_is_rejected_immediately() -> None:
    with pytest.raises(TypeError, match="Invalid effect"):
        Effect(lambda: "not a cleanup")


@pytest.mark.asyncio
async def test_cleanups_run_in_reverse_order() -> None:
    trace: list[str] = []
    effect = Effect(
        lambda: [
            lambda: trace.append("first"),
            lambda: trace.append("second"),
        ]
    )
    await effect()
    assert trace == ["second", "first"]


@pytest.mark.asyncio
async def test_repeated_calls_share_one_dispose_task() -> None:
    trace: list[str] = []
    effect = Effect(lambda: lambda: trace.append("cleanup"))
    first = effect()
    second = effect()
    assert first is second
    await first
    assert trace == ["cleanup"]


@pytest.mark.asyncio
async def test_dispose_waits_for_async_setup() -> None:
    started = asyncio.Event()
    ready = asyncio.Event()
    trace: list[str] = []

    async def setup():  # type: ignore[no-untyped-def]
        trace.append("setup-start")
        started.set()
        await ready.wait()
        trace.append("setup-end")
        return lambda: trace.append("cleanup")

    effect = Effect(setup)
    await started.wait()
    disposing = effect()
    assert not disposing.done()
    assert trace == ["setup-start"]

    ready.set()
    await disposing
    assert trace == ["setup-start", "setup-end", "cleanup"]


@pytest.mark.asyncio
async def test_async_cleanup_is_awaited() -> None:
    started = asyncio.Event()
    ready = asyncio.Event()
    trace: list[str] = []

    async def cleanup() -> None:
        started.set()
        await ready.wait()
        trace.append("cleanup")

    effect = Effect(lambda: cleanup)
    disposing = effect()
    await started.wait()
    assert not disposing.done()
    ready.set()
    await disposing
    assert trace == ["cleanup"]


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_stop_remaining_cleanup() -> None:
    trace: list[str] = []

    def fail() -> None:
        trace.append("fail")
        raise RuntimeError("broken")

    effect = Effect(lambda: [lambda: trace.append("first"), fail])
    with pytest.raises(ExceptionGroup, match="effect cleanup failed") as captured:
        await effect()

    assert trace == ["fail", "first"]
    assert str(captured.value.exceptions[0]) == "broken"
