# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-04

### Added
- `update_route()` method for in-place modification of an existing route's
  fields without removing and re-adding it.
- `clear()` method to remove all registered routes at once.
- `__len__`, `__contains__`, and `__iter__` dunder methods so that
  `len(router)`, `"name" in router`, and `for route in router` work
  naturally.
- `default_cost` property to expose the configured default cost per 1 000
  tokens.
- `Route` is now exported from the top-level package (`from modelrouter
  import Route`) for use in type annotations.
- `modelrouter-gui` console script: a zero-dependency tkinter desktop GUI for
  building route tables, managing default models, and testing prompt routing
  interactively.
- `cost_per_1k` and `tags` are now included in the dict returned by
  `explain()`, making the output self-contained and consistent with the full
  route definition.
- `priority` is now `None` (not ``-1``) in the `explain()` dict when no route
  matches, so callers can distinguish "not set" from "set to zero".
- Structured logging via `logging.getLogger(__name__)` for route events and
  resolution decisions.
- Comprehensive docstrings on all public classes and methods (NumPy/Google
  hybrid style).
- Extended test suite covering all new methods, dunder methods, properties,
  and edge cases.

### Fixed
- `explain()` previously omitted `cost_per_1k` and `tags` from its return
  value, making it inconsistent with the information carried by a `Route`.
- `explain()` returned the magic number ``-1`` for `priority` when falling
  back to the default model; it now returns `None`.

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
