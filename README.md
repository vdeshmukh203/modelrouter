# modelrouter

Route LLM requests to appropriate models based on configurable, priority-ordered rules.

[![CI](https://github.com/vdeshmukh203/modelrouter/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/modelrouter/actions)

## Installation

```bash
pip install modelrouter
```

Python 3.9+ required. No external dependencies.

## Quick start

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
router.add_route("code",  "gpt-4o",           lambda p: "```" in p,     priority=10, cost_per_1k=0.005)
router.add_route("long",  "claude-3-5-sonnet", lambda p: len(p) > 2000, priority=5,  cost_per_1k=0.003)

# Resolve to a model name
model = router.resolve("Write me a ```python``` script")
print(model)  # "gpt-4o"

# Explain the routing decision
info = router.explain("Hello!")
# {"model": "gpt-4o-mini", "reason": "default (no route matched)", "priority": -1, "matched": False}

# Get model + estimated cost together
model, cost = router.resolve_with_cost("Write me a ```python``` script")
print(model, cost)  # "gpt-4o" 0.005
```

## API overview

### `Modelrouter(default, default_cost_per_1k)`

| Method | Returns | Description |
|---|---|---|
| `add_route(name, model, condition, *, priority, cost_per_1k, tags)` | `None` | Register a rule; raises `ValueError` for duplicate names |
| `remove_route(name)` | `bool` | Remove a rule by name; `True` if found |
| `clear()` | `None` | Remove all registered routes |
| `resolve(prompt)` | `str` | Selected model name |
| `explain(prompt)` | `dict` | Decision dict: `model`, `reason`, `priority`, `matched` |
| `resolve_with_cost(prompt)` | `(str, float)` | Model name + cost per 1k tokens |
| `routes()` | `List[Route]` | All routes, highest priority first |
| `routes_by_tag(tag)` | `List[Route]` | Routes carrying `tag` |
| `len(router)` | `int` | Number of registered routes |

### `Route` fields

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique identifier |
| `model` | `str` | Target LLM name |
| `condition` | `Callable[[str], bool]` | Match predicate |
| `priority` | `int ≥ 0` | Evaluation order (higher = first) |
| `cost_per_1k` | `float ≥ 0` | Estimated USD cost per 1 000 tokens |
| `tags` | `List[str]` | Organisational labels |

## Priority and ordering

Routes are evaluated highest-priority first. The first route whose condition
returns `True` wins. If no route matches, `default` is used.

```python
router.add_route("urgent", "gpt-4o",      lambda p: "urgent" in p, priority=20)
router.add_route("code",   "gpt-4o",      lambda p: "```" in p,    priority=10)
router.add_route("cheap",  "gpt-4o-mini", lambda p: True,           priority=0)
```

## Tags

```python
router.add_route("summarise", "gpt-4o-mini", lambda p: "summarise" in p, tags=["prod", "cheap"])
prod_routes = router.routes_by_tag("prod")
```

## Error resilience

If a condition raises an exception it is logged at `DEBUG` level and the route
is skipped, so a bad condition never breaks production traffic.

## Interactive GUI

A Tkinter GUI ships with the package. Launch it with:

```bash
modelrouter-gui
```

The GUI lets you add and remove routes interactively, choose from seven
condition types (substring match, prefix/suffix, length thresholds, regex,
custom Python expression), and test prompts to see routing decisions and cost
estimates in real time.

> **Note**: Tkinter is part of Python's standard library but may require a
> separate system package on some Linux distributions
> (`sudo apt install python3-tk` on Debian/Ubuntu).

## Citation

If you use `modelrouter` in published research, please cite the accompanying
JOSS paper:

```
@article{deshmukh2026modelrouter,
  title   = {modelrouter: condition-based routing for large language model requests},
  author  = {Deshmukh, Vaibhav},
  journal = {Journal of Open Source Software},
  year    = {2026}
}
```

## License

MIT
