"""LLM request router with priority, explanation, and cost-awareness."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.getLogger(__name__).addHandler(logging.NullHandler())
logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A single routing rule mapping a condition to a target model.

    Attributes:
        name: Unique identifier for this route.
        model: Name of the target LLM (e.g. ``"gpt-4o"``).
        condition: Callable that receives a prompt string and returns ``True``
            when this route should be applied.  Exceptions raised during
            evaluation are logged and the route is skipped.
        priority: Routes are evaluated in descending priority order.
            Must be a non-negative integer (default ``0``).
        cost_per_1k: Estimated USD cost per 1 000 tokens for *model*
            (default ``0.0``).
        tags: Arbitrary string labels for grouping / filtering routes.
    """

    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.priority < 0:
            raise ValueError(f"priority must be >= 0, got {self.priority!r}")
        if self.cost_per_1k < 0:
            raise ValueError(f"cost_per_1k must be >= 0, got {self.cost_per_1k!r}")

    def __repr__(self) -> str:
        tags_str = f", tags={self.tags!r}" if self.tags else ""
        return (
            f"Route(name={self.name!r}, model={self.model!r}, "
            f"priority={self.priority}{tags_str})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable, priority-ordered rules.

    Routes are evaluated highest-priority first; the first matching route
    determines the target model.  When no route matches, *default* is used.

    Parameters
    ----------
    default:
        Model name returned when no route condition matches.
    default_cost_per_1k:
        Estimated cost per 1 000 tokens for the default model.
    """

    def __init__(
        self,
        default: str = "gpt-4o-mini",
        default_cost_per_1k: float = 0.0,
    ) -> None:
        if default_cost_per_1k < 0:
            raise ValueError(
                f"default_cost_per_1k must be >= 0, got {default_cost_per_1k!r}"
            )
        self._default = default
        self._default_cost = default_cost_per_1k
        self._routes: List[Route] = []

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_route(
        self,
        name: str,
        model: str,
        condition: Callable[[str], bool],
        *,
        priority: int = 0,
        cost_per_1k: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register a routing rule.

        Parameters
        ----------
        name:
            Unique identifier.  Raises :exc:`ValueError` if a route with
            this name is already registered.
        model:
            Target model name.
        condition:
            Callable ``(prompt: str) -> bool``.  Exceptions raised during
            evaluation are logged at DEBUG level and the route is skipped.
        priority:
            Higher values are evaluated first (must be >= 0; default ``0``).
        cost_per_1k:
            Estimated USD cost per 1 000 tokens (must be >= 0; default ``0.0``).
        tags:
            Optional list of string labels for grouping.

        Raises
        ------
        ValueError
            If *name* is already registered, or if *priority* / *cost_per_1k*
            are negative.
        """
        if any(r.name == name for r in self._routes):
            raise ValueError(f"A route named {name!r} already exists")
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

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Returns
        -------
        bool
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        original = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < original

    def clear(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model name to use for *prompt*."""
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Return a dict describing the routing decision for *prompt*.

        The returned dict always contains the keys ``model``, ``reason``,
        ``priority``, and ``matched``.
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
        """Return ``(model, cost_per_1k)`` for *prompt*."""
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    def routes(self) -> List[Route]:
        """Return all registered routes in priority order (highest first)."""
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that carry *tag*, in priority order."""
        return [r for r in self._routes if tag in r.tags]

    # ------------------------------------------------------------------
    # Properties / dunder helpers
    # ------------------------------------------------------------------

    @property
    def default(self) -> str:
        """Model name used when no route matches."""
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
        """Evaluate routes in priority order; return first match or None."""
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception as exc:
                logger.debug(
                    "Condition for route %r raised %s; skipping",
                    route.name,
                    exc,
                )
        return None
