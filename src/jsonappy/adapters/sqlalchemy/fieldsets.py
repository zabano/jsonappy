"""Translate sparse fieldsets into ORM column loading options.

resolve_sqlalchemy_fieldset uses load_only for mapped columns while retaining
ORM identity columns. Empty fieldsets defer non-identity columns. Computed
fields keep columns unrestricted because dependencies are undeclared.
Relationship loading belongs to the include adapter; serialization remains
responsible for enforcing the public output fieldset.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Load, load_only
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.interfaces import ORMOption

from .paths import (
    SQLAlchemyPathResolutionError,
    resolve_sqlalchemy_path,
)
from ...query.fieldsets import (
    FieldsetResolutionError,
    FieldsetSpec,
    ResolvedFieldset,
    resolve_fieldset,
)
from ...resource.base import Resource
from ...resource.fields import ComputedField, Field
from ...resource.relationships import Relationship


# ==========================================================================
# Errors
# ==========================================================================


class SQLAlchemyFieldsetError(ValueError):
    """
    Raised when a JSON:API sparse fieldset cannot be translated into
    SQLAlchemy.
    """


# ==========================================================================
# Resolved SQLAlchemy fieldset
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SQLAlchemyResolvedFieldset:
    """
    A Resource-level sparse fieldset resolved for SQLAlchemy.

    Attribute fields are translated into SQLAlchemy ``load_only()``
    options.

    Relationships remain Resource declarations. Relationship loading
    itself is handled by the include adapter.
    """

    fieldset: ResolvedFieldset
    fields: tuple[Field, ...]
    relationships: tuple[Relationship, ...]
    options: tuple[ORMOption, ...]

    @property
    def resource(self) -> type[Resource]:
        return self.fieldset.resource

    @property
    def resource_type(self) -> str:
        return self.fieldset.resource_type


# ==========================================================================
# Field resolution
# ==========================================================================


def _resolve_field_attribute(
        resource: type[Resource],
        field: Field,
) -> Any:
    """
    Resolve a Resource Field to its SQLAlchemy ORM attribute.

    ``load_only()`` requires the mapped class-bound attribute, rather
    than the lower-level SQL ``ColumnElement``.
    """

    try:
        resolved = resolve_sqlalchemy_path(
            resource,
            field.public_name,
        )
    except SQLAlchemyPathResolutionError as exc:
        raise SQLAlchemyFieldsetError(
            f"Unable to resolve field "
            f"{field.public_name!r} for Resource "
            f"{resource.__name__!r}: {exc}",
        ) from exc

    return resolved.attribute


# ==========================================================================
# Resolution
# ==========================================================================


def resolve_sqlalchemy_fieldset(
        resource: type[Resource],
        fieldset: FieldsetSpec | ResolvedFieldset,
) -> SQLAlchemyResolvedFieldset:
    """
    Resolve a Resource-level fieldset for SQLAlchemy.
    """

    if isinstance(
            fieldset,
            FieldsetSpec,
    ):
        try:
            resolved_fieldset = resolve_fieldset(
                resource,
                fieldset,
            )
        except FieldsetResolutionError as exc:
            raise SQLAlchemyFieldsetError(
                str(exc),
            ) from exc
    else:
        resolved_fieldset = fieldset

    if resolved_fieldset.resource is not resource:
        raise SQLAlchemyFieldsetError(
            f"Fieldset was resolved against "
            f"{resolved_fieldset.resource.__name__!r}, but "
            f"{resource.__name__!r} was expected.",
        )

    options: list[ORMOption] = []

    if any(
            isinstance(field, ComputedField)
            for field in resolved_fieldset.fields
    ):
        # Computed values may depend on an arbitrary model state. Without
        # declared dependencies, restricting columns is not safe.
        pass
    elif resolved_fieldset.fields:
        attributes = tuple(
            _resolve_field_attribute(
                resource,
                field,
            )
            for field in resolved_fieldset.fields
        )

        if all(
                isinstance(attribute, InstrumentedAttribute)
                and isinstance(attribute.property, ColumnProperty)
                for attribute in attributes
        ):
            options.append(
                load_only(
                    *attributes,
                ),
            )
    else:
        model = resource.model

        if model is None:
            raise SQLAlchemyFieldsetError(
                f"Resource {resource.__name__!r} does not define "
                "a SQLAlchemy model.",
            )

        # SQLAlchemy must retain identity columns, but all other mapped
        # attributes can be deferred for an explicitly empty fieldset.
        options.append(
            Load(model).defer("*"),
        )

    return SQLAlchemyResolvedFieldset(
        fieldset=resolved_fieldset,
        fields=resolved_fieldset.fields,
        relationships=resolved_fieldset.relationships,
        options=tuple(options),
    )


def resolve_sqlalchemy_fieldsets(
        resource: type[Resource],
        fieldset: FieldsetSpec | ResolvedFieldset | None,
) -> SQLAlchemyResolvedFieldset | None:
    """
    Resolve an optional Resource-level fieldset.

    Returns ``None`` when no fieldset was supplied.
    """

    if fieldset is None:
        return None

    return resolve_sqlalchemy_fieldset(
        resource,
        fieldset,
    )


# ==========================================================================
# Applying fieldsets
# ==========================================================================


def apply_fieldset(
        stmt: Select[Any],
        fieldset: SQLAlchemyResolvedFieldset,
) -> Select[Any]:
    """
    Apply a resolved sparse fieldset to an SQLAlchemy SELECT statement.
    """

    if not fieldset.options:
        return stmt

    return stmt.options(
        *fieldset.options,
    )


def apply_fieldsets(
        stmt: Select[Any],
        fieldsets: tuple[SQLAlchemyResolvedFieldset, ...],
) -> Select[Any]:
    """
    Apply multiple resolved fieldsets to an SQLAlchemy SELECT statement.
    """

    if not fieldsets:
        return stmt

    options: list[ORMOption] = []

    for fieldset in fieldsets:
        options.extend(
            fieldset.options,
        )

    if not options:
        return stmt

    return stmt.options(
        *options,
    )
