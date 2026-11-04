"""Page-based pagination specifications and response metadata.

PageSpec validates page numbers and bounded sizes and exposes offset and
limit values. PaginationMeta describes totals and page counts separately
from client intent. Database adapters apply limits and count records;
applications supply stable ordering for predictable pagination.
"""

from dataclasses import dataclass

DEFAULT_PAGE_NUMBER = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


class PaginationError(ValueError):
    """
    Raised when a pagination specification is invalid.
    """


@dataclass(frozen=True, slots=True)
class PageSpec:
    """
    Pagination requested by the client.

    ``number`` and ``size`` correspond to the JSON:API pagination
    parameters:

        page[number]
        page[size]

    Example:

        PageSpec(
            number=2,
            size=25,
        )

    represents the second page containing at most 25 records.
    """

    number: int = DEFAULT_PAGE_NUMBER
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.number < 1:
            raise PaginationError(
                "Page number must be greater than or equal to 1.",
            )

        if self.size < 1:
            raise PaginationError(
                "Page size must be greater than or equal to 1.",
            )

        if self.size > MAX_PAGE_SIZE:
            raise PaginationError(
                f"Page size cannot exceed {MAX_PAGE_SIZE}.",
            )

    @property
    def offset(self) -> int:
        """
        Zero-based offset suitable for database queries.

        Examples:

            Page 1, size 10 -> offset 0
            Page 2, size 10 -> offset 10
            Page 3, size 25 -> offset 50
        """
        return (self.number - 1) * self.size

    @property
    def limit(self) -> int:
        """
        Maximum number of records to return.

        This is equivalent to ``size`` and exists primarily to make the
        pagination object convenient for database adapters.
        """
        return self.size

    @classmethod
    def parse(
            cls,
            number: int | str | None = None,
            size: int | str | None = None,
    ) -> "PageSpec":
        """
        Parse JSON:API pagination values.

        Missing values use the configured defaults.

        Examples:

            PageSpec.parse(
                number="2",
                size="25",
            )

            PageSpec.parse(
                number=None,
                size=None,
            )
        """

        parsed_number = (
            cls._parse_integer(
                number,
                "page[number]",
            )
            if number is not None
            else DEFAULT_PAGE_NUMBER
        )

        parsed_size = (
            cls._parse_integer(
                size,
                "page[size]",
            )
            if size is not None
            else DEFAULT_PAGE_SIZE
        )

        return cls(
            number=parsed_number,
            size=parsed_size,
        )

    @staticmethod
    def _parse_integer(
            value: int | str,
            parameter: str,
    ) -> int:
        if isinstance(value, bool):
            raise PaginationError(
                f"{parameter} must be an integer.",
            )

        if isinstance(value, int):
            return value

        value = value.strip()

        if not value:
            raise PaginationError(
                f"{parameter} cannot be empty.",
            )

        try:
            return int(value)
        except ValueError as exc:
            raise PaginationError(
                f"{parameter} must be an integer.",
            ) from exc

    def to_query_parameters(self) -> dict[str, int]:
        """
        Return the JSON:API query parameter representation.
        """

        return {
            "page[number]": self.number,
            "page[size]": self.size,
        }


@dataclass(frozen=True, slots=True)
class PaginationMeta:
    """
    Pagination metadata for a response.

    This is intentionally separate from PageSpec.

    ``PageSpec`` describes what the client requested.

    ``PaginationMeta`` describes what the server returned and the
    available result set.
    """

    total: int
    number: int
    size: int

    def __post_init__(self) -> None:
        if self.total < 0:
            raise PaginationError(
                "Total number of records cannot be negative.",
            )

        if self.number < 1:
            raise PaginationError(
                "Page number must be greater than or equal to 1.",
            )

        if self.size < 1:
            raise PaginationError(
                "Page size must be greater than or equal to 1.",
            )

    @property
    def pages(self) -> int:
        """
        Total number of pages.

        Returns zero when there are no records.
        """

        if self.total == 0:
            return 0

        return (
                self.total + self.size - 1
        ) // self.size

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.pages

    @property
    def first(self) -> int:
        """
        Position of the first record on the current page.

        Returns zero when there are no records.
        """

        if self.total == 0:
            return 0

        return (self.number - 1) * self.size + 1

    @property
    def last(self) -> int:
        """
        Position of the last record on the current page.
        """

        if self.total == 0:
            return 0

        return min(
            self.number * self.size,
            self.total,
        )

    @classmethod
    def from_page(
            cls,
            page: PageSpec,
            total: int,
    ) -> "PaginationMeta":
        return cls(
            total=total,
            number=page.number,
            size=page.size,
        )
