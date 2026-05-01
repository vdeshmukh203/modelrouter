"""LLM request router with priority, explanation, and cost-awareness."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A single routing rule mapping a condition to a target LLM.

    Attributes:
        name: Unique identifier for this route.
        model: Name or identifier of the target LLM.
        condition: Callable that accepts a prompt string and returns ``True``
            when this route should match.
        priority: Higher values are evaluated first.  Defaults to 0.
        cost_per_1k: Estimated cost in USD per 1,000 tokens.  Defaults to 0.0.
        tags: Arbitrary labels for grouping and filtering routes.
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
    route wins.  When no route matches the *default* model is returned.

    Parameters
    ----------
    default:
        Model identifier returned when no route matches.
    default_cost_per_1k:
        Cost per 1,000 tokens for the default model (used by
        :meth:`resolve_with_cost`).

    Examples
    --------
    >>> router = Modelrouter(default="gpt-4o-mini")
    >>> router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
    >>> router.resolve("Write me a ```python``` snippet")
    'gpt-4o'
    """

    def __init__(self, default: str = "gpt-4o-mini", default_cost_per_1k: float = 0.0):
        if not default:
            raise ValueError("default model name must not be empty")
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

        If a route with *name* already exists it is silently replaced.

        Parameters
        ----------
        name:
            Unique route identifier.
        model:
            Target LLM identifier (e.g. ``"gpt-4o"``).
        condition:
            Callable ``(prompt: str) -> bool`` that returns ``True`` when the
            route should match.
        priority:
            Evaluation order; higher values are checked first.
        cost_per_1k:
            Estimated USD cost per 1,000 tokens for budget-aware dispatch.
        tags:
            Optional list of string labels for organisational filtering.
        """
        if not name:
            raise ValueError("route name must not be empty")
        if not model:
            raise ValueError("model name must not be empty")
        if not callable(condition):
            raise TypeError("condition must be callable")
        self._routes = [r for r in self._routes if r.name != name]
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
        logger.debug("Registered route %r -> %r (priority=%d)", name, model, priority)

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Returns
        -------
        bool
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        original = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        removed = len(self._routes) < original
        if removed:
            logger.debug("Removed route %r", name)
        return removed

    def clear_routes(self) -> None:
        """Remove all registered routes, keeping the default model."""
        self._routes.clear()
        logger.debug("All routes cleared")

    def set_default(self, model: str, cost_per_1k: float = 0.0) -> None:
        """Update the default fallback model.

        Parameters
        ----------
        model:
            New default model identifier.
        cost_per_1k:
            Estimated cost per 1,000 tokens for the default model.
        """
        if not model:
            raise ValueError("default model name must not be empty")
        self._default = model
        self._default_cost = cost_per_1k
        logger.debug("Default model set to %r", model)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model to use for *prompt*.

        Parameters
        ----------
        prompt:
            The input text to route.

        Returns
        -------
        str
            Model identifier of the first matching route, or the default model
            when no route matches.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Explain the routing decision for *prompt*.

        Returns
        -------
        dict
            A dictionary with keys ``model``, ``reason``, ``priority``,
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
        """Return ``(model, estimated_cost_per_1k)`` for *prompt*.

        Parameters
        ----------
        prompt:
            The input text to route.

        Returns
        -------
        tuple[str, float]
            Model identifier and cost-per-1k-tokens estimate.
        """
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def routes(self) -> List[Route]:
        """Return all registered routes in descending priority order."""
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that carry *tag*."""
        return [r for r in self._routes if tag in r.tags]

    @property
    def default(self) -> str:
        """The fallback model identifier."""
        return self._default

    @property
    def default_cost(self) -> float:
        """Cost-per-1k-tokens estimate for the default model."""
        return self._default_cost

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)

    def __repr__(self) -> str:
        return (
            f"Modelrouter(default={self._default!r}, routes={len(self._routes)})"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Route %r condition raised %s; skipping", route.name, exc
                )
        return None
