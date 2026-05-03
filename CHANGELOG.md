# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-03

### Added
- Input validation in `add_route`: raises `ValueError` for duplicate route names,
  non-callable conditions, and negative `cost_per_1k` values.
- `update_route()` method to modify fields of an existing route in place.
- `clear()` method to remove all registered routes at once.
- `__len__`, `__contains__`, and `__repr__` on `Modelrouter` for Pythonic use.
- `__repr__` on `Route` for readable debugging output.
- `explain()` now returns `cost_per_1k` and `tags` keys.
- `Route` is now exported from the top-level package (`from modelrouter import Route`).
- `debug`-level logging throughout routing and route-management operations;
  faulty conditions now emit a `WARNING` instead of silently swallowing errors.
- Full Google-style docstrings (Args / Returns / Raises) on all public methods.
- Interactive Tkinter GUI (`modelrouter.gui`) with route table, add/remove form,
  and a prompt tester showing `resolve`, `explain`, and cost output.
- `python -m modelrouter` entry point that opens the GUI directly.

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
