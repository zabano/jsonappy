# Query options

The FastAPI dependency parses these parameters into a `QuerySpec`:

| Concern | Example |
| --- | --- |
| Sorting | `sort=name,-createdAt` |
| Exact filter | `filter[name]=Example` |
| Pagination | `page[number]=2&page[size]=25` |
| Sparse fieldsets | `fields[articles]=title,author` |
| Included resources | `include=author.organization,tags` |

The pure query layer also exposes `QuerySpec.parse()` and `resolve_query()`
for use outside FastAPI. Parsing and resource-specific resolution are separate:
parsing records client intent, while resolution checks exposed names, paths,
and allowed operations.

## Filtering

Filter behavior is selected by the resource field's declaration:

| Declaration | Input | Operation |
| --- | --- | --- |
| `filterable=True` or `Filter()` | `value` | Equality |
| `MultiValueFilter()` | `one,two` | Membership |
| `RangeFilter()` | `10:20`, `10:`, `:20`, `start..end` | Inclusive range |
| `TextFilter()` | `text` | Case-insensitive containment in SQLAlchemy |
| `BooleanFilter()` | Boolean value | Boolean equality |

Use `..` between datetime range boundaries so timestamp colons remain intact:
`filter[createdAt]=2026-01-01T10:00:00Z..2026-01-02T10:00:00Z`.
Open ranges use `timestamp..` or `..timestamp`. The `..` separator also works
for other range fields; existing `start:end` ranges remain supported.

Filter values remain strings until their backend adapter performs conversion.
The library's filter syntax is its own convention; JSON:API does not mandate
these filter operations or value encodings.

Nested filter and sort paths traverse declared to-one relationships. Includes
can load to-one and to-many relationships. Unsupported paths or capabilities
raise validation errors. Filters and sorts can use multiple relationships to
the same model and self-referential paths; SQLAlchemy joins those paths with
separate aliases when needed.

## Pagination and loading

Page numbers start at one. Defaults are page 1 and 10 records; the maximum
page size is 100. SQLAlchemy applies pagination through OFFSET and LIMIT.
`paginate_sqlalchemy_query()` executes a count and returns a paginated SELECT
plus pagination metadata. Applications execute the returned SELECT themselves.

`build_sqlalchemy_query_from_spec(..., paginate=False)` disables pagination.
Supply a stable sort for predictable paging.

SQLAlchemy sparse fieldsets restrict loaded columns while preserving identity
columns. Includes use `selectinload` and can apply fieldsets to related models.
Serialization also applies fieldsets, builds linkage, and deduplicates included
resources by `(type, id)`. Shared resources are emitted once while all
requested descendant include paths are traversed, including paths through
resources already present in primary data.
