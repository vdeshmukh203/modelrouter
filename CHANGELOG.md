# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-27

### Added
- `update_route()` — modify individual fields of an existing route in-place.
- `clear()` — remove all registered routes in one call.
- `DuplicateRouteError` — raised by `add_route()` when a route name collision
  occurs, replacing silent overwrites.
- `__len__` and `__contains__` on `Modelrouter` (`len(router)`,
  `"name" in router`).
- `__repr__` on both `Route` and `Modelrouter` for easier debugging.
- `explain()` now includes `cost_per_1k` and `tags` in its return dict.
- Input validation in `__init__` and `add_route()`: empty name, model, or
  default raises `ValueError`.
- Interactive Tkinter GUI (`modelrouter.gui`) with a `modelrouter-gui` console
  entry point — add/edit/remove routes visually and test routing decisions
  interactively.
- `pyproject.toml`: PyPI classifiers, keywords, repository URL, and
  `[project.scripts]` entry point.

### Changed
- Version bumped to `0.2.0`.
- `CITATION.cff` version updated to `0.2.0`.

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
