"""Tests for modelrouter."""
import pytest

from modelrouter import Modelrouter, Route


# ---------------------------------------------------------------------------
# Original tests (preserved + extended)
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


def test_explain_matched():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5)
    exp = r.explain("write code")
    assert exp["matched"] is True
    assert exp["model"] == "gpt-4o"
    assert exp["reason"] == "code"


def test_explain_default():
    r = Modelrouter(default="mini")
    exp = r.explain("hello")
    assert exp["matched"] is False
    assert exp["model"] == "mini"


def test_resolve_with_cost():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == 0.03


def test_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 0


def test_bad_condition_skipped():
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    assert r.resolve("test") == "mini"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_empty_default_raises():
    with pytest.raises(ValueError):
        Modelrouter(default="")


def test_add_route_empty_name_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("", "gpt-4o", lambda p: True)


def test_add_route_empty_model_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.add_route("myroute", "", lambda p: True)


def test_add_route_non_callable_condition_raises():
    r = Modelrouter()
    with pytest.raises(TypeError):
        r.add_route("myroute", "gpt-4o", "not_callable")  # type: ignore[arg-type]


def test_set_default_empty_raises():
    r = Modelrouter()
    with pytest.raises(ValueError):
        r.set_default("")


# ---------------------------------------------------------------------------
# New methods
# ---------------------------------------------------------------------------

def test_set_default():
    r = Modelrouter(default="gpt-4o-mini")
    r.set_default("claude-3-5-sonnet", cost_per_1k=0.003)
    assert r.default == "claude-3-5-sonnet"
    assert r.default_cost == 0.003
    # new default is used when no route matches
    assert r.resolve("hello") == "claude-3-5-sonnet"


def test_clear_routes():
    r = Modelrouter(default="mini")
    r.add_route("a", "m1", lambda p: True)
    r.add_route("b", "m2", lambda p: True)
    assert len(r) == 2
    r.clear_routes()
    assert len(r) == 0
    assert r.resolve("anything") == "mini"


def test_add_route_replaces_duplicate_name():
    r = Modelrouter()
    r.add_route("x", "model-v1", lambda p: True, priority=5)
    r.add_route("x", "model-v2", lambda p: True, priority=10)
    # only one route should exist
    assert len(r) == 1
    assert r.resolve("test") == "model-v2"


def test_len():
    r = Modelrouter()
    assert len(r) == 0
    r.add_route("a", "m1", lambda p: True)
    assert len(r) == 1
    r.add_route("b", "m2", lambda p: False)
    assert len(r) == 2
    r.remove_route("a")
    assert len(r) == 1


# ---------------------------------------------------------------------------
# Default property and cost
# ---------------------------------------------------------------------------

def test_default_property():
    r = Modelrouter(default="my-model")
    assert r.default == "my-model"


def test_default_cost_property():
    r = Modelrouter(default_cost_per_1k=0.005)
    assert r.default_cost == 0.005


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("no match possible" * 0)
    assert model == "mini"
    assert cost == 0.001


# ---------------------------------------------------------------------------
# explain() extended fields
# ---------------------------------------------------------------------------

def test_explain_includes_cost_and_tags():
    r = Modelrouter()
    r.add_route("code", "gpt-4o", lambda p: "code" in p,
                priority=3, cost_per_1k=0.03, tags=["premium", "code"])
    exp = r.explain("write code")
    assert exp["cost_per_1k"] == 0.03
    assert "premium" in exp["tags"]
    assert "code" in exp["tags"]


def test_explain_default_cost_and_tags():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    exp = r.explain("hello")
    assert exp["cost_per_1k"] == 0.001
    assert exp["tags"] == []


def test_explain_priority_field():
    r = Modelrouter()
    r.add_route("hi", "m1", lambda p: True, priority=7)
    exp = r.explain("test")
    assert exp["priority"] == 7


# ---------------------------------------------------------------------------
# routes() ordering
# ---------------------------------------------------------------------------

def test_routes_returned_in_priority_order():
    r = Modelrouter()
    r.add_route("low", "m-low", lambda p: True, priority=1)
    r.add_route("high", "m-high", lambda p: True, priority=99)
    r.add_route("mid", "m-mid", lambda p: True, priority=50)
    names = [rt.name for rt in r.routes()]
    assert names == ["high", "mid", "low"]


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

def test_route_repr():
    rt = Route("myroute", "gpt-4o", lambda p: True, priority=5,
               cost_per_1k=0.01, tags=["prod"])
    r = repr(rt)
    assert "myroute" in r
    assert "gpt-4o" in r
    assert "5" in r


def test_modelrouter_repr():
    r = Modelrouter(default="mini")
    r.add_route("a", "m1", lambda p: True)
    txt = repr(r)
    assert "mini" in txt
    assert "1" in txt


# ---------------------------------------------------------------------------
# Edge: empty prompt
# ---------------------------------------------------------------------------

def test_empty_prompt_uses_default():
    r = Modelrouter(default="fallback")
    r.add_route("any", "gpt-4o", lambda p: len(p) > 0)
    assert r.resolve("") == "fallback"


def test_empty_prompt_condition_not_triggered():
    r = Modelrouter(default="fallback")
    r.add_route("nonempty", "gpt-4o", lambda p: bool(p))
    assert r.resolve("") == "fallback"
    assert r.resolve("hello") == "gpt-4o"
