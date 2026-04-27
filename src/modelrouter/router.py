"""LLM request router with priority, explanation, and cost-awareness."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class DuplicateRouteError(ValueError):
    """Raised when a route with the same name already exists."""


@dataclass
class Route:
    """A single routing rule.

    Attributes:
        name: Unique identifier for the route.
        model: Name of the target LLM model.
        condition: Callable that accepts a prompt string and returns ``True``
            when this route should be selected.
        priority: Evaluation order — higher values are evaluated first.
        cost_per_1k: Estimated cost in USD per 1 000 tokens (informational).
        tags: Arbitrary labels used for grouping and filtering routes.
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
            f"priority={self.priority}, cost_per_1k={self.cost_per_1k})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable rules.

    Routes are evaluated in descending priority order; the first matching
    route determines the model.  When no route matches, the default model is
    returned.

    Args:
        default: Model name returned when no route matches.
        default_cost_per_1k: Cost estimate (USD / 1 k tokens) reported for
            the default model by :meth:`resolve_with_cost` and :meth:`explain`.

    Example::

        router = Modelrouter(default="gpt-4o-mini")
        router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
        model = router.resolve("Write a ```python``` snippet")
        # model == "gpt-4o"
    """

    def __init__(
        self,
        default: str = "gpt-4o-mini",
        default_cost_per_1k: float = 0.0,
    ) -> None:
        if not default:
            raise ValueError("default model name must be a non-empty string")
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
        """Register a new routing rule.

        Args:
            name: Unique identifier for this route.
            model: Target model to use when the condition matches.
            condition: Callable ``(prompt: str) -> bool``; returning ``True``
                selects this route.
            priority: Evaluation order; higher values are evaluated first.
                Defaults to ``0``.
            cost_per_1k: Estimated cost in USD per 1 000 tokens.
                Defaults to ``0.0``.
            tags: Optional list of string labels for grouping routes.

        Raises:
            DuplicateRouteError: If a route named *name* is already registered.
            ValueError: If *name* or *model* is an empty string.
        """
        if not name:
            raise ValueError("route name must be a non-empty string")
        if not model:
            raise ValueError("model name must be a non-empty string")
        if name in self:
            raise DuplicateRouteError(
                f"route {name!r} already exists; call update_route() to modify it"
            )
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
        """Update one or more fields of an existing route in-place.

        Only the supplied keyword arguments are changed; omitted arguments
        retain their current values.

        Args:
            name: Name of the route to update.
            model: New target model name.
            condition: New condition callable.
            priority: New priority value.
            cost_per_1k: New cost estimate.
            tags: Replacement tag list.

        Raises:
            KeyError: If no route named *name* exists.
            ValueError: If *model* is an empty string.
        """
        route = next((r for r in self._routes if r.name == name), None)
        if route is None:
            raise KeyError(f"route {name!r} not found")
        if model is not None:
            if not model:
                raise ValueError("model name must be a non-empty string")
            route.model = model
        if condition is not None:
            route.condition = condition
        if priority is not None:
            route.priority = priority
            self._routes.sort(key=lambda r: r.priority, reverse=True)
        if cost_per_1k is not None:
            route.cost_per_1k = cost_per_1k
        if tags is not None:
            route.tags = list(tags)

    def remove_route(self, name: str) -> bool:
        """Remove the route identified by *name*.

        Args:
            name: Name of the route to remove.

        Returns:
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        original = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < original

    def clear(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model name to use for *prompt*.

        Args:
            prompt: The input text to route.

        Returns:
            The model name from the first matching route, or the default model
            if no route matches.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Return a structured explanation of the routing decision for *prompt*.

        Args:
            prompt: The input text to route.

        Returns:
            A dict with the following keys:

            * ``model`` — the resolved model name.
            * ``matched`` — ``True`` if a route matched, ``False`` for default.
            * ``reason`` — matched route name, or ``"default (no route matched)"``.
            * ``priority`` — matched route's priority, or ``-1`` for default.
            * ``cost_per_1k`` — cost estimate for the selected model.
            * ``tags`` — tags of the matched route (empty list for default).
        """
        route = self._match(prompt)
        if route:
            return {
                "model": route.model,
                "matched": True,
                "reason": route.name,
                "priority": route.priority,
                "cost_per_1k": route.cost_per_1k,
                "tags": list(route.tags),
            }
        return {
            "model": self._default,
            "matched": False,
            "reason": "default (no route matched)",
            "priority": -1,
            "cost_per_1k": self._default_cost,
            "tags": [],
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return ``(model, cost_per_1k)`` for *prompt*.

        Args:
            prompt: The input text to route.

        Returns:
            A ``(model_name, cost_per_1k_tokens)`` tuple.
        """
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def routes(self) -> List[Route]:
        """Return a snapshot of all registered routes in priority order."""
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that include *tag* in their tag list.

        Args:
            tag: The tag to filter by.

        Returns:
            A list of matching :class:`Route` objects in priority order.
        """
        return [r for r in self._routes if tag in r.tags]

    @property
    def default(self) -> str:
        """The fallback model name used when no route matches."""
        return self._default

    def __len__(self) -> int:
        return len(self._routes)

    def __contains__(self, name: object) -> bool:
        return any(r.name == name for r in self._routes)

    def __repr__(self) -> str:
        return f"Modelrouter(default={self._default!r}, routes={len(self._routes)})"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception:
                continue
        return None
