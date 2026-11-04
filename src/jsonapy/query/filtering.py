"""Parse filter parameters and infer operations from field declarations.

FilterSpecList preserves ordered client values as strings. resolve_filters
checks public relationship paths and field capabilities, producing operation
and value tuples. RangeFilter accepts colon or double-dot separators; use
double dots for timestamp boundaries. Backend adapters convert values and
build predicates; applications decide which fields to expose.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Iterator, Mapping

from ..resource.base import Resource
from ..resource.fields import Field
from ..resource.options import (
    BooleanFilter,
    Filter,
    MultiValueFilter,
    RangeFilter,
    TextFilter,
)


# --------------------------------------------------------------------------
# Filter operations
# --------------------------------------------------------------------------


class FilterOp(StrEnum):
    """
    Semantic filter operation.

    The client does not normally specify these operations explicitly.

    The Resource's filter declaration determines which operation is
    appropriate for the supplied value.

    Examples:

        Filter()
            -> EQ

        MultiValueFilter()
            -> IN

        RangeFilter()
            -> RANGE

        TextFilter()
            -> CONTAINS

        BooleanFilter()
            -> EQ
    """

    EQ = "eq"
    IN = "in"
    RANGE = "range"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


# --------------------------------------------------------------------------
# Filter specification
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilterSpec:
    """
    A single filter requested by the client.

    The value is intentionally kept as a string at this stage.

    Conversion into the appropriate Python type is the responsibility
    of the adapter/resolution layer because the Resource Field determines
    the expected type.

    Examples:

        FilterSpec(
            field="category",
            value="news",
        )

        FilterSpec(
            field="status",
            value="draft,published",
        )

        FilterSpec(
            field="author.rank",
            value="1000:2000",
        )
    """

    field: str
    value: str

    def __post_init__(self) -> None:
        field = self.field.strip()

        if not field:
            raise ValueError(
                "Filter field cannot be empty.",
            )

        object.__setattr__(
            self,
            "field",
            field,
        )

    def __str__(self) -> str:
        return f"filter[{self.field}]={self.value}"


# --------------------------------------------------------------------------
# Filter specification collection
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilterSpecList:
    """
    An ordered collection of FilterSpec objects.
    """

    items: tuple[FilterSpec, ...] = ()

    def __iter__(self) -> Iterator[FilterSpec]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __getitem__(
            self,
            index: int,
    ) -> FilterSpec:
        return self.items[index]

    @classmethod
    def from_iterable(
            cls,
            specs: Iterable[FilterSpec],
    ) -> "FilterSpecList":
        return cls(tuple(specs))

    @classmethod
    def parse(
            cls,
            parameters: Mapping[str, str | Iterable[str]] | None,
    ) -> "FilterSpecList":
        """
        Parse filter query parameters.

        Expected JSON:API-style parameters:

            filter[category]=news

            filter[category]=news,opinion

            filter[author.rank]=1000:2000

        The parser intentionally does not determine the operation.
        That happens when the filter is resolved against a Resource.

        Parameters that are not ``filter[...]`` parameters are ignored.

        Repeated parameters are preserved as separate FilterSpec objects.
        """

        if not parameters:
            return cls()

        specs: list[FilterSpec] = []

        for parameter, raw_value in parameters.items():
            field = cls._extract_field(parameter)

            if field is None:
                continue

            if isinstance(raw_value, str):
                specs.append(
                    FilterSpec(
                        field=field,
                        value=raw_value.strip(),
                    ),
                )
                continue

            for value in raw_value:
                specs.append(
                    FilterSpec(
                        field=field,
                        value=str(value).strip(),
                    ),
                )

        return cls.from_iterable(specs)

    @staticmethod
    def _extract_field(
            parameter: str,
    ) -> str | None:
        """
        Extract the field name from a JSON:API filter parameter.

        Example:

            filter[category]
                -> category

        Returns None for non-filter parameters.
        """

        if not parameter.startswith("filter["):
            return None

        if not parameter.endswith("]"):
            raise ValueError(
                f"Invalid filter parameter {parameter!r}.",
            )

        field = parameter[7:-1].strip()

        if not field:
            raise ValueError(
                "Filter field cannot be empty.",
            )

        return field

    def to_query_parameters(
            self,
    ) -> dict[str, str]:
        """
        Convert filters into JSON:API query parameters.

        Repeated filters for the same field are combined using commas.

        Example:

            FilterSpec("status", "draft")
            FilterSpec("status", "published")

        becomes:

            {
                "filter[status]": "draft,published"
            }
        """

        parameters: dict[str, list[str]] = {}

        for spec in self.items:
            key = f"filter[{spec.field}]"

            parameters.setdefault(
                key,
                [],
            ).append(spec.value)

        return {
            key: ",".join(values)
            for key, values in parameters.items()
        }

    def to_query_string(self) -> str:
        """
        Return the filter portion as a query-string-like string.

        This is primarily useful for debugging and tests.
        """

        return "&".join(
            f"filter[{spec.field}]={spec.value}"
            for spec in self.items
        )


# --------------------------------------------------------------------------
# Resolved filter
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResolvedFilter:
    """
    A FilterSpec resolved against a Resource field.

    The Resource declaration determines the semantic operation.

    Examples:

        Filter()
            value="news"
            -> EQ

        MultiValueFilter()
            value="news,opinion"
            -> IN

        RangeFilter()
            value="100:200"
            -> RANGE

        TextFilter()
            value="BRCA"
            -> CONTAINS

        BooleanFilter()
            value="true"
            -> EQ
    """

    spec: FilterSpec
    resource: type[Resource]
    field: Field
    operation: FilterOp
    values: tuple[str, ...]

    @property
    def public_name(self) -> str:
        return self.field.public_name

    @property
    def path(self) -> tuple[str, ...]:
        return tuple(
            self.spec.field.split(".")
        )

    @property
    def value(self) -> str:
        """
        Return the original single filter value.

        For multi-value filters, use ``values`` instead.
        """

        return self.spec.value

    @property
    def is_multi_value(self) -> bool:
        return self.operation is FilterOp.IN

    @property
    def is_range(self) -> bool:
        return self.operation is FilterOp.RANGE


class FilterResolutionError(ValueError):
    """
    Raised when a filter cannot be resolved against a Resource.
    """


# --------------------------------------------------------------------------
# Filter value parsing
# --------------------------------------------------------------------------


def _parse_multi_value(
        value: str,
) -> tuple[str, ...]:
    """
    Parse a comma-separated multi-value filter.

    Example:

        "draft,published"

        -> ("draft", "published")
    """

    values = tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )

    if not values:
        raise FilterResolutionError(
            "Multi-value filter cannot be empty.",
        )

    return values


def _parse_range(
        value: str,
) -> tuple[str, str]:
    """
    Parse a range filter.

    Range syntax:

        100:200
        2026-01-01T10:00:00..2026-01-02T10:00:00

    Use ``..`` when boundaries contain colons, such as ISO timestamps.
    Either boundary may be omitted, but not both.
    """

    # The alternative separator leaves colons inside ISO timestamps intact.
    separator = ".." if ".." in value else ":"
    parts = value.split(separator)

    if len(parts) != 2:
        raise FilterResolutionError(
            f"Invalid range value {value!r}. "
            "Expected '<start>:<end>' or '<start>..<end>'.",
        )

    start, end = (
        part.strip()
        for part in parts
    )

    if not start and not end:
        raise FilterResolutionError(
            f"Invalid range value {value!r}. "
            "At least one range boundary is required.",
        )

    return start, end


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------


def _resolve_field(
        resource: type[Resource],
        field_path: str,
) -> tuple[type[Resource], Field]:
    """
    Resolve a filter field path against a Resource.

    Examples:

        category

        author.rank

        author.organization.sortOrder
    """

    parts = tuple(
        part.strip()
        for part in field_path.split(".")
    )

    if not parts or any(not part for part in parts):
        raise FilterResolutionError(
            f"Invalid filter path {field_path!r}.",
        )

    current_resource = resource

    for index, part in enumerate(parts):
        field_result = (
            current_resource.field_for_public_name(
                part,
            )
        )

        if field_result is not None:
            _, field = field_result

            if index != len(parts) - 1:
                raise FilterResolutionError(
                    f"Filter path {field_path!r} is invalid: "
                    f"{part!r} is a field, but additional path "
                    "components follow it.",
                )

            return current_resource, field

        relationship_result = (
            current_resource.relationship_for_public_name(
                part,
            )
        )

        if relationship_result is None:
            raise FilterResolutionError(
                f"Resource {current_resource.__name__!r} has no "
                f"field or relationship named {part!r} while "
                f"resolving filter {field_path!r}.",
            )

        _, relationship = relationship_result

        if index == len(parts) - 1:
            raise FilterResolutionError(
                f"Filter path {field_path!r} ends at relationship "
                f"{part!r}; a field is required.",
            )

        current_resource = relationship.resource

    raise FilterResolutionError(
        f"Filter path {field_path!r} does not resolve to a field.",
    )


def _resolve_filter_definition(
        field: Field,
) -> Filter:
    filter_definition = field.options.filterable

    if filter_definition is None:
        raise FilterResolutionError(
            f"Field {field.public_name!r} is not filterable.",
        )

    return filter_definition


def resolve_filter(
        resource: type[Resource],
        spec: FilterSpec,
) -> ResolvedFilter:
    """
    Resolve a FilterSpec against a Resource.

    The declared filter type determines the operation.

    Examples:

        Filter()
            filter[x]=10
            -> EQ

        MultiValueFilter()
            filter[x]=10,20
            -> IN

        RangeFilter()
            filter[x]=10:20
            -> RANGE

        TextFilter()
            filter[x]=abc
            -> CONTAINS

        BooleanFilter()
            filter[x]=true
            -> EQ
    """

    _, field = _resolve_field(
        resource,
        spec.field,
    )

    filter_definition = _resolve_filter_definition(
        field,
    )

    # ------------------------------------------------------------------
    # Multi-value filter
    # ------------------------------------------------------------------

    if isinstance(
            filter_definition,
            MultiValueFilter,
    ):
        values = _parse_multi_value(
            spec.value,
        )

        return ResolvedFilter(
            spec=spec,
            resource=resource,
            field=field,
            operation=FilterOp.IN,
            values=values,
        )

    # ------------------------------------------------------------------
    # Range filter
    # ------------------------------------------------------------------

    if isinstance(
            filter_definition,
            RangeFilter,
    ):
        values = _parse_range(
            spec.value,
        )

        return ResolvedFilter(
            spec=spec,
            resource=resource,
            field=field,
            operation=FilterOp.RANGE,
            values=values,
        )

    # ------------------------------------------------------------------
    # Text filter
    # ------------------------------------------------------------------

    if isinstance(
            filter_definition,
            TextFilter,
    ):
        if not spec.value:
            raise FilterResolutionError(
                f"Text filter for field "
                f"{field.public_name!r} cannot be empty.",
            )

        return ResolvedFilter(
            spec=spec,
            resource=resource,
            field=field,
            operation=FilterOp.CONTAINS,
            values=(spec.value,),
        )

    # ------------------------------------------------------------------
    # Boolean filter
    # ------------------------------------------------------------------

    if isinstance(
            filter_definition,
            BooleanFilter,
    ):
        value = spec.value.lower()

        if value not in {
            "true",
            "false",
        }:
            raise FilterResolutionError(
                f"Invalid boolean value {spec.value!r} "
                f"for field {field.public_name!r}. "
                "Expected 'true' or 'false'.",
            )

        return ResolvedFilter(
            spec=spec,
            resource=resource,
            field=field,
            operation=FilterOp.EQ,
            values=(value,),
        )

    # ------------------------------------------------------------------
    # Generic equality filter
    # ------------------------------------------------------------------

    if isinstance(
            filter_definition,
            Filter,
    ):
        if not spec.value:
            raise FilterResolutionError(
                f"Filter value for field "
                f"{field.public_name!r} cannot be empty.",
            )

        return ResolvedFilter(
            spec=spec,
            resource=resource,
            field=field,
            operation=FilterOp.EQ,
            values=(spec.value,),
        )

    raise FilterResolutionError(
        f"Unsupported filter declaration "
        f"{type(filter_definition).__name__!r} "
        f"for field {field.public_name!r}.",
    )


def resolve_filters(
        resource: type[Resource],
        specs: FilterSpecList,
) -> tuple[ResolvedFilter, ...]:
    """
    Resolve all filters against a Resource.
    """

    return tuple(
        resolve_filter(
            resource,
            spec,
        )
        for spec in specs
    )


# --------------------------------------------------------------------------
# Parsing / formatting convenience functions
# --------------------------------------------------------------------------


def parse_filter(
        parameters: Mapping[str, str | Iterable[str]] | None,
) -> FilterSpecList:
    """
    Parse JSON:API filter query parameters.

    Example:
        filter[status]=draft&filter[category]=news

    Returns a FilterSpecList containing the requested filters.
    """

    return FilterSpecList.parse(parameters)


def format_filter(
        specs: Iterable[FilterSpec],
) -> dict[str, str]:
    """
    Convert FilterSpec objects into JSON:API filter parameters.

    Example:

        format_filter([
            FilterSpec("status", "draft,published"),
            FilterSpec("category", "news"),
        ])

    returns:

        {
            "filter[status]": "draft,published",
            "filter[category]": "news",
        }
    """

    return (
        FilterSpecList
        .from_iterable(specs)
        .to_query_parameters()
    )
