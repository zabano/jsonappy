"""Parse sparse fieldsets and validate exposed attributes and relationships.

Each FieldsetSpec targets a public resource type. resolve_fieldsets selects
the matching spec for a Resource and validates its public member names.
An absent fieldset leaves selection unrestricted; an explicit empty fieldset
selects no members. Serializers and database adapters apply those selections.
"""

from dataclasses import dataclass
from typing import Iterable, Iterator

from ..resource.base import Resource
from ..resource.fields import Field
from ..resource.relationships import Relationship


# --------------------------------------------------------------------------
# Fieldset specification
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FieldsetSpec:
    """
    A sparse fieldset requested for a single JSON:API resource type.

    Example:

        FieldsetSpec(
            resource_type="articles",
            fields=("rating", "status", "author"),
        )

    Represents:

        fields[articles]=rating,status,author
    """

    resource_type: str
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        resource_type = self.resource_type.strip()

        if not resource_type:
            raise ValueError(
                "Fieldset resource type cannot be empty.",
            )

        object.__setattr__(
            self,
            "resource_type",
            resource_type,
        )

        normalized_fields = tuple(
            field.strip()
            for field in self.fields
            if field.strip()
        )

        object.__setattr__(
            self,
            "fields",
            normalized_fields,
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.fields)

    def __len__(self) -> int:
        return len(self.fields)

    def __bool__(self) -> bool:
        return bool(self.fields)

    def __contains__(self, field: str) -> bool:
        return field in self.fields

    def to_query_value(self) -> str:
        """
        Return the value used for the JSON:API query parameter.

        Example:

            rating,status,author
        """
        return ",".join(self.fields)

    def to_query_parameter(self) -> tuple[str, str]:
        """
        Return the JSON:API query parameter name and value.

        Example:

            (
                "fields[articles]",
                "rating,status,author",
            )
        """
        return (
            f"fields[{self.resource_type}]",
            self.to_query_value(),
        )

    @classmethod
    def parse(
            cls,
            resource_type: str,
            value: str | None,
    ) -> "FieldsetSpec":
        """
        Parse a single JSON:API sparse fieldset.

        Example:

            FieldsetSpec.parse(
                "articles",
                "rating,status,author",
            )
        """

        if value is None:
            return cls(
                resource_type=resource_type,
            )

        value = value.strip()

        if not value:
            return cls(
                resource_type=resource_type,
            )

        fields = tuple(
            field.strip()
            for field in value.split(",")
            if field.strip()
        )

        return cls(
            resource_type=resource_type,
            fields=fields,
        )


# --------------------------------------------------------------------------
# Fieldset collection
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FieldsetSpecList:
    """
    An ordered collection of sparse fieldset specifications.

    JSON:API allows multiple ``fields[...]`` parameters, one for each
    resource type.
    """

    items: tuple[FieldsetSpec, ...] = ()

    def __iter__(self) -> Iterator[FieldsetSpec]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __getitem__(
            self,
            index: int,
    ) -> FieldsetSpec:
        return self.items[index]

    def __contains__(
            self,
            resource_type: str,
    ) -> bool:
        return any(
            item.resource_type == resource_type
            for item in self.items
        )

    def get(
            self,
            resource_type: str,
    ) -> FieldsetSpec | None:
        for item in self.items:
            if item.resource_type == resource_type:
                return item

        return None

    @classmethod
    def from_iterable(
            cls,
            specs: Iterable[FieldsetSpec],
    ) -> "FieldsetSpecList":
        return cls(tuple(specs))

    def to_query_parameters(self) -> dict[str, str]:
        """
        Convert the fieldsets into JSON:API query parameters.

        Example:

            {
                "fields[articles]": "rating,status",
                "fields[authors]": "name,rank,biography,organization",
            }
        """

        return dict(
            item.to_query_parameter()
            for item in self.items
        )


# --------------------------------------------------------------------------
# Resolved fieldsets
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResolvedFieldset:
    """
    A fieldset resolved against a Resource.

    A sparse fieldset may contain both attributes and relationships.

    For example:

        fields[articles]=rating,status,author

    resolves to:

        fields
            rating
            status

        relationships
            author
    """

    spec: FieldsetSpec
    resource: type[Resource]
    fields: tuple[Field, ...]
    relationships: tuple[Relationship, ...]

    @property
    def resource_type(self) -> str:
        return self.spec.resource_type

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(
            field.public_name
            for field in self.fields
        )

    @property
    def relationship_names(self) -> tuple[str, ...]:
        return tuple(
            relationship.public_name
            for relationship in self.relationships
        )

    def contains_field(
            self,
            name: str,
    ) -> bool:
        return any(
            field.public_name == name
            for field in self.fields
        )

    def contains_relationship(
            self,
            name: str,
    ) -> bool:
        return any(
            relationship.public_name == name
            for relationship in self.relationships
        )


class FieldsetResolutionError(ValueError):
    """
    Raised when a sparse fieldset cannot be resolved against a Resource.
    """


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------


def resolve_fieldset(
        resource: type[Resource],
        spec: FieldsetSpec,
) -> ResolvedFieldset:
    """
    Resolve a single FieldsetSpec against a Resource.

    The Resource's public field and relationship names are used for
    resolution.

    Example:

        fields[articles]=rating,status,author
    """

    expected_type = resource.type

    if expected_type is None:
        raise FieldsetResolutionError(
            f"Resource {resource.__name__!r} does not define "
            f"a JSON:API type.",
        )

    if expected_type != spec.resource_type:
        raise FieldsetResolutionError(
            f"Fieldset targets resource type "
            f"{spec.resource_type!r}, but Resource "
            f"{resource.__name__!r} has type "
            f"{expected_type!r}.",
        )

    fields: list[Field] = []
    relationships: list[Relationship] = []

    for public_name in spec.fields:
        field_result = resource.field_for_public_name(
            public_name,
        )

        if field_result is not None:
            _, field = field_result
            fields.append(field)
            continue

        relationship_result = (
            resource.relationship_for_public_name(
                public_name,
            )
        )

        if relationship_result is not None:
            _, relationship = relationship_result
            relationships.append(relationship)
            continue

        raise FieldsetResolutionError(
            f"Resource {resource.__name__!r} has no "
            f"field or relationship named "
            f"{public_name!r}.",
        )

    return ResolvedFieldset(
        spec=spec,
        resource=resource,
        fields=tuple(fields),
        relationships=tuple(relationships),
    )


def resolve_fieldsets(
        resource: type[Resource],
        specs: FieldsetSpecList,
) -> ResolvedFieldset | None:
    """
    Resolve the fieldset for a particular Resource.

    Returns ``None`` when no fieldset was specified for this Resource.
    """

    spec = specs.get(
        resource.type
        if resource.type is not None
        else "",
    )

    if spec is None:
        return None

    return resolve_fieldset(
        resource,
        spec,
    )


# --------------------------------------------------------------------------
# Parsing / formatting convenience functions
# --------------------------------------------------------------------------


def parse_fieldset(
        resource_type: str,
        value: str | None,
) -> FieldsetSpec:
    """
    Parse a JSON:API sparse fieldset.

    Example:
        fields[articles]=rating,status,author

    Returns a FieldsetSpec containing the requested fields for the
    specified resource type.
    """

    return FieldsetSpec.parse(
        resource_type,
        value,
    )


def format_fieldset(
        spec: FieldsetSpec,
) -> tuple[str, str]:
    """
    Convert a fieldset into a JSON:API query parameter.

    Returns:

        (
            "fields[articles]",
            "rating,status,author",
        )
    """

    return spec.to_query_parameter()
