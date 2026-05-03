"""Tests for modelrouter."""
import pytest
from modelrouter import Modelrouter, Route


# ------------------------------------------------------------------
# Basic resolution
# ------------------------------------------------------------------

def test_default():
    r = Modelrouter(default="gpt-4o-mini")
    assert r.resolve("hello") == "gpt-4o-mini"


def test_route_match():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    assert r.resolve("write code") == "gpt-4o"


def test_route_no_match():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    assert r.resolve("hello world") == "mini"


def test_priority():
    r = Modelrouter()
    r.add_route("low", "model-low", lambda p: True, priority=0)
    r.add_route("high", "model-high", lambda p: True, priority=10)
    assert r.resolve("test") == "model-high"


# ------------------------------------------------------------------
# Route management
# ------------------------------------------------------------------

def test_remove_route():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    assert r.remove_route("code") is True
    assert r.resolve("anything") == "mini"


def test_remove_nonexistent():
    r = Modelrouter()
    assert r.remove_route("nope") is False


def test_duplicate_name_raises():
    r = Modelrouter()
    r.add_route("dup", "m1", lambda p: True)
    with pytest.raises(ValueError, match="already exists"):
        r.add_route("dup", "m2", lambda p: True)


def test_noncallable_condition_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="callable"):
        r.add_route("bad", "m1", "not a callable")  # type: ignore[arg-type]


def test_negative_cost_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="non-negative"):
        r.add_route("cheap", "m1", lambda p: True, cost_per_1k=-1.0)


def test_update_route_model_and_priority():
    r = Modelrouter()
    r.add_route("x", "m1", lambda p: True, priority=0)
    r.update_route("x", model="m2", priority=5)
    route = r.routes()[0]
    assert route.model == "m2"
    assert route.priority == 5


def test_update_route_condition():
    r = Modelrouter()
    r.add_route("x", "m1", lambda p: False)
    assert r.resolve("hello") == r.default
    r.update_route("x", condition=lambda p: True)
    assert r.resolve("hello") == "m1"


def test_update_nonexistent_raises():
    r = Modelrouter()
    with pytest.raises(KeyError):
        r.update_route("ghost", model="m1")


def test_update_negative_cost_raises():
    r = Modelrouter()
    r.add_route("x", "m1", lambda p: True)
    with pytest.raises(ValueError, match="non-negative"):
        r.update_route("x", cost_per_1k=-5.0)


def test_clear():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True)
    r.add_route("b", "m2", lambda p: True, priority=1)
    r.clear()
    assert len(r) == 0
    assert r.resolve("test") == r.default


# ------------------------------------------------------------------
# Explanation
# ------------------------------------------------------------------

def test_explain_matched():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5)
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"
    assert exp["priority"] == 5
    assert "cost_per_1k" in exp
    assert "tags" in exp


def test_explain_default():
    r = Modelrouter(default="mini")
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"
    assert exp["priority"] == -1
    assert "cost_per_1k" in exp
    assert exp["tags"] == []


def test_explain_includes_tags():
    r = Modelrouter()
    r.add_route("t", "m1", lambda p: True, tags=["prod", "v2"])
    exp = r.explain("anything")
    assert exp["tags"] == ["prod", "v2"]


# ------------------------------------------------------------------
# Cost resolution
# ------------------------------------------------------------------

def test_resolve_with_cost_matched():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == 0.03


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("no match")
    assert model == "mini"
    assert cost == 0.001


# ------------------------------------------------------------------
# Tags
# ------------------------------------------------------------------

def test_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 0


def test_routes_by_tag_multiple():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod", "fast"])
    r.add_route("r2", "m2", lambda p: True, tags=["dev"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("fast")) == 1
    assert len(r.routes_by_tag("dev")) == 1


# ------------------------------------------------------------------
# Error tolerance
# ------------------------------------------------------------------

def test_bad_condition_skipped():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


def test_bad_condition_does_not_block_subsequent_routes():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0, priority=10)
    r.add_route("good", "claude-3", lambda p: True, priority=5)
    assert r.resolve("test") == "claude-3"


# ------------------------------------------------------------------
# Python data model
# ------------------------------------------------------------------

def test_len():
    r = Modelrouter()
    assert len(r) == 0
    r.add_route("a", "m1", lambda p: True)
    assert len(r) == 1
    r.add_route("b", "m2", lambda p: True)
    assert len(r) == 2


def test_contains():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True)
    assert "a" in r
    assert "b" not in r


def test_repr_router():
    r = Modelrouter(default="mini")
    text = repr(r)
    assert "Modelrouter" in text
    assert "mini" in text


def test_repr_route():
    route = Route("r", "m", lambda p: True, priority=3, cost_per_1k=0.01, tags=["x"])
    text = repr(route)
    assert "Route" in text
    assert "'r'" in text
    assert "'m'" in text
    assert "priority=3" in text
