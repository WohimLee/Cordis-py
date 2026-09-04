from __future__ import annotations

import asyncio

import pytest
from chapter11 import CleanupGroup, FiberState, RaceFiber, SetupScope


@pytest.mark.asyncio
async def test_dependency_loss_while_loading_rolls_back_once() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    cleanups = 0

    async def plugin(_epoch: int):  # type: ignore[no-untyped-def]
        nonlocal cleanups
        started.set()
        await release.wait()

        def cleanup() -> None:
            nonlocal cleanups
            cleanups += 1

        return cleanup

    fiber = RaceFiber(plugin)
    fiber.set_epoch(1)
    await started.wait()
    fiber.set_epoch(None)
    release.set()
    await fiber.wait()

    assert fiber.state is FiberState.PENDING
    assert cleanups == 1


@pytest.mark.asyncio
async def test_dependency_restoration_while_unloading_reactivates() -> None:
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()
    activations: list[int] = []

    def plugin(epoch: int):  # type: ignore[no-untyped-def]
        activations.append(epoch)

        async def cleanup() -> None:
            cleanup_started.set()
            await release_cleanup.wait()

        return cleanup

    fiber = RaceFiber(plugin)
    fiber.set_epoch(1)
    await fiber.wait()
    fiber.set_epoch(None)
    await cleanup_started.wait()
    fiber.set_epoch(2)
    release_cleanup.set()
    await fiber.wait()

    assert fiber.state is FiberState.ACTIVE
    assert fiber.active_epoch == 2
    assert activations == [1, 2]


@pytest.mark.asyncio
async def test_dispose_waits_for_loading_then_cleans_result() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    cleaned = asyncio.Event()

    async def plugin(_epoch: int):  # type: ignore[no-untyped-def]
        started.set()
        await release.wait()
        return cleaned.set

    fiber = RaceFiber(plugin)
    fiber.set_epoch(1)
    await started.wait()
    dispose_task = asyncio.create_task(fiber.dispose())
    await fiber.dispose_started.wait()

    assert not dispose_task.done()
    release.set()
    await dispose_task

    assert cleaned.is_set()
    assert fiber.state is FiberState.DISPOSED
    assert fiber.removed


@pytest.mark.asyncio
async def test_scope_close_waits_for_setup_and_cleans_late_result() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    cleaned = asyncio.Event()

    async def setup():  # type: ignore[no-untyped-def]
        started.set()
        await release.wait()
        return cleaned.set

    scope = SetupScope()
    install_task = asyncio.create_task(scope.install(setup))
    await started.wait()
    close_task = asyncio.create_task(scope.close())
    assert not close_task.done()
    release.set()

    with pytest.raises(RuntimeError, match="closed during setup"):
        await install_task
    await close_task

    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_cleanup_group_continues_and_aggregates_failures() -> None:
    trace: list[str] = []

    def fail(name: str):  # type: ignore[no-untyped-def]
        def cleanup() -> None:
            trace.append(name)
            raise ValueError(name)

        return cleanup

    group = CleanupGroup([fail("first"), lambda: trace.append("middle"), fail("last")])

    with pytest.raises(BaseExceptionGroup) as caught:
        await group.close()

    assert trace == ["last", "middle", "first"]
    assert [str(error) for error in caught.value.exceptions] == ["last", "first"]


@pytest.mark.asyncio
async def test_cleanup_failure_still_disposes_and_removes_fiber() -> None:
    def plugin(_epoch: int):  # type: ignore[no-untyped-def]
        def cleanup() -> None:
            raise ValueError("cleanup failed")

        return cleanup

    fiber = RaceFiber(plugin)
    fiber.set_epoch(1)
    await fiber.wait()

    with pytest.raises(BaseExceptionGroup):
        await fiber.dispose()

    assert fiber.state is FiberState.DISPOSED
    assert fiber.removed


@pytest.mark.asyncio
async def test_disposed_fiber_ignores_dependency_restoration() -> None:
    activations = 0

    def plugin(_epoch: int) -> None:
        nonlocal activations
        activations += 1

    fiber = RaceFiber(plugin)
    fiber.set_epoch(1)
    await fiber.wait()
    await fiber.dispose()
    fiber.set_epoch(2)
    await fiber.wait()

    assert fiber.state is FiberState.DISPOSED
    assert activations == 1
