from dataclasses import dataclass

from .fieldsets import (
    FieldsetSpecList,
    ResolvedFieldset,
    resolve_fieldsets,
)
from .filtering import (
    FilterSpecList,
    ResolvedFilter,
    resolve_filters,
)
from .include import (
    IncludeSpecList,
    ResolvedInclude,
    resolve_includes,
)
from .pagination import PageSpec
from .sorting import (
    ResolvedSort,
    SortSpecList,
    resolve_sorts,
)
from ..resource.base import Resource


# ==========================================================================
# Query specification
# ==========================================================================


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """
    Complete JSON:API query specification.

    QuerySpec is the central representation of client query parameters.

    It is intentionally independent of:

    - FastAPI
    - SQLAlchemy
    - Pydantic
    - Marshmallow

    Those concerns belong to adapters.

    A query may contain:

    - sorting
    - filtering
    - pagination
    - sparse fieldsets
    - included relationships
    """

    sort: SortSpecList = SortSpecList()
    filters: FilterSpecList = FilterSpecList()
    pagination: PageSpec = PageSpec()
    fieldsets: FieldsetSpecList = FieldsetSpecList()
    include: IncludeSpecList = IncludeSpecList()

    def __bool__(self) -> bool:
        """
        Return whether the query contains any non-default options.

        Default pagination does not by itself make a query non-empty.
        """

        return any(
            (
                bool(self.sort),
                bool(self.filters),
                bool(self.fieldsets),
                bool(self.include),
                self.pagination != PageSpec(),
            ),
        )

    @property
    def is_paginated(self) -> bool:
        """
        Whether pagination differs from the default pagination.
        """

        return self.pagination != PageSpec()

    @property
    def has_sort(self) -> bool:
        return bool(self.sort)

    @property
    def has_filters(self) -> bool:
        return bool(self.filters)

    @property
    def has_fieldsets(self) -> bool:
        return bool(self.fieldsets)

    @property
    def has_include(self) -> bool:
        return bool(self.include)

    @classmethod
    def parse(
            cls,
            *,
            sort: str | None = None,
            filters: FilterSpecList | None = None,
            page_number: int | str | None = None,
            page_size: int | str | None = None,
            fieldsets: FieldsetSpecList | None = None,
            include: str | None = None,
    ) -> "QuerySpec":
        """
        Construct a QuerySpec from already-separated query parameters.

        Parsing of individual query syntaxes remains the responsibility
        of the corresponding query module.
        """

        return cls(
            sort=SortSpecList.parse(sort),
            filters=(
                filters
                if filters is not None
                else FilterSpecList()
            ),
            pagination=PageSpec.parse(
                number=page_number,
                size=page_size,
            ),
            fieldsets=(
                fieldsets
                if fieldsets is not None
                else FieldsetSpecList()
            ),
            include=IncludeSpecList.parse(include),
        )

    # ------------------------------------------------------------------
    # Immutable modifiers
    # ------------------------------------------------------------------

    def with_pagination(
            self,
            pagination: PageSpec,
    ) -> "QuerySpec":
        """
        Return a new QuerySpec with different pagination.
        """

        return QuerySpec(
            sort=self.sort,
            filters=self.filters,
            pagination=pagination,
            fieldsets=self.fieldsets,
            include=self.include,
        )

    def with_sort(
            self,
            sort: SortSpecList,
    ) -> "QuerySpec":
        """
        Return a new QuerySpec with different sorting.
        """

        return QuerySpec(
            sort=sort,
            filters=self.filters,
            pagination=self.pagination,
            fieldsets=self.fieldsets,
            include=self.include,
        )

    def with_filters(
            self,
            filters: FilterSpecList,
    ) -> "QuerySpec":
        """
        Return a new QuerySpec with different filters.
        """

        return QuerySpec(
            sort=self.sort,
            filters=filters,
            pagination=self.pagination,
            fieldsets=self.fieldsets,
            include=self.include,
        )

    def with_fieldsets(
            self,
            fieldsets: FieldsetSpecList,
    ) -> "QuerySpec":
        """
        Return a new QuerySpec with different sparse fieldsets.
        """

        return QuerySpec(
            sort=self.sort,
            filters=self.filters,
            pagination=self.pagination,
            fieldsets=fieldsets,
            include=self.include,
        )

    def with_include(
            self,
            include: IncludeSpecList,
    ) -> "QuerySpec":
        """
        Return a new QuerySpec with different includes.
        """

        return QuerySpec(
            sort=self.sort,
            filters=self.filters,
            pagination=self.pagination,
            fieldsets=self.fieldsets,
            include=include,
        )

    # ------------------------------------------------------------------
    # Query parameters
    # ------------------------------------------------------------------

    def to_query_parameters(self) -> dict[str, str | int]:
        """
        Convert the query specification into JSON:API query parameters.

        Pagination parameters are always included because PageSpec
        always contains concrete values.

        Empty sort, filter, fieldset, and include components are omitted.
        """

        parameters: dict[str, str | int] = {}

        if self.sort:
            parameters["sort"] = self.sort.to_query_string()

        parameters.update(
            self.filters.to_query_parameters(),
        )

        parameters.update(
            self.pagination.to_query_parameters(),
        )

        parameters.update(
            self.fieldsets.to_query_parameters(),
        )

        if self.include:
            parameters["include"] = (
                self.include.to_query_string()
            )

        return parameters


