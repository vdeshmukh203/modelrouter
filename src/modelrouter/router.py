"""LLM request router with priority, explanation, and cost-awareness."""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A routing rule that maps a condition to a target model.

    Parameters
    ----------
    name:
        Unique identifier for this route.
    model:
        Target model identifier to route matching requests to.
    condition:
        Predicate ``(prompt: str) -> bool``. Evaluated in priority order;
        the first route whose condition returns ``True`` wins.
    priority:
        Evaluation order; higher values are checked first. Default 0.
    cost_per_1k:
        Estimated cost in USD per 1 000 tokens for this model. Default 0.0.
    condition_label:
        Human-readable description of the condition (e.g. ``"keyword:code"``).
        Used for display and ``explain()`` output.
    tags:
        Arbitrary labels for grouping or filtering routes.
    """

    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    condition_label: str = ""
    tags: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        label = self.condition_label or "<callable>"
        return (
            f"Route(name={self.name!r}, model={self.model!r}, "
            f"priority={self.priority}, cost_per_1k={self.cost_per_1k}, "
            f"condition={label!r}, tags={self.tags!r})"
        )


class Modelrouter:
    """Route LLM requests to models based on configurable rules.

    Routes are evaluated in descending priority order. The first route
    whose condition returns ``True`` for a given prompt is selected; if
    none match, the default model is used. Exceptions raised inside a
    condition are logged as warnings and that route is skipped.

    Parameters
    ----------
    default:
        Model identifier returned when no route matches.
        Defaults to ``"gpt-4o-mini"``.
    default_cost_per_1k:
        Cost estimate in USD per 1 000 tokens for the default model.
        Must be >= 0. Defaults to 0.0.

    Raises
    ------
    ValueError
        If *default_cost_per_1k* is negative.
    """

    def __init__(
        self,
        default: str = "gpt-4o-mini",
        default_cost_per_1k: float = 0.0,
    ) -> None:
        if default_cost_per_1k < 0:
            raise ValueError("default_cost_per_1k must be >= 0")
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
        condition_label: str = "",
    ) -> None:
        """Register a routing rule.

        Parameters
        ----------
        name:
            Unique identifier for this route. Raises :exc:`ValueError`
            if a route with this name already exists.
        model:
            Target model identifier (e.g. ``"gpt-4o"``).
        condition:
            Predicate ``(prompt: str) -> bool``. If the callable raises,
            the route is skipped and a warning is logged.
        priority:
            Higher values are evaluated first. Default 0.
        cost_per_1k:
            Estimated cost in USD per 1 000 tokens. Must be >= 0.
        tags:
            Optional labels for grouping or filtering routes.
        condition_label:
            Human-readable description of the condition. Included in
            :meth:`explain` output.

        Raises
        ------
        ValueError
            If *name* is already registered or *cost_per_1k* is negative.
        """
        if any(r.name == name for r in self._routes):
            raise ValueError(
                f"A route named {name!r} already exists. "
                "Remove it first or choose a different name."
            )
        if cost_per_1k < 0:
            raise ValueError("cost_per_1k must be >= 0")
        self._routes.append(
            Route(
                name=name,
                model=model,
                condition=condition,
                priority=priority,
                cost_per_1k=cost_per_1k,
                condition_label=condition_label,
                tags=tags or [],
            )
        )
        self._routes.sort(key=lambda r: r.priority, reverse=True)

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
        before = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < before

    def update_route(
        self,
        name: str,
        *,
        model: Optional[str] = None,
        condition: Optional[Callable[[str], bool]] = None,
        priority: Optional[int] = None,
        cost_per_1k: Optional[float] = None,
        tags: Optional[List[str]] = None,
        condition_label: Optional[str] = None,
    ) -> None:
        """Update fields of an existing route in place.

        Only keyword arguments that are explicitly provided are changed.

        Parameters
        ----------
        name:
            Name of the route to update.
        model, condition, priority, cost_per_1k, tags, condition_label:
            Fields to overwrite. Omit to leave unchanged.

        Raises
        ------
        KeyError
            If no route with *name* exists.
        ValueError
            If *cost_per_1k* is negative.
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
                    if cost_per_1k < 0:
                        raise ValueError("cost_per_1k must be >= 0")
                    route.cost_per_1k = cost_per_1k
                if tags is not None:
                    route.tags = tags
                if condition_label is not None:
                    route.condition_label = condition_label
                self._routes.sort(key=lambda r: r.priority, reverse=True)
                return
        raise KeyError(f"No route named {name!r}")

    def clear(self) -> None:
        """Remove all registered routes."""
        self._routes.clear()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model identifier to use for *prompt*.

        Parameters
        ----------
        prompt:
            Input text to route.

        Returns
        -------
        str
            Model identifier from the first matching route, or the default.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Return a dict describing the routing decision for *prompt*.

        Returns
        -------
        dict
            Keys: ``model``, ``reason``, ``priority``, ``matched``,
            ``cost_per_1k``, ``tags``, ``condition_label``.
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
                "condition_label": route.condition_label,
            }
        return {
            "model": self._default,
            "reason": "default (no route matched)",
            "priority": -1,
            "matched": False,
            "cost_per_1k": self._default_cost,
            "tags": [],
            "condition_label": "",
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return ``(model, cost_per_1k)`` for *prompt*.

        Parameters
        ----------
        prompt:
            Input text to route.

        Returns
        -------
        tuple of (str, float)
            Model identifier and estimated cost per 1 000 tokens.
        """
        route = self._match(prompt)
        if route:
            return route.model, route.cost_per_1k
        return self._default, self._default_cost

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def routes(self) -> List[Route]:
        """Return a copy of all registered routes in priority order."""
        return list(self._routes)

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes that carry *tag*.

        Parameters
        ----------
        tag:
            Tag string to filter by.
        """
        return [r for r in self._routes if tag in r.tags]

    @property
    def default(self) -> str:
        """Default model identifier used when no route matches."""
        return self._default

    @property
    def default_cost(self) -> float:
        """Cost per 1 000 tokens for the default model."""
        return self._default_cost

    def __len__(self) -> int:
        """Return the number of registered routes."""
        return len(self._routes)

    def __contains__(self, name: object) -> bool:
        """Return ``True`` if a route with this name is registered."""
        return any(r.name == name for r in self._routes)

    def __repr__(self) -> str:
        return (
            f"Modelrouter(default={self._default!r}, "
            f"routes={len(self._routes)})"
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
                    "Condition for route %r raised an exception and was skipped: %s",
                    route.name,
                    exc,
                )
        return None
