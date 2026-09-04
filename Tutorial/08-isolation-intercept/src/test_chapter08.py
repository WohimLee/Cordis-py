from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest
from chapter08 import Context, Service


def test_fresh_label_separates_same_named_services() -> None:
    root = Context()
    private = root.isolate("database")

    root.provide("database", "root database")
    private.provide("database", "private database")

    assert root.get("database") == "root database"
    assert private.get("database") == "private database"


def test_extend_inherits_isolation_label() -> None:
    private = Context().isolate("database")
    child = private.extend()
    private.provide("database", "private database")

    assert child.get("database") == "private database"


def test_explicit_label_joins_separate_contexts() -> None:
    root = Context()
    shared_label = object()
    app_a = root.isolate("database", shared_label)
    app_b = root.isolate("database", shared_label)
    app_a.provide("database", "shared database")

    assert app_b.get("database") == "shared database"
    assert root.get("database") is None


def test_intercept_derives_without_mutating_parent() -> None:
    root = Context()
    outer = root.intercept("database", {"scope": "outer"})
    inner = outer.intercept("database", {"scope": "inner"})

    assert root.intercepts_for("database") == ()
    assert outer.intercepts_for("database") == ({"scope": "outer"},)
    assert inner.intercepts_for("database") == (
        {"scope": "outer"},
        {"scope": "inner"},
    )


def test_default_merge_orders_base_intercepts_and_inject_head() -> None:
    service = Service("database")
    context = (
        Context()
        .intercept("database", {"outer": 2, "shared": "outer"})
        .intercept("database", {"middle": 3, "shared": "middle"})
    )

    result = service.resolve_config(
        context,
        base={"base": 1, "shared": "base"},
        head={"head": 4, "shared": "inject"},
    )

    assert result == {
        "base": 1,
        "outer": 2,
        "middle": 3,
        "head": 4,
        "shared": "inject",
    }


def test_service_can_customize_config_merge() -> None:
    class TaggedService(Service):
        class Config:
            @staticmethod
            def merge(*configs: dict[str, object]) -> dict[str, object]:
                groups = (cast(Sequence[object], config.get("tags", [])) for config in configs)
                tags = [tag for group in groups for tag in group]
                return {"tags": tags}

    service = TaggedService("search")
    context = Context().intercept("search", {"tags": ["context"]})

    assert service.resolve_config(
        context,
        base={"tags": ["base"]},
        head={"tags": ["inject"]},
    ) == {"tags": ["base", "context", "inject"]}


@pytest.mark.parametrize("invalid", [42, ["not", "a", "mapping"], {1: "bad key"}])
def test_service_config_must_be_a_string_keyed_mapping(invalid: object) -> None:
    service = Service("database")

    with pytest.raises(TypeError):
        service.resolve_config(Context(), head=invalid)