# ==========================================================================
# Resolved query
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ResolvedQuery:
    """
    A QuerySpec resolved against a root Resource.

    QuerySpec represents what the client requested.

    ResolvedQuery represents the same request after all resource-specific
    declarations have been validated and resolved.

    Individual query modules remain responsible for their own resolution.
    This class only coordinates those resolutions.
    """

    spec: QuerySpec
    resource: type[Resource]

    sorts: tuple[ResolvedSort, ...]
    filters: tuple[ResolvedFilter, ...]
    fieldset: ResolvedFieldset | None
    includes: tuple[ResolvedInclude, ...]

    @property
    def pagination(self) -> PageSpec:
        """
        The requested pagination.
        """

        return self.spec.pagination

    @property
    def has_sort(self) -> bool:
        return bool(self.sorts)

    @property
    def has_filters(self) -> bool:
        return bool(self.filters)

    @property
    def has_fieldset(self) -> bool:
        return self.fieldset is not None

    @property
    def has_include(self) -> bool:
        return bool(self.includes)


# ==========================================================================
# Query resolution
# ==========================================================================


def resolve_query(
        resource: type[Resource],
        spec: QuerySpec,
) -> ResolvedQuery:
    """
    Resolve a complete QuerySpec against a Resource.

    Resolution is delegated to the individual query modules.

    Resolution errors are intentionally allowed to propagate unchanged.

    This means callers can distinguish:

        SortResolutionError
        FilterResolutionError
        FieldsetResolutionError
        IncludeResolutionError
    """

    sorts = resolve_sorts(
        resource,
        spec.sort,
    )

    filters = resolve_filters(
        resource,
        spec.filters,
    )

    fieldset = resolve_fieldsets(
        resource,
        spec.fieldsets,
    )

    includes = resolve_includes(
        resource,
        spec.include,
    )

    return ResolvedQuery(
        spec=spec,
        resource=resource,
        sorts=sorts,
        filters=filters,
        fieldset=fieldset,
        includes=includes,
    )


# ==========================================================================
# Convenience helpers
# ==========================================================================


def parse_query(
        *,
        sort: str | None = None,
        filters: FilterSpecList | None = None,
        page_number: int | str | None = None,
        page_size: int | str | None = None,
        fieldsets: FieldsetSpecList | None = None,
        include: str | None = None,
) -> QuerySpec:
    """
    Convenience function for constructing a QuerySpec.
    """

    return QuerySpec.parse(
        sort=sort,
        filters=filters,
        page_number=page_number,
        page_size=page_size,
        fieldsets=fieldsets,
        include=include,
    )
