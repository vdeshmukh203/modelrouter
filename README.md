# modelrouter

**Route LLM requests to the right model based on configurable, priority-ordered rules.**

`modelrouter` is a lightweight, dependency-free Python library for declaratively
selecting the appropriate large language model (LLM) for each request.  Routes
specify match conditions and a target model; routing policy lives separately from
application code, making it easy to audit, test, and update.

## Installation

```bash
pip install modelrouter
```

Requires Python 3.9 or later.  No external dependencies.

## Quick start

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini")
router.add_route("code",  "gpt-4o",            lambda p: "```" in p,    priority=10)
router.add_route("long",  "claude-3-5-sonnet", lambda p: len(p) > 2000, priority=5)

model = router.resolve("Write a ```python``` snippet")
# "gpt-4o"

model = router.resolve("hello")
# "gpt-4o-mini"  (default — no route matched)
```

## Core concepts

| Concept | Description |
|---------|-------------|
| **Route** | A named rule: a target model, a condition callable, a priority, optional cost and tags. |
| **Priority** | Routes are evaluated highest-priority first; the first match wins. |
| **Default** | Returned when no route matches. |
| **Condition** | Any Python callable `(prompt: str) -> bool`. |

## API reference

### `Modelrouter(default, default_cost_per_1k)`

```python
router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
```

### `add_route(name, model, condition, *, priority, cost_per_1k, tags)`

```python
router.add_route(
    "summarise",
    "gpt-4o",
    lambda p: p.lower().startswith("summarise"),
    priority=8,
    cost_per_1k=0.005,
    tags=["prod", "expensive"],
)
```

Raises `DuplicateRouteError` if a route with the same name already exists.

### `update_route(name, *, model, condition, priority, cost_per_1k, tags)`

Update individual fields of an existing route in-place.

```python
router.update_route("summarise", model="claude-3-5-sonnet", priority=12)
```

### `remove_route(name) -> bool`

Returns `True` if the route was found and removed.

### `clear()`

Remove all registered routes.

### `resolve(prompt) -> str`

Return the model name for the given prompt.

### `explain(prompt) -> dict`

Return a structured routing decision:

```python
{
    "model":       "gpt-4o",
    "matched":     True,
    "reason":      "summarise",
    "priority":    8,
    "cost_per_1k": 0.005,
    "tags":        ["prod", "expensive"],
}
```

### `resolve_with_cost(prompt) -> (str, float)`

Return `(model_name, cost_per_1k_tokens)`.

### `routes() -> list[Route]`

Snapshot of all routes in priority order.

### `routes_by_tag(tag) -> list[Route]`

Filter routes by tag.

### Container protocol

```python
len(router)        # number of registered routes
"code" in router   # True if a route named "code" exists
```

## GUI

`modelrouter` ships with an optional Tkinter-based desktop GUI for
interactively configuring routes and testing routing decisions.

**Launch from the command line** (after `pip install modelrouter`):

```bash
modelrouter-gui
```

**Or from Python:**

```python
from modelrouter.gui import launch
launch()
```

The GUI lets you:
- Add, edit, and remove routes with a form dialog.
- Set the default model.
- Enter a test prompt and inspect the resolved model, full decision explanation,
  and cost estimate.

## Error handling

| Exception | When raised |
|-----------|-------------|
| `DuplicateRouteError` | `add_route()` called with a name that already exists |
| `KeyError` | `update_route()` called with an unknown name |
| `ValueError` | Empty name/model string, or empty default |

Exceptions thrown inside a condition callable are silently caught and that
route is skipped, so a faulty condition never blocks routing.

## Contributing

Bug reports and pull requests are welcome on the
[GitHub repository](https://github.com/vdeshmukh203/modelrouter).
Please add a test for any new behaviour.

## License

MIT — see `LICENSE`.
