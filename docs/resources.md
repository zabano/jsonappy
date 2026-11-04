# Resources

[Documentation index](README.md) · Next: [Queries](queries.md)

Resources describe an API representation independently of application models.
Subclass `Resource`, set a nonempty JSON:API `type`, and declare fields and
relationships. Install no extras for these declarations.

## Public names and Python attributes

```python
from jsonappy import Resource, ResourceRegistry
from jsonappy.resource import ComputedField, Relationship, String


class AppResource(Resource):
    abstract = True
    registry = ResourceRegistry()
    name_style = "camelcase"


class AuthorResource(AppResource):
    type = "authors"
    full_name = String(required=True)


class ArticleResource(AppResource):
    type = "articles"
    title = String(public_name="headline", sortable=True, filterable=True,
                   required=True)
    author = Relationship("authors", nullable=False)
    label = ComputedField(lambda obj, ctx: ctx.get("prefix", "") + obj.title)


AppResource.validate_all()
assert ArticleResource.public_field_name("title") == "headline"
assert AuthorResource.public_field_name("full_name") == "fullName"
assert ArticleResource.field_for_public_name("headline")[0] == "title"
```

Objects expose `title` and `full_name`; clients use `headline` and `fullName`
in attributes, query paths, sparse fieldsets, and mutation input. There is no
separate model-attribute alias: declarations use the object's Python names.
`name_style` supports `identity` (default), `camelcase`, and `dashes`.
Explicit `public_name` takes precedence. Duplicate public names across fields
and relationships and reserved names `id` and `type` are rejected at class
creation.

## Field types and capabilities

| Field | Value type | Supported filter declarations |
| --- | --- | --- |
| `String` | `str` | Exact, multi-value, text |
| `Integer` | `int` | Exact, multi-value, range |
| `Float`, `Number` | `float` | Exact, multi-value, range |
| `Decimal` | `decimal.Decimal` | Exact, multi-value, range |
| `Boolean` | `bool` | Exact, boolean |
| `Date`, `DateTime` | `datetime.date`, `datetime.datetime` | Exact, multi-value, range |
| `UUID` | `uuid.UUID` | Exact, multi-value |
| `EnumField(MyEnum)` | Member of the supplied enum | Exact, multi-value |
| `AnyField` | Unconstrained | Exact |
| `JSON` | JSON-compatible value | None |
| `ComputedField(getter)` | Getter result | None |

Import concrete fields and filter declarations from `jsonappy.resource`.
Capabilities are opt-in; listing a supported filter does not enable it.
Unsupported filter declarations raise `TypeError` at class creation. See
[filter syntax](queries.md#filtering) for the capability classes.

| Ordinary field option | Default | Behavior |
| --- | --- | --- |
| `public_name` | Naming style applied to Python name | Client-facing name |
| `sortable` | `False` | Enables sorting |
| `filterable` | `None` | `True` enables exact filtering; a filter instance chooses its operation |
| `nullable` | `False` | Allows null on input and during serialization |
| `writable` | `True` | Accepts create/update input |
| `required` | `False` | Requires presence on create; updates may omit it |

`required` controls presence, while `nullable` controls explicit nulls. Resource
fields supply no persistence defaults. Applications enforce length, bounds,
precision, and other business constraints.

`ComputedField(getter, public_name=None, nullable=False)` is read-only and
cannot be sorted or filtered. The getter receives `(object, context)` and runs
only if selected for serialization; its exceptions propagate. SQLAlchemy
retains all root columns when a selected computed field has undeclared
dependencies. Applications must still load any relationships its getter uses.

`Decimal` serializes as a JSON string. Send strings such as `"19.9900"` to
preserve exact precision and trailing zeros; no rounding or quantization is
performed. See [value encoding](serialization.md#value-encoding).

## Relationships and identifiers

`Relationship(TargetResource)` declares a to-one relationship; `many=True`
declares to-many. Targets can be resource classes, registered type strings,
or deferred zero-argument callables. Relationship defaults are `many=False`,
`writable=True`, `required=False`, and `nullable=True`. They also accept
`public_name`. A to-many mutation always uses an array, including `[]` to
clear it; null linkage applies only to nullable to-one mutations.

Objects expose related objects under the declaration name. Serializers derive
linkage from those objects; request validation retains identifiers for the
application to resolve. See [serialization](serialization.md) and
[mutation validation](mutations.md).

Identifiers default to `obj.id`. Set `id_attribute = "article_id"` to read a
different attribute, or supply an `id_resolver` callable taking the object.
Serialized IDs are strings, and missing/null IDs raise `SerializationError`.
Set `model` to the mapped class when using the SQLAlchemy adapter.

## Inheritance, registries, and inspection

Use `abstract = True` for configured base classes. Abstractness is not
inherited: subclasses become concrete unless explicitly marked abstract.
Fields, relationships, and configuration are inherited. Concrete resources
register their `type` by default; `register = False` disables registration.
Duplicate types in a registry raise `ValueError`.

All resources share `Resource.registry` unless a base supplies its own
`ResourceRegistry`, as above. String targets resolve within the owning
resource's registry; direct classes and callables are explicit references.
Call `AppResource.validate_all()` after importing all declarations to validate
deferred targets before serving requests.

`fields()`, `relationships()`, `field(name)`, and `relationship(name)` use Python
declaration names. `field_for_public_name()` and `relationship_for_public_name()`
return a `(Python name, declaration)` pair or `None`. `resolve_path()` resolves
public paths. `get_resource()`, `registered_types()`, and `validate_all()` use
the resource's registry; the registry also exposes `get()`, `registered_types()`,
and `validate_all()` directly.
