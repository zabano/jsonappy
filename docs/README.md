# Documentation

These guides describe the API implemented in this checkout. The package is
alpha, is tested on Python 3.12–3.14 (metadata allows `>=3.12,<4.0`), and has no
runtime dependencies unless an adapter extra is installed. See
[installation and the quickstart](../README.md).

## Using the library

Read these in order for a complete integration:

1. [Architecture](architecture.md): layers, data flow, application responsibilities,
   and current limitations.
2. [Resources](resources.md): fields, public names, relationships, IDs, and registries.
3. [Queries](queries.md): parsing, resolution, filtering, fieldsets, and pagination.
4. [Serialization](serialization.md): documents, linkage, includes, and value encoding.
5. [Adapters](adapters.md): SQLAlchemy queries, FastAPI responses, errors, and OpenAPI.
6. [Mutation validation](mutations.md): create/update input and application handoff.

Python blocks run in order within each guide; each guide starts with its own
imports and declarations. Shell commands assume the repository root and a
POSIX shell unless stated otherwise. Examples use local data and SQLite.

## Developing and releasing

- [Changelog](../CHANGELOG.md): notable changes and upcoming release notes.
- [Development](development.md): environments, PyCharm, tests, typing, and package checks.
- [Documentation site](hosting.md): local preview, build checks, and Read the Docs setup.
- [Validation checklist](validation.md): checks to complete before merging or releasing.
- [Publishing](publishing.md): owner decisions and release preparation.

The source module docstrings document individual entry points and exceptions.
Public imports live in `jsonappy.resource`, `jsonappy.query`, and the relevant
`jsonappy.adapters` module; the root package exports the common resource base
classes only. Consult [package metadata](../pyproject.toml) for exact dependency
bounds and [CI](../.github/workflows/tests.yml) for the verification matrix.
