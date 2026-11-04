# Validation checklist

[Documentation index](README.md) · [Commands and environments](development.md)

## Changes and reviews

- Preserve package boundaries and unrelated local changes; follow
  [AGENTS.md](../AGENTS.md).
- Run `python -m pytest -q` with the `dev` extra installed. This includes
  docstrings, README examples, and user-guide examples. Tests must use local
  fixtures and SQLite without external services, credentials, or secrets.
- Run `python -m mypy` for library annotations and typed consumer examples.
- Check changed public names, relationship paths, field capabilities, linkage,
  includes, sparse fieldsets, and mutation semantics against the relevant tests.
- Update the owning guide and index links for public API changes. Keep examples
  general-purpose: articles, authors, and organizations. Check that Python
  blocks execute in order within each guide and that local Markdown links resolve.

## Packaging and release preparation

- Build wheel and source distribution into a directory without stale artifacts;
  run `python -m twine check` on both.
- Run `scripts/check_installation.py` for both artifact types and each profile:
  `core`, `pydantic`, `fastapi`, `sqlalchemy`, and `all`. These checks install in
  clean environments, run relevant tests outside the source tree, inspect the
  typing marker and requirements, and verify unselected frameworks are absent.
- Verify core imports without any optional dependencies installed. An installed
  development environment is not evidence of core isolation.
- Check the source distribution includes source modules, tests, scripts,
  documentation, `AGENTS.md`, and `pytest.ini`; check the wheel contains package
  modules and `py.typed`.
- Review the Python 3.12, 3.13, and 3.14 CI matrix and dependency bounds in
  [package metadata](../pyproject.toml). Run all CI jobs before release.
- Resolve the owner decisions in [Publishing](publishing.md), including license,
  real project URLs, release version, and explicit authorization to publish.

Package checks may download dependencies; test execution requires no external
services. Passing this checklist does not establish full JSON:API conformance.
