# Serialization

[Documentation index](README.md) · Next: [Adapters](adapters.md)

Install the `pydantic` extra. Serialization reads Python attributes from
dataclasses, ORM instances, or other attribute-bearing objects. It uses public
names in output and does not persist objects or validate application permissions.

## Documents, linkage, and includes

```python
from dataclasses import dataclass
from jsonappy import Resource, ResourceRegistry
from jsonappy.resource import Relationship, String
from jsonappy.query import FieldsetSpec, FieldsetSpecList
from jsonappy.adapters.pydantic import serialize_collection, serialize_document


class AppResource(Resource):
    abstract = True
    registry = ResourceRegistry()


class AuthorResource(AppResource):
    type = "authors"
    name = String()


class ArticleResource(AppResource):
    type = "articles"
    title = String(public_name="headline")
    author = Relationship(AuthorResource)


@dataclass
class Author:
    id: int
    name: str


@dataclass
class Article:
    id: int
    title: str
    author: Author | None


author = Author(2, "Ada")
article = Article(1, "Hello", author)
document = serialize_document(
    article, ArticleResource,
    include="author",
    fieldsets=FieldsetSpecList((FieldsetSpec.parse("articles", "headline,author"),)),
    links={"self": "/articles/1"},
    meta={"source": "example"},
)
payload = document.to_payload()
assert payload["data"]["relationships"]["author"] == {
    "data": {"type": "authors", "id": "2"},
}
assert payload["included"] == [
    {"type": "authors", "id": "2", "attributes": {"name": "Ada"}},
]
assert serialize_document(None, ArticleResource).to_payload() == {"data": None}
assert serialize_collection([], ArticleResource).to_payload() == {"data": []}
assert serialize_document(Article(3, "News", None), ArticleResource).to_payload()[
    "data"
]["relationships"]["author"] == {"data": None}
```

| Entry point | Returns | Options |
| --- | --- | --- |
| `serialize_resource(obj, resource)` | `ResourceObject` | `fieldsets`, `context` |
| `serialize_document(obj, resource)` | `JSONAPIDocument` with one object or null | Also `include`, `links`, `meta` |
| `serialize_collection(objects, resource)` | `JSONAPIDocument` with a data array | Same as document helper |

`include` accepts a comma-separated string or `IncludeSpecList`; `fieldsets`
accepts `FieldsetSpecList`; `context` is a mapping passed to computed getters.
Collection serialization materializes the iterable once. It does not filter,
sort, or paginate. `to_payload()` produces JSON-compatible dictionaries while
preserving null primary data, null attributes, and null relationship linkage.
Empty optional document members may be omitted.

Selected relationships emit identifier linkage even without `include`.
Requested related objects appear separately in `included`, deduplicated by
`(type, id)`. A null to-one emits `{"data": null}` and an empty to-many emits
`{"data": []}`. Serialization treats a to-many object value of `None` as empty;
mutation input still requires an array. Relationship `nullable` governs mutation
validation; serialization does not enforce relationship nullability.

## Value encoding

Dates and datetimes become ISO strings, UUIDs become strings, and enum members
use their values. Decimal fields require finite values and emit decimal strings
preserving digits and scale. Applications choose datetime timezone policy and
decimal rounding, scale, and bounds. `JSON` values must be JSON-compatible;
`AnyField` does not make arbitrary Python objects JSON serializable.

Serialization checks identifiers, attribute presence, and attribute nullability.
It is not a general output type validator for every field. Attribute access uses
Python names, independently of `public_name`.

## Loading and failures

`SerializationError` indicates missing/null identifiers, missing selected
attributes or relationships, invalid decimal values, or null non-nullable
attributes. Computed getter exceptions propagate. Invalid includes and fieldsets
raise their query resolution errors even for empty/null primary data.

Load required data before serialization. Selected relationships may need loading
for linkage even without an include. ORM access can trigger lazy loads, and
computed getters may require additional columns or relationships. The SQLAlchemy
adapter loads requested include paths; applications arrange other loader options
and keep the session available as needed. For async sessions, explicitly load
all attributes used during serialization to avoid implicit database I/O.
