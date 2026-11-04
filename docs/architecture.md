# Architecture

[Documentation index](README.md) · Next: [Resources](resources.md)

The library separates API declarations from framework implementations:

```text
HTTP query parameters -> QuerySpec -> resource validation -> SQLAlchemy SELECT
                                                           |
                                               application executes query
                                                           |
objects -> resource serialization -> JSON:API document -> HTTP response
```

`resource` describes fields, relationships, identifiers, and public names.
`query` parses client intent and validates paths and declared capabilities.
These layers use only the Python standard library.

The SQLAlchemy adapter turns resolved query options into expressions, joins,
column-loading options, `selectinload` relationship loading, and pagination.
Applications supply their own base SELECT, including access restrictions.

The Pydantic adapter defines request, response, and error document models,
validates mutation semantics, and serializes objects using their attributes.
Objects can be dataclasses, ORM instances, or other attribute-bearing objects.

The FastAPI adapter provides dependencies, response helpers, error handlers,
media-type checks, and reusable OpenAPI declarations.

JSON:API describes representations and interaction conventions. OpenAPI
describes the concrete HTTP operations an application exposes. Installing
this library does not create routes or supply application authorization.

Applications own authentication, authorization, business rules, database
sessions, transactions, relationship lookups, and persistence.

## Mutation flow

```text
request document -> structural validation -> resource mutation validation
                                                        |
                              application authorization and linked-ID lookup
                                                        |
                                   business rules, transaction, persistence
                                                        |
                              serialization -> JSON:API response
```

Mutation validation returns supplied values keyed by Python declaration names
and relationship linkage retaining public resource types. It does not fetch
related objects or write changes. See [Mutation validation](mutations.md).

## Scope and current limitations

The supported flow covers resource declarations, query specifications, SQLAlchemy
SELECT translation, document serialization, mutation input validation, and
FastAPI integration. It is not a complete JSON:API server implementation.

- Applications define endpoints, resource-specific OpenAPI schemas, authorization,
  and persistence; there is no generated CRUD or relationship routing.
- SQLAlchemy filters and sorts traverse to-one relationships; to-many traversal
  is supported for includes. Pagination is page-based with OFFSET/LIMIT.
- Count helpers are synchronous. Async applications execute statements and counts
  themselves and arrange loading before synchronous serialization.
- Serialization shapes supplied objects; it does not apply query filters, sorting,
  or pagination. Selected relationships can need loading for linkage alone.
- Media-type checks do not implement complete Accept quality negotiation or
  JSON:API extension/profile negotiation. Full conformance requires a separate
  specification audit.

See [Adapters](adapters.md) for loading, error mapping, media types, and OpenAPI
behavior. The project is alpha; check the implemented API before upgrading.
