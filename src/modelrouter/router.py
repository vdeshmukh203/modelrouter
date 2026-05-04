"""LLM request router with priority, explanation, and cost-awareness."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A single routing rule that maps a condition to a target model.

    Attributes:
        name: Unique identifier for this route.
        model: The LLM model name to dispatch to when this route matches.
        condition: A callable that accepts a prompt string and returns ``True``
            when this route should be selected.
        priority: Higher values are evaluated first (default ``0``).
        cost_per_1k: Estimated cost in USD per 1 000 tokens (default ``0.0``).
        tags: Arbitrary labels for grouping or filtering routes.
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
            f"priority={self.priority}, cost_per_1k={self.cost_per_1k})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable rules.

    Routes are evaluated in descending priority order.  The first route whose
    ``condition`` returns ``True`` for a given prompt wins.  When no route
    matches the configured *default* model is used.

    Parameters
    ----------
    default:
        Model name returned when no route matches.
    default_cost_per_1k:
        Estimated cost (USD / 1 000 tokens) associated with the default model.

    Examples
    --------
    >>> router = Modelrouter(default="gpt-4o-mini")
    >>> router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
    >>> router.resolve("Write a ```python``` script")
    'gpt-4o'
    """

    def __init__(
        self,
        default: str = "gpt-4o-mini",
        default_cost_per_1k: float = 0.0,
    ) -> None:
        self._default = default
        self._default_cost = default_cost_per_1k
        self._routes: List[Route] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def default(self) -> str:
        """The model used when no route matches."""
        return self._default

    @property
    def default_cost(self) -> float:
        """Cost per 1 000 tokens for the default model."""
        return self._default_cost

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

        If a route with *name* already exists it is replaced in-place so that
        the original insertion position relative to same-priority peers is
        preserved before re-sorting.

        Parameters
        ----------
        name:
            Unique name for the route.  Used by :meth:`remove_route` and
            :meth:`update_route`.
        model:
            Target model identifier.
        condition:
            Callable ``(prompt: str) -> bool``.  Exceptions raised by the
            callable are caught and treated as ``False``.
        priority:
            Evaluation order; higher values are checked first.
        cost_per_1k:
            Estimated cost in USD per 1 000 tokens.
        tags:
            Optional list of string labels for :meth:`routes_by_tag`.
        """
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
        logger.debug("Route %r added (model=%s, priority=%d)", name, model, priority)

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Parameters
        ----------
        name:
            Name of the route to remove.

        Returns
        -------
        bool
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        original_len = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        removed = len(self._routes) < original_len
        if removed:
            logger.debug("Route %r removed", name)
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
    ) -> bool:
        """Update fields of an existing route in-place.

        Only supplied keyword arguments are modified; others are left
        unchanged.

        Parameters
        ----------
        name:
            Name of the route to update.

        Returns
        -------
        bool
            ``True`` if the route was found and updated, ``False`` otherwise.
        """
        for route in self._routes:
            if route.name == name:
                if model is not None:
                    route.model = model
                if condition is not None:
                    route.condition = condition
                if priority is not None:
                    route.priority = priority
                if cost_per_1k is not None:
                    route.cost_per_1k = cost_per_1k
                if tags is not None:
                    route.tags = list(tags)
                self._routes.sort(key=lambda r: r.priority, reverse=True)
                logger.debug("Route %r updated", name)
                return True
        return False

    def clear(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()
        logger.debug("All routes cleared")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model name to use for *prompt*.

        Parameters
        ----------
        prompt:
            The input text whose routing is to be determined.

        Returns
        -------
        str
            Model identifier from the first matching route, or
            :attr:`default` if no route matches.
        """
        route = self._match(prompt)
        model = route.model if route else self._default
        logger.debug("resolve(%r…) → %s", prompt[:40], model)
        return model

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Return a dict describing why a model was chosen for *prompt*.

        Returns
        -------
        dict
            Keys: ``model``, ``reason``, ``priority``, ``cost_per_1k``,
            ``tags``, ``matched``.
        """
        route = self._match(prompt)
        if route:
            return {
                "model": route.model,
                "reason": route.name,
                "priority": route.priority,
                "cost_per_1k": route.cost_per_1k,
                "tags": list(route.tags),
                "matched": True,
            }
        return {
            "model": self._default,
            "reason": "default (no route matched)",
            "priority": None,
            "cost_per_1k": self._default_cost,
            "tags": [],
            "matched": False,
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return ``(model, cost_per_1k)`` for *prompt*.

        Parameters
        ----------
        prompt:
            The input text whose routing is to be determined.

        Returns
        -------
        tuple[str, float]
            Model identifier and estimated cost in USD per 1 000 tokens.
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
        """Return routes that carry *tag* (exact match, case-sensitive)."""
        return [r for r in self._routes if tag in r.tags]

    # ------------------------------------------------------------------
    # Python data-model
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)

    def __contains__(self, name: object) -> bool:
        """Return ``True`` if a route named *name* is registered."""
        return any(r.name == name for r in self._routes)

    def __iter__(self) -> Iterator[Route]:
        """Iterate over routes in priority order."""
        return iter(list(self._routes))

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Modelrouter(default={self._default!r}, routes={len(self)})"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    return route
            except Exception:
                logger.warning(
                    "Condition for route %r raised an exception; skipping",
                    route.name,
                )
        return None
