# Contributing to modelrouter

Thank you for considering a contribution to `modelrouter`!  This document describes how to set up a development environment, run the test suite, and submit a pull request.

---

## Code of conduct

Please be respectful and constructive in all interactions.  We follow the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct.

---

## Development setup

```bash
git clone https://github.com/vdeshmukh203/modelrouter.git
cd modelrouter
pip install -e ".[dev]"
```

The `[dev]` extras install `pytest`, `pytest-cov`, `ruff`, and `mypy`.

---

## Running the tests

```bash
pytest                          # run all tests
pytest --cov                    # run tests with coverage report
```

The test suite must pass in full before a pull request is merged.  Coverage must remain at or above 90%.

---

## Linting and type checking

```bash
ruff check src/ tests/          # lint
ruff format --check src/ tests/ # format check
mypy src/modelrouter/           # static type check (excludes gui.py)
```

CI enforces all three checks.

---

## Submitting a pull request

1. Fork the repository and create a feature branch (`git checkout -b feat/my-feature`).
2. Write your changes.
3. Add or update tests in `tests/test_modelrouter.py`.
4. Ensure `pytest`, `ruff check`, and `mypy` all pass.
5. Update `CHANGELOG.md` under the `[Unreleased]` heading.
6. Open a pull request against the `main` branch with a clear description of what changed and why.

---

## Reporting bugs

Open a GitHub issue and include:
- Python version (`python --version`)
- `modelrouter` version (`python -c "import modelrouter; print(modelrouter.__version__)"`)
- A minimal reproducible example

---

## Suggesting features

Open a GitHub issue tagged **enhancement** with a description of the use case and, if possible, an example of the API you would like to see.
