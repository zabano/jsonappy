from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import asc, desc
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.sql.elements import UnaryExpression, ColumnElement

from .paths import (
    SQLAlchemyPathResolutionError,
    SQLAlchemyResolvedPath,
    resolve_sqlalchemy_path,
)
from ...query.sorting import (
    ResolvedSort,
    SortSpec,
    resolve_sort,
)
from ...resource.base import Resource


# ==========================================================================
# Errors
# ==========================================================================


class SQLAlchemySortError(ValueError):
    """
    Raised when a JSON:API sort specification cannot be converted into
    an SQLAlchemy ORDER BY expression.
    """


# ==========================================================================
# Resolved SQLAlchemy sort
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SQLAlchemyResolvedSort:
    """
    A sort specification resolved all the way to SQLAlchemy.

    This combines:

    - the Resource-level ResolvedSort
    - the SQLAlchemy relationship path
    - the SQLAlchemy ORDER BY expression

    Example:

        -author.organization.sortOrder

    Becomes approximately:

        resource_sort:
            ResolvedSort(...)

        path:
            Article.author
            Author.organization

        column:
            Organization.sort_order

        expression:
            Organization.sort_order DESC
    """

    sort: ResolvedSort
    path: SQLAlchemyResolvedPath
    expression: UnaryExpression[Any]

    @property
    def column(self) -> ColumnElement[Any]:
        """
        The SQLAlchemy column being sorted.
        """
        return self.path.column

    @property
    def relationships(
            self,
    ) -> tuple[RelationshipProperty[Any], ...]:
        """
        SQLAlchemy relationships that must be traversed to reach the
        sorted column.
        """
        return self.path.relationships

    @property
    def ascending(self) -> bool:
        return self.sort.ascending

    @property
    def descending(self) -> bool:
        return self.sort.descending


# ==========================================================================
# Resolution
# ==========================================================================


def resolve_sqlalchemy_sort(
        resource: type[Resource],
        sort: ResolvedSort,
) -> SQLAlchemyResolvedSort:
    """
    Resolve a Resource-level sort specification to SQLAlchemy.

    The Resource layer has already established that the requested field
    exists and is sortable.

    This function maps that resolved field path onto the SQLAlchemy ORM.
    """

    try:
        path = resolve_sqlalchemy_path(
            resource,
            sort.spec.field,
        )
    except SQLAlchemyPathResolutionError as exc:
        raise SQLAlchemySortError(
            str(exc),
        ) from exc

    many_relationships = tuple(
        relationship.public_name
        for relationship in path.resource_path.relationships
        if relationship.many
    )

    if many_relationships:
        raise SQLAlchemySortError(
            f"Sorting through to-many relationship "
            f"{many_relationships[0]!r} is not supported.",
        )

    if sort.ascending:
        expression = asc(
            path.column,
        )
    else:
        expression = desc(
            path.column,
        )

    return SQLAlchemyResolvedSort(
        sort=sort,
        path=path,
        expression=expression,
    )


def resolve_sqlalchemy_sort_spec(
        resource: type[Resource],
        spec: SortSpec,
) -> SQLAlchemyResolvedSort:
    """
    Resolve a raw SortSpec directly to SQLAlchemy.

    This is the convenient entry point when the caller has not already
    resolved the query-level SortSpec.
    """

    try:
        resolved_sort = resolve_sort(
            resource,
            spec,
        )
    except ValueError as exc:
        raise SQLAlchemySortError(
            str(exc),
        ) from exc

    return resolve_sqlalchemy_sort(
        resource,
        resolved_sort,
    )


def resolve_sqlalchemy_sorts(
        resource: type[Resource],
        sorts: tuple[ResolvedSort, ...],
) -> tuple[SQLAlchemyResolvedSort, ...]:
    """
    Resolve multiple Resource-level sort specifications to SQLAlchemy.

    The order supplied by the client is preserved.
    """

    return tuple(
        resolve_sqlalchemy_sort(
            resource,
            sort,
        )
        for sort in sorts
    )


def resolve_sqlalchemy_sort_specs(
        resource: type[Resource],
        specs: tuple[SortSpec],
) -> tuple[SQLAlchemyResolvedSort, ...]:
    """
    Resolve multiple raw SortSpec objects directly to SQLAlchemy.
    """

    return tuple(
        resolve_sqlalchemy_sort_spec(
            resource,
            spec,
        )
        for spec in specs
    )


# ==========================================================================
# ORDER BY expressions
# ==========================================================================


def sqlalchemy_order_by(
        sorts: Iterable[SQLAlchemyResolvedSort],
) -> tuple[UnaryExpression[Any], ...]:
    """
    Return SQLAlchemy ORDER BY expressions.

    Example:

        sorts = resolve_sqlalchemy_sort_specs(
            ArticleResource,
            [
                SortSpec("author.organization.sortOrder"),
                SortSpec(
                    "author.rank",
                    SortOrder.DESC,
                ),
            ],
        )

        stmt = stmt.order_by(
            *sqlalchemy_order_by(sorts),
        )
    """

    return tuple(
        sort.expression
        for sort in sorts
    )


def apply_sorting(
        stmt,
        sorts: Iterable[SQLAlchemyResolvedSort],
):
    """
    Apply already-resolved SQLAlchemy sorting expressions to a Select.

    This is intentionally a very small adapter helper. Query construction
    remains the responsibility of ``adapters/sqlalchemy/query.py``.
    """

    expressions = sqlalchemy_order_by(
        sorts,
    )

    if not expressions:
        return stmt

    return stmt.order_by(
        *expressions,
    )
