"""modelrouter — condition-based routing for LLM requests."""

from .router import Modelrouter, Route, RouteError

__all__ = ["Modelrouter", "Route", "RouteError"]
__version__ = "0.2.0"
