"""Executable problem statements for tutorial chapter 00."""

import pytest
from chapter00 import NaiveRuntime


def test_direct_calls_work_only_in_the_right_order() -> None:
    services: dict[str, object] = {}

    def provider(scope: dict[str, object]) -> None:
        scope["message"] = "hello"

    def consumer(scope: dict[str, object]) -> None:
        assert scope["message"] == "hello"

    provider(services)
    consumer(services)


def test_provider_before_consumer_works() -> None:
    runtime = NaiveRuntime()
    seen: list[str] = []
    runtime.mount(lambda scope: scope.__setitem__("message", "hello"))
    runtime.mount(lambda scope: seen.append(str(scope["message"])))
    assert seen == ["hello"]


def test_consumer_before_provider_fails_and_is_not_retried() -> None:
    runtime = NaiveRuntime()
    seen: list[str] = []

    def consumer(scope: dict[str, object]) -> None:
        seen.append(str(scope["message"]))

    with pytest.raises(KeyError, match="message"):
        runtime.mount(consumer)
    runtime.mount(lambda scope: scope.__setitem__("message", "hello"))
    assert seen == []


def test_returned_cleanup_runs_during_final_close() -> None:
    runtime = NaiveRuntime()

    def provider(scope: dict[str, object]) -> object:
        scope["message"] = "hello"
        return lambda: scope.pop("message", None)

    runtime.mount(provider)
    runtime.close()
    assert "message" not in runtime.services
    assert runtime.cleanups == []


def test_naive_runtime_cannot_unmount_one_plugin() -> None:
    runtime = NaiveRuntime()
    assert not hasattr(runtime, "unmount")


def test_service_replacement_does_not_restart_consumer() -> None:
    runtime = NaiveRuntime()
    trace: list[str] = []
    runtime.services["message"] = "v1"

    def consumer(scope: dict[str, object]) -> object:
        value = str(scope["message"])
        trace.append(f"activate:{value}")
        return lambda: trace.append(f"cleanup:{value}")

    runtime.mount(consumer)
    runtime.services["message"] = "v2"
    assert trace == ["activate:v1"]
    runtime.close()
    assert trace == ["activate:v1", "cleanup:v1"]
