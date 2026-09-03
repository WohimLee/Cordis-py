"""Behavior checkpoints for tutorial chapter 04."""

import pytest
from chapter04 import Callback, Context, FiberState, PluginRuntime


@pytest.mark.asyncio
async def test_function_class_and_object_plugin_shapes() -> None:
    root = Context()
    trace: list[str] = []

    def function_plugin(_context: Context, config: object) -> None:
        trace.append(f"function:{config}")

    class ClassPlugin:
        def __init__(self, _context: Context, config: object) -> None:
            trace.append(f"class:{config}")

    class ObjectPlugin:
        name = "object-plugin"

        def apply(self, _context: Context, config: object) -> None:
            trace.append(f"object:{config}")

    fibers = [
        root.plugin(function_plugin, "A"),
        root.plugin(ClassPlugin, "B"),
        root.plugin(ObjectPlugin(), "C"),
    ]
    for fiber in fibers:
        await fiber

    assert trace == ["function:A", "class:B", "object:C"]
    assert [fiber.state for fiber in fibers] == [FiberState.ACTIVE] * 3
    await root.aclose()


@pytest.mark.asyncio
async def test_same_plugin_shares_runtime_but_not_fiber() -> None:
    root = Context()

    def plugin(_context: Context, _config: object) -> None:
        return None

    first = root.plugin(plugin, "A")
    second = root.plugin(plugin, "B")
    await first
    await second
    runtime = root.registry.get(plugin)

    assert runtime is not None
    assert first is not second
    assert first.runtime is runtime
    assert second.runtime is runtime
    assert runtime.fibers == {first, second}
    assert first.config == "A"
    assert second.config == "B"
    await root.aclose()


def test_resolve_preserves_plugin_identity() -> None:
    root = Context()

    def plugin(_context: Context) -> None:
        return None

    def first_copy(_context: Context) -> None:
        return None

    def second_copy(_context: Context) -> None:
        return None

    assert root.registry.resolve(plugin) is root.registry.resolve(plugin)
    assert root.registry.resolve(first_copy) is not root.registry.resolve(second_copy)


@pytest.mark.asyncio
async def test_registry_inspection_is_read_only() -> None:
    root = Context()
    calls = 0

    def plugin(_context: Context) -> None:
        nonlocal calls
        calls += 1

    fiber = root.plugin(plugin)
    await fiber
    visited: list[tuple[Callback, PluginRuntime]] = []
    root.registry.forEach(lambda runtime, callback: visited.append((callback, runtime)))

    runtime = root.registry.get(plugin)
    assert runtime is not None
    assert root.registry.has(plugin)
    assert root.registry.size == 1
    assert list(root.registry.keys()) == [runtime.callback]
    assert list(root.registry.values()) == [runtime]
    assert list(root.registry.entries()) == [(runtime.callback, runtime)]
    assert visited == [(runtime.callback, runtime)]
    assert calls == 1
    await root.aclose()


@pytest.mark.asyncio
async def test_delete_disposes_every_fiber_for_plugin() -> None:
    root = Context()
    trace: list[str] = []

    def plugin(_context: Context, config: object):  # type: ignore[no-untyped-def]
        return lambda: trace.append(f"cleanup:{config}")

    first = root.plugin(plugin, "A")
    second = root.plugin(plugin, "B")
    await first
    await second

    runtime = root.registry.delete(plugin)
    assert runtime is not None
    assert not root.registry.has(plugin)
    assert root.registry.size == 0
    await first.dispose()
    await second.dispose()

    assert sorted(trace) == ["cleanup:A", "cleanup:B"]
    assert runtime.fibers == set()
    await root.aclose()


@pytest.mark.asyncio
async def test_root_close_clears_registry() -> None:
    root = Context()

    def plugin(_context: Context) -> None:
        return None

    fiber = root.plugin(plugin)
    await fiber
    assert root.registry.size == 1

    await root.aclose()
    assert root.registry.size == 0
    assert fiber.state is FiberState.DISPOSED


def test_invalid_plugin_is_rejected() -> None:
    root = Context()
    with pytest.raises(TypeError, match="invalid plugin"):
        root.plugin(object())
