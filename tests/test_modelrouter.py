"""Tests for modelrouter."""

import pytest

from modelrouter import Modelrouter, RouteError

# ---------------------------------------------------------------------------
# Basic resolution
# ---------------------------------------------------------------------------


def test_default_model():
    r = Modelrouter(default="gpt-4o-mini")
    assert r.resolve("hello") == "gpt-4o-mini"


def test_route_match():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    assert r.resolve("write code") == "gpt-4o"


def test_route_no_match_falls_back_to_default():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    assert r.resolve("hello world") == "mini"


def test_priority_order():
    r = Modelrouter()
    r.add_route("low", "model-low", lambda p: True, priority=0)
    r.add_route("high", "model-high", lambda p: True, priority=10)
    assert r.resolve("test") == "model-high"


def test_priority_ties_respect_insertion_order():
    r = Modelrouter()
    r.add_route("first", "model-first", lambda p: True, priority=5)
    r.add_route("second", "model-second", lambda p: True, priority=5)
    assert r.resolve("test") == "model-first"


# ---------------------------------------------------------------------------
# Route management
# ---------------------------------------------------------------------------


def test_remove_route():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    assert r.remove_route("code") is True
    assert r.resolve("anything") == "mini"


def test_remove_nonexistent_route_returns_false():
    r = Modelrouter()
    assert r.remove_route("nope") is False


def test_clear_routes():
    r = Modelrouter(default="mini")
    r.add_route("r1", "m1", lambda p: True)
    r.add_route("r2", "m2", lambda p: True)
    r.clear_routes()
    assert r.route_count == 0
    assert r.resolve("any") == "mini"


def test_route_count():
    r = Modelrouter()
    assert r.route_count == 0
    r.add_route("a", "m1", lambda p: True)
    r.add_route("b", "m2", lambda p: True)
    assert r.route_count == 2
    r.remove_route("a")
    assert r.route_count == 1


def test_get_route_found():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True, priority=5, tags=["prod"])
    route = r.get_route("code")
    assert route is not None
    assert route.model == "gpt-4o"
    assert route.priority == 5


def test_get_route_not_found_returns_none():
    r = Modelrouter()
    assert r.get_route("missing") is None


def test_duplicate_route_name_raises():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    with pytest.raises(RouteError):
        r.add_route("code", "gpt-4-turbo", lambda p: True)


def test_update_route_model():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    r.update_route("code", model="gpt-4-turbo")
    assert r.get_route("code").model == "gpt-4-turbo"


def test_update_route_priority_reorders():
    r = Modelrouter()
    r.add_route("low", "m-low", lambda p: True, priority=0)
    r.add_route("high", "m-high", lambda p: True, priority=10)
    assert r.routes()[0].name == "high"
    r.update_route("low", priority=20)
    assert r.routes()[0].name == "low"


def test_update_nonexistent_route_raises():
    r = Modelrouter()
    with pytest.raises(RouteError):
        r.update_route("ghost", model="x")


def test_update_route_invalid_condition_type():
    r = Modelrouter()
    r.add_route("r", "m", lambda p: True)
    with pytest.raises(TypeError):
        r.update_route("r", condition="not a callable")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------


def test_explain_matched_route():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5, tags=["prod"])
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"
    assert exp["priority"] == 5
    assert "prod" in exp["tags"]
    assert "cost_per_1k" in exp


def test_explain_default_fallback():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"
    assert exp["priority"] == -1
    assert exp["cost_per_1k"] == 0.001
    assert exp["tags"] == []


# ---------------------------------------------------------------------------
# Cost resolution
# ---------------------------------------------------------------------------


def test_resolve_with_cost_matched():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == pytest.approx(0.03)


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("nothing matches")
    assert model == "mini"
    assert cost == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# Tag filtering
# ---------------------------------------------------------------------------


def test_routes_by_tag():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    r.add_route("r2", "m2", lambda p: True, tags=["dev"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 1
    assert len(r.routes_by_tag("staging")) == 0


def test_routes_by_tag_multiple_matches():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod", "fast"])
    r.add_route("r2", "m2", lambda p: True, tags=["prod", "slow"])
    r.add_route("r3", "m3", lambda p: True, tags=["dev"])
    assert len(r.routes_by_tag("prod")) == 2


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_statistics_increments_on_match():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    r.resolve("a")
    r.resolve("b")
    r.resolve("c")
    assert r.statistics()["code"] == 3


def test_statistics_reset_on_clear():
    r = Modelrouter()
    r.add_route("r", "m", lambda p: True)
    r.resolve("x")
    r.clear_routes()
    assert r.statistics() == {}


def test_statistics_not_incremented_for_default():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    r.resolve("no match here")
    assert r.statistics()["code"] == 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_route_name_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("", "gpt-4o", lambda p: True)


def test_empty_model_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("r", "", lambda p: True)


def test_non_callable_condition_raises():
    r = Modelrouter()
    with pytest.raises(TypeError):
        r.add_route("r", "m", "not callable")  # type: ignore[arg-type]


def test_negative_priority_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("r", "m", lambda p: True, priority=-1)


def test_negative_cost_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("r", "m", lambda p: True, cost_per_1k=-0.01)


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


def test_bad_condition_skipped_falls_back_to_default():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


def test_bad_condition_skipped_next_route_evaluated():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0, priority=10)
    r.add_route("good", "claude-3", lambda p: True, priority=5)
    assert r.resolve("test") == "claude-3"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_prompt():
    r = Modelrouter(default="mini")
    r.add_route("len", "big", lambda p: len(p) > 0)
    assert r.resolve("") == "mini"


def test_unicode_prompt():
    r = Modelrouter()
    r.add_route("emoji", "emoji-model", lambda p: "🤖" in p)
    assert r.resolve("Hello 🤖") == "emoji-model"


def test_very_long_prompt():
    r = Modelrouter()
    r.add_route("long", "big-model", lambda p: len(p) > 1000)
    long_prompt = "x" * 2000
    assert r.resolve(long_prompt) == "big-model"


def test_default_property():
    r = Modelrouter(default="my-model")
    assert r.default == "my-model"


def test_routes_returns_copy():
    r = Modelrouter()
    r.add_route("r", "m", lambda p: True)
    snapshot = r.routes()
    r.clear_routes()
    assert len(snapshot) == 1
    assert r.route_count == 0
