"""Parse sort directions and validate sortable public field paths.

SortSpecList accepts comma-separated fields with a leading minus for
descending order. resolve_sorts follows declared relationships and checks the
terminal field's sortable option. Backend adapters translate the resulting
ResolvedSort objects into ordering expressions and enforce backend limits.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Iterator

from ..resource import ResolvedFieldPath
from ..resource.base import Resource
from ..resource.fields import Field


# ==========================================================================
# Sort order
# ==========================================================================


class SortOrder(StrEnum):
    """
    Direction in which a field should be sorted.
    """

    ASC = "asc"
    DESC = "desc"


# ==========================================================================
# Sort specification
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SortSpec:
    """
    A single sort specification.

    The field is the public JSON:API field path.

    Examples:

        SortSpec("author.name")

        SortSpec(
            field="author.rank",
            order=SortOrder.DESC,
        )
    """

    field: str
    order: SortOrder = SortOrder.ASC

    def __post_init__(self) -> None:
        field = self.field.strip()

        if not field:
            raise ValueError(
                "Sort field cannot be empty.",
            )

        if field.startswith("-"):
            raise ValueError(
                "SortSpec.field must not contain the '-' prefix.",
            )

        object.__setattr__(
            self,
            "field",
            field,
        )

    @property
    def ascending(self) -> bool:
        """
        Whether this sort is ascending.
        """
        return self.order is SortOrder.ASC

    @property
    def descending(self) -> bool:
        """
        Whether this sort is descending.
        """
        return self.order is SortOrder.DESC

    def __str__(self) -> str:
        """
        Return the JSON:API representation.

        Examples:

            author.name
            -author.rank
        """
        if self.descending:
            return f"-{self.field}"

        return self.field


# ==========================================================================
# Sort specification collection
# ==========================================================================


@dataclass(frozen=True, slots=True)
class SortSpecList:
    """
    An ordered collection of SortSpec objects.
    """

    items: tuple[SortSpec, ...] = ()

    def __iter__(self) -> Iterator[SortSpec]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __getitem__(self, index: int) -> SortSpec:
        return self.items[index]

    def __str__(self) -> str:
        return ",".join(
            str(item)
            for item in self.items
        )

    @classmethod
    def from_iterable(
            cls,
            specs: Iterable[SortSpec],
    ) -> "SortSpecList":
        """
        Create a SortSpecList from an iterable of SortSpec objects.
        """
        return cls(tuple(specs))

    @classmethod
    def parse(
            cls,
            value: str | None,
    ) -> "SortSpecList":
        """
        Parse a JSON:API sort query parameter.

        Examples:

            "author.name,author.rank"

                -> ASC author.name
                -> ASC author.rank

            "-author.name,-author.rank"

                -> DESC author.name
                -> DESC author.rank

            "author.name,-author.rank"

                -> ASC author.name
                -> DESC author.rank

        Empty entries are ignored.

        Raises
        ------
        ValueError
            If a sort field is invalid.
        """

        if value is None:
            return cls()

        value = value.strip()

        if not value:
            return cls()

        specs: list[SortSpec] = []

        for raw_field in value.split(","):
            raw_field = raw_field.strip()

            if not raw_field:
                continue

            order = SortOrder.ASC

            if raw_field.startswith("-"):
                order = SortOrder.DESC
                raw_field = raw_field[1:].strip()

            if not raw_field:
                raise ValueError(
                    "Sort field cannot be empty.",
                )

            specs.append(
                SortSpec(
                    field=raw_field,
                    order=order,
                ),
            )

        return cls.from_iterable(specs)

    def to_query_string(self) -> str:
        """
        Convert the collection back into a JSON:API sort parameter.
        """
        return str(self)


# ==========================================================================
# Resolved sorting
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ResolvedSort:
    """
    A sort specification resolved against a Resource.

    ``Resource.resolve_path()`` is responsible for resolving the public
    attribute path. This class adds the sorting-specific semantics.
    """

    spec: SortSpec
    resolved_field: ResolvedFieldPath

    @property
    def field(self) -> Field:
        """
        The final Field declaration targeted by the sort.
        """
        return self.resolved_field.field

    @property
    def path(self) -> tuple[str, ...]:
        """
        The resolved resource path.

        Example:

            ("author", "organization", "sortOrder")
        """
        return self.resolved_field.path

    @property
    def ascending(self) -> bool:
        """
        Whether the sort is ascending.
        """
        return self.spec.ascending

    @property
    def descending(self) -> bool:
        """
        Whether the sort is descending.
        """
        return self.spec.descending


class SortResolutionError(ValueError):
    """
    Raised when a sort specification cannot be resolved against a
    Resource or targets a field that is not sortable.
    """


# ==========================================================================
# Sort resolution
# ==========================================================================


def resolve_sort(
        resource: type[Resource],
        spec: SortSpec,
) -> ResolvedSort:
    """
    Resolve a SortSpec against a Resource.

    The Resource layer is responsible for resolving the public field path.
    The sorting layer verifies that the resolved field is sortable.

    Examples
    --------

    Given:

        class ArticleResource(Resource):
            author = Relationship(AuthorResource)

    and:

        class AuthorResource(Resource):
            name = String(sortable=True)

    then:

        resolve_sort(
            ArticleResource,
            SortSpec("author.name"),
        )

    produces a ResolvedSort whose:

        spec.field == "author.name"
        path == ("author", "name")
        field == AuthorResource.name
    """

    try:
        resolved_field = resource.resolve_path(
            spec.field,
        )
    except ValueError as exc:
        raise SortResolutionError(
            str(exc),
        ) from exc

    if resolved_field.field.options.sortable is None:
        raise SortResolutionError(
            f"Field {spec.field!r} is not sortable.",
        )

    return ResolvedSort(
        spec=spec,
        resolved_field=resolved_field,
    )


def resolve_sorts(
        resource: type[Resource],
        specs: SortSpecList,
) -> tuple[ResolvedSort, ...]:
    """
    Resolve multiple sort specifications against a Resource.

    The order of the returned tuple is identical to the order supplied
    by the client.
    """

    return tuple(
        resolve_sort(
            resource,
            spec,
        )
        for spec in specs
    )


# ==========================================================================
# Parsing / formatting convenience functions
# ==========================================================================


def parse_sort(
        value: str | None,
) -> SortSpecList:
    """
    Parse a JSON:API sort parameter.

    Example:
        "author.name,-author.rank"

    Returns a SortSpecList containing two SortSpec objects:
    one ascending for ``author.name`` and one descending for
    ``author.rank``.
    """

    return SortSpecList.parse(value)


def format_sort(
        specs: Iterable[SortSpec],
) -> str:
    """
    Convert SortSpec objects into a JSON:API sort parameter.

    Example:

        format_sort([
            SortSpec("author.name"),
            SortSpec(
                "author.rank",
                SortOrder.DESC,
            ),
        ])

    returns:

        "author.name,-author.rank"
    """

    return str(
        SortSpecList.from_iterable(specs),
    )
