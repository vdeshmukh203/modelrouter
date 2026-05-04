"""Tests for modelrouter."""
import pytest
from modelrouter import Modelrouter, Route


# ---------------------------------------------------------------------------
# Basic resolution
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


# ---------------------------------------------------------------------------
# Route management
# ---------------------------------------------------------------------------

def test_remove_route():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    assert r.remove_route("code") is True
    assert r.resolve("anything") == "mini"


def test_remove_nonexistent():
    r = Modelrouter()
    assert r.remove_route("nope") is False


def test_add_route_replaces_existing():
    r = Modelrouter(default="mini")
    r.add_route("x", "model-a", lambda p: True)
    r.add_route("x", "model-b", lambda p: True)
    assert r.resolve("hi") == "model-b"
    assert len(r) == 1


def test_update_route_model():
    r = Modelrouter()
    r.add_route("x", "old-model", lambda p: True)
    assert r.update_route("x", model="new-model") is True
    assert r.resolve("hi") == "new-model"


def test_update_route_priority_reorders():
    r = Modelrouter()
    r.add_route("a", "model-a", lambda p: True, priority=5)
    r.add_route("b", "model-b", lambda p: True, priority=1)
    assert r.resolve("hi") == "model-a"
    r.update_route("b", priority=10)
    assert r.resolve("hi") == "model-b"


def test_update_route_nonexistent():
    r = Modelrouter()
    assert r.update_route("nope", model="x") is False


def test_clear():
    r = Modelrouter(default="mini")
    r.add_route("a", "m", lambda p: True)
    r.add_route("b", "m", lambda p: True)
    r.clear()
    assert len(r) == 0
    assert r.resolve("hi") == "mini"


# ---------------------------------------------------------------------------
# explain()
# ---------------------------------------------------------------------------

def test_explain_matched():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5,
                cost_per_1k=0.01, tags=["prod"])
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"
    assert exp["priority"] == 5
    assert exp["cost_per_1k"] == 0.01
    assert exp["tags"] == ["prod"]


def test_explain_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.002)
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"
    assert exp["priority"] is None
    assert exp["cost_per_1k"] == 0.002
    assert exp["tags"] == []


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
    model, cost = r.resolve_with_cost("hello")
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


def test_routes_by_tag_multiple():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True, tags=["prod", "fast"])
    r.add_route("b", "m2", lambda p: True, tags=["prod"])
    r.add_route("c", "m3", lambda p: True, tags=["dev"])
    assert len(r.routes_by_tag("prod")) == 2
    assert len(r.routes_by_tag("fast")) == 1
    assert len(r.routes_by_tag("staging")) == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_bad_condition_skipped():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


# ---------------------------------------------------------------------------
# Python data model
# ---------------------------------------------------------------------------

def test_len_empty():
    r = Modelrouter()
    assert len(r) == 0


def test_len_with_routes():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True)
    r.add_route("b", "m2", lambda p: True)
    assert len(r) == 2


def test_contains_true():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    assert "code" in r


def test_contains_false():
    r = Modelrouter()
    assert "missing" not in r


def test_iter():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True, priority=1)
    r.add_route("b", "m2", lambda p: True, priority=5)
    names = [route.name for route in r]
    assert names == ["b", "a"]


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_default_property():
    r = Modelrouter(default="my-model")
    assert r.default == "my-model"


def test_default_cost_property():
    r = Modelrouter(default_cost_per_1k=0.007)
    assert r.default_cost == 0.007


# ---------------------------------------------------------------------------
# Route export
# ---------------------------------------------------------------------------

def test_route_class_importable():
    assert Route is not None


def test_routes_snapshot_is_copy():
    r = Modelrouter()
    r.add_route("a", "m", lambda p: True)
    snapshot = r.routes()
    snapshot.clear()
    assert len(r) == 1
