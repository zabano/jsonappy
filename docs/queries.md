# Query options

[Documentation index](README.md) · Next: [Serialization](serialization.md)

Parsing records client intent. Resolution checks public names, relationship
paths, and declared capabilities. Neither step executes a database query.

| Concern | HTTP example |
| --- | --- |
| Sorting | `sort=headline,-createdAt` |
| Filtering | `filter[headline]=Hello` |
| Pagination | `page[number]=2&page[size]=25` |
| Sparse fieldsets | `fields[articles]=headline,author` |
| Included resources | `include=author.organization,tags` |

Each example assumes the corresponding members are declared by the application.
The FastAPI `JSONAPIQuery` dependency extracts these parameters into `QuerySpec`.
Outside FastAPI, pass separated components to `QuerySpec.parse()`:

```python
from jsonappy import Resource, ResourceRegistry
from jsonappy.resource import Integer, RangeFilter, String
from jsonappy.query import (
    FieldsetSpec, FieldsetSpecList, FilterSpecList, QuerySpec, resolve_query,
)


class ArticleResource(Resource):
    registry = ResourceRegistry()
    type = "articles"
    title = String(public_name="headline", sortable=True, filterable=True)
    word_count = Integer(public_name="wordCount", filterable=RangeFilter())


spec = QuerySpec.parse(
    sort="-headline",
    filters=FilterSpecList.parse({"filter[wordCount]": "100:500"}),
    fieldsets=FieldsetSpecList((FieldsetSpec.parse("articles", "headline"),)),
    page_number="2",
    page_size="25",
)
resolved = resolve_query(ArticleResource, spec)
assert resolved.sorts[0].field.name == "title"
assert spec.pagination.offset == 25
assert spec.to_query_parameters()["fields[articles]"] == "headline"
```

`parse_query()` is a convenience equivalent to `QuerySpec.parse()`. Use
`SortSpecList`, `FilterSpecList`, `FieldsetSpecList`, and `IncludeSpecList` for
individual components. `with_sort()`, `with_filters()`, `with_fieldsets()`,
`with_include()`, and `with_pagination()` return new specs. Formatting through
`to_query_parameters()` always includes concrete pagination defaults.

Malformed syntax raises `ValueError` or a query-specific subclass. Resource
resolution raises `SortResolutionError`, `FilterResolutionError`,
`FieldsetResolutionError`, or `IncludeResolutionError`; all subclass `ValueError`.
`resolve_query()` validates the root fieldset; serializers and include loaders
also resolve fieldsets for resources reached through requested includes.

## Filtering

The declaration selects one operation; the client does not select operators:

| Declaration | Input | Operation |
| --- | --- | --- |
| `filterable=True` or `Filter()` | `value` | Equality |
| `MultiValueFilter()` | `one,two` | Membership |
| `RangeFilter()` | `10:20`, `10:`, `:20`, `10..20` | Inclusive range |
| `TextFilter()` | `text` | Case-insensitive containment in SQLAlchemy |
| `BooleanFilter()` | `true` | Boolean equality |

Use `..` between datetime range boundaries so timestamp colons remain intact:
`filter[createdAt]=2026-01-01T10:00:00Z..2026-01-02T10:00:00Z`.
Open ranges use `timestamp..` or `..timestamp`. The `..` separator works
for other range fields too. Empty ranges are invalid.

Values remain strings through core resolution. SQLAlchemy converts them using
mapped column types. Boolean columns accept `true`, `1`, `yes`, `false`, `0`,
and `no`, case-insensitively. Multiple filters, including repeated parameters,
combine with AND; multi-value membership provides alternatives within one
filter. Text matching escapes SQL wildcard characters.

Filtering is this library's convention; JSON:API does not mandate these
operations or encodings. There is no generic OR expression language or null
filter operator. Only the capabilities supported by each [field](resources.md)
can be declared.

## Paths, includes, and fieldsets

Nested sort/filter paths use public names, such as `author.fullName`, and
traverse to-one relationships. SQLAlchemy rejects traversal through to-many
relationships for filters and sorts. Includes support both cardinalities,
including paths such as `author.organization`. Invalid paths and disabled
capabilities raise resolution errors. SQLAlchemy aliases repeated model targets
and self-referential paths as needed.

Sparse fieldsets select attributes and relationships per public resource type.
No fieldset means all declared members; `fields[articles]=` selects none,
retaining `type` and `id`. `id` and `type` are not selectable field names.
Fieldsets for unrelated types are not a global registry validation: they are
resolved when that resource is used. FastAPI rejects duplicate `fields[...]`
parameters for the same resource type.

Includes and fieldsets are independent. An include still traverses a relationship
omitted from the primary resource's fieldset. Related fieldsets shape included
objects. Serialization deduplicates included objects by `(type, id)` and never
repeats primary data in `included`; it still traverses every requested descendant
path through shared and primary objects.

## Pagination and loading

Page numbers start at one. Defaults are page 1 and 10 records; the maximum
page size is 100. Invalid or out-of-bounds values raise `PaginationError`.
`PageSpec` exposes `offset` and `limit`; `PaginationMeta` describes total rows,
page number, page size, and page count.

`QuerySpec.is_paginated` reports whether pagination differs from defaults.
It does not disable pagination: `build_sqlalchemy_query_from_spec()` applies
default OFFSET/LIMIT even when `bool(spec)` is false. Pass `paginate=False`
to disable it. The lower-level `build_sqlalchemy_query()` only paginates when
supplied a `page`.

`paginate_sqlalchemy_query()` synchronously executes a count and returns a
paginated SELECT with metadata. Applications execute the SELECT themselves.
Counts reflect statement rows, so application joins must preserve the intended
resource cardinality. Supply stable ordering for predictable paging.

SQLAlchemy fieldsets restrict loaded columns while retaining identity columns;
includes use `selectinload`. Column loading does not replace output fieldsets.
See the [adapter integration](adapters.md) for a complete SQLite example.
