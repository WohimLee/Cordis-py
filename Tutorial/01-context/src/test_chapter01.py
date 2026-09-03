"""Behavior checkpoints for tutorial chapter 01."""

import pytest
from chapter01 import Context


def test_root_context_points_to_itself() -> None:
    context = Context()
    assert context.root is context


def test_context_identity() -> None:
    context = Context()
    assert Context.is_context(context)
    assert not Context.is_context({})


def test_extend_inherits_and_overrides_metadata() -> None:
    root = Context()
    app = root.extend({"baseUrl": "file:///app/", "mode": "dev"})
    plugin = app.extend({"mode": "test", "name": "demo"})

    assert plugin.root is root
    assert plugin.baseUrl == "file:///app/"
    assert plugin.mode == "test"
    assert plugin.name == "demo"
    assert app.mode == "dev"
    with pytest.raises(AttributeError, match="name"):
        _ = app.name


def test_extend_without_metadata_still_creates_child() -> None:
    root = Context()
    child = root.extend()
    assert child is not root
    assert child.root is root


def test_plugin_receives_the_calling_context() -> None:
    root = Context()
    child = root.extend({"name": "child"})
    seen: list[Context] = []

    child.plugin(lambda context: seen.append(context))
    assert seen == [child]


def test_derived_contexts_share_runtime_services() -> None:
    root = Context()
    provider_context = root.extend({"name": "provider"})
    consumer_context = root.extend({"name": "consumer"})
    seen: list[str] = []

    provider_context.plugin(lambda context: context.services.__setitem__("message", "hello"))
    consumer_context.plugin(lambda context: seen.append(str(context.services["message"])))

    assert seen == ["hello"]
    assert provider_context.services is consumer_context.services


def test_only_root_can_close_the_shared_runtime() -> None:
    root = Context()
    child = root.extend()
    trace: list[str] = []
    child.plugin(lambda _context: lambda: trace.append("cleanup"))

    with pytest.raises(RuntimeError, match="only the root"):
        child.close()
    assert trace == []

    root.close()
    assert trace == ["cleanup"]
