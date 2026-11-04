"""SQLAlchemy query construction and pagination entry points.

Install the sqlalchemy extra and set Resource.model to an ORM mapped class.
build_sqlalchemy_query_from_spec resolves and applies a QuerySpec;
paginate_sqlalchemy_query also executes its count through a caller-supplied
session. Applications execute returned SELECT statements and own session and
transaction lifetimes. Mutations are outside this adapter's scope.
"""

from .pagination import build_count_query, execute_count
from .query import (
    SQLAlchemyQueryError,
    apply_sqlalchemy_query,
    build_sqlalchemy_count_query,
    build_sqlalchemy_query,
    build_sqlalchemy_query_from_spec,
    paginate_sqlalchemy_query,
    resolve_sqlalchemy_query,
)

__all__ = [
    "SQLAlchemyQueryError",
    "apply_sqlalchemy_query",
    "build_count_query",
    "build_sqlalchemy_count_query",
    "build_sqlalchemy_query",
    "build_sqlalchemy_query_from_spec",
    "execute_count",
    "paginate_sqlalchemy_query",
    "resolve_sqlalchemy_query",
]
