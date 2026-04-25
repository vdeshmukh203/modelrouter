"""Tests for modelrouter."""
from modelrouter import Modelrouter

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

def test_routes_list():
    r = Modelrouter()
    r.add_route("r1", "m1", lambda p: True)
    assert len(r.routes()) == 1
