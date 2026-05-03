"""LLM request router with priority, explanation, and cost-awareness."""
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A single routing rule.

    Attributes:
        name: Unique identifier for this route.
        model: Target model name when this route matches.
        condition: Callable that returns True when this route should fire.
        priority: Evaluation order; higher values are checked first.
        cost_per_1k: Estimated cost in USD per 1 000 tokens.
        tags: Arbitrary string labels for grouping and filtering.
    """

    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"Route(name={self.name!r}, model={self.model!r}, "
            f"priority={self.priority}, cost_per_1k={self.cost_per_1k}, "
            f"tags={self.tags!r})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable rules.

    Routes are evaluated in descending priority order; the first matching
    route wins. If no route matches, the default model is used.

    Args:
        default: Model name returned when no route matches.
        default_cost_per_1k: Cost estimate for the default model (USD / 1k tokens).

    Examples:
        >>> router = Modelrouter(default="gpt-4o-mini")
        >>> router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
        >>> router.resolve("Show me a ```python``` example")
        'gpt-4o'
    """

    def __init__(self, default: str = "gpt-4o-mini", default_cost_per_1k: float = 0.0):
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
            name: Unique name for this route.
            model: Model to use when this route matches.
            condition: Callable ``(prompt: str) -> bool`` that decides if the
                route fires.  Exceptions raised by the condition are caught at
                resolution time and the route is skipped.
            priority: Evaluation order; higher values are checked first.
                Defaults to 0.
            cost_per_1k: Estimated cost per 1 000 tokens.  Must be >= 0.
            tags: Optional list of string labels for grouping.

        Raises:
            ValueError: If *name* is already registered, *condition* is not
                callable, or *cost_per_1k* is negative.
        """
        if not callable(condition):
            raise ValueError(
                f"condition for route {name!r} must be callable, "
                f"got {type(condition).__name__!r}"
            )
        if cost_per_1k < 0:
            raise ValueError(
                f"cost_per_1k must be non-negative, got {cost_per_1k}"
            )
        if any(r.name == name for r in self._routes):
            raise ValueError(
                f"a route named {name!r} already exists; "
                "use update_route() to modify it"
            )
        self._routes.append(
            Route(
                name=name,
                model=model,
                condition=condition,
                priority=priority,
                cost_per_1k=cost_per_1k,
                tags=tags or [],
            )
        )
        self._routes.sort(key=lambda r: r.priority, reverse=True)
        logger.debug("Added route %r (model=%r, priority=%d)", name, model, priority)

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Args:
            name: The name of the route to remove.

        Returns:
            True if the route was found and removed, False if it did not exist.
        """
        before = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        removed = len(self._routes) < before
        if removed:
            logger.debug("Removed route %r", name)
        return removed

    def update_route(
        self,
        name: str,
        *,
        model: Optional[str] = None,
        condition: Optional[Callable[[str], bool]] = None,
        priority: Optional[int] = None,
        cost_per_1k: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Update fields of an existing route in place.

        Only keyword arguments that are explicitly provided are changed;
        omitted arguments leave the corresponding field unchanged.

        Args:
            name: Name of the route to update.
            model: New model name.
            condition: New condition callable.
            priority: New priority value.
            cost_per_1k: New cost estimate.  Must be >= 0 if provided.
            tags: New tag list.

        Raises:
            KeyError: If no route with *name* exists.
            ValueError: If *condition* is not callable or *cost_per_1k* is
                negative.
        """
        route = next((r for r in self._routes if r.name == name), None)
        if route is None:
            raise KeyError(f"no route named {name!r}")
        if condition is not None and not callable(condition):
            raise ValueError("condition must be callable")
        if cost_per_1k is not None and cost_per_1k < 0:
            raise ValueError(f"cost_per_1k must be non-negative, got {cost_per_1k}")

        if model is not None:
            route.model = model
        if condition is not None:
            route.condition = condition
        if priority is not None:
            route.priority = priority
            self._routes.sort(key=lambda r: r.priority, reverse=True)
        if cost_per_1k is not None:
            route.cost_per_1k = cost_per_1k
        if tags is not None:
            route.tags = tags
        logger.debug("Updated route %r", name)

    def clear(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()
        logger.debug("Cleared all routes")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model to use for the given prompt.

        Args:
            prompt: The input text to route.

        Returns:
            The model name selected for *prompt*.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Explain which model was chosen and why.

        Args:
            prompt: The input text to route.

        Returns:
            A dict with keys ``model``, ``reason``, ``priority``,
            ``matched``, ``cost_per_1k``, and ``tags``.
        """
        route = self._match(prompt)
        if route:
            return {
                "model": route.model,
                "reason": route.name,
                "priority": route.priority,
                "matched": True,
                "cost_per_1k": route.cost_per_1k,
                "tags": list(route.tags),
            }
        return {
            "model": self._default,
            "reason": "default (no route matched)",
            "priority": -1,
            "matched": False,
            "cost_per_1k": self._default_cost,
            "tags": [],
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return the selected model and its estimated cost per 1 000 tokens.

        Args:
            prompt: The input text to route.

        Returns:
            A ``(model, cost_per_1k)`` tuple.
        """
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def routes(self) -> List[Route]:
        """Return all registered routes in priority order.

        Returns:
            A new list containing all routes, sorted descending by priority.
        """
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that carry a specific tag.

        Args:
            tag: The tag string to filter by.

        Returns:
            A list of matching routes in priority order.
        """
        return [r for r in self._routes if tag in r.tags]

    # ------------------------------------------------------------------
    # Python data-model helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)

    def __contains__(self, name: object) -> bool:
        """Return True if a route with the given *name* is registered."""
        return any(r.name == name for r in self._routes)

    def __repr__(self) -> str:
        return (
            f"Modelrouter(default={self._default!r}, routes={len(self._routes)})"
        )

    @property
    def default(self) -> str:
        """The fallback model used when no route matches."""
        return self._default

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    logger.debug(
                        "Prompt matched route %r (model=%r)", route.name, route.model
                    )
                    return route
            except Exception as exc:
                logger.warning(
                    "Condition for route %r raised %s: %s — skipping",
                    route.name,
                    type(exc).__name__,
                    exc,
                )
                continue
        logger.debug("No route matched; using default %r", self._default)
        return None
