from enum import Enum
from datetime import date, datetime
from uuid import UUID as UUIDValue
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from .options import (
    BooleanFilter,
    FieldOptions,
    Filter,
    MultiValueFilter,
    RangeFilter,
    TextFilter,
)


class Field:
    """
    Base class for all resource attributes.

    A Field describes the public JSON:API representation of an
    attribute. It does not know how the value is obtained from a
    model.

    Model-specific resolution belongs to an adapter.
    """

    python_type: ClassVar[type[Any] | None] = None

    supported_filters: ClassVar[tuple[type[Filter], ...]] = (
        Filter,
    )

    def __init__(
            self,
            *,
            sortable: bool = False,
            filterable: Filter | bool | None = None,
            public_name: str | None = None,
            nullable: bool = False,
            writable: bool = True,
            required: bool = False,
    ) -> None:
        self.options = FieldOptions(
            sortable=sortable,
            filterable=filterable,
            public_name=public_name,
            nullable=nullable,
            writable=writable,
            required=required,
        )

        # Filled by ResourceMeta.
        self.name: str | None = None

    @property
    def public_name(self) -> str:
        """
        Public JSON:API attribute name.
        """

        if self.options.public_name is not None:
            return self.options.public_name

        if self.name is None:
            raise RuntimeError(
                "Field has not been attached to a Resource.",
            )

        return self.name

    def supports_filter(
            self,
            filter_type: type[Filter],
    ) -> bool:
        """
        Return whether this field supports the given filter type.
        """

        return any(
            issubclass(filter_type, supported)
            for supported in self.supported_filters
        )

    def validate(self) -> None:
        """
        Validate the field declaration.

        This is called when the Resource class is constructed.
        """

        filter_definition = self.options.filterable

        if filter_definition is None:
            return

        filter_type = type(filter_definition)

        if not self.supports_filter(filter_type):
            field_name = self.name or "<unbound>"

            supported = ", ".join(
                filter_class.__name__
                for filter_class in self.supported_filters
            )

            raise TypeError(
                f"Field {field_name!r} ({type(self).__name__}) "
                f"does not support {filter_type.__name__}. "
                f"Supported filter types: {supported}.",
            )


class String(Field):
    """
    String-valued resource field.
    """

    python_type = str

    supported_filters = (
        Filter,
        MultiValueFilter,
        TextFilter,
    )


class Integer(Field):
    """
    Integer-valued resource field.
    """

    python_type = int

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class Float(Field):
    """
    Floating-point resource field.
    """

    python_type = float

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class Number(Field):
    """
    Generic numeric resource field.
    """

    python_type = float

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class Decimal(Field):
    """
    Decimal-valued resource field.
    """

    python_type = float

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class Boolean(Field):
    """
    Boolean-valued resource field.
    """

    python_type = bool

    supported_filters = (
        Filter,
        BooleanFilter,
    )


class Date(Field):
    """
    Date-valued resource field.
    """

    python_type = date

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class DateTime(Field):
    """
    Date/time-valued resource field.
    """

    python_type = datetime

    supported_filters = (
        Filter,
        MultiValueFilter,
        RangeFilter,
    )


class UUID(Field):
    """
    UUID-valued resource field.
    """

    python_type = UUIDValue

    supported_filters = (
        Filter,
        MultiValueFilter,
    )


class EnumField(Field):
    """
    Enum-valued resource field.
    """

    supported_filters = (
        Filter,
        MultiValueFilter,
    )

    def __init__(
            self,
            enum: type[Enum],
            *,
            sortable: bool = False,
            filterable: Filter | bool | None = None,
            public_name: str | None = None,
            nullable: bool = False,
            writable: bool = True,
            required: bool = False,
    ) -> None:
        if not isinstance(enum, type) or not issubclass(enum, Enum):
            raise TypeError(
                "EnumField requires an Enum class.",
            )

        self.enum = enum

        super().__init__(
            sortable=sortable,
            filterable=filterable,
            public_name=public_name,
            nullable=nullable,
            writable=writable,
            required=required,
        )

    @property
    def python_type(self) -> type[Enum]:
        return self.enum


class AnyField(Field):
    """
    Unconstrained field.
    """

    python_type = Any

    supported_filters = (
        Filter,
    )


class JSON(Field):
    """JSON-compatible object, array, scalar, or null attribute."""

    python_type = Any

    # JSON comparison behavior varies between database adapters. Query
    # support can be added explicitly later without implying portable
    # filtering semantics here.
    supported_filters: ClassVar[tuple[type[Filter], ...]] = ()


class ComputedField(Field):
    """Attribute whose serialized value is produced by a callable."""

    python_type = Any
    supported_filters: ClassVar[tuple[type[Filter], ...]] = ()

    def __init__(
            self,
            getter: Callable[[Any, Mapping[str, Any]], Any],
            *,
            public_name: str | None = None,
            nullable: bool = False,
    ) -> None:
        if not callable(getter):
            raise TypeError("ComputedField getter must be callable.")

        self.getter = getter
        super().__init__(
            sortable=False,
            filterable=None,
            public_name=public_name,
            nullable=nullable,
            writable=False,
            required=False,
        )

    def get_value(
            self,
            obj: Any,
            context: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.getter(obj, context or {})
