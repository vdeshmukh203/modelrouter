# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-01

### Added
- `Modelrouter.clear_routes()` — remove all registered routes at once.
- `Modelrouter.set_default(model, cost_per_1k)` — update the fallback model at runtime.
- `Modelrouter.default_cost` property — expose the default cost estimate.
- `Modelrouter.__len__` — `len(router)` returns the number of registered routes.
- `Modelrouter.__repr__` and `Route.__repr__` for readable debugging output.
- Input validation in `Modelrouter.__init__`, `add_route`, and `set_default`
  (`ValueError` / `TypeError` for empty names or non-callable conditions).
- `add_route` now silently replaces an existing route with the same name instead
  of appending a duplicate.
- `explain()` now includes `cost_per_1k` and `tags` fields in its return dict.
- `debug`-level logging via `logging.getLogger("modelrouter")` in `add_route`,
  `remove_route`, `clear_routes`, `set_default`, and `_match`.
- `modelrouter.gui` — a `tkinter`-based GUI for interactive route management and
  prompt testing, launched via `modelrouter-gui` or `from modelrouter.gui import launch`.
- `modelrouter-gui` console script entry point.
- Expanded test suite: 35 tests covering validation, new methods, `explain` fields,
  priority ordering, `repr`, edge cases (empty prompt, duplicate names).
- Full package metadata in `pyproject.toml` (authors, keywords, classifiers, URLs).
- Expanded JOSS paper with Functionality, API summary, GUI description, and new
  citations (Shazeer 2017, Ouyang 2022, Chen 2023).

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
