from __future__ import annotations

from typing import cast

import pytest
from chapter09 import Fiber, FiberDisposedError, FiberState


@pytest.mark.asyncio
async def test_status_reports_old_and_new_states() -> None:
    transitions: list[tuple[FiberState, FiberState]] = []
    fiber = Fiber(lambda _config: None)
    fiber.on_status(lambda current, old: transitions.append((old, current.state)))

    await fiber.start()

    assert transitions == [
        (FiberState.PENDING, FiberState.LOADING),
        (FiberState.LOADING, FiberState.ACTIVE),
    ]


@pytest.mark.asyncio
async def test_missing_dependency_stays_pending() -> None:
    calls = 0

    def plugin(_config: object) -> None:
        nonlocal calls
        calls += 1

    fiber = Fiber(plugin, dependencies_ready=lambda: False)
    await fiber.start()

    assert fiber.state is FiberState.PENDING
    assert calls == 0


@pytest.mark.asyncio
async def test_activation_failure_enters_failed_and_wait_raises() -> None:
    error = RuntimeError("cannot start")

    def plugin(_config: object) -> None:
        raise error

    fiber = Fiber(plugin).start()

    with pytest.raises(RuntimeError, match="cannot start") as raised:
        await fiber

    assert raised.value is error
    assert fiber.state is FiberState.FAILED
    assert fiber.error is error


@pytest.mark.asyncio
async def test_same_failed_epoch_does_not_retry_automatically() -> None:
    calls = 0

    def plugin(_config: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("still broken")

    fiber = Fiber(plugin).start()
    with pytest.raises(RuntimeError):
        await fiber

    fiber.request_refresh()
    with pytest.raises(RuntimeError):
        await fiber

    assert calls == 1
    assert fiber.state is FiberState.FAILED


@pytest.mark.asyncio
async def test_restart_forces_a_new_activation() -> None:
    starts = 0
    cleanups = 0

    def plugin(_config: object):  # type: ignore[no-untyped-def]
        nonlocal starts
        starts += 1

        def cleanup() -> None:
            nonlocal cleanups
            cleanups += 1

        return cleanup

    fiber = Fiber(plugin)
    await fiber.start()
    await fiber.restart()

    assert fiber.state is FiberState.ACTIVE
    assert (starts, cleanups) == (2, 1)


@pytest.mark.asyncio
async def test_restart_can_recover_a_failed_fiber() -> None:
    broken = True

    def plugin(_config: object) -> None:
        if broken:
            raise RuntimeError("broken")

    fiber = Fiber(plugin).start()
    with pytest.raises(RuntimeError):
        await fiber

    broken = False
    await fiber.restart()

    assert fiber.state is FiberState.ACTIVE
    assert fiber.error is None


@pytest.mark.asyncio
async def test_invalid_update_preserves_active_epoch() -> None:
    starts: list[int] = []

    def validate(value: object) -> int:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("config must be positive")
        return value

    fiber = Fiber(lambda config: starts.append(cast(int, config)), 1, validator=validate)
    await fiber.start()

    with pytest.raises(ValueError, match="positive"):
        await fiber.update(0)

    assert fiber.state is FiberState.ACTIVE
    assert fiber.config == 1
    assert starts == [1]


@pytest.mark.asyncio
async def test_valid_update_restarts_with_new_config() -> None:
    starts: list[object] = []
    fiber = Fiber(lambda config: starts.append(config), "one")
    await fiber.start()

    await fiber.update("two")

    assert fiber.state is FiberState.ACTIVE
    assert fiber.config == "two"
    assert starts == ["one", "two"]


@pytest.mark.asyncio
async def test_dispose_is_final_and_idempotent() -> None:
    cleanups = 0

    def plugin(_config: object):  # type: ignore[no-untyped-def]
        def cleanup() -> None:
            nonlocal cleanups
            cleanups += 1

        return cleanup

    fiber = Fiber(plugin)
    await fiber.start()
    await fiber.dispose()
    await fiber.dispose()

    assert fiber.state is FiberState.DISPOSED
    assert cleanups == 1
    with pytest.raises(FiberDisposedError):
        await fiber.restart()
    with pytest.raises(FiberDisposedError):
        await fiber.update("new")
