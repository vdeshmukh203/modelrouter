---
title: 'modelrouter: condition-based routing for large language model requests'
tags:
  - Python
  - large language models
  - routing
  - MLOps
  - cost optimization
authors:
  - name: Vaibhav Deshmukh
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 27 April 2026
bibliography: paper.bib
---

# Summary

`modelrouter` is a Python library for selecting the most appropriate large
language model (LLM) [@brown2020language] for each request based on
configurable, priority-ordered conditions.  Each *route* pairs a Boolean
condition callable with a target model name; routes are evaluated in descending
priority order and the first matching route determines which model is called.
When no route matches, a configurable default model is used.  The library
additionally provides per-route cost estimates, tag-based filtering, and a
structured explanation of every routing decision.  A desktop GUI built on the
Python standard-library `tkinter` module allows developers to configure routes
interactively and test routing decisions without writing code.

# Statement of need

Modern LLM applications routinely combine multiple models: a fast, low-cost
model for simple classification or retrieval-augmented generation, a frontier
model for difficult multi-step reasoning [@vaswani2017attention], and
specialised models for code generation or tool use.  Selecting the right model
for each request is a policy decision that is frequently embedded directly in
application code as a series of `if`/`elif` branches.  This approach makes the
routing policy difficult to audit, test, or update independently of the
application logic.

Several commercial services and research systems address this at the
infrastructure level, either by training a lightweight router model on
preference data [@ong2024routellm] or by cascading queries to progressively
more capable models until a quality threshold is met [@chen2023frugalgpt].
`modelrouter` targets the complementary, application-level problem: providing a
minimal, dependency-free, declarative configuration model that works with *any*
provider API and does not require training data or a network service.  Its
intended audience is developers who need reproducible, testable routing policies
in Python applications without adding infrastructure complexity.

# Design and implementation

The library is implemented in a single module (`modelrouter/router.py`) with no
runtime dependencies beyond the Python standard library.  The public interface
centres on two objects:

**`Route`** — a `dataclass` holding a unique name, a target model identifier, a
condition callable `(prompt: str) -> bool`, an integer priority, an optional
cost-per-1k-token estimate, and an optional list of string tags.

**`Modelrouter`** — the router itself.  It maintains a priority-sorted list of
`Route` objects and exposes the following core operations:

- `add_route` / `remove_route` / `update_route` / `clear` — route lifecycle
  management.  `add_route` raises `DuplicateRouteError` on name collision.
- `resolve(prompt)` — returns the model name for a prompt.
- `explain(prompt)` — returns a structured dict describing which route matched,
  its priority, cost estimate, and tags.
- `resolve_with_cost(prompt)` — convenience wrapper returning
  `(model, cost_per_1k)`.
- `routes_by_tag(tag)` — filter the route list by tag for introspection.

The matching algorithm iterates routes in priority order and returns the first
whose condition evaluates to `True`.  Exceptions raised inside a condition are
silently caught and that route is skipped, so a misconfigured condition does not
block routing.  The container protocol (`__len__`, `__contains__`) and `__repr__`
on both classes support debugging and scripted introspection.

A typical usage pattern is shown below:

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
router.add_route("code",  "gpt-4o",            lambda p: "```" in p,    priority=10, cost_per_1k=0.005)
router.add_route("long",  "claude-3-5-sonnet", lambda p: len(p) > 2000, priority=5,  cost_per_1k=0.003)

model = router.resolve("Explain ```recursion``` with an example")
# model == "gpt-4o"

info = router.explain("hello")
# {'model': 'gpt-4o-mini', 'matched': False, 'reason': 'default (no route matched)',
#  'priority': -1, 'cost_per_1k': 0.00015, 'tags': []}
```

# Quality controls

The library ships with a `pytest` test suite that covers: basic resolution and
fallback to default; priority ordering; route addition, removal, update, and
clearing; explanation output including cost and tags; cost-aware resolution;
tag-based filtering; resilience to exceptions in condition callables; and all
`__len__`, `__contains__`, and `__repr__` behaviours.  Continuous integration
runs the test suite on Python 3.11 via GitHub Actions on every push and pull
request.  Input validation (empty names, duplicate route names, empty default)
raises typed exceptions with descriptive messages.

# Graphical user interface

The optional `modelrouter.gui` module provides a two-panel `tkinter` desktop
application.  The left panel displays the current route table with controls to
add, edit, remove, or clear routes through a form dialog; conditions are entered
as Python expressions using `p` as the prompt variable and are validated before
acceptance.  The right panel accepts a test prompt and displays the result of
`resolve`, `explain`, or `resolve_with_cost` in a read-only text area.  The GUI
requires no additional packages beyond the Python standard library and is
launched via the `modelrouter-gui` console entry point installed by `pip`.

# Acknowledgements

This work was developed independently.  The author thanks the open-source
community whose tooling made this project possible.

# References
