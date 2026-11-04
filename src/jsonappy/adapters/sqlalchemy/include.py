"""Build selectinload options for resolved relationship include paths.

build_include_options removes redundant prefixes, chains relationship loaders,
and applies sparse fieldsets to included models. Both to-one and to-many
relationships can be included. These helpers configure SELECT loading only;
serializers construct compound documents and callers execute statements.
"""

from typing import Any, cast

from sqlalchemy.orm import Load, RelationshipProperty, selectinload

from .paths import (
    SQLAlchemyPathResolutionError,
    resolve_sqlalchemy_relationship_path,
)
from ...query.include import (
    IncludeSpecList,
    ResolvedInclude,
    resolve_includes,
)
from ...query.fieldsets import FieldsetSpecList, resolve_fieldsets
from ...resource.base import Resource
from ...resource.relationships import Relationship
from ...resource.fields import ComputedField
from .fieldsets import SQLAlchemyFieldsetError, resolve_sqlalchemy_fieldset


class SQLAlchemyIncludeError(ValueError):
    """
    Raised when a JSON:API include cannot be translated into an
    SQLAlchemy loader option.
    """


def _relationship_attribute(
        relationship: RelationshipProperty[Any],
) -> Any:
    """
    Return the class-bound SQLAlchemy attribute for a relationship.
    """

    attribute = relationship.class_attribute

    if attribute is None:
        raise SQLAlchemyIncludeError(
            "Unable to obtain the class-bound attribute for "
            f"SQLAlchemy relationship {relationship.key!r}.",
        )

    return attribute


def _build_loader(
        relationships: tuple[
            RelationshipProperty[Any],
            ...,
        ],
        resource_relationships: tuple[Relationship, ...],
        fieldsets: FieldsetSpecList,
) -> Load:
    """
    Build a chained selectinload() option.
    """

    if not relationships:
        raise SQLAlchemyIncludeError(
            "Cannot build an include loader without relationships.",
        )

    # The standalone loader factory constructs a concrete Load object.
    loader = cast(Load, selectinload(
        _relationship_attribute(
            relationships[0],
        ),
    ))

    loader = _apply_included_fieldset(
        loader,
        resource_relationships[0].resolve_resource(),
        fieldsets,
    )

    for index, relationship in enumerate(relationships[1:], start=1):
        # Chaining a Load retains that concrete loader at runtime.
        loader = cast(Load, loader.selectinload(
            _relationship_attribute(
                relationship,
            ),
        ))
        loader = _apply_included_fieldset(
            loader,
            resource_relationships[index].resolve_resource(),
            fieldsets,
        )

    return loader


def _apply_included_fieldset(
        loader: Load,
        resource: type[Resource],
        fieldsets: FieldsetSpecList,
) -> Load:
    """Apply a resource's sparse fieldset to its include loader."""

    resolved = resolve_fieldsets(resource, fieldsets)

    if resolved is None:
        return loader

    try:
        sqlalchemy_fieldset = resolve_sqlalchemy_fieldset(
            resource,
            resolved,
        )
    except SQLAlchemyFieldsetError as exc:
        raise SQLAlchemyIncludeError(str(exc)) from exc

    model = resource.model

    if model is None:
        raise SQLAlchemyIncludeError(
            f"Resource {resource.__name__!r} does not define a "
            "SQLAlchemy model.",
        )

    if not sqlalchemy_fieldset.fields:
        return loader.defer("*")

    if any(
            isinstance(field, ComputedField)
            for field in sqlalchemy_fieldset.fields
    ):
        return loader

    if sqlalchemy_fieldset.fields and not sqlalchemy_fieldset.options:
        # Hybrid/queryable attributes cannot be passed to load_only().
        return loader

    attributes: list[Any] = []

    for field in sqlalchemy_fieldset.fields:
        if field.name is None:
            raise SQLAlchemyIncludeError(
                "Resolved Resource field has no declaration name.",
            )

        attributes.append(getattr(model, field.name))

    return loader.load_only(*attributes)


def _remove_overlapping_includes(
        includes: tuple[ResolvedInclude, ...],
) -> tuple[ResolvedInclude, ...]:
    """
    Remove include paths already implied by a deeper include.

    ``author.organization`` loads ``author`` as part of the same loader
    chain, so a separate ``author`` option is redundant.
    """

    return tuple(
        include
        for include in includes
        if not any(
            len(other.parts) > len(include.parts)
            and other.parts[:len(include.parts)] == include.parts
            for other in includes
        )
    )


def build_include_option(
        resource: type[Resource],
        include: ResolvedInclude,
        fieldsets: FieldsetSpecList | None = None,
) -> Load:
    """
    Build an SQLAlchemy loader option for one resolved include.
    """

    try:
        relationships = resolve_sqlalchemy_relationship_path(
            resource,
            include.relationships,
        )
    except SQLAlchemyPathResolutionError as exc:
        raise SQLAlchemyIncludeError(
            str(exc),
        ) from exc

    if not relationships:
        raise SQLAlchemyIncludeError(
            f"Include path {include.path!r} does not contain "
            "any relationships.",
        )

    return _build_loader(
        relationships,
        include.relationships,
        fieldsets if fieldsets is not None else FieldsetSpecList(),
    )


def build_include_options(
        resource: type[Resource],
        includes: IncludeSpecList,
        fieldsets: FieldsetSpecList | None = None,
) -> tuple[Load, ...]:
    """
    Resolve all JSON:API include paths and convert them into SQLAlchemy
    loader options.
    """

    resolved_includes = _remove_overlapping_includes(
        resolve_includes(
            resource,
            includes,
        ),
    )

    return tuple(
        build_include_option(
            resource,
            include,
            fieldsets,
        )
        for include in resolved_includes
    )
