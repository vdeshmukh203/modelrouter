---
title: 'modelrouter: condition-based routing for large language model requests'
tags:
  - Python
  - large language models
  - routing
  - MLOps
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

`modelrouter` is a Python library for selecting an appropriate large language
model (LLM) for each request based on user-defined, priority-ordered conditions.
As applications increasingly combine multiple LLMs — a lightweight model for
straightforward queries, a frontier model for complex reasoning — routing logic
tends to accumulate inside application code as chains of `if`/`else` branches,
making it hard to test, audit, or reuse.  `modelrouter` externalises this logic
into declarative *Route* objects.  Each route pairs a callable condition
(e.g. "prompt contains a code block", "prompt length exceeds 2 000 tokens")
with a target model name and an optional cost estimate.  Routes are evaluated
in descending priority order; the first match wins, and a configurable default
model is used when no route fires [@brown2020language].

# Statement of need

Modern LLM applications routinely dispatch requests to several different
models.  Cheap models handle classification or summarisation; high-capability
frontier models handle multi-step reasoning or code generation.  Without
a structured routing layer this dispatch logic is typically embedded inside
application handlers, making it difficult to:

1. **Audit** which model handled which class of request.
2. **Test** routing rules in isolation from the rest of the application.
3. **Optimise costs** by redirecting traffic to less expensive models where
   capability permits.
4. **Share** routing policies across multiple services or experiments.

Existing libraries that wrap LLM APIs (e.g. LangChain, LlamaIndex) include
router abstractions, but they are tightly coupled to those frameworks' agent
and chain primitives [@chase2022langchain].  `modelrouter` is intentionally
framework-agnostic: it accepts any prompt string and returns a model name
string, integrating without modification into any Python application or
framework.

# Functionality

## Core abstractions

**`Route`** is a dataclass with six fields:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique identifier |
| `model` | `str` | Target model name |
| `condition` | `Callable[[str], bool]` | Match predicate |
| `priority` | `int` | Evaluation order (higher = first, ≥ 0) |
| `cost_per_1k` | `float` | Estimated USD cost per 1 000 tokens |
| `tags` | `List[str]` | Organisational labels |

**`Modelrouter`** maintains an ordered list of routes and exposes the
following public API:

- `add_route(name, model, condition, *, priority, cost_per_1k, tags)` —
  register a rule; raises `ValueError` for duplicate names or invalid values.
- `remove_route(name) -> bool` — deregister a rule by name.
- `clear()` — remove all registered routes.
- `resolve(prompt) -> str` — return the selected model name.
- `explain(prompt) -> dict` — return a dict with keys `model`, `reason`,
  `priority`, and `matched`, enabling transparent decision logging.
- `resolve_with_cost(prompt) -> (str, float)` — return model and estimated
  cost simultaneously, supporting budget-aware dispatch.
- `routes() -> List[Route]` — introspect the full route table.
- `routes_by_tag(tag) -> List[Route]` — filter routes by label.

## Fault tolerance

If a condition callable raises an exception during evaluation, the exception
is caught, logged at `DEBUG` level, and the route is skipped.  This prevents
a malformed condition from breaking production traffic.

## Interactive GUI

An optional Tkinter GUI (`modelrouter-gui`) ships with the package and allows
practitioners to add, remove, and test routes interactively without writing
code.  Routes are created via a form that supports seven condition types:
substring match, prefix/suffix match, length thresholds, regular expressions,
and arbitrary Python expressions.  Resolved routing decisions and cost
estimates are displayed in real time.

## Example

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
router.add_route(
    "code", "gpt-4o",
    lambda p: "```" in p,
    priority=10, cost_per_1k=0.005,
)
router.add_route(
    "long", "claude-3-5-sonnet",
    lambda p: len(p) > 2000,
    priority=5, cost_per_1k=0.003,
)

model = router.resolve("Write me a ```python``` script")
# → "gpt-4o"

info = router.explain("Hello!")
# → {"model": "gpt-4o-mini", "reason": "default (no route matched)",
#    "priority": -1, "matched": False}
```

# Related work

LangChain [@chase2022langchain] and LlamaIndex provide routing primitives but
require adoption of their broader abstractions.  Semantic routing libraries
such as SemanticRouter [@aurelio2024semanticrouter] classify prompts using
embedding similarity rather than explicit predicates, trading determinism for
flexibility.  `modelrouter` occupies a complementary niche: fully
deterministic, zero-dependency, framework-independent rule evaluation with
built-in cost accounting.  The transformer architecture underlying modern LLMs
[@vaswani2017attention] makes capability heterogeneity between models large
enough that careful routing can yield substantial cost savings with no quality
regression on the majority of requests.

# Acknowledgements

This work was developed independently.  The author thanks the open-source
community whose tooling made this project possible.

# References
