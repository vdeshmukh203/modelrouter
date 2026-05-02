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
date: 2 May 2026
bibliography: paper.bib
---

# Summary

`modelrouter` is a Python library for selecting an appropriate large language model (LLM) [@brown2020language] for each request based on configurable, declarative rules.  Routes are evaluated in priority order; the first condition that matches the prompt determines the target model.  The library includes cost-estimation helpers to support budget-aware dispatch, a rich explainability API that records the matched route name, priority, tags, and per-route match counts at runtime, and a Tkinter-based graphical interface for interactive route management and prompt testing.  Routing logic is kept entirely separate from application code, improving reproducibility and auditability of multi-model LLM systems.

# Statement of need

Modern LLM applications routinely combine multiple models: a low-cost model for simple classification or extraction, and a frontier model [@wei2022emergent] for difficult reasoning or long-horizon planning.  Deciding which model handles which request is currently handled in ad hoc ways — inline conditionals scattered across application code, hand-rolled priority queues, or external proxy services that require network round-trips.  None of these approaches offers systematic explainability, systematic cost tracking, or a path to declarative configuration.

`modelrouter` addresses this gap.  A single `Modelrouter` instance holds an ordered list of `Route` objects, each of which pairs a callable condition with a model name, an optional priority, an optional cost estimate, and a set of string tags.  The condition receives the raw prompt text; any Python expression that returns a Boolean is valid, from a simple keyword check to a call into a local classifier.  This design follows the *separation of concerns* principle [@martin2003agile]: routing policy is expressed once, in one place, and the rest of the codebase calls `router.resolve(prompt)` without knowing which model is chosen.

Existing work closest to `modelrouter` includes FrugalGPT [@chen2023frugalgpt], which learns routing policies from data, and routing layers built into commercial LLM-proxy products such as LiteLLM [@litellm2024] and RouteLLM [@ong2024routellm].  `modelrouter` occupies a complementary niche: it is a *library*, not a service; it requires no training data; it imposes no latency overhead from network calls; and its rules are transparent Python expressions that can be version-controlled, tested, and audited alongside application code.

# Implementation

`modelrouter` is implemented in a single pure-Python module (`router.py`, ~230 lines) with no runtime dependencies beyond the standard library.  The `Route` dataclass captures the routing rule; `Modelrouter` maintains routes sorted by descending priority and provides the public API summarised below.

**Resolution.**  `resolve(prompt)` iterates through routes in priority order and returns the model name of the first matching route.  Exceptions raised by a condition (e.g. a malformed regex or a failed network call inside a custom predicate) are caught, logged, and skipped, so a single faulty route cannot prevent the router from falling back to a working route or the default model.

**Explainability.**  `explain(prompt)` returns a dictionary containing the chosen model, the matched route name, its priority, its tags, its cost estimate, and a boolean `matched` flag.  When no route matches, the dictionary records the reason as `"default (no route matched)"`.  This makes routing decisions transparent and easy to log in production systems.

**Statistics.**  The router accumulates per-route match counts in a lightweight in-memory dictionary (`statistics()`), enabling operators to identify over- or under-used routes without external tooling.

**Validation.**  Route fields are validated at construction time: names and model identifiers must be non-empty strings, conditions must be callable, and numeric fields must be non-negative.  Duplicate route names raise `RouteError` at `add_route` time rather than silently overwriting an existing rule.

**Graphical interface.**  `modelrouter.gui` provides a `RouterGUI` class built on Python's built-in `tkinter` library.  The interface presents a live route table, a form-based route builder with a menu-driven condition selector (keyword match, length threshold, regular expression, etc.), a freetext prompt testing area, an instant routing decision display, and a per-route match-count bar chart.  The condition builder avoids `eval()` by mapping GUI-selected condition types to pre-validated lambda factories, preserving safety without limiting expressiveness for the most common use cases.

# Acknowledgements

This work was developed independently.  The author thanks the open-source community whose tooling made this project possible.

# References
