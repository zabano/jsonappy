from typing import Any

from sqlalchemy import Select, func, select

from ...query.pagination import PageSpec


# ==========================================================================
# Pagination errors
# ==========================================================================


class SQLAlchemyPaginationError(ValueError):
    """
    Raised when pagination cannot be applied to an SQLAlchemy statement.
    """


# ==========================================================================
# Applying pagination
# ==========================================================================


def apply_pagination(
        stmt: Select[Any],
        page: PageSpec,
) -> Select[Any]:
    """
    Apply a PageSpec to an SQLAlchemy SELECT statement.
    """

    return stmt.offset(
        page.offset,
    ).limit(
        page.limit,
    )


# ==========================================================================
# Count query
# ==========================================================================


def build_count_query(
        stmt: Select[Any],
) -> Select[Any]:
    """
    Build an SQLAlchemy COUNT query from an unpaginated SELECT.

    ORDER BY, LIMIT, and OFFSET are removed before constructing the
    count query.
    """

    countable_stmt = stmt.order_by(None).limit(None).offset(None)
    return select(
        func.count(),
    ).select_from(
        countable_stmt.subquery(),
    )


# ==========================================================================
# Count execution
# ==========================================================================


def execute_count(
        session: Any,
        stmt: Select[Any],
) -> int:
    """
    Execute a count query and return the total number of records.
    """

    result = session.execute(build_count_query(stmt))
    return int(result.scalar_one())


# ==========================================================================
# Convenience pagination
# ==========================================================================


def paginate(
        stmt: Select[Any],
        page: PageSpec,
) -> Select[Any]:
    """
    Convenience alias for apply_pagination().
    """

    return apply_pagination(
        stmt,
        page,
    )
