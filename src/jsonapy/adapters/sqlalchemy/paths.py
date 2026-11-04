from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.orm import (
    InstrumentedAttribute,
    RelationshipProperty,
)
from sqlalchemy.orm.properties import ColumnProperty

from ...resource.base import Resource
from ...resource.fields import Field
from ...resource.paths import ResolvedFieldPath
from ...resource.relationships import Relationship


# ==========================================================================
# Errors
# ==========================================================================


class SQLAlchemyPathResolutionError(ValueError):
    """
    Raised when a resolved Resource path cannot be mapped to SQLAlchemy.
    """


# ==========================================================================
# Resolved SQLAlchemy path
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SQLAlchemyResolvedPath:
    """
    A Resource field path resolved to SQLAlchemy ORM attributes.

    Example:

        author.organization.sortOrder

    resolves to:

        resource_path
            ("author", "organization", "sortOrder")

        relationships
            (
                Article.author.property,
                Author.organization.property,
            )

        attribute
            Organization.sort_order

        column
            Organization.sort_order
    """

    resource_path: ResolvedFieldPath
    relationships: tuple[RelationshipProperty[Any], ...]
    attribute: Any
    column: ColumnElement[Any]

    @property
    def path(self) -> tuple[str, ...]:
        return self.resource_path.path

    @property
    def field(self) -> Field:
        return self.resource_path.field

    @property
    def name(self) -> str:
        name = self.resource_path.name

        if name is None:
            raise SQLAlchemyPathResolutionError(
                "Resolved Resource field has no declaration name.",
            )

        return name

    @property
    def public_name(self) -> str:
        public_name = self.resource_path.public_name

        if public_name is None:
            raise SQLAlchemyPathResolutionError(
                "Resolved Resource field has no public name.",
            )

        return public_name

    @property
    def resource(self) -> type[Resource]:
        return self.resource_path.resource

    @property
    def target_resource(self) -> type[Resource]:
        return self.resource_path.target_resource

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)


# ==========================================================================
# SQLAlchemy attribute helpers
# ==========================================================================


def _get_attribute(
        model: type[Any],
        name: str,
) -> InstrumentedAttribute[Any]:
    """
    Return a mapped SQLAlchemy attribute from a model.

    Raises
    ------
    SQLAlchemyPathResolutionError
        If the attribute does not exist or is not a mapped
        SQLAlchemy attribute.
    """

    try:
        attribute = getattr(
            model,
            name,
        )
    except AttributeError as exc:
        raise SQLAlchemyPathResolutionError(
            f"SQLAlchemy model {model.__name__!r} has no "
            f"attribute {name!r}.",
        ) from exc

    if not isinstance(
            attribute,
            InstrumentedAttribute,
    ):
        raise SQLAlchemyPathResolutionError(
            f"Attribute {model.__name__}.{name} is not a "
            "SQLAlchemy mapped attribute.",
        )

    return attribute


def _get_relationship(
        model: type[Any],
        name: str,
) -> RelationshipProperty[Any]:
    """
    Return a mapped SQLAlchemy relationship from a model.
    """

    attribute = _get_attribute(
        model,
        name,
    )

    property_ = attribute.property

    if not isinstance(
            property_,
            RelationshipProperty,
    ):
        raise SQLAlchemyPathResolutionError(
            f"Attribute {model.__name__}.{name} is not a "
            "SQLAlchemy relationship.",
        )

    return property_


def _get_column_attribute(
        model: type[Any],
        name: str,
) -> Any:
    """
    Return a mapped SQLAlchemy column attribute from a model.
    """

    try:
        attribute = getattr(model, name)
    except AttributeError as exc:
        raise SQLAlchemyPathResolutionError(
            f"SQLAlchemy model {model.__name__!r} has no attribute "
            f"{name!r}.",
        ) from exc

    if isinstance(attribute, InstrumentedAttribute) and isinstance(
            attribute.property,
            ColumnProperty,
    ):
        return attribute

    if not callable(getattr(attribute, "__clause_element__", None)):
        raise SQLAlchemyPathResolutionError(
            f"Attribute {model.__name__}.{name} is not a mapped "
            "SQLAlchemy column or queryable expression.",
        )

    return attribute


def _get_column(
        model: type[Any],
        name: str,
        attribute: Any,
) -> ColumnElement[Any]:
    """
    Return the SQL expression represented by a mapped column
    attribute.

    The model and attribute name are passed separately so error
    messages do not depend on InstrumentedAttribute.__repr__().
    """

    try:
        expression = attribute.__clause_element__()
    except (AttributeError, TypeError) as exc:
        raise SQLAlchemyPathResolutionError(
            f"Attribute {model.__name__}.{name} did not produce a "
            "SQLAlchemy expression.",
        ) from exc

    if not isinstance(
            expression,
            ColumnElement,
    ):
        raise SQLAlchemyPathResolutionError(
            f"Attribute {model.__name__}.{name} did not produce "
            "a SQLAlchemy ColumnElement.",
        )

    return expression


