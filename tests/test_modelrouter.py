"""Tests for modelrouter."""
import pytest
from modelrouter import Modelrouter
from modelrouter.router import DuplicateRouteError, Route


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


def test_add_duplicate_raises():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    with pytest.raises(DuplicateRouteError):
        r.add_route("code", "another-model", lambda p: True)


def test_add_empty_name_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("", "gpt-4o", lambda p: True)


def test_add_empty_model_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("code", "", lambda p: True)


def test_empty_default_raises():
    with pytest.raises(ValueError):
        Modelrouter(default="")


def test_update_route():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True, priority=5)
    r.update_route("code", model="claude-3-5-sonnet", priority=10)
    route = r.routes()[0]
    assert route.model == "claude-3-5-sonnet"
    assert route.priority == 10


def test_update_route_condition():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: "code" in p)
    r.update_route("code", condition=lambda p: "python" in p)
    assert r.resolve("write python") == "gpt-4o"
    assert r.resolve("write code") == "mini"


def test_update_nonexistent_raises():
    r = Modelrouter()
    with pytest.raises(KeyError):
        r.update_route("nope", model="x")


def test_update_empty_model_raises():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    with pytest.raises(ValueError):
        r.update_route("code", model="")


def test_clear():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    r.add_route("long", "claude", lambda p: len(p) > 100)
    r.clear()
    assert len(r) == 0
    assert r.resolve("any prompt") == r.default


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

def test_explain_matched():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5)
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"
    assert exp["priority"] == 5


def test_explain_default():
    r = Modelrouter(default="mini")
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"
    assert exp["priority"] == -1


def test_explain_includes_cost_and_tags():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("code", "gpt-4o", lambda p: True, cost_per_1k=0.03, tags=["prod", "expensive"])
    exp = r.explain("test")
    assert exp["cost_per_1k"] == 0.03
    assert exp["tags"] == ["prod", "expensive"]


def test_explain_default_cost_and_tags():
    r = Modelrouter(default="mini", default_cost_per_1k=0.005)
    exp = r.explain("test")
    assert exp["cost_per_1k"] == 0.005
    assert exp["tags"] == []


# ---------------------------------------------------------------------------
# Cost resolution
# ---------------------------------------------------------------------------

def test_resolve_with_cost():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == 0.03


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("test")
    assert model == "mini"
    assert cost == 0.001


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def test_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 0


def test_update_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    r.update_route("r1", tags=["dev", "staging"])
    assert r.routes_by_tag("prod") == []
    assert len(r.routes_by_tag("dev")) == 1


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------

def test_bad_condition_skipped():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


def test_bad_condition_falls_through_to_next():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0, priority=10)
    r.add_route("good", "claude", lambda p: True, priority=5)
    assert r.resolve("test") == "claude"


# ---------------------------------------------------------------------------
# Dunder methods
# ---------------------------------------------------------------------------

def test_len():
    r = Modelrouter()
    assert len(r) == 0
    r.add_route("code", "gpt-4o", lambda p: True)
    assert len(r) == 1
    r.add_route("long", "claude", lambda p: len(p) > 100)
    assert len(r) == 2


def test_contains():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    assert "code" in r
    assert "other" not in r


def test_repr_route():
    route = Route(name="code", model="gpt-4o", condition=lambda p: True, priority=5)
    text = repr(route)
    assert "code" in text
    assert "gpt-4o" in text
    assert "5" in text


def test_repr_modelrouter():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    text = repr(r)
    assert "mini" in text
    assert "1" in text


# ---------------------------------------------------------------------------
# Routes snapshot is independent of internal state
# ---------------------------------------------------------------------------

def test_routes_returns_copy():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: True)
    snapshot = r.routes()
    r.clear()
    assert len(snapshot) == 1
    assert len(r) == 0
