"""Declarative JSON:API resources with optional framework adapters.

The top-level namespace exposes Resource, Field, Relationship, and
ComputedField. Import concrete field types from jsonapy.resource and query
specifications from jsonapy.query. Both layers use only the standard library.
Framework integrations live in jsonapy.adapters and require their extras.

Applications own authorization, object lookups, persistence, and transactions.
"""

from .resource import (
    ComputedField,
    Field,
    Relationship,
    Resource,
)

__all__ = [
    "ComputedField",
    "Field",
    "Relationship",
    "Resource",
]
