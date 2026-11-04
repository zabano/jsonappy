# Development

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

To test the dependency-free core in an environment without adapters:

```bash
python -m pip install -e . pytest
python -m pytest -q tests/query tests/test_resource.py
```

Preserve layer boundaries described in `AGENTS.md`. Keep framework-specific
changes in their adapter and update relevant examples and documentation.

The minimum supported Python version is 3.12. CI runs the test suite,
builds packages, and checks installed core imports on Python 3.12, 3.13,
and 3.14. Keep this matrix current when adding supported Python versions.

## Documentation examples and typing

The default pytest run executes docstring examples in `src/jsonapy` as well
as the test suite. `tests/test_documentation.py` runs the README's Python
blocks in order and checks the documented FastAPI endpoint. Keep those
blocks executable, including any assertions.

The package includes a `py.typed` marker so type checkers can use its inline
annotations after installation. `python -m mypy` checks all library modules
and consumer examples in `tests/typing`. It uses Python 3.12 as the language
baseline, and runs in every supported Python version's CI job. Mypy is a
development dependency; using the library adds no typing runtime dependency.

Give each module a top-level docstring describing its role, entry points,
and application responsibilities.

When documenting public APIs, describe defaults, return values, exceptions,
and responsibilities that the caller retains. Use executable `>>>` examples
for small core operations. Use the test suite for examples needing adapters
or application setup.
