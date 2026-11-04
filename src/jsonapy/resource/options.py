class Sortable:
    """
    Marks a field as sortable.

    This contains only declarative metadata. The query/backend adapter
    decides how sorting is actually implemented.
    """

    def __init__(
            self,
            *,
            default: bool = False,
    ) -> None:
        self.default = default


class Filter:
    """
    Declares that a field supports exact-value filtering.
    """

    pass


class MultiValueFilter(Filter):
    """
    Declares that a field supports filtering against multiple values.
    """

    pass


class RangeFilter(Filter):
    """
    Declares that a field supports range filtering.
    """

    pass


class TextFilter(Filter):
    """
    Declares that a field supports text-based filtering.
    """

    pass


class BooleanFilter(Filter):
    """
    Declares that a field supports boolean filtering.
    """

    pass


class FieldOptions:
    """
    Declarative options shared by all resource fields.
    """

    def __init__(
            self,
            *,
            sortable: Sortable | bool | None = None,
            filterable: Filter | bool | None = None,
            public_name: str | None = None,
            nullable: bool = True,
            writable: bool = True,
            required: bool = False,
    ) -> None:
        if isinstance(sortable, bool):
            sortable = Sortable() if sortable else None

        if isinstance(filterable, bool):
            filterable = Filter() if filterable else None

        self.sortable = sortable
        self.filterable = filterable
        self.public_name = public_name
        self.nullable = nullable
        self.writable = writable
        self.required = required
