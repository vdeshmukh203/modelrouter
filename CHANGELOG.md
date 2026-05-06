# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-06

### Added
- `update_route()` method to modify individual fields of an existing route in place.
- `clear()` method to remove all registered routes at once.
- `__len__` — `len(router)` returns the number of registered routes.
- `__contains__` — `"name" in router` tests whether a route name is registered.
- `__repr__` on both `Modelrouter` and `Route` for readable debug output.
- `condition_label` parameter on `add_route()` / `Route` for human-readable condition descriptions.
- `default_cost` property on `Modelrouter`.
- `explain()` now returns `cost_per_1k`, `tags`, and `condition_label` in its dict.
- Warning log when a route condition raises an exception (previously silent).
- `Route` is now exported from the top-level package alongside `Modelrouter`.
- Interactive tkinter GUI (`modelrouter.gui`) — run via `python -m modelrouter.gui`
  or the `modelrouter-gui` console script. Supports route management, prompt
  testing, and live explain-output display.

### Changed
- `__version__` bumped to `0.2.0`.
- `pyproject.toml` adds `[project.optional-dependencies] dev` and the
  `modelrouter-gui` console-script entry point.

### Fixed
- `add_route()` now raises `ValueError` for duplicate route names and for
  negative `cost_per_1k` values (previously accepted silently).
- `Modelrouter.__init__` raises `ValueError` for negative `default_cost_per_1k`.

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
