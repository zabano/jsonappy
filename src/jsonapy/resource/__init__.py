"""Public declarations for JSON:API resources, attributes, and relationships.

Subclass Resource, declare Field and Relationship instances, and customize
public names independently of Python attribute names. Filter and Sortable
options advertise capabilities consumed by query resolvers and adapters.
This namespace has no framework or database dependencies.
"""

from .base import Resource
from .registry import ResourceRegistry
from .fields import (
    AnyField,
    Boolean,
    ComputedField,
    Date,
    DateTime,
    Decimal,
    Field,
    Float,
    Integer,
    JSON,
    Number,
    String,
    UUID,
    EnumField,
)
from .options import (
    BooleanFilter,
    FieldOptions,
    Filter,
    MultiValueFilter,
    RangeFilter,
    Sortable,
    TextFilter,
)
from .paths import ResolvedFieldPath
from .relationships import Relationship

__all__ = [
    "AnyField",
    "Boolean",
    "BooleanFilter",
    "ComputedField",
    "Date",
    "DateTime",
    "Decimal",
    "EnumField",
    "Field",
    "FieldOptions",
    "Float",
    "Filter",
    "Integer",
    "JSON",
    "MultiValueFilter",
    "Number",
    "Relationship",
    "RangeFilter",
    "ResolvedFieldPath",
    "Resource",
    "ResourceRegistry",
    "Sortable",
    "String",
    "TextFilter",
    "UUID",
]
