# Architecture

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
