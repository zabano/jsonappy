# Framework adapters

## SQLAlchemy

Install the `sqlalchemy` extra. Set the resource's `model` to its mapped class.
The example assumes an application-defined mapped `Article` and matching
`ArticleResource`:

```python
from sqlalchemy import select
from jsonapy.query import QuerySpec
from jsonapy.adapters.sqlalchemy import build_sqlalchemy_query_from_spec

spec = QuerySpec.parse(sort="-title", page_number=1, page_size=25)
stmt = build_sqlalchemy_query_from_spec(
    select(Article), ArticleResource, spec,
)
articles = session.scalars(stmt).unique().all()
```

Begin with a statement that already restricts rows according to application
permissions. The adapter adds client-selected options; it does not authorize
access. Pagination helpers use synchronous SQLAlchemy session operations.

## Pydantic serialization

Install the `pydantic` extra. `serialize_resource` produces one resource object;
`serialize_document` and `serialize_collection` produce top-level documents.
They accept sparse fieldsets and context; document helpers also accept includes,
links, and metadata. `to_payload()` converts supported Python values to
JSON-compatible values while retaining required null linkage.

Relationship identifiers are included in `relationships`. Requested related
objects are emitted separately in `included`, deduplicated by resource identity.
ORM callers must arrange appropriate loading before serialization; computed
field dependencies may require additional application-specific loader options.

## FastAPI

Install the `fastapi` extra, which also installs Pydantic.

- `JSONAPIQuery` parses query parameters as a dependency.
- `resource_response` and `collection_response` serialize data with the media
  type `application/vnd.api+json`.
- `resource_request(ResourceClass, operation="create")` validates mutation
  input. For updates, set `operation="update"` and `id_parameter` to the route's
  identifier parameter.
- `install_jsonapi_exception_handlers(app)` installs JSON:API handlers for this
  adapter's HTTP exceptions and FastAPI request-validation errors.
- `jsonapi_fieldset_openapi` and `jsonapi_error_responses` generate reusable
  OpenAPI declarations. Routes remain the application's responsibility.

Mutation validation checks public field names, writability, required create
values, nullability, value types, resource type/ID consistency, relationship
types, and to-one/to-many cardinality. It returns a `ValidatedResourceRequest`
whose dictionary keys are Python declaration names.

It does not check whether linked identifiers exist or whether the caller has
permission to use them. Your application must perform those lookups and enforce
business rules before writing. `validate_response_query` can check response
fieldsets/includes before a mutation has side effects.

The exception handlers apply globally to FastAPI validation errors
when installed. Account for this when mixing JSON:API and unrelated routes.
