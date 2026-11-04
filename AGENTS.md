# Library development guidance

This is an independent JSON:API library. Keep application models, business
rules, permissions, credentials, and deployment configuration out of it.
Use general-purpose examples such as articles, authors, and organizations in
documentation, docstrings, and test fixtures.

## Package boundaries

- `resource/` defines declarative fields, relationships, names, and identifiers.
  It must remain independent of FastAPI, Pydantic, and SQLAlchemy.
- `query/` parses and resolves query specifications against resources. Keep
  framework and database imports in adapters.
- `adapters/` translates resource and query behavior into each framework.
  Keep third-party dependencies optional and declare their extras explicitly.
- Mutation validation resolves input; applications own authorization,
  relationship lookups, persistence, transactions, and business validation.

## Changes and verification

- Preserve unrelated local changes and existing behavior when making changes.
- Keep public names distinct from Python attribute names.
- Maintain validation of relationship paths, field capabilities, JSON:API
  linkage, and sparse fieldsets when changing query or serialization code.
- Run the existing test suite after behavioral changes. Tests use local
  fixtures and SQLite; they must not require external services or secrets.
- Verify core imports with no optional dependencies installed.
- Verify built artifacts can be installed and imported outside the source tree.
- Update documentation and examples when changing the public API.
- Never publish a release or add a license grant without the owner's direction.
