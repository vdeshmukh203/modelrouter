# modelrouter

[![CI](https://github.com/vdeshmukh203/modelrouter/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/modelrouter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/modelrouter)](https://pypi.org/project/modelrouter/)
[![Python](https://img.shields.io/pypi/pyversions/modelrouter)](https://pypi.org/project/modelrouter/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**modelrouter** is a lightweight Python library for routing large language model (LLM) requests to the most appropriate model based on configurable, declarative rules.  It lets you combine multiple models — a cheap model for simple tasks, a frontier model for complex reasoning — while keeping all routing logic in one place, separate from application code.

---

## Features

- **Priority-based routing** — routes are evaluated in descending priority order; the first match wins
- **Cost-aware dispatch** — attach a cost estimate to each route and retrieve it alongside the chosen model
- **Explainability** — `explain()` returns the matched route name, priority, tags and cost for every decision
- **Tag filtering** — group and query routes by arbitrary string labels
- **Match statistics** — track how often each route is selected at runtime
- **Resilient conditions** — exceptions raised by a condition are silently skipped and the next route is tried
- **Tkinter GUI** — a built-in graphical interface for managing routes and testing prompts interactively
- **Zero runtime dependencies** — only the Python standard library

---

## Installation

```bash
pip install modelrouter
```

For development (includes linting, type-checking, and test tools):

```bash
pip install "modelrouter[dev]"
```

`modelrouter` requires Python 3.9 or later.

---

## Quick start

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini")

# Routes are evaluated highest-priority-first
router.add_route(
    name="code",
    model="gpt-4o",
    condition=lambda p: "```" in p,
    priority=10,
    cost_per_1k=0.005,
    tags=["prod"],
)
router.add_route(
    name="long",
    model="claude-3-5-sonnet-20241022",
    condition=lambda p: len(p) > 2_000,
    priority=5,
    cost_per_1k=0.003,
)

# Basic resolution
model = router.resolve("Write me a ```python``` script")
print(model)  # "gpt-4o"

# Cost-aware resolution
model, cost = router.resolve_with_cost("Short question")
print(model, cost)  # "gpt-4o-mini"  0.0

# Explainability
decision = router.explain("Write me a ```python``` script")
# {
#   "model": "gpt-4o",
#   "reason": "code",
#   "priority": 10,
#   "matched": True,
#   "tags": ["prod"],
#   "cost_per_1k": 0.005,
# }
```

---

## API reference

### `Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.0)`

Create a new router.

| Parameter | Type | Description |
|---|---|---|
| `default` | `str` | Model returned when no route matches |
| `default_cost_per_1k` | `float` | Cost (USD) per 1 000 tokens for the default model |

---

#### `add_route(name, model, condition, *, priority=0, cost_per_1k=0.0, tags=None)`

Register a routing rule.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Unique identifier for this route |
| `model` | `str` | LLM model name to dispatch to |
| `condition` | `Callable[[str], bool]` | Predicate receiving the raw prompt |
| `priority` | `int ≥ 0` | Higher values are evaluated first |
| `cost_per_1k` | `float ≥ 0` | Estimated USD cost per 1 000 tokens |
| `tags` | `list[str]` | Arbitrary labels for grouping / filtering |

Raises `RouteError` if `name` is already registered.

---

#### `update_route(name, *, model=None, condition=None, priority=None, cost_per_1k=None, tags=None)`

Update one or more fields of an existing route in-place.  Only keyword arguments that are not `None` are changed.  Raises `RouteError` if the route does not exist.

---

#### `remove_route(name) → bool`

Remove a route by name.  Returns `True` if found and removed.

---

#### `clear_routes()`

Remove all routes and reset match statistics.

---

#### `resolve(prompt) → str`

Return the model name to use for `prompt`.

---

#### `explain(prompt) → dict`

Return a dict describing the routing decision:

```python
{
    "model": "gpt-4o",
    "reason": "code",       # route name, or "default (no route matched)"
    "priority": 10,
    "matched": True,
    "tags": ["prod"],
    "cost_per_1k": 0.005,
}
```

---

#### `resolve_with_cost(prompt) → tuple[str, float]`

Return `(model, cost_per_1k)` for `prompt`.

---

#### `get_route(name) → Route | None`

Return the `Route` object with the given name, or `None`.

---

#### `routes() → list[Route]`

Return all registered routes sorted by descending priority.

---

#### `routes_by_tag(tag) → list[Route]`

Return routes whose tag list contains `tag`.

---

#### `statistics() → dict[str, int]`

Return a snapshot mapping route name → number of times it has been matched.

---

#### `route_count` *(property)*

Number of currently registered routes.

---

#### `default` *(property)*

The fallback model name.

---

### `Route` dataclass

| Field | Type | Default |
|---|---|---|
| `name` | `str` | — |
| `model` | `str` | — |
| `condition` | `Callable[[str], bool]` | — |
| `priority` | `int` | `0` |
| `cost_per_1k` | `float` | `0.0` |
| `tags` | `list[str]` | `[]` |

---

### `RouteError`

Raised when a routing configuration is invalid (e.g. duplicate route name, missing route on update).

---

## GUI

`modelrouter` ships with a Tkinter-based graphical interface for managing routes and testing prompts without writing code.

**Launch from Python:**

```python
from modelrouter import Modelrouter
from modelrouter.gui import launch

router = Modelrouter(default="gpt-4o-mini")
router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
launch(router)
```

**Launch from the command line:**

```bash
python -m modelrouter.gui
```

The GUI provides:

- A **route table** showing all registered routes (name, model, priority, cost, tags)
- An **Add Route** form with a safe condition builder (contains, regex, length thresholds, etc.) — no `eval()` used
- A **Test Prompt** panel with a plain-text input and an instant routing decision display
- A **Match Statistics** panel showing a bar chart of per-route match counts

Tkinter is bundled with most Python distributions.  On some Linux systems it can be installed with `sudo apt-get install python3-tk`.

---

## Advanced patterns

### Loading routes from configuration

```python
import json
from modelrouter import Modelrouter

ROUTE_DEFS = [
    {"name": "code",  "model": "gpt-4o",        "keyword": "```",  "priority": 10},
    {"name": "long",  "model": "claude-3-5-sonnet-20241022", "min_len": 2000, "priority": 5},
]

router = Modelrouter(default="gpt-4o-mini")
for r in ROUTE_DEFS:
    if "keyword" in r:
        kw = r["keyword"]
        cond = lambda p, k=kw: k in p
    else:
        n = r["min_len"]
        cond = lambda p, n=n: len(p) > n
    router.add_route(r["name"], r["model"], cond, priority=r["priority"])
```

### Inspecting routing decisions in production

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # modelrouter logs at DEBUG level

decision = router.explain(prompt)
if not decision["matched"]:
    logging.warning("No route matched; using default model %s", decision["model"])
```

### Tag-based A/B routing

```python
router.add_route("v1", "gpt-4o",    lambda p: True, priority=5, tags=["stable"])
router.add_route("v2", "gpt-4-turbo", lambda p: True, priority=5, tags=["canary"])

stable_routes = router.routes_by_tag("stable")
```

---

## Development

```bash
git clone https://github.com/vdeshmukh203/modelrouter.git
cd modelrouter
pip install -e ".[dev]"
pytest                      # run tests
ruff check src/ tests/      # lint
mypy src/modelrouter/       # type-check (excludes gui.py)
```

---

## Contributing

Contributions are welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## Citation

If you use `modelrouter` in academic work, please cite:

```bibtex
@software{deshmukh2026modelrouter,
  author  = {Deshmukh, Vaibhav},
  title   = {modelrouter: condition-based routing for large language model requests},
  year    = {2026},
  url     = {https://github.com/vdeshmukh203/modelrouter},
}
```

A machine-readable citation is also available in [CITATION.cff](CITATION.cff).

---

## License

MIT — see [LICENSE](LICENSE).
