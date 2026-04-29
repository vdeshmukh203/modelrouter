"""Tests for modelrouter."""
import logging
import pytest
from modelrouter import Modelrouter, Route


# ---------------------------------------------------------------------------
# Existing behaviour
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


def test_resolve_with_cost_default():
    r = Modelrouter(default="mini", default_cost_per_1k=0.001)
    model, cost = r.resolve_with_cost("no match here")
    assert model == "mini"
    assert cost == 0.001


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
    with pytest.raises(ValueError, match="default"):
        Modelrouter(default="")


def test_negative_default_cost_raises():
    with pytest.raises(ValueError, match="default_cost_per_1k"):
        Modelrouter(default_cost_per_1k=-1.0)


def test_empty_name_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="name"):
        r.add_route("", "gpt-4o", lambda p: True)


def test_empty_model_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="model"):
        r.add_route("myroute", "", lambda p: True)


def test_noncallable_condition_raises():
    r = Modelrouter()
    with pytest.raises(TypeError, match="callable"):
        r.add_route("bad", "gpt-4o", "not-a-callable")  # type: ignore[arg-type]


def test_negative_cost_raises():
    r = Modelrouter()
    with pytest.raises(ValueError, match="cost_per_1k"):
        r.add_route("r", "m", lambda p: True, cost_per_1k=-0.01)


def test_duplicate_name_raises():
    r = Modelrouter()
    r.add_route("same", "gpt-4o", lambda p: True)
    with pytest.raises(ValueError, match="already exists"):
        r.add_route("same", "gpt-4o-mini", lambda p: False)


# ---------------------------------------------------------------------------
# New methods
# ---------------------------------------------------------------------------

def test_clear_routes():
    r = Modelrouter(default="mini")
    r.add_route("a", "gpt-4o", lambda p: True)
    r.add_route("b", "claude", lambda p: False)
    r.clear_routes()
    assert len(r) == 0
    assert r.resolve("anything") == "mini"


def test_len():
    r = Modelrouter()
    assert len(r) == 0
    r.add_route("r1", "m1", lambda p: True)
    assert len(r) == 1
    r.add_route("r2", "m2", lambda p: False)
    assert len(r) == 2
    r.remove_route("r1")
    assert len(r) == 1


def test_repr():
    r = Modelrouter(default="mini")
    r.add_route("r1", "m1", lambda p: True)
    rep = repr(r)
    assert "mini" in rep
    assert "routes=1" in rep


def test_routes_returns_copy():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True)
    copy = r.routes()
    copy.clear()
    assert len(r) == 1


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------

def test_route_exported():
    """Route must be importable from the top-level package."""
    from modelrouter import Route as R
    assert R is Route


def test_version_exported():
    import modelrouter
    assert hasattr(modelrouter, "__version__")
    assert modelrouter.__version__ == "0.2.0"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_bad_condition_logs_warning(caplog):
    r = Modelrouter(default="mini")
    r.add_route("bad", "gpt-4o", lambda p: 1 / 0)
    with caplog.at_level(logging.WARNING, logger="modelrouter.router"):
        r.resolve("test")
    assert any("bad" in rec.message for rec in caplog.records)
