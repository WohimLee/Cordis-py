from dataclasses import dataclass
from typing import cast

import pytest

from cordis import Context, CordisError, Service, inject
from cordis.fiber import FiberState


@pytest.mark.asyncio
async def test_accessor_and_mixin_are_owned_and_reversible() -> None:
    context = Context()
    state = {"value": 1}

    def set_value(receiver: Context, value: object) -> None:
        assert isinstance(value, int)
        state["value"] = value

    def plugin(plugin_context: Context, config: object) -> None:
        plugin_context.accessor(
            "computed",
            lambda receiver: state["value"],
            set_value,
        )

        @dataclass
        class Source:
            count: int = 2

        plugin_context.provide("source", Source())
        plugin_context.mixin("source", ["count"])

    fiber = context.plugin(plugin)
    await fiber.wait()
    assert context.computed == 1
    context.set("computed", 3)
    assert context.computed == 3
    assert context.count == 2
    context.set("count", 4)
    assert context.count == 4

    await fiber.dispose()
    with pytest.raises(CordisError):
        context.get("computed")
    with pytest.raises(CordisError):
        context.get("count")
    await context.aclose()


@pytest.mark.asyncio
async def test_service_write_requires_owner_fiber() -> None:
    context = Context()

    def provider(plugin_context: Context, config: object) -> None:
        plugin_context.provide("value", 1)
        plugin_context.set("value", 2)

    fiber = context.plugin(provider)
    await fiber.wait()
    assert context.value == 2
    with pytest.raises(PermissionError):
        context.set("value", 3)
    await context.aclose()


@pytest.mark.asyncio
async def test_inject_intercept_is_visible_to_service() -> None:
    context = Context()

    class Configurable(Service):
        provide = "configurable"

        def __init__(self, plugin_context: Context, config: object = None) -> None:
            super().__init__(plugin_context)

    provider = context.plugin(Configurable)
    await provider.wait()
    seen: list[dict[str, object]] = []

    @inject(configurable={"timeout": 3})
    def consumer(plugin_context: Context, config: object) -> None:
        service = cast(Configurable, plugin_context.configurable)
        seen.append(service.resolve_config({"timeout": 10}, {"retries": 2}))

    fiber = context.plugin(consumer)
    await fiber.wait()
    assert seen == [{"timeout": 3, "retries": 2}]
    await context.aclose()


@pytest.mark.asyncio
async def test_service_availability_refreshes_dependents() -> None:
    context = Context()

    class Switchable(Service):
        provide = "switchable"

        def __init__(self, plugin_context: Context, config: object = None) -> None:
            self.enabled = True
            super().__init__(plugin_context)

        def available(self) -> bool:
            return self.enabled

    provider = context.plugin(Switchable)
    await provider.wait()
    service = cast(Switchable, provider.context.reflect.get(provider.context, "switchable"))
    activations = 0

    @inject("switchable")
    def consumer(plugin_context: Context, config: object) -> None:
        nonlocal activations
        activations += 1

    fiber = context.plugin(consumer)
    await fiber.wait()
    assert fiber.state is FiberState.ACTIVE

    service.enabled = False
    await service.refresh()
    assert fiber.state is FiberState.PENDING

    service.enabled = True
    await service.refresh()
    assert fiber.state is FiberState.ACTIVE
    assert activations == 2
    await context.aclose()
