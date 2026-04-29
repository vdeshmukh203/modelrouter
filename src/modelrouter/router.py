"""LLM request router with priority, explanation, and cost-awareness."""
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["Route", "Modelrouter"]

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A routing rule that maps a prompt condition to a target LLM model.

    Attributes:
        name: Unique identifier for this route.
        model: Name of the target LLM model.
        condition: Callable that receives a prompt string and returns ``True``
            when this route should be selected.
        priority: Higher values are evaluated first (default 0).
        cost_per_1k: Estimated cost in USD per 1 000 tokens (default 0.0).
        tags: Optional labels for grouping and filtering routes.
    """

    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Route(name={self.name!r}, model={self.model!r}, "
            f"priority={self.priority})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable, priority-ordered rules.

    Routes are evaluated in descending priority order; the first matching
    route determines the model.  When no route matches the default model is
    returned.

    Args:
        default: Fallback model name used when no route matches.
        default_cost_per_1k: Estimated cost in USD per 1 000 tokens for the
            default model.

    Raises:
        ValueError: If *default* is empty or *default_cost_per_1k* is negative.

    Examples:
        >>> router = Modelrouter(default="gpt-4o-mini")
        >>> router.add_route("code", "gpt-4o", lambda p: "code" in p, priority=5)
        >>> router.resolve("write code for me")
        'gpt-4o'
    """

    def __init__(self, default: str = "gpt-4o-mini", default_cost_per_1k: float = 0.0):
        if not isinstance(default, str) or not default.strip():
            raise ValueError("default must be a non-empty string")
        if default_cost_per_1k < 0:
            raise ValueError("default_cost_per_1k must be non-negative")
        self._default = default
        self._default_cost = default_cost_per_1k
        self._routes: List[Route] = []

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def add_route(
        self,
        name: str,
        model: str,
        condition: Callable[[str], bool],
        priority: int = 0,
        cost_per_1k: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register a routing rule.

        Args:
            name: Unique identifier for this route.
            model: Target LLM model name.
            condition: Callable that accepts a prompt string and returns
                ``True`` when this route should be selected.
            priority: Evaluation order; higher values are checked first.
            cost_per_1k: Estimated cost in USD per 1 000 tokens.
            tags: Labels for grouping and filtering routes.

        Raises:
            ValueError: If *name* or *model* is empty, *cost_per_1k* is
                negative, or a route with *name* already exists.
            TypeError: If *condition* is not callable.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not callable(condition):
            raise TypeError("condition must be callable")
        if cost_per_1k < 0:
            raise ValueError("cost_per_1k must be non-negative")
        if any(r.name == name for r in self._routes):
            raise ValueError(f"A route named {name!r} already exists")

        self._routes.append(
            Route(
                name=name,
                model=model,
                condition=condition,
                priority=priority,
                cost_per_1k=cost_per_1k,
                tags=list(tags) if tags else [],
            )
        )
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def remove_route(self, name: str) -> bool:
        """Remove the route with the given name.

        Args:
            name: Name of the route to remove.

        Returns:
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        original = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < original

    def clear_routes(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model name to use for *prompt*.

        Args:
            prompt: Input text to route.

        Returns:
            Model name string.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Return a dictionary explaining why a model was selected for *prompt*.

        Args:
            prompt: Input text to route.

        Returns:
            Dict with keys ``model``, ``reason``, ``priority``, and ``matched``.
        """
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
        """Return ``(model, estimated_cost_per_1k)`` for *prompt*.

        Args:
            prompt: Input text to route.

        Returns:
            Tuple of ``(model_name, cost_per_1k_tokens)``.
        """
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def routes(self) -> List[Route]:
        """Return all registered routes in descending priority order.

        Returns:
            Copy of the internal route list sorted by priority (highest first).
        """
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that carry a specific tag.

        Args:
            tag: Tag string to filter by.

        Returns:
            List of matching :class:`Route` objects in priority order.
        """
        return [r for r in self._routes if tag in r.tags]

    @property
    def default(self) -> str:
        """Fallback model name returned when no route matches."""
        return self._default

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)

    def __repr__(self) -> str:
        return (
            f"Modelrouter(default={self._default!r}, routes={len(self._routes)})"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception as exc:
                logger.warning(
                    "Route %r skipped: condition raised %s: %s",
                    route.name,
                    type(exc).__name__,
                    exc,
                )
        return None
