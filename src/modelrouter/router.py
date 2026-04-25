"""LLM request router."""
from dataclasses import dataclass
from typing import Callable, List, Optional

@dataclass
class Route:
    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0

class Modelrouter:
    """Route LLM requests to models based on rules."""
    def __init__(self, default: str = "gpt-4o-mini"):
        self._default = default
        self._routes: List[Route] = []

    def add_route(self, name: str, model: str, condition: Callable[[str], bool], priority: int = 0) -> None:
        """Register a routing rule."""
        self._routes.append(Route(name=name, model=model, condition=condition, priority=priority))
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def resolve(self, prompt: str) -> str:
        """Resolve which model to use for a given prompt."""
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route.model
            except Exception:
                continue
        return self._default

    def routes(self) -> List[Route]:
        """Return registered routes."""
        return list(self._routes)

    @property
    def default(self) -> str:
        return self._default
