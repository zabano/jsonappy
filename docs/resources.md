# Resources

Subclass `Resource`, set a nonempty JSON:API `type`, and declare fields and
relationships as class attributes. Set `model` when using SQLAlchemy.

Available fields include `String`, `Integer`, `Float`, `Number`, `Decimal`,
`Boolean`, `Date`, `DateTime`, `UUID`, `EnumField`, `AnyField`, `JSON`, and
`ComputedField`.

Field options:

| Option | Behavior |
| --- | --- |
| `public_name` | Overrides the name exposed to API clients. |
| `sortable` | Enables sorting; disabled by default. |
| `filterable` | Enables an explicitly declared filter capability. |
| `nullable` | Allows null attribute values; false by default. |
| `writable` | Allows create/update input; true for ordinary fields by default. |
| `required` | Requires the field in create input; false by default. |

`ComputedField(getter)` is read-only. Its getter receives `(object, context)`.
`JSON` accepts arbitrary JSON-compatible values and has no portable filtering
capability.

`Decimal` uses Python's `decimal.Decimal` and serializes as a JSON string.
Send strings such as `"19.9900"` to preserve exact precision and trailing zeros.

## Relationships and identifiers

`Relationship(TargetResource)` declares a to-one relationship; pass
`many=True` for to-many. Targets can be resource classes, registered type
strings, or deferred zero-argument callables. Relationships also accept
`public_name`, `writable`, `required`, and `nullable`.

Set `name_style` to `identity`, `camelcase`, or `dashes` for default public
names. Use `abstract = True` for configured resource base classes. Concrete
resources register their type by default; `register = False` disables this.
Duplicate types in the same registry raise `ValueError`.

Identifiers default to `obj.id`; customize `id_attribute` or `id_resolver`.
Serialized identifiers are strings. Call `validate_all()` on your resource
base after importing its declarations to check deferred relationship targets.

Invalid duplicate public names and reserved names (`id`, `type`) are rejected
when the resource class is defined.

## Registries

Resources share `Resource.registry` by default. Give each application or test
suite a `ResourceRegistry` to keep type names and string targets isolated:

```python
from jsonapy import Resource, ResourceRegistry


class AppResource(Resource):
    abstract = True
    registry = ResourceRegistry()
```

Declare application resources by subclassing `AppResource`. Subclasses inherit
the registry. String relationship targets resolve only
within the owning resource's registry; direct classes and callables remain
explicit references. `get_resource()`, `registered_types()`, and `validate_all()`
on a resource use its registry. The registry also exposes `get()`,
`registered_types()`, and `validate_all()` directly.
