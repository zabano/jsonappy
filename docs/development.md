# Development

[Documentation index](README.md) · Related: [Validation checklist](validation.md)

## Environment

Use Python 3.12, 3.13, or 3.14 for the tested support matrix. Package metadata
allows `>=3.12,<4.0`. Run commands from the repository root. The shell examples
use POSIX activation; on Windows use `.venv\Scripts\activate` instead.

## PyCharm

Open this project directory in PyCharm as a new project. Create a project-local
`.venv`, select its Python interpreter, then install `.[dev]`. Mark `src` as a
Sources Root if the IDE does not infer the standard src layout. Use pytest as
the test runner with this directory as the working directory.

No machine-specific `.idea` files or interpreter paths are required or shared.

Alternatively, use a Poetry environment with Python 3.12 or later:

```bash
poetry env use python3.12
poetry install
poetry run python -m pytest -q
poetry run python -m mypy
```

Select that existing Poetry environment as the project interpreter in PyCharm.
The default Poetry installation includes the `dev` dependency group, so the IDE
can detect the development packages without selecting optional extras. The
`.[dev]` extra remains available for pip installations.

## Install, test, and build

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m mypy
python -m build
python -m twine check dist/*
```

The existing suite covers resource declarations, query parsing/resolution,
SQLAlchemy expressions and SQLite execution, document serialization, input
validation, and FastAPI responses and errors. It requires no application
database, Docker, credentials, or external services.

Use a fresh environment to test the dependency-free core; reusing a development
environment would leave optional dependencies installed:

```bash
python -m venv /tmp/jsonappy-core-check
/tmp/jsonappy-core-check/bin/python -m pip install -e . pytest
/tmp/jsonappy-core-check/bin/python -m pytest -q tests/query tests/test_resource.py tests/test_registry.py src/jsonappy/resource src/jsonappy/query src/jsonappy/__init__.py
```

Preserve layer boundaries described in `AGENTS.md`. Keep framework-specific
changes in their adapter and update relevant examples and documentation.

The minimum supported Python version is 3.12. CI runs the test suite,
builds packages, and checks installed core imports on Python 3.12, 3.13,
and 3.14. Keep this matrix current when adding supported Python versions.

## Documentation examples and typing

The default pytest run executes docstring examples in `src/jsonappy` as well
as the test suite. `tests/test_documentation.py` runs the README's Python
blocks in order and checks the documented FastAPI endpoint. It also executes
the resource, query, serialization, adapter, and mutation guides in separate
module namespaces, with their blocks run in order. Keep those
blocks executable, including any assertions.

The package includes a `py.typed` marker so type checkers can use its inline
annotations after installation. `python -m mypy` checks all library modules,
the installation checker, and consumer examples in `tests/typing`. It uses
Python 3.12 as the language baseline and runs in every supported Python
version's CI job. Mypy is a development dependency; using the library adds no typing runtime dependency.

Give each module a top-level docstring describing its role, entry points,
and application responsibilities.

When documenting public APIs, describe defaults, return values, exceptions,
and responsibilities that the caller retains. Use executable `>>>` examples
for small core operations. Use the test suite for examples needing adapters
or application setup.

## Isolated installation checks

CI installs both the wheel and source distribution with each profile: `core`,
`pydantic`, `fastapi`, `sqlalchemy`, and `all`, on Python 3.12, 3.13, and 3.14.
Each check creates a fresh environment, copies relevant tests outside the
checkout, and runs them against the installed package. It also checks package
requirements, the typing marker, and the absence of unselected frameworks.
Test tooling adds only pytest and, for HTTP profiles, httpx.

After building, run a profile locally with:

```bash
python scripts/check_installation.py --extra pydantic --distribution wheel
python scripts/check_installation.py --extra core --distribution sdist
```


The installation checker requires exactly one matching artifact of the selected
kind in `dist`. If older builds are present, use a fresh directory:

```bash
python -m build --outdir /tmp/jsonappy-docs-dist
python -m twine check /tmp/jsonappy-docs-dist/*
python scripts/check_installation.py --artifacts /tmp/jsonappy-docs-dist --extra core --distribution wheel
```

Use a new output path if that directory already contains old builds. Repeat the
checker for both `wheel` and `sdist` with each profile: `core`, `pydantic`,
`fastapi`, `sqlalchemy`, and `all`. Installation checks need package-index access
to install build/test tooling and optional dependencies; the tests themselves
use only local fixtures and SQLite.

## Maintaining documentation

[The index](README.md) owns the reading order; keep the root README focused on
installation and the quickstart. Put declarations in the resource guide, query
syntax in queries, output behavior in serialization, HTTP/database integration
in adapters, and input validation in mutations. Link to the owning guide when
other pages need the same detail.

Check claims against public constructors, exports, tests, `pyproject.toml`, and
CI. Keep Python examples executable and independent between guides. When adding
a guide to the example tests, preserve optional-dependency isolation and copy
any required documentation in `scripts/check_installation.py`. Check local
Markdown links, defaults, error behavior, and application responsibilities when
changing public APIs. Do not imply that successful examples establish complete
JSON:API conformance.
