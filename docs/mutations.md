# Mutation validation

[Documentation index](README.md) · Related: [Adapters](adapters.md)

Install the `pydantic` extra for framework-independent input validation, or the
`fastapi` extra for request dependencies. Validation resolves client input;
applications own authorization, linked-resource lookup, business rules,
persistence, and transactions.

## Validate a create or partial update

```python
from jsonappy import Resource, ResourceRegistry
from jsonappy.resource import Relationship, String
from jsonappy.adapters.pydantic import JSONAPIRequestDocument, validate_request_document


class AppResource(Resource):
    abstract = True
    registry = ResourceRegistry()


class AuthorResource(AppResource):
    type = "authors"
    name = String()


class ArticleResource(AppResource):
    type = "articles"
    title = String(public_name="headline", required=True)
    author = Relationship(AuthorResource)


document = JSONAPIRequestDocument.model_validate({
    "data": {
        "type": "articles",
        "attributes": {"headline": "Hello"},
        "relationships": {"author": {"data": {"type": "authors", "id": "2"}}},
    },
})
created = validate_request_document(document, ArticleResource, operation="create")
assert created.id is None
assert created.attributes == {"title": "Hello"}
assert created.relationships["author"].data.id == "2"

update = JSONAPIRequestDocument.model_validate({
    "data": {"type": "articles", "id": "1", "relationships": {"author": {"data": None}}},
})
validated = validate_request_document(
    update, ArticleResource, operation="update", expected_id="1",
)
assert validated.attributes == {}
assert validated.relationships["author"].data is None
```

Structural errors from `model_validate()` raise Pydantic `ValidationError`.
Semantic errors from `validate_request_document()` raise `ResourceRequestError`
with `detail`, `pointer`, `code`, and `status_code`.

Create requires fields and relationships marked `required=True`; it permits an
optional client ID. Updates require a body ID and accept omitted members as
unchanged. `expected_id`, when supplied, must match the body ID exactly. Type
or ID conflicts use status 409; missing required values and invalid attribute
values generally use 422; unknown/read-only members use 400.

Validation checks public names, writability, attribute nullability and types,
relationship target types, and to-one/to-many cardinality. Strings, booleans,
and integers must have their expected JSON types; numeric fields accept JSON
numbers. Date, datetime, UUID, enum, and decimal values are converted to their
Python types. Prefer decimal strings for exact input. JSON request values are
already decoded; `JSON` and `AnyField` add no business schema validation.

`ValidatedResourceRequest.attributes` uses Python declaration names.
`relationships` also uses Python names, with `RelationshipObject` values whose
`data` contains `ResourceIdentifier` objects, a list of identifiers, or `None`.
Identifiers retain public resource types and string IDs; they are not looked up.
Only supplied members appear in the result; no model defaults are applied.

To clear a to-many relationship, send `{"data": []}`. To clear a nullable to-one,
send `{"data": null}`. To-many never accepts null, even if declared nullable.
Nested related-resource creation is not supported by this linkage validator.

## FastAPI dependency

The following continues with `ArticleResource` above. It demonstrates validation
and hands the resolved input back as metadata; a real endpoint performs its own
application operations before returning a persisted resource response.

```python
from typing import Annotated
from fastapi import Depends, FastAPI
from jsonappy.adapters.fastapi import (
    JSONAPIQuery, JSONAPIResponse, install_jsonapi_exception_handlers,
    resource_request, validate_response_query,
)
from jsonappy.adapters.pydantic import ValidatedResourceRequest

app = FastAPI()
install_jsonapi_exception_handlers(app)


@app.patch("/articles/{article_id}", response_class=JSONAPIResponse)
def validate_article_update(
    article_id: str,
    body: Annotated[ValidatedResourceRequest, Depends(resource_request(
        ArticleResource, operation="update", id_parameter="article_id",
    ))],
    query: JSONAPIQuery,
):
    validate_response_query(ArticleResource, query)
    return JSONAPIResponse({"meta": {"id": article_id, "attributes": body.attributes}})
```

For create, use `operation="create"`; `id_parameter` is optional. An update
dependency requires `id_parameter` at construction and matches the body ID to
the string form of that route parameter. The dependency checks Accept and
Content-Type and translates semantic errors into `JSONAPIHTTPException`.
Install the exception handlers to emit JSON:API error documents.

Before changing state, validate response fieldsets/includes with
`validate_response_query()`, authorize the operation and supplied members,
resolve and authorize linked identifiers, and enforce business rules. Apply only
supplied attributes and relationships, manage the transaction, then serialize the
persisted object with `resource_response()`. `validate_response_query()` checks
response shaping only; it does not resolve filters or sorting.