# ==========================================================================
# Relationship helpers
# ==========================================================================


def _relationship_target_model(
        relationship: RelationshipProperty[Any],
) -> type[Any]:
    """
    Return the SQLAlchemy model targeted by a relationship.
    """

    return relationship.mapper.class_


def _validate_relationship(
        resource_relationship: Relationship,
        sqlalchemy_relationship: RelationshipProperty[Any],
        *,
        model: type[Any],
) -> None:
    """
    Verify that a Resource relationship maps to the expected
    SQLAlchemy model.
    """

    target_resource = resource_relationship.resource
    target_model = target_resource.model

    if target_model is None:
        raise SQLAlchemyPathResolutionError(
            f"Resource {target_resource.__name__!r} does not define "
            "a SQLAlchemy model.",
        )

    mapped_model = _relationship_target_model(
        sqlalchemy_relationship,
    )

    if mapped_model is not target_model:
        relationship_name = resource_relationship.name

        if relationship_name is None:
            relationship_name = "<unnamed>"

        raise SQLAlchemyPathResolutionError(
            f"Resource relationship {relationship_name!r} on "
            f"{model.__name__!r} maps to SQLAlchemy model "
            f"{mapped_model.__name__!r}, but the target Resource "
            f"declares model {target_model.__name__!r}.",
        )

    sqlalchemy_many = bool(sqlalchemy_relationship.uselist)

    if sqlalchemy_many is not resource_relationship.many:
        relationship_name = resource_relationship.name or "<unnamed>"
        raise SQLAlchemyPathResolutionError(
            f"Resource relationship {relationship_name!r} on "
            f"{model.__name__!r} declares many="
            f"{resource_relationship.many}, but the SQLAlchemy "
            f"relationship declares uselist={sqlalchemy_many}.",
        )


# ==========================================================================
# Relationship path resolution
# ==========================================================================


def resolve_sqlalchemy_relationship_path(
        resource: type[Resource],
        relationships: tuple[Relationship, ...],
) -> tuple[RelationshipProperty[Any], ...]:
    """
    Resolve a Resource relationship path to SQLAlchemy relationships.

    Example:

        ArticleResource
            author
            organization

    resolves to:

        (
            Article.author.property,
            Author.organization.property,
        )
    """

    model = resource.model

    if model is None:
        raise SQLAlchemyPathResolutionError(
            f"Resource {resource.__name__!r} does not define "
            "a SQLAlchemy model.",
        )

    current_model = model

    resolved_relationships: list[
        RelationshipProperty[Any]
    ] = []

    for resource_relationship in relationships:
        relationship_name = resource_relationship.name

        if relationship_name is None:
            raise SQLAlchemyPathResolutionError(
                "Resolved Resource relationship has no "
                "declaration name.",
            )

        sqlalchemy_relationship = _get_relationship(
            current_model,
            relationship_name,
        )

        _validate_relationship(
            resource_relationship,
            sqlalchemy_relationship,
            model=current_model,
        )

        resolved_relationships.append(
            sqlalchemy_relationship,
        )

        current_model = _relationship_target_model(
            sqlalchemy_relationship,
        )

    return tuple(
        resolved_relationships,
    )


# ==========================================================================
# Field path resolution
# ==========================================================================


def resolve_sqlalchemy_path(
        resource: type[Resource],
        field_path: str,
) -> SQLAlchemyResolvedPath:
    """
    Resolve a Resource field path to SQLAlchemy.

    The Resource path is resolved first.

    Each declared relationship is then mapped onto the SQLAlchemy ORM,
    and the terminal Resource field is mapped to a SQLAlchemy column.

    Example:

        author.organization.sortOrder

    becomes:

        Article
            -> Author
            -> Organization
            -> Organization.sort_order
    """

    model = resource.model

    if model is None:
        raise SQLAlchemyPathResolutionError(
            f"Resource {resource.__name__!r} does not define "
            "a SQLAlchemy model.",
        )

    try:
        resolved = resource.resolve_path(
            field_path,
        )
    except ValueError as exc:
        raise SQLAlchemyPathResolutionError(
            str(exc),
        ) from exc

    relationships = resolve_sqlalchemy_relationship_path(
        resource,
        resolved.relationships,
    )

    field_name = resolved.field.name

    if field_name is None:
        raise SQLAlchemyPathResolutionError(
            "Resolved Resource field has no declaration name.",
        )

    current_model = model

    for relationship in relationships:
        current_model = _relationship_target_model(
            relationship,
        )

    attribute = _get_column_attribute(
        current_model,
        field_name,
    )

    column = _get_column(
        current_model,
        field_name,
        attribute,
    )

    return SQLAlchemyResolvedPath(
        resource_path=resolved,
        relationships=relationships,
        attribute=attribute,
        column=column,
    )
