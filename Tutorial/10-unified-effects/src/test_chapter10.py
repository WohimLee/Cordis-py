from __future__ import annotations

import asyncio

import pytest
from chapter10 import EffectScope, InactiveEffectError, ResourceContext


@pytest.mark.asyncio
async def test_cleanups_run_in_reverse_order() -> None:
    trace: list[str] = []
    scope = EffectScope()
    await scope.install(lambda: [lambda: trace.append("first"), lambda: trace.append("second")])

    await scope.close()

    assert trace == ["second", "first"]


@pytest.mark.asyncio
async def test_effect_and_scope_disposal_are_idempotent() -> None:
    cleanups = 0

    def setup():  # type: ignore[no-untyped-def]
        def cleanup() -> None:
            nonlocal cleanups
            cleanups += 1

        return cleanup

    scope = EffectScope()
    effect = await scope.install(setup)
    await asyncio.gather(effect.dispose(), effect.dispose())
    await asyncio.gather(scope.close(), scope.close())

    assert cleanups == 1


@pytest.mark.asyncio
async def test_async_and_iterable_results_share_collection() -> None:
    trace: list[str] = []

    async def setup():  # type: ignore[no-untyped-def]
        return (lambda: trace.append("a"), lambda: trace.append("b"))

    scope = EffectScope()
    await scope.install(setup)
    await scope.close()

    assert trace == ["b", "a"]


@pytest.mark.asyncio
async def test_partial_setup_failure_rolls_back_collected_cleanup() -> None:
    trace: list[str] = []

    def setup():  # type: ignore[no-untyped-def]
        yield lambda: trace.append("rollback")
        raise ValueError("setup failed")

    scope = EffectScope()
    with pytest.raises(ValueError, match="setup failed"):
        await scope.install(setup)

    assert trace == ["rollback"]


@pytest.mark.asyncio
async def test_cleanup_failures_do_not_stop_remaining_cleanup() -> None:
    trace: list[str] = []

    def broken() -> None:
        trace.append("broken")
        raise ValueError("cleanup failed")

    scope = EffectScope()
    await scope.install(lambda: [lambda: trace.append("last"), broken])

    with pytest.raises(BaseExceptionGroup) as caught:
        await scope.close()

    assert trace == ["broken", "last"]
    assert isinstance(caught.value.exceptions[0], BaseExceptionGroup)


@pytest.mark.asyncio
async def test_nested_effect_builds_metadata_tree() -> None:
    scope = EffectScope()

    async def parent_setup() -> None:
        await scope.install(lambda: None, "child")

    await scope.install(parent_setup, "parent")

    assert scope.effects[0].label == "parent"
    assert [child.label for child in scope.effects[0].children] == ["child"]
    await scope.close()


@pytest.mark.asyncio
async def test_framework_resources_use_the_same_scope() -> None:
    context = ResourceContext()
    child_disposed = False
    task_started = asyncio.Event()
    task_stopped = asyncio.Event()

    class Child:
        async def dispose(self) -> None:
            nonlocal child_disposed
            child_disposed = True

    async def worker() -> None:
        task_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            task_stopped.set()

    await context.provide("database", object())

    def listener() -> None:
        pass

    await context.on("message", listener)
    await context.child(Child())
    await context.task(worker())
    await task_started.wait()

    await context.close()

    assert context.services == {}
    assert context.listeners["message"] == []
    assert child_disposed
    assert task_stopped.is_set()


@pytest.mark.asyncio
async def test_closed_scope_rejects_new_effects() -> None:
    scope = EffectScope()
    await scope.close()

    with pytest.raises(InactiveEffectError):
        await scope.install(lambda: None)
