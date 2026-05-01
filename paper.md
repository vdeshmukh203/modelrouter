---
title: 'modelrouter: condition-based routing for large language model requests'
tags:
  - Python
  - large language models
  - routing
  - MLOps
  - cost optimisation
authors:
  - name: Vaibhav Deshmukh
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 25 April 2026
bibliography: paper.bib
---

# Summary

`modelrouter` is a lightweight Python library for dispatching large language
model (LLM) requests to the most appropriate model based on declarative,
priority-ordered routing rules [@brown2020language].  Each route associates a
match condition — a plain Python callable — with a target model identifier,
an optional priority, a cost-per-1 000-token estimate, and an arbitrary set
of string tags.  The router evaluates conditions in descending priority order
and returns the first matching model, falling back to a configurable default.
A companion graphical user interface (GUI) built with the standard-library
`tkinter` module lets users configure routes and test prompts interactively
without writing any code.

# Statement of need

Modern LLM-powered applications routinely combine several models: a small,
inexpensive model for classification or intent detection, a mid-tier model for
summarisation, and a frontier model for complex reasoning [@ouyang2022training].
Hardcoding branching logic directly in application code couples routing
decisions to business logic, impedes testing, and makes cost profiling
difficult.

Several proxy servers (e.g.\ LiteLLM, OpenRouter) address routing at the HTTP
gateway level but require running a persistent service, introduce network hops,
and couple applications to a specific deployment topology.  `modelrouter`
instead operates as an in-process Python library: routing decisions are made
locally, there is no daemon to manage, and the full Python type system is
available for writing conditions.

Mixture-of-experts architectures [@shazeer2017outrageously] inspire a
similar intuition — routing tokens to specialised sub-networks — applied here
at the API call level.  `modelrouter` makes the same principle accessible to
application developers through a minimal, dependency-free interface.

# Design and implementation

`modelrouter` is a pure Python package with no runtime dependencies beyond the
standard library, which keeps installation simple and avoids version conflicts
in constrained environments.

The library exposes two public types:

**`Route`** — a `dataclasses.dataclass` holding the route `name`, `model`
identifier, `condition` callable, integer `priority`, `cost_per_1k` float, and
`tags` list.  The dataclass is intentionally shallow: conditions are arbitrary
Python callables, so any logic expressible in Python — regular expressions,
token-count heuristics, metadata inspection — can be used as a match
criterion.

**`Modelrouter`** — the router class.  It maintains a sorted list of `Route`
objects and exposes the following public API:

| Method | Description |
|---|---|
| `add_route(name, model, condition, …)` | Register or replace a route |
| `remove_route(name)` | Remove a route by name |
| `clear_routes()` | Remove all routes |
| `set_default(model, …)` | Change the fallback model |
| `resolve(prompt)` | Return the target model for a prompt |
| `explain(prompt)` | Return a dict describing the routing decision |
| `resolve_with_cost(prompt)` | Return `(model, cost_per_1k)` |
| `routes()` | Return all routes in priority order |
| `routes_by_tag(tag)` | Filter routes by tag |

Priority is an integer; higher values are evaluated first.  If a condition
callable raises an exception the route is silently skipped (and a debug-level
log message is emitted), so a faulty condition degrades gracefully without
breaking the entire dispatch chain.

Input validation raises `ValueError` or `TypeError` for empty model names,
empty route names, or non-callable conditions, surfacing misconfiguration
at the earliest possible point.

# Graphical user interface

The optional `modelrouter.gui` module provides a `tkinter`-based desktop
application that ships with the package and requires no additional
dependencies.  It can be launched from the command line:

```
modelrouter-gui
```

or programmatically:

```python
from modelrouter.gui import launch
launch(router=my_router)
```

The GUI has two tabs.  The *Routes* tab lists all registered routes in a
sortable table and provides a form for adding, updating, and removing routes.
Condition expressions are entered as the body of a `lambda p: …` expression
(e.g. `"code" in p` or `len(p) > 2000`), compiled with `eval` in a
builtins-restricted namespace to limit the attack surface.  The *Test Prompt*
tab accepts free-text input and displays the full `explain()` output —
matched model, reason, priority, cost estimate, and tags — making it easy to
verify routing rules interactively.

# Example usage

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
router.add_route("code",  "gpt-4o",            lambda p: "```" in p,
                 priority=20, cost_per_1k=0.005)
router.add_route("long",  "claude-3-5-sonnet", lambda p: len(p) > 2000,
                 priority=10, cost_per_1k=0.003)
router.add_route("cheap", "gpt-4o-mini",       lambda p: True,
                 priority=0,  cost_per_1k=0.00015, tags=["budget"])

model, cost = router.resolve_with_cost("Write me a ```python``` script")
# model == "gpt-4o", cost == 0.005

explanation = router.explain("Hello!")
# {'model': 'gpt-4o-mini', 'reason': 'cheap', 'priority': 0,
#  'matched': True, 'cost_per_1k': 0.00015, 'tags': ['budget']}
```

# Testing

The test suite uses `pytest` and covers default resolution, priority
ordering, tag filtering, cost estimation, duplicate route replacement,
input validation, the `explain()` output fields, `__repr__`, `__len__`, and
graceful handling of faulty condition callables.  Tests are executed
automatically on every push via GitHub Actions.

# Acknowledgements

This work was developed independently.  The author thanks the open-source
community whose tooling made this project possible.

# References
