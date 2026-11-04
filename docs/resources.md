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
Type strings resolve through the process-wide registry, so use distinct types.

Identifiers default to `obj.id`; customize `id_attribute` or `id_resolver`.
Serialized identifiers are strings. `Resource.validate_all()` resolves deferred
relationship targets after application resource modules have been imported.

Invalid duplicate public names and reserved names (`id`, `type`) are rejected
when the resource class is defined.
