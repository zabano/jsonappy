from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.sqltypes import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    Numeric,
    String,
    Time,
)

from .paths import (
    SQLAlchemyPathResolutionError,
    SQLAlchemyResolvedPath,
    resolve_sqlalchemy_path,
)
from ...query.filtering import (
    FilterOp,
    FilterSpec,
    ResolvedFilter,
    resolve_filter,
)
from ...resource.base import Resource


# ==========================================================================
# Errors
# ==========================================================================


class SQLAlchemyFilterError(ValueError):
    """
    Raised when a JSON:API filter cannot be converted into an SQLAlchemy
    expression.
    """


# ==========================================================================
# Resolved SQLAlchemy filter
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SQLAlchemyResolvedFilter:
    """
    A filter resolved all the way to SQLAlchemy.
    """

    filter: ResolvedFilter
    path: SQLAlchemyResolvedPath
    expression: ColumnElement[Any]

    @property
    def column(self) -> ColumnElement[Any]:
        return self.path.column

    @property
    def relationships(self):
        return self.path.relationships

    @property
    def operation(self) -> FilterOp:
        return self.filter.operation


# ==========================================================================
# Filter value helpers
# ==========================================================================


def _first_value(
        resolved_filter: ResolvedFilter,
) -> str:
    """
    Return the first value from a resolved filter.
    """

    if not resolved_filter.values:
        raise SQLAlchemyFilterError(
            f"Filter for field "
            f"{resolved_filter.public_name!r} has no values.",
        )

    return resolved_filter.values[0]


# ==========================================================================
# Value coercion
# ==========================================================================


def _coerce_value(
        column: ColumnElement[Any],
        value: str,
) -> Any:
    """
    Convert a query-string value into the Python value expected by the
    SQLAlchemy column type.
    """

    column_type = getattr(
        column,
        "type",
        None,
    )

    if column_type is None:
        return value

    # ------------------------------------------------------------------
    # Boolean
    # ------------------------------------------------------------------

    if isinstance(column_type, Boolean):
        normalized = value.strip().lower()

        if normalized in {"true", "1", "yes"}:
            return True

        if normalized in {"false", "0", "no"}:
            return False

        raise SQLAlchemyFilterError(
            f"Invalid boolean value {value!r}.",
        )

    # ------------------------------------------------------------------
    # Integer
    # ------------------------------------------------------------------

    if isinstance(column_type, Integer):
        try:
            return int(value)
        except ValueError as exc:
            raise SQLAlchemyFilterError(
                f"Invalid integer value {value!r}.",
            ) from exc

    # ------------------------------------------------------------------
    # Float
    # ------------------------------------------------------------------

    if isinstance(column_type, Float):
        try:
            return float(value)
        except ValueError as exc:
            raise SQLAlchemyFilterError(
                f"Invalid floating-point value {value!r}.",
            ) from exc

    # ------------------------------------------------------------------
    # Numeric / Decimal
    # ------------------------------------------------------------------

    if isinstance(column_type, Numeric):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise SQLAlchemyFilterError(
                f"Invalid numeric value {value!r}.",
            ) from exc

    # ------------------------------------------------------------------
    # DateTime
    # ------------------------------------------------------------------

    if isinstance(column_type, DateTime):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise SQLAlchemyFilterError(
                f"Invalid datetime value {value!r}. "
                "Expected ISO-8601 format.",
            ) from exc

    # ------------------------------------------------------------------
    # Date
    # ------------------------------------------------------------------

    if isinstance(column_type, Date):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise SQLAlchemyFilterError(
                f"Invalid date value {value!r}. "
                "Expected YYYY-MM-DD.",
            ) from exc

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------

    if isinstance(column_type, Time):
        try:
            return time.fromisoformat(value)
        except ValueError as exc:
            raise SQLAlchemyFilterError(
                f"Invalid time value {value!r}. "
                "Expected ISO-8601 time format.",
            ) from exc

    # ------------------------------------------------------------------
    # Enum
    # ------------------------------------------------------------------

    if isinstance(column_type, SAEnum):
        enum_class = column_type.enum_class

        if enum_class is None:
            return value

        try:
            return enum_class(value)
        except ValueError:
            try:
                return enum_class[value]
            except KeyError as exc:
                raise SQLAlchemyFilterError(
                    f"Invalid enum value {value!r}.",
                ) from exc

    # ------------------------------------------------------------------
    # String
    # ------------------------------------------------------------------

    if isinstance(column_type, String):
        return value

    return value


# ==========================================================================
# Expression construction
# ==========================================================================


