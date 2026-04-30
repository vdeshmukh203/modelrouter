# Changelog

All notable changes to modelrouter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-30

### Added
- `Route.__post_init__` validation: raises `ValueError` for negative `priority`
  or `cost_per_1k`.
- `Route.__repr__` for readable debug output.
- `Modelrouter.__repr__` and `Modelrouter.__len__`.
- `Modelrouter.clear()` to remove all routes in one call.
- Duplicate-name guard in `add_route`: raises `ValueError` if a route with
  the given name already exists.
- `priority`, `cost_per_1k`, and `tags` are now keyword-only arguments in
  `add_route` for clearer call sites.
- `default_cost_per_1k` validation in `Modelrouter.__init__`.
- `logging.NullHandler` on the package logger; condition exceptions are now
  logged at `DEBUG` level rather than silently discarded.
- `Route` is now exported from the top-level `modelrouter` package.
- Interactive Tkinter GUI (`modelrouter-gui` CLI entry point) with support for
  seven condition types, real-time routing decisions, and cost display.
- Expanded test suite (34 tests) covering all new behaviour.
- Expanded `paper.md` with related work, functionality table, and GUI section.
- Added SemanticRouter and LangChain entries to `paper.bib`.
- Project classifiers, URLs, and `dev` optional-dependency group in
  `pyproject.toml`.

## [0.1.0] - 2026-04-25

### Added
- Initial release of modelrouter.
- Priority-ordered, condition-based routes.
- Tag-based filtering and per-route cost estimation.
- Declarative configuration that keeps routing policy out of application code.
