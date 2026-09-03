"""Behavior checkpoints for tutorial chapter 03."""

import asyncio

import pytest
from chapter03 import Context, Fiber, FiberState


@pytest.mark.asyncio
async def test_plugin_activation_returns_awaitable_fiber() -> None:
    root = Context()
    seen: list[Context] = []
    fiber = root.plugin(lambda context: seen.append(context))

    assert await fiber is fiber
    assert seen == [fiber.ctx]
    assert fiber.ctx is not root
    assert fiber.ctx.root is root
    assert fiber.state is FiberState.ACTIVE
    await root.aclose()


@pytest.mark.asyncio
async def test_plugin_returned_cleanup_belongs_to_fiber() -> None:
    root = Context()
    trace: list[str] = []
    fiber = root.plugin(
        lambda _context: (trace.append("activate"), lambda: trace.append("cleanup"))[1]
    )

    await fiber
    await fiber.dispose()
    assert trace == ["activate", "cleanup"]
    assert fiber.state is FiberState.DISPOSED
    await root.aclose()


@pytest.mark.asyncio
async def test_context_effect_is_owned_by_current_fiber() -> None:
    root = Context()
    trace: list[str] = []

    def plugin(context: Context) -> None:
        context.effect(lambda: lambda: trace.append("first"))
        context.effect(lambda: lambda: trace.append("second"))

    fiber = root.plugin(plugin)
    await fiber
    await fiber.dispose()
    assert trace == ["second", "first"]
    await root.aclose()


@pytest.mark.asyncio
async def test_fiber_dispose_is_idempotent() -> None:
    root = Context()
    trace: list[str] = []
    fiber = root.plugin(lambda _context: lambda: trace.append("cleanup"))
    await fiber

    first = fiber.dispose()
    second = fiber.dispose()
    assert first is second
    await first
    assert trace == ["cleanup"]
    await root.aclose()


@pytest.mark.asyncio
async def test_parent_disposal_cascades_to_child_fiber() -> None:
    root = Context()
    trace: list[str] = []
    children: list[Fiber] = []

    def parent(context: Context):  # type: ignore[no-untyped-def]
        trace.append("parent activate")
        child = context.plugin(
            lambda _context: (
                trace.append("child activate"),
                lambda: trace.append("child cleanup"),
            )[1]
        )
        children.append(child)
        return lambda: trace.append("parent cleanup")

    parent_fiber = root.plugin(parent)
    await parent_fiber
    await children[0]
    await parent_fiber.dispose()

    assert trace == [
        "parent activate",
        "child activate",
        "child cleanup",
        "parent cleanup",
    ]
    assert children[0].state is FiberState.DISPOSED
    await root.aclose()


@pytest.mark.asyncio
async def test_root_close_disposes_the_fiber_tree() -> None:
    root = Context()
    trace: list[str] = []
    fiber = root.plugin(lambda _context: lambda: trace.append("cleanup"))
    await fiber

    await root.aclose()
    assert trace == ["cleanup"]
    assert fiber.state is FiberState.DISPOSED
    assert root.fiber.state is FiberState.DISPOSED


@pytest.mark.asyncio
async def test_dispose_during_loading_waits_for_setup() -> None:
    root = Context()
    started = asyncio.Event()
    ready = asyncio.Event()
    trace: list[str] = []

    async def plugin(_context: Context):  # type: ignore[no-untyped-def]
        trace.append("setup-start")
        started.set()
        await ready.wait()
        trace.append("setup-end")
        return lambda: trace.append("cleanup")

    fiber = root.plugin(plugin)
    await started.wait()
    disposing = fiber.dispose()
    assert not disposing.done()

    ready.set()
    await disposing
    assert trace == ["setup-start", "setup-end", "cleanup"]
    assert fiber.state is FiberState.DISPOSED
    await root.aclose()
