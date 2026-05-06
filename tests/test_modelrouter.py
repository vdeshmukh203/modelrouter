"""Tests for modelrouter."""
import logging

import pytest

from modelrouter import Modelrouter, Route


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------

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


def test_remove_route():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    assert r.remove_route("code") is True
    assert r.resolve("anything") == "mini"


def test_remove_nonexistent():
    r = Modelrouter()
    assert r.remove_route("nope") is False


# ---------------------------------------------------------------------------
# explain()
# ---------------------------------------------------------------------------

def test_explain_matched():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5,
                condition_label="keyword:code", tags=["prod"])
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"
    assert exp["priority"] == 5
    assert exp["cost_per_1k"] == 0.0
    assert exp["tags"] == ["prod"]
    assert exp["condition_label"] == "keyword:code"


def test_explain_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"
    assert exp["cost_per_1k"] == 0.001
    assert exp["tags"] == []
    assert exp["condition_label"] == ""


# ---------------------------------------------------------------------------
# resolve_with_cost()
# ---------------------------------------------------------------------------

def test_resolve_with_cost():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == 0.03


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("anything")
    assert model == "mini"
    assert cost == 0.001


# ---------------------------------------------------------------------------
# Tag filtering
# ---------------------------------------------------------------------------

def test_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 0


# ---------------------------------------------------------------------------
# Fault tolerance
# ---------------------------------------------------------------------------

def test_bad_condition_skipped():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


def test_bad_condition_logs_warning(caplog):
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    with caplog.at_level(logging.WARNING, logger="modelrouter.router"):
        r.resolve("test")
    assert any("bad" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_duplicate_name_raises():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    with pytest.raises(ValueError, match="already exists"):
        r.add_route("code", "gpt-4o-mini", lambda p: True)


def test_negative_cost_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="cost_per_1k"):
        r.add_route("x", "m", lambda p: True, cost_per_1k=-0.01)


def test_negative_default_cost_raises():
    with pytest.raises(ValueError, match="default_cost_per_1k"):
        Modelrouter(default_cost_per_1k=-1.0)


# ---------------------------------------------------------------------------
# update_route()
# ---------------------------------------------------------------------------

def test_update_route_model():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    r.update_route("code", model="claude-3-5-sonnet")
    assert r.resolve("x") == "claude-3-5-sonnet"


def test_update_route_priority_resorts():
    r = Modelrouter()
    r.add_route("a", "model-a", lambda p: True, priority=0)
    r.add_route("b", "model-b", lambda p: True, priority=5)
    assert r.resolve("x") == "model-b"
    r.update_route("a", priority=10)
    assert r.resolve("x") == "model-a"


def test_update_route_cost():
    r = Modelrouter()
    r.add_route("x", "m", lambda p: True, cost_per_1k=0.01)
    r.update_route("x", cost_per_1k=0.05)
    _, cost = r.resolve_with_cost("test")
    assert cost == 0.05


def test_update_route_negative_cost_raises():
    r = Modelrouter()
    r.add_route("x", "m", lambda p: True)
    with pytest.raises(ValueError, match="cost_per_1k"):
        r.update_route("x", cost_per_1k=-1.0)


def test_update_route_missing_raises():
    r = Modelrouter()
    with pytest.raises(KeyError):
        r.update_route("nonexistent", model="m")


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

def test_clear():
    r = Modelrouter(default="mini")
    r.add_route("a", "m", lambda p: True)
    r.add_route("b", "n", lambda p: True)
    r.clear()
    assert len(r) == 0
    assert r.resolve("x") == "mini"


# ---------------------------------------------------------------------------
# Dunder helpers
# ---------------------------------------------------------------------------

def test_len():
    r = Modelrouter()
    assert len(r) == 0
    r.add_route("a", "m", lambda p: True)
    assert len(r) == 1
    r.add_route("b", "n", lambda p: True)
    assert len(r) == 2
    r.remove_route("a")
    assert len(r) == 1


def test_contains():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    assert "code" in r
    assert "other" not in r


def test_repr_router():
    r = Modelrouter(default="mini")
    r.add_route("x", "m", lambda p: True)
    assert "mini" in repr(r)
    assert "routes=1" in repr(r)


def test_repr_route():
    route = Route("r1", "gpt-4o", lambda p: True, condition_label="kw:test")
    assert "r1" in repr(route)
    assert "gpt-4o" in repr(route)
    assert "kw:test" in repr(route)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_default_property():
    r = Modelrouter(default="my-model")
    assert r.default == "my-model"


def test_default_cost_property():
    r = Modelrouter(default_cost_per_1k=0.005)
    assert r.default_cost == 0.005


# ---------------------------------------------------------------------------
# routes() returns a copy (mutation safety)
# ---------------------------------------------------------------------------

def test_routes_returns_copy():
    r = Modelrouter()
    r.add_route("a", "m", lambda p: True)
    snapshot = r.routes()
    snapshot.clear()
    assert len(r) == 1
