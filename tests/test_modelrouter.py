"""Tests for modelrouter."""
import pytest
from modelrouter import Modelrouter, Route


# ---------------------------------------------------------------------------
# Route dataclass
# ---------------------------------------------------------------------------

def test_route_repr():
    r = Route("code", "gpt-4o", lambda p: True, priority=5)
    assert "code" in repr(r)
    assert "gpt-4o" in repr(r)
    assert "5" in repr(r)


def test_route_repr_with_tags():
    r = Route("t", "m", lambda p: True, tags=["prod"])
    assert "prod" in repr(r)


def test_route_negative_priority_raises():
    with pytest.raises(ValueError, match="priority"):
        Route("bad", "m", lambda p: True, priority=-1)


def test_route_negative_cost_raises():
    with pytest.raises(ValueError, match="cost_per_1k"):
        Route("bad", "m", lambda p: True, cost_per_1k=-0.01)


# ---------------------------------------------------------------------------
# Modelrouter construction
# ---------------------------------------------------------------------------

def test_default():
    r = Modelrouter(default="gpt-4o-mini")
    assert r.resolve("hello") == "gpt-4o-mini"


def test_default_property():
    r = Modelrouter(default="my-model")
    assert r.default == "my-model"


def test_repr():
    r = Modelrouter(default="mini")
    assert "mini" in repr(r)
    assert "0" in repr(r)


def test_negative_default_cost_raises():
    with pytest.raises(ValueError, match="default_cost_per_1k"):
        Modelrouter(default_cost_per_1k=-1.0)


# ---------------------------------------------------------------------------
# add_route / remove_route / clear
# ---------------------------------------------------------------------------

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


def test_routes_returned_in_priority_order():
    r = Modelrouter()
    r.add_route("a", "m1", lambda p: True, priority=1)
    r.add_route("b", "m2", lambda p: True, priority=10)
    r.add_route("c", "m3", lambda p: True, priority=5)
    names = [rt.name for rt in r.routes()]
    assert names == ["b", "c", "a"]


def test_duplicate_name_raises():
    r = Modelrouter()
    r.add_route("x", "m1", lambda p: True)
    with pytest.raises(ValueError, match="already exists"):
        r.add_route("x", "m2", lambda p: True)


def test_remove_route():
    r = Modelrouter(default="mini")
    r.add_route("code", "gpt-4o", lambda p: True)
    assert r.remove_route("code") is True
    assert r.resolve("anything") == "mini"


def test_remove_nonexistent():
    r = Modelrouter()
    assert r.remove_route("nope") is False


def test_clear():
    r = Modelrouter(default="mini")
    r.add_route("a", "m", lambda p: True)
    r.add_route("b", "m", lambda p: True)
    r.clear()
    assert len(r) == 0
    assert r.resolve("hi") == "mini"


# ---------------------------------------------------------------------------
# __len__
# ---------------------------------------------------------------------------

def test_len_empty():
    assert len(Modelrouter()) == 0


def test_len_after_add():
    r = Modelrouter()
    r.add_route("a", "m", lambda p: True)
    r.add_route("b", "m2", lambda p: True)
    assert len(r) == 2


def test_len_after_remove():
    r = Modelrouter()
    r.add_route("a", "m", lambda p: True)
    r.remove_route("a")
    assert len(r) == 0


# ---------------------------------------------------------------------------
# explain
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


# ---------------------------------------------------------------------------
# resolve_with_cost
# ---------------------------------------------------------------------------

def test_resolve_with_cost_matched():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: True, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "gpt-4o"
    assert cost == 0.03


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    r.add_route("expensive", "gpt-4o", lambda p: False, cost_per_1k=0.03)
    model, cost = r.resolve_with_cost("test")
    assert model == "mini"
    assert cost == 0.001


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------

def test_tags():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod"])
    assert len(r.routes_by_tag("prod")) == 1
    assert len(r.routes_by_tag("dev")) == 0


def test_routes_by_tag_multiple():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True, tags=["prod", "ml"])
    r.add_route("r2", "m2", lambda p: True, tags=["prod"])
    r.add_route("r3", "m3", lambda p: True, tags=["dev"])
    assert len(r.routes_by_tag("prod")) == 2
    assert len(r.routes_by_tag("ml")) == 1
    assert len(r.routes_by_tag("dev")) == 1


# ---------------------------------------------------------------------------
# error resilience
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
