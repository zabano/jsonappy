"""Public query specifications, parsers, resolvers, and query errors.

Parsing records client syntax; resolution checks public names and declared
capabilities against a Resource. QuerySpec combines sorting, filtering,
page-based pagination, sparse fieldsets, and relationship includes. Database
execution and HTTP parameter extraction belong to adapters.

Examples:
    >>> query = QuerySpec.parse(sort="-title", page_number="2", page_size="5")
    >>> query.pagination.offset
    5
    >>> query.sort.to_query_string()
    '-title'
"""

from .fieldsets import (
    FieldsetResolutionError,
    FieldsetSpec,
    FieldsetSpecList,
    ResolvedFieldset,
    format_fieldset,
    parse_fieldset,
    resolve_fieldset,
    resolve_fieldsets,
)
from .filtering import (
    FilterOp,
    FilterResolutionError,
    FilterSpec,
    FilterSpecList,
    ResolvedFilter,
    format_filter,
    parse_filter,
    resolve_filter,
    resolve_filters,
)
from .include import (
    IncludeResolutionError,
    IncludeSpec,
    IncludeSpecList,
    ResolvedInclude,
    format_include,
    parse_include,
    resolve_include,
    resolve_includes,
)
from .pagination import (
    DEFAULT_PAGE_NUMBER,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageSpec,
    PaginationError,
    PaginationMeta,
)
from .spec import (
    QuerySpec,
    ResolvedQuery,
    parse_query,
    resolve_query,
)
from .sorting import (
    ResolvedSort,
    SortOrder,
    SortResolutionError,
    SortSpec,
    SortSpecList,
    format_sort,
    parse_sort,
    resolve_sort,
    resolve_sorts,
)

__all__ = [
    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    "QuerySpec",
    "ResolvedQuery",
    "parse_query",
    "resolve_query",

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------
    "ResolvedSort",
    "SortOrder",
    "SortResolutionError",
    "SortSpec",
    "SortSpecList",
    "format_sort",
    "parse_sort",
    "resolve_sort",
    "resolve_sorts",

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    "FilterOp",
    "FilterResolutionError",
    "FilterSpec",
    "FilterSpecList",
    "ResolvedFilter",
    "format_filter",
    "parse_filter",
    "resolve_filter",
    "resolve_filters",

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    "DEFAULT_PAGE_NUMBER",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PageSpec",
    "PaginationError",
    "PaginationMeta",

    # ------------------------------------------------------------------
    # Fieldsets
    # ------------------------------------------------------------------
    "FieldsetResolutionError",
    "FieldsetSpec",
    "FieldsetSpecList",
    "ResolvedFieldset",
    "format_fieldset",
    "parse_fieldset",
    "resolve_fieldset",
    "resolve_fieldsets",

    # ------------------------------------------------------------------
    # Includes
    # ------------------------------------------------------------------
    "IncludeResolutionError",
    "IncludeSpec",
    "IncludeSpecList",
    "ResolvedInclude",
    "format_include",
    "parse_include",
    "resolve_include",
    "resolve_includes",
]
