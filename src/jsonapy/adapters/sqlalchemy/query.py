from dataclasses import replace
from typing import Any

from sqlalchemy import Select, inspect
from sqlalchemy.orm import aliased
from sqlalchemy.sql.util import ClauseAdapter

from .fieldsets import (
    SQLAlchemyFieldsetError,
    SQLAlchemyResolvedFieldset,
    resolve_sqlalchemy_fieldset,
)
from .filtering import (
    SQLAlchemyFilterError,
    SQLAlchemyResolvedFilter,
    resolve_sqlalchemy_filters,
)
from .include import (
    SQLAlchemyIncludeError,
    build_include_options,
)
from .pagination import (
    apply_pagination,
    build_count_query,
    execute_count,
)
from .sorting import (
    SQLAlchemyResolvedSort,
    SQLAlchemySortError,
    resolve_sqlalchemy_sorts,
)
from ...query.fieldsets import (
    FieldsetResolutionError,
    FieldsetSpecList,
    ResolvedFieldset,
    resolve_fieldsets,
)
from ...query.filtering import (
    FilterResolutionError,
    FilterSpecList,
    ResolvedFilter,
    resolve_filters,
)
from ...query.include import IncludeResolutionError, IncludeSpecList
from ...query.pagination import PageSpec, PaginationMeta
from ...query.sorting import (
    ResolvedSort,
    SortResolutionError,
    SortSpecList,
    resolve_sorts,
)
from ...query.spec import QuerySpec
from ...resource.base import Resource


# ==========================================================================
# Errors
# ==========================================================================


class SQLAlchemyQueryError(ValueError):
    """
    Raised when a Resource-level query specification cannot be translated
    into an SQLAlchemy query.
    """


# ==========================================================================
# Resolved SQLAlchemy query
# ==========================================================================


class SQLAlchemyResolvedQuery:
    """
    A complete query resolved from the JSON:API/Resource query layer
    into SQLAlchemy components and loader options.

    This object deliberately contains no SQLAlchemy SELECT statement.
    """

    def __init__(
            self,
            *,
            filters: tuple[SQLAlchemyResolvedFilter, ...],
            sorts: tuple[SQLAlchemyResolvedSort, ...],
            fieldsets: tuple[SQLAlchemyResolvedFieldset, ...],
            include_options: tuple[Any, ...],
            page: PageSpec | None,
    ) -> None:
        self.filters = filters
        self.sorts = sorts
        self.fieldsets = fieldsets
        self.include_options = include_options
        self.page = page


def _apply_relationship_joins(
        stmt: Select[Any],
        query: SQLAlchemyResolvedQuery,
) -> tuple[Select[Any], SQLAlchemyResolvedQuery]:
    """
    Join each to-one relationship path required by filters and sorts.

    Prefixes are applied before deeper paths and shared prefixes are
    joined only once. Repeated target models receive independent aliases;
    expressions are adapted without mutating the resolved input query.
    """

    filter_paths = tuple(
        item.path.relationships
        for item in query.filters
        if item.path.relationships
    )
    paths = filter_paths + tuple(
        item.path.relationships
        for item in query.sorts
        if item.path.relationships
    )

    required = {
        tuple(
            (relationship.parent.class_, relationship.key)
            for relationship in relationships[:length]
        )
        for relationships in filter_paths
        for length in range(1, len(relationships) + 1)
    }

    entities: dict[tuple[tuple[type[Any], str], ...], Any] = {}
    used_models = {relationships[0].parent.class_ for relationships in paths}

    for relationships in sorted(paths, key=len):
        for length in range(1, len(relationships) + 1):
            prefix = relationships[:length]
            key = tuple(
                (relationship.parent.class_, relationship.key)
                for relationship in prefix
            )

            if key in entities:
                continue

            relationship = prefix[-1]
            parent = entities[key[:-1]] if length > 1 else relationship.parent.class_
            target_model = relationship.mapper.class_
            target = aliased(target_model) if target_model in used_models else target_model
            used_models.add(target_model)
            attribute = getattr(parent, relationship.key)
            stmt = stmt.join(target, attribute, isouter=key not in required)
            entities[key] = target

    def adapt(item: Any) -> Any:
        if not item.path.relationships:
            return item
        key = tuple(
            (relationship.parent.class_, relationship.key)
            for relationship in item.path.relationships
        )
        entity = inspect(entities[key])
        if not entity.is_aliased_class:
            return item
        expression = ClauseAdapter(entity.selectable).traverse(item.expression)
        return replace(item, expression=expression)

    return stmt, SQLAlchemyResolvedQuery(
        filters=tuple(adapt(item) for item in query.filters),
        sorts=tuple(adapt(item) for item in query.sorts),
        fieldsets=query.fieldsets,
        include_options=query.include_options,
        page=query.page,
    )


