# Framework adapters

[Documentation index](README.md) · Next: [Mutation validation](mutations.md)

Install only the extras you use. `sqlalchemy` provides database translation;
`pydantic` provides document models and serialization; `fastapi` includes
Pydantic and adds HTTP helpers. `all` installs all three. Import adapters from
`jsonappy.adapters.sqlalchemy`, `.pydantic`, and `.fastapi` respectively.

## SQLAlchemy: declaration to query to document

This example needs the `sqlalchemy` and `pydantic` extras (or `all`) and runs
against in-memory SQLite:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from jsonappy import Resource, ResourceRegistry
from jsonappy.resource import String
from jsonappy.query import QuerySpec
from jsonappy.adapters.pydantic import serialize_collection
from jsonappy.adapters.sqlalchemy import paginate_sqlalchemy_query


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]


class ArticleResource(Resource):
    registry = ResourceRegistry()
    type = "articles"
    model = Article
    title = String(public_name="headline", sortable=True, filterable=True)


engine = create_engine("sqlite://")
Base.metadata.create_all(engine)
spec = QuerySpec.parse(sort="headline", page_number=1, page_size=25)
with Session(engine) as session:
    session.add(Article(id=1, title="Hello"))
    session.commit()
    # Add application access restrictions to the base SELECT here.
    stmt, pagination = paginate_sqlalchemy_query(
        session, select(Article), ArticleResource, spec,
    )
    articles = session.scalars(stmt).unique().all()
    document = serialize_collection(
        articles, ArticleResource, include=spec.include, fieldsets=spec.fieldsets,
    )
    assert pagination.total == 1
    assert document.to_payload()["data"][0]["attributes"] == {"headline": "Hello"}
engine.dispose()
```

`build_sqlalchemy_query_from_spec(stmt, resource, spec, paginate=True)` builds a
SELECT without executing or counting. `paginate_sqlalchemy_query()` additionally
runs a synchronous count and returns `(Select, PaginationMeta)`; execute the
SELECT yourself. For async sessions, use the statement builder and execute/count
through application async operations.

The lower-level pipeline is `resolve_sqlalchemy_query()` followed by
`apply_sqlalchemy_query()`, or `build_sqlalchemy_query()` with individual parsed
components. These helpers apply required relationship joins, filtering, root
fieldsets, include loaders, sorting, and finally pagination. Translation errors
from the combined builder raise `SQLAlchemyQueryError`, a `ValueError` subclass.
This exception is not automatically translated by FastAPI handlers; applications
must map client-query failures to an appropriate HTTP error.

The base SELECT must already implement access restrictions. SQLAlchemy mapping
attributes must match Python declaration names, independently of public names.
Counts reflect rows; custom joins must preserve resource cardinality. Includes
use `selectinload`; fieldsets preserve primary keys. Arrange additional loading
for selected linkage and computed dependencies before
[serialization](serialization.md#loading-and-failures).

## Pydantic

`serialize_resource()` returns a resource object; `serialize_document()` and
`serialize_collection()` return top-level documents. Use `.to_payload()` for
JSON-compatible dictionaries. See [Serialization](serialization.md) for complete
examples, includes, fieldsets, context, and null linkage.

`JSONAPIRequestDocument` and `validate_request_document()` validate mutation
input without requiring FastAPI. See [Mutation validation](mutations.md) for the
resolved return value and application handoff.

## FastAPI responses and query handling

The [README quickstart](../README.md#add-fastapi-endpoints) constructs a GET route.
`JSONAPIQuery` is an annotated dependency returning `QuerySpec`; it parses syntax
and checks Accept, but cannot validate resource-specific filter/sort capabilities.
Pass the spec to your data query builder, then pass the fetched objects to the
response helper.

`resource_response(obj, resource, query=spec)` returns a single resource document
(or null data). `collection_response(objects, resource, query=spec)` returns a
data array. Both return `JSONAPIResponse` with `application/vnd.api+json`, apply
includes/fieldsets, and accept `context`, `links`, `meta`, `status_code`, and
`headers`. They do not filter, sort, or slice supplied objects.

Pass `pagination=PaginationMeta(...)` to `collection_response()` to add:

```json
{"meta": {"page": {"total": 1, "number": 1, "size": 25, "pages": 1}}}
```

This overrides a supplied `meta.page` but preserves other metadata. Pagination
links are application-supplied via `links`; helpers do not generate URLs.
`resource_response(None, ...)` produces null data with the requested status;
raise `JSONAPIHTTPException` explicitly for a missing-resource 404.

## Errors and media types

Call `install_jsonapi_exception_handlers(app)` once. It installs handlers for
`JSONAPIHTTPException` and FastAPI `RequestValidationError`. The latter applies
globally, including routes unrelated to JSON:API. Ordinary `HTTPException`,
SQLAlchemy query errors, and `SerializationError` are not converted by these
handlers. Use `error_response(*errors, status_code=...)` for explicit error
responses, or raise `JSONAPIHTTPException` with `title`, `detail`, and optional
`code`, `source`, and `headers`.

| Condition | Adapter response |
| --- | --- |
| Malformed query syntax, invalid response includes/fieldsets | 400 |
| Incompatible Accept | 406 |
| Mutation Content-Type other than `application/vnd.api+json` | 415 |
| FastAPI structural request validation | 422 |
| Mutation semantic failure | 400, 409, or 422 depending on failure |

Mutation dependencies check Content-Type and Accept. `JSONAPIQuery` checks
Accept; response helpers alone do not negotiate request headers. Use
`Depends(require_jsonapi_accept)` or `JSONAPIAccept` for routes without the query
or mutation dependency. Missing Accept and `*/*` are accepted. Checks are basic:
quality values, full wildcard negotiation, and JSON:API extension/profile
negotiation are not implemented. Framework body parsing may fail before semantic
mutation validation, so malformed bodies can produce 422 before media checks.

## OpenAPI and routes

Declare `response_class=JSONAPIResponse` on JSON:API routes so FastAPI documents
the response media type. Use `JSONAPIEmptyResponse` for bodyless routes when
appropriate. `jsonapi_fieldset_openapi(*resources)` supplies `openapi_extra`
parameters; `jsonapi_error_responses(*status_codes)` supplies `responses` entries.
`COMMON_JSONAPI_ERROR_RESPONSES` provides the common statuses. These declarations
help describe routes; they do not install runtime behavior or generate a complete
resource-specific request/response schema. Explicitly document application filter
parameters and resource schemas as needed.

Applications define routes, sessions, transactions, authorization, persistence,
and relationship endpoints. The library does not generate CRUD operations.
