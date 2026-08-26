import asyncio
from collections.abc import Awaitable, Callable

import pytest

from cordis.context import Context


@pytest.mark.asyncio
async def test_event_dispatch_modes() -> None:
    context = Context()
    emitted: list[str] = []

    def receive(value: str) -> None:
        emitted.append(value)

    context.on("emit", receive)
    context.emit("emit", "seen")
    assert emitted == ["seen"]

    context.on("decision", lambda: False)
    context.on("decision", lambda: 0)
    context.on("decision", lambda: "late")
    assert context.bail("decision") == 0

    serial_order: list[int] = []

    async def first() -> None:
        await asyncio.sleep(0)
        serial_order.append(1)

    async def second() -> str:
        serial_order.append(2)
        return "done"

    context.on("serial", first)
    context.on("serial", second)
    assert await context.serial("serial") == "done"
    assert serial_order == [1, 2]


@pytest.mark.asyncio
async def test_parallel_aggregates_errors_after_all_listeners_finish() -> None:
    context = Context()
    completed: list[bool] = []

    async def fail() -> None:
        raise ValueError("failed")

    async def finish() -> None:
        await asyncio.sleep(0)
        completed.append(True)

    context.on("parallel", fail)
    context.on("parallel", finish)

    with pytest.raises(BaseExceptionGroup) as caught:
        await context.parallel("parallel")

    assert completed == [True]
    assert len(caught.value.exceptions) == 1


@pytest.mark.asyncio
async def test_waterfall_wraps_and_can_short_circuit() -> None:
    context = Context()

    async def outer(value: str, next_: Callable[[], Awaitable[object]]) -> str:
        result = await next_()
        return f"outer({result})"

    async def inner(value: str, next_: Callable[[], Awaitable[object]]) -> str:
        result = await next_()
        return f"inner({result})"

    context.on("flow", outer)
    context.on("flow", inner)
    result = await context.waterfall("flow", "value", next_=lambda: "default")
    assert result == "outer(inner(default))"

    def short(value: str, next_: Callable[[], Awaitable[object]]) -> str:
        return "cached"

    context.on("short", short)
    reached_default = False

    def default() -> str:
        nonlocal reached_default
        reached_default = True
        return "default"

    assert await context.waterfall("short", "value", next_=default) == "cached"
    assert reached_default is False


@pytest.mark.asyncio
async def test_listener_is_removed_when_plugin_unloads() -> None:
    context = Context()
    seen: list[str] = []

    def plugin(plugin_context: Context, config: object) -> None:
        plugin_context.on("owned", lambda: seen.append("called"))

    fiber = context.plugin(plugin)
    await fiber.wait()
    context.emit("owned")
    await fiber.dispose()
    context.emit("owned")

    assert seen == ["called"]
    await context.aclose()


@pytest.mark.asyncio
async def test_once_listener_runs_only_once_for_immediate_emits() -> None:
    context = Context()
    seen: list[bool] = []
    context.once("once", lambda: seen.append(True))

    context.emit("once")
    context.emit("once")
    await asyncio.sleep(0)

    assert seen == [True]
    await context.aclose()
