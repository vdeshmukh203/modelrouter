# modelrouter

Route LLM requests to appropriate models based on configurable, priority-ordered rules.

```
pip install modelrouter
```

## Quick start

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
router.add_route("code",  "gpt-4o",            lambda p: "```" in p,   priority=20, cost_per_1k=0.005)
router.add_route("long",  "claude-3-5-sonnet", lambda p: len(p) > 2000, priority=10, cost_per_1k=0.003)

model = router.resolve("Write me a ```python``` script")
print(model)  # "gpt-4o"

model, cost = router.resolve_with_cost("Short question")
print(model, cost)  # "gpt-4o-mini" 0.00015

print(router.explain("Write me a ```python``` script"))
# {'model': 'gpt-4o', 'reason': 'code', 'priority': 20,
#  'matched': True, 'cost_per_1k': 0.005, 'tags': []}
```

## API reference

| Method | Description |
|---|---|
| `add_route(name, model, condition, priority=0, cost_per_1k=0.0, tags=None)` | Register or replace a route |
| `remove_route(name) → bool` | Remove a route; returns `True` if found |
| `clear_routes()` | Remove all routes |
| `set_default(model, cost_per_1k=0.0)` | Update the fallback model |
| `resolve(prompt) → str` | Return the target model |
| `explain(prompt) → dict` | Describe the routing decision |
| `resolve_with_cost(prompt) → (str, float)` | Model and cost estimate |
| `routes() → list[Route]` | All routes in priority order |
| `routes_by_tag(tag) → list[Route]` | Filter by tag |

## Graphical interface

Launch the desktop GUI (requires `tkinter`, included with most Python distributions):

```
modelrouter-gui
```

or from Python:

```python
from modelrouter.gui import launch
launch()          # start with a blank router
launch(router)    # edit an existing router
```

The GUI has two tabs:

- **Routes** — add, update, and remove routes; condition expressions are written as the body of `lambda p: …` (e.g. `"code" in p`, `len(p) > 2000`).
- **Test Prompt** — enter free text and inspect the full routing explanation.

## License

MIT
