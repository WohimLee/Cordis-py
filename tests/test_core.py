import json
from pathlib import Path
from typing import cast

import pytest

from cordis.context import Context
from cordis.errors import CordisError, CordisErrorCode
from cordis.fiber import FiberState
from cordis.model import inject
from cordis.service import Service


class ValueService(Service):
    provide = "value"

    def __init__(self, context: Context, config: object = None) -> None:
        self.value = config
        super().__init__(context)


@pytest.mark.asyncio
async def test_consumer_waits_for_provider_and_reloads_after_replacement() -> None:
    context = Context()
    trace: list[dict[str, object]] = []
    consumer_fiber = None

    @inject("value")
    def consumer(plugin_context: Context, config: object) -> object:
        value = cast(ValueService, plugin_context.value)
        assert consumer_fiber is not None
        trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})
        trace.append(
            {
                "plugin": "consumer",
                "event": "activate",
                "service_owner": value.value,
            }
        )

        def cleanup() -> None:
            fiber = consumer_fiber
            assert fiber is not None
            trace.append({"plugin": "consumer", "state": fiber.state.value})
            trace.append(
                {
                    "plugin": "consumer",
                    "event": "dispose-effect",
                    "effect": "consumer-resource",
                }
            )

        return cleanup

    consumer_fiber = context.plugin(consumer)
    await consumer_fiber.wait()
    assert consumer_fiber.state is FiberState.PENDING
    trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})

    provider_a = context.plugin(ValueService, "provider-a")
    await provider_a.wait()
    await consumer_fiber.wait()
    assert consumer_fiber.state is FiberState.ACTIVE
    trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})

    await provider_a.dispose()
    await consumer_fiber.wait()
    assert consumer_fiber.state is FiberState.PENDING
    trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})

    provider_b = context.plugin(ValueService, "provider-b")
    await provider_b.wait()
    await consumer_fiber.wait()
    assert consumer_fiber.state is FiberState.ACTIVE
    trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})

    await context.aclose()
    assert consumer_fiber.state is FiberState.DISPOSED
    trace.append({"plugin": "consumer", "state": consumer_fiber.state.value})

    scenario_path = Path(__file__).parent / "compat/scenarios/001-provider-replacement.json"
    scenario = cast(dict[str, object], json.loads(scenario_path.read_text()))
    assert trace == cast(list[dict[str, object]], scenario["expected"])


@pytest.mark.asyncio
async def test_isolated_services_do_not_conflict() -> None:
    context = Context()
    isolated = context.isolate("value")

    root_provider = context.plugin(ValueService, "root")
    isolated_provider = isolated.plugin(ValueService, "isolated")
    await root_provider.wait()
    await isolated_provider.wait()

    root_value = cast(ValueService, context.value)
    isolated_value = cast(ValueService, isolated.value)
    assert root_value.value == "root"
    assert isolated_value.value == "isolated"
    await context.aclose()


@pytest.mark.asyncio
async def test_duplicate_provider_fails_without_replacing_original() -> None:
    context = Context()
    original = context.plugin(ValueService, "original")
    duplicate = context.plugin(ValueService, "duplicate")
    await original.wait()

    with pytest.raises(CordisError) as caught:
        await duplicate.wait()

    assert caught.value.code is CordisErrorCode.DUPLICATE_SERVICE
    assert cast(ValueService, context.value).value == "original"
    await context.aclose()
