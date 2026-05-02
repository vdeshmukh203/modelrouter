"""LLM request router with priority, explanation, and cost-awareness."""
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RouteError(Exception):
    """Raised for invalid routing configurations (e.g. duplicate route names)."""


@dataclass
class Route:
    """A single routing rule that maps a condition to a target model.

    Parameters
    ----------
    name:
        Unique identifier for this route.
    model:
        LLM model name to dispatch to when *condition* returns ``True``.
    condition:
        Predicate that receives the raw prompt string and returns a bool.
    priority:
        Evaluation order — higher values are tested first.
    cost_per_1k:
        Estimated USD cost per 1 000 tokens (used for budget-aware dispatch).
    tags:
        Arbitrary labels for grouping and filtering routes.
    """

    name: str
    model: str
    condition: Callable[[str], bool]
    priority: int = 0
    cost_per_1k: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Route name cannot be empty.")
        if not self.model:
            raise ValueError("Route model cannot be empty.")
        if not callable(self.condition):
            raise TypeError("Route condition must be callable.")
        if self.priority < 0:
            raise ValueError("Route priority must be a non-negative integer.")
        if self.cost_per_1k < 0:
            raise ValueError("Route cost_per_1k must be non-negative.")


class Modelrouter:
    """Route LLM requests to models based on configurable, prioritised rules.

    Routes are evaluated in descending priority order; the first condition that
    returns ``True`` determines the target model.  When no route matches, the
    configured *default* model is returned.

    Parameters
    ----------
    default:
        Model name returned when no route condition matches.
    default_cost_per_1k:
        Estimated USD cost per 1 000 tokens for the default model.

    Examples
    --------
    >>> router = Modelrouter(default="gpt-4o-mini")
    >>> router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
    >>> router.resolve("Show me a ```python``` example")
    'gpt-4o'
    """

    def __init__(self, default: str = "gpt-4o-mini", default_cost_per_1k: float = 0.0) -> None:
        self._default = default
        self._default_cost = default_cost_per_1k
        self._routes: List[Route] = []
        self._stats: Dict[str, int] = {}
        logger.debug("Modelrouter initialised with default=%r", default)

    # ------------------------------------------------------------------
    # Mutation helpers
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

        Parameters
        ----------
        name:
            Unique identifier for this route.
        model:
            LLM model name to dispatch to when *condition* is satisfied.
        condition:
            Predicate that receives the raw prompt string.
        priority:
            Higher values are evaluated first; ties preserve insertion order.
        cost_per_1k:
            Estimated USD cost per 1 000 tokens for budget-aware dispatch.
        tags:
            Arbitrary labels used for grouping and filtering.

        Raises
        ------
        RouteError
            If *name* is already registered — use :meth:`update_route` to
            modify an existing route.
        ValueError
            If *name* or *model* is empty, or *priority*/*cost_per_1k* is
            negative.
        TypeError
            If *condition* is not callable.
        """
        if any(r.name == name for r in self._routes):
            raise RouteError(
                f"Route {name!r} is already registered; "
                "call update_route() to modify it."
            )
        route = Route(
            name=name,
            model=model,
            condition=condition,
            priority=priority,
            cost_per_1k=cost_per_1k,
            tags=list(tags) if tags else [],
        )
        self._routes.append(route)
        self._routes.sort(key=lambda r: r.priority, reverse=True)
        self._stats[name] = 0
        logger.debug("Route %r added (model=%r, priority=%d)", name, model, priority)

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

        Only the keyword arguments that are not ``None`` are changed.

        Parameters
        ----------
        name:
            Name of the route to update.

        Raises
        ------
        RouteError
            If *name* is not registered.
        """
        for route in self._routes:
            if route.name == name:
                if model is not None:
                    route.model = model
                if condition is not None:
                    if not callable(condition):
                        raise TypeError("condition must be callable.")
                    route.condition = condition
                if priority is not None:
                    if priority < 0:
                        raise ValueError("priority must be a non-negative integer.")
                    route.priority = priority
                if cost_per_1k is not None:
                    if cost_per_1k < 0:
                        raise ValueError("cost_per_1k must be non-negative.")
                    route.cost_per_1k = cost_per_1k
                if tags is not None:
                    route.tags = list(tags)
                self._routes.sort(key=lambda r: r.priority, reverse=True)
                logger.debug("Route %r updated", name)
                return
        raise RouteError(f"Route {name!r} is not registered.")

    def remove_route(self, name: str) -> bool:
        """Remove a route by name.

        Returns
        -------
        bool
            ``True`` if the route was found and removed, ``False`` otherwise.
        """
        before = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        removed = len(self._routes) < before
        if removed:
            self._stats.pop(name, None)
            logger.debug("Route %r removed", name)
        return removed

    def clear_routes(self) -> None:
        """Remove all registered routes and reset statistics."""
        self._routes.clear()
        self._stats.clear()
        logger.debug("All routes cleared")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, prompt: str) -> str:
        """Return the model name to use for *prompt*.

        Parameters
        ----------
        prompt:
            Raw user prompt text.

        Returns
        -------
        str
            Name of the matched model, or :attr:`default` if no route matched.
        """
        route = self._match(prompt)
        return route.model if route else self._default

    def explain(self, prompt: str) -> Dict[str, Any]:
        """Explain the routing decision for *prompt*.

        Returns
        -------
        dict
            Keys: ``model``, ``reason``, ``priority``, ``matched``,
            ``tags``, ``cost_per_1k``.
        """
        route = self._match(prompt)
        if route:
            return {
                "model": route.model,
                "reason": route.name,
                "priority": route.priority,
                "matched": True,
                "tags": list(route.tags),
                "cost_per_1k": route.cost_per_1k,
            }
        return {
            "model": self._default,
            "reason": "default (no route matched)",
            "priority": -1,
            "matched": False,
            "tags": [],
            "cost_per_1k": self._default_cost,
        }

    def resolve_with_cost(self, prompt: str) -> Tuple[str, float]:
        """Return *(model, cost_per_1k)* for *prompt*.

        Returns
        -------
        tuple[str, float]
            Model name and estimated cost per 1 000 tokens.
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

    def get_route(self, name: str) -> Optional[Route]:
        """Return the route with *name*, or ``None`` if not found."""
        for route in self._routes:
            if route.name == name:
                return route
        return None

    def routes_by_tag(self, tag: str) -> List[Route]:
        """Return routes whose tag list contains *tag*."""
        return [r for r in self._routes if tag in r.tags]

    def statistics(self) -> Dict[str, int]:
        """Return a snapshot mapping route name → number of times matched."""
        return dict(self._stats)

    @property
    def default(self) -> str:
        """The fallback model used when no route matches."""
        return self._default

    @property
    def route_count(self) -> int:
        """Number of currently registered routes."""
        return len(self._routes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match(self, prompt: str) -> Optional[Route]:
        for route in self._routes:
            try:
                if route.condition(prompt):
                    self._stats[route.name] = self._stats.get(route.name, 0) + 1
                    return route
            except Exception:
                logger.warning(
                    "Condition for route %r raised an exception; skipping.",
                    route.name,
                )
                continue
        return None