# ==========================================================================
# Query resolution
# ==========================================================================


def resolve_sqlalchemy_query(
        resource: type[Resource],
        *,
        filters: FilterSpecList | None = None,
        sorts: SortSpecList | None = None,
        fieldsets: FieldsetSpecList | None = None,
        includes: IncludeSpecList | None = None,
        page: PageSpec | None = None,
) -> SQLAlchemyResolvedQuery:
    """
    Resolve a complete Resource-level query into SQLAlchemy components.

    The query layer remains responsible for parsing and validating
    JSON:API semantics.

    This adapter is responsible only for translating those resolved
    semantics into SQLAlchemy.
    """

    # ------------------------------------------------------------------
    # Normalize optional inputs
    # ------------------------------------------------------------------

    filter_specs = (
        filters
        if filters is not None
        else FilterSpecList()
    )

    sort_specs = (
        sorts
        if sorts is not None
        else SortSpecList()
    )

    fieldset_specs = (
        fieldsets
        if fieldsets is not None
        else FieldsetSpecList()
    )

    include_specs = (
        includes
        if includes is not None
        else IncludeSpecList()
    )

    # ------------------------------------------------------------------
    # Resolve filters
    # ------------------------------------------------------------------

    try:
        resolved_filters: tuple[
            ResolvedFilter,
            ...,
        ] = resolve_filters(
            resource,
            filter_specs,
        )
    except FilterResolutionError as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Resolve sorting
    # ------------------------------------------------------------------

    try:
        resolved_sorts: tuple[
            ResolvedSort,
            ...,
        ] = resolve_sorts(
            resource,
            sort_specs,
        )
    except SortResolutionError as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Resolve fieldset
    # ------------------------------------------------------------------

    try:
        resolved_fieldset: ResolvedFieldset | None = resolve_fieldsets(
            resource,
            fieldset_specs,
        )
    except FieldsetResolutionError as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Translate filters
    # ------------------------------------------------------------------

    try:
        sqlalchemy_filters: tuple[
            SQLAlchemyResolvedFilter,
            ...,
        ] = resolve_sqlalchemy_filters(
            resource,
            resolved_filters,
        )
    except SQLAlchemyFilterError as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Translate sorting
    # ------------------------------------------------------------------

    try:
        sqlalchemy_sorts: tuple[
            SQLAlchemyResolvedSort,
            ...,
        ] = resolve_sqlalchemy_sorts(
            resource,
            resolved_sorts,
        )
    except SQLAlchemySortError as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Translate fieldset
    # ------------------------------------------------------------------

    if resolved_fieldset is None:
        sqlalchemy_fieldsets: tuple[
            SQLAlchemyResolvedFieldset,
            ...,
        ] = ()
    else:
        try:
            sqlalchemy_fieldset = resolve_sqlalchemy_fieldset(
                resource,
                resolved_fieldset,
            )
        except SQLAlchemyFieldsetError as exc:
            raise SQLAlchemyQueryError(
                str(exc),
            ) from exc

        sqlalchemy_fieldsets = (
            sqlalchemy_fieldset,
        )

    # ------------------------------------------------------------------
    # Translate includes
    # ------------------------------------------------------------------

    try:
        include_options: tuple[Any, ...] = (
            build_include_options(
                resource,
                include_specs,
                fieldset_specs,
            )
            if include_specs
            else ()
        )
    except (IncludeResolutionError, SQLAlchemyIncludeError) as exc:
        raise SQLAlchemyQueryError(
            str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # Build resolved query
    # ------------------------------------------------------------------

    return SQLAlchemyResolvedQuery(
        filters=sqlalchemy_filters,
        sorts=sqlalchemy_sorts,
        fieldsets=sqlalchemy_fieldsets,
        include_options=include_options,
        page=page,
    )


# ==========================================================================
# Applying resolved query
# ==========================================================================


def apply_sqlalchemy_query(
        stmt: Select[Any],
        query: SQLAlchemyResolvedQuery,
) -> Select[Any]:
    """
    Apply all resolved query components to an SQLAlchemy SELECT.

    The order is intentional:

        filters
        fieldsets
        includes
        sorting
        pagination

    Pagination is applied last.
    """

    stmt, query = _apply_relationship_joins(
        stmt,
        query,
    )

    from .fieldsets import apply_fieldsets
    from .filtering import apply_filtering
    from .sorting import apply_sorting

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    stmt = apply_filtering(
        stmt,
        query.filters,
    )

    # ------------------------------------------------------------------
    # Fieldsets
    # ------------------------------------------------------------------

    stmt = apply_fieldsets(
        stmt,
        query.fieldsets,
    )

    # ------------------------------------------------------------------
    # Includes
    # ------------------------------------------------------------------

    if query.include_options:
        stmt = stmt.options(
            *query.include_options,
        )

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    stmt = apply_sorting(
        stmt,
        query.sorts,
    )

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    if query.page is not None:
        stmt = apply_pagination(
            stmt,
            query.page,
        )

    return stmt


# ==========================================================================
# Count query
# ==========================================================================


def build_sqlalchemy_count_query(
        stmt: Select[Any],
) -> Select[Any]:
    """
    Build a count query from an unpaginated SQLAlchemy statement.
    """

    return build_count_query(
        stmt,
    )


# ==========================================================================
# Complete query application
# ==========================================================================


def build_sqlalchemy_query(
        stmt: Select[Any],
        resource: type[Resource],
        *,
        filters: FilterSpecList | None = None,
        sorts: SortSpecList | None = None,
        fieldsets: FieldsetSpecList | None = None,
        includes: IncludeSpecList | None = None,
        page: PageSpec | None = None,
) -> Select[Any]:
    """
    Resolve and apply a complete JSON:API query to an SQLAlchemy SELECT.

    This is the main convenience entry point for callers that already
    have parsed query specifications.
    """

    resolved_query = resolve_sqlalchemy_query(
        resource,
        filters=filters,
        sorts=sorts,
        fieldsets=fieldsets,
        includes=includes,
        page=page,
    )

    return apply_sqlalchemy_query(
        stmt,
        resolved_query,
    )


def build_sqlalchemy_query_from_spec(
        stmt: Select[Any],
        resource: type[Resource],
        spec: QuerySpec,
        *,
        paginate: bool = True,
) -> Select[Any]:
    """Resolve and apply a complete parsed QuerySpec."""

    return build_sqlalchemy_query(
        stmt,
        resource,
        filters=spec.filters,
        sorts=spec.sort,
        fieldsets=spec.fieldsets,
        includes=spec.include,
        page=spec.pagination if paginate else None,
    )


def paginate_sqlalchemy_query(
        session: Any,
        stmt: Select[Any],
        resource: type[Resource],
        spec: QuerySpec,
) -> tuple[Select[Any], PaginationMeta]:
    """Apply a QuerySpec and calculate pagination metadata."""

    unpaginated = build_sqlalchemy_query_from_spec(
        stmt,
        resource,
        spec,
        paginate=False,
    )
    total = execute_count(session, unpaginated)
    paginated = apply_pagination(unpaginated, spec.pagination)

    return paginated, PaginationMeta.from_page(spec.pagination, total)
