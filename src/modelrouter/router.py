"""LLM request router with priority, explanation, and cost-awareness."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class Route:
    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    tags: List[str] = field(default_factory=list)


class Modelrouter:
    """Route LLM requests to models based on configurable rules."""

    def __init__(self, default: str = "gpt-4o-mini", default_cost_per_1k: float = 0.0):
        self._default = default
        self._default_cost = default_cost_per_1k
        self._routes: List[Route] = []

    def add_route(self, name: str, model: str,
                  condition: Callable[[str], bool],
                  priority: int = 0,
                  cost_per_1k: float = 0.0,
                  tags: Optional[List[str]] = None) -> None:
        """Register a routing rule."""
        self._routes.append(Route(
            name=name, model=model, condition=condition,
            priority=priority, cost_per_1k=cost_per_1k,
            tags=tags or [],
        ))
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def remove_route(self, name: str) -> bool:
        """Remove a route by name. Returns True if found and removed."""
        original = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < original

    def resolve(self, prompt: str) -> str:
        """Return the model to use for a given prompt."""
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Explain why a model was chosen for the given prompt."""
        route = self._match(prompt)
        if route:
            return {
                "model": route.model,
                "reason": route.name,
                "priority": route.priority,
                "matched": True,
            }
        return {
            "model": self._default,
            "reason": "default (no route matched)",
            "priority": -1,
            "matched": False,
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return (model, estimated_cost_per_1k) for a given prompt."""
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    def routes(self) -> List[Route]:
        """Return all registered routes in priority order."""
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that have a specific tag."""
        return [r for r in self._routes if tag in r.tags]

    @property
    def default(self) -> str:
        return self._default

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception:
                continue
        return None