def _column_expression(
        column: ColumnElement[Any],
        resolved_filter: ResolvedFilter,
) -> ColumnElement[Any]:
    """
    Build the SQLAlchemy expression for a resolved filter.
    """

    if not resolved_filter.values:
        raise SQLAlchemyFilterError(
            f"Filter for field "
            f"{resolved_filter.public_name!r} has no values.",
        )

    if resolved_filter.operation is FilterOp.EQ:
        value = _first_value(
            resolved_filter,
        )

        return column == _coerce_value(
            column,
            value,
        )

    if resolved_filter.operation is FilterOp.IN:
        converted_values = tuple(
            _coerce_value(
                column,
                value,
            )
            for value in resolved_filter.values
        )

        return column.in_(
            converted_values,
        )

    if resolved_filter.operation is FilterOp.RANGE:
        if len(resolved_filter.values) != 2:
            raise SQLAlchemyFilterError(
                f"Range filter for field "
                f"{resolved_filter.public_name!r} "
                "must contain exactly two values.",
            )

        start_value, end_value = resolved_filter.values

        expressions: list[ColumnElement[Any]] = []

        if start_value:
            expressions.append(
                column >= _coerce_value(column, start_value),
            )

        if end_value:
            expressions.append(
                column <= _coerce_value(column, end_value),
            )

        return and_(*expressions)

    if resolved_filter.operation is FilterOp.CONTAINS:
        value = _first_value(
            resolved_filter,
        )

        return column.icontains(
            _coerce_value(
                column,
                value,
            ),
            autoescape=True,
        )

    if resolved_filter.operation is FilterOp.STARTS_WITH:
        value = _first_value(
            resolved_filter,
        )

        return column.startswith(
            _coerce_value(
                column,
                value,
            ),
        )

    if resolved_filter.operation is FilterOp.ENDS_WITH:
        value = _first_value(
            resolved_filter,
        )

        return column.endswith(
            _coerce_value(
                column,
                value,
            ),
        )

    raise SQLAlchemyFilterError(
        f"Unsupported filter operation "
        f"{resolved_filter.operation!r}.",
    )


# ==========================================================================
# Resolution
# ==========================================================================


def resolve_sqlalchemy_filter(
        resource: type[Resource],
        filter_: ResolvedFilter,
) -> SQLAlchemyResolvedFilter:
    """
    Resolve a Resource-level filter to SQLAlchemy.
    """

    try:
        path = resolve_sqlalchemy_path(
            resource,
            filter_.spec.field,
        )
    except SQLAlchemyPathResolutionError as exc:
        raise SQLAlchemyFilterError(
            str(exc),
        ) from exc

    many_relationships = tuple(
        relationship.public_name
        for relationship in path.resource_path.relationships
        if relationship.many
    )

    if many_relationships:
        raise SQLAlchemyFilterError(
            f"Filtering through to-many relationship "
            f"{many_relationships[0]!r} is not supported.",
        )

    expression = _column_expression(
        path.column,
        filter_,
    )

    return SQLAlchemyResolvedFilter(
        filter=filter_,
        path=path,
        expression=expression,
    )


def resolve_sqlalchemy_filter_spec(
        resource: type[Resource],
        spec: FilterSpec,
) -> SQLAlchemyResolvedFilter:
    """
    Resolve a raw FilterSpec directly to SQLAlchemy.
    """

    try:
        resolved_filter = resolve_filter(
            resource,
            spec,
        )
    except ValueError as exc:
        raise SQLAlchemyFilterError(
            str(exc),
        ) from exc

    return resolve_sqlalchemy_filter(
        resource,
        resolved_filter,
    )


def resolve_sqlalchemy_filters(
        resource: type[Resource],
        filters: tuple[ResolvedFilter, ...],
) -> tuple[SQLAlchemyResolvedFilter, ...]:
    """
    Resolve multiple Resource-level filters to SQLAlchemy.
    """

    return tuple(
        resolve_sqlalchemy_filter(
            resource,
            filter_,
        )
        for filter_ in filters
    )


def resolve_sqlalchemy_filter_specs(
        resource: type[Resource],
        specs: tuple[FilterSpec, ...],
) -> tuple[SQLAlchemyResolvedFilter, ...]:
    """
    Resolve multiple raw FilterSpec objects directly to SQLAlchemy.
    """

    return tuple(
        resolve_sqlalchemy_filter_spec(
            resource,
            spec,
        )
        for spec in specs
    )


# ==========================================================================
# WHERE expressions
# ==========================================================================


def sqlalchemy_where_clauses(
        filters: tuple[SQLAlchemyResolvedFilter, ...],
) -> tuple[ColumnElement[Any], ...]:
    """
    Return SQLAlchemy WHERE clauses.

    Multiple filter parameters are returned separately, so SQLAlchemy
    can combine them using normal AND semantics.
    """

    return tuple(
        filter_.expression
        for filter_ in filters
    )


def apply_filtering(
        stmt: Any,
        filters: tuple[SQLAlchemyResolvedFilter, ...],
) -> Any:
    """
    Apply already-resolved SQLAlchemy filters to a Select.
    """

    clauses = sqlalchemy_where_clauses(
        filters,
    )

    if not clauses:
        return stmt

    return stmt.where(
        *clauses,
    )
