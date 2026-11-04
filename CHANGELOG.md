# Changelog

Notable changes to jsonappy are recorded here.

Entries follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), with
versions following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
During initial development (`0.x`), public APIs may change between minor versions.

## [Unreleased]

The first public release is in preparation; no release date has been assigned.

### Added

- Dependency-free resource declarations with typed fields, relationships,
  configurable public names, identifiers, computed fields, and isolated registries.
- Query parsing and resource validation for sorting, filtering, page-based
  pagination, sparse fieldsets, and relationship includes.
- Optional SQLAlchemy adapter for SELECT construction, relationship joins,
  eager loading, column selection, and pagination counts.
- Optional Pydantic adapter for JSON:API serialization, relationship linkage,
  included-resource deduplication, and create/update validation.
- Decimal fields that preserve precision and scale in input validation and output.
- Optional FastAPI adapter with query and mutation dependencies, JSON:API
  responses, error handlers, media-type checks, and OpenAPI helpers.
- Inline type annotations, a `py.typed` marker, and executable documentation examples.
- User guides for resources, queries, serialization, adapters, and mutation validation.
- CI coverage for Python 3.12, 3.13, and 3.14, including isolated wheel and source
  distribution checks for the core and optional adapters.
- MIT license.
