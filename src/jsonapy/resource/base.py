"""Resource construction, declaration inspection, and type registration.

ResourceMeta collects inherited fields and relationships and validates public
names when classes are defined. Resource provides declaration lookups and
identifier resolution. Concrete types register in their configured registry
unless registration is disabled; validate_all resolves deferred targets after
imports complete.
No model access beyond identifier resolution or persistence occurs here.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Type, cast

from .fields import Field
from .relationships import Relationship
from .registry import ResourceRegistry

if TYPE_CHECKING:
    from .paths import ResolvedFieldPath


class ResourceMeta(type):
    """
    Collects and validates declarative Field and Relationship definitions.
    """

    abstract: bool
    _declared_fields: dict[str, Field]
    _declared_relationships: dict[str, Relationship]

    def __new__(
            mcls,
            name: str,
            bases: tuple[type, ...],
            namespace: dict[str, Any],
            **kwargs: Any,
    ) -> "ResourceMeta":
        cls = super().__new__(
            mcls,
            name,
            bases,
            namespace,
            **kwargs,
        )

        # Abstractness is intentionally not inherited. A project can define
        # an abstract configured base while its subclasses remain concrete.
        is_abstract = bool(namespace.get("abstract", False))
        cls.abstract = is_abstract
        registry = getattr(cls, "registry", None)
        if not isinstance(registry, ResourceRegistry):
            raise TypeError(f"Resource {name!r} registry must be a ResourceRegistry.")

        fields: dict[str, Field] = {}
        relationships: dict[str, Relationship] = {}

        # ------------------------------------------------------------------
        # Inherit declarations
        # ------------------------------------------------------------------

        for base in bases:
            fields.update(
                getattr(base, "_declared_fields", {}),
            )

            relationships.update(
                getattr(base, "_declared_relationships", {}),
            )

        # ------------------------------------------------------------------
        # Collect declarations from this class
        # ------------------------------------------------------------------

        for attribute_name, value in namespace.items():
            if isinstance(value, Field):
                value.name = attribute_name

                if value.options.public_name is None:
                    value.options.public_name = mcls._format_public_name(
                        cls,
                        attribute_name,
                    )

                value.validate()
                fields[attribute_name] = value

            elif isinstance(value, Relationship):
                relationships[attribute_name] = value

        # Inherited and reused relationships need independent binding so a
        # subclass registry cannot change resolution on its parent or siblings.
        for attribute_name, relationship in relationships.items():
            bound = relationship._bind(attribute_name, registry)
            if bound.public_name_override is None:
                bound.public_name_override = mcls._format_public_name(cls, attribute_name)
            relationships[attribute_name] = bound
            setattr(cls, attribute_name, bound)

        # ------------------------------------------------------------------
        # Store declarations
        # ------------------------------------------------------------------

        cls._declared_fields = fields
        cls._declared_relationships = relationships

        # ------------------------------------------------------------------
        # Validate resource
        # ------------------------------------------------------------------

        mcls._validate_resource(cls, is_abstract=is_abstract)

        resource_type: str | None = getattr(cls, "type", None)
        if (
                not is_abstract
                and resource_type
                and getattr(cls, "register", True)
        ):
            registry.register(cast(type["Resource"], cls))

        return cls

    @staticmethod
    def _format_public_name(cls: "ResourceMeta", name: str) -> str:
        style = getattr(cls, "name_style", "identity")

        if style == "identity":
            return name
        if style == "camelcase":
            first, *rest = name.split("_")
            return first + "".join(part.capitalize() for part in rest)
        if style == "dashes":
            return name.replace("_", "-")

        raise TypeError(
            f"Resource {cls.__name__!r} has unsupported name_style "
            f"{style!r}.",
        )

    @staticmethod
    def _validate_resource(
            cls: "ResourceMeta",
            *,
            is_abstract: bool = False,
    ) -> None:
        """
        Validate the complete declarative Resource definition.

        Relationship targets are deliberately not resolved here because
        relationships may use deferred callables to support circular
        Resource definitions.
        """

        if not is_abstract:
            resource_type = getattr(cls, "type", None)

            if not resource_type:
                raise TypeError(
                    f"Resource {cls.__name__!r} must define a "
                    "non-empty 'type'.",
                )

        # ------------------------------------------------------------------
        # Public field names
        # ------------------------------------------------------------------

        field_public_names: dict[str, str] = {}

        for name, field in cls._declared_fields.items():
            public_name = field.public_name

            if public_name in {"id", "type"}:
                raise TypeError(
                    f"Resource {cls.__name__!r} field {name!r} uses "
                    f"reserved public name {public_name!r}.",
                )

            previous_name = field_public_names.get(public_name)

            if previous_name is not None:
                raise TypeError(
                    f"Resource {cls.__name__!r} defines fields "
                    f"{previous_name!r} and {name!r} with the same "
                    f"public name {public_name!r}.",
                )

            field_public_names[public_name] = name

        # ------------------------------------------------------------------
        # Public relationship names
        # ------------------------------------------------------------------

        relationship_public_names: dict[str, str] = {}

        for name, relationship in cls._declared_relationships.items():
            public_name = relationship.public_name

            if public_name in {"id", "type"}:
                raise TypeError(
                    f"Resource {cls.__name__!r} relationship {name!r} "
                    f"uses reserved public name {public_name!r}.",
                )

            previous_name = relationship_public_names.get(
                public_name,
            )

            if previous_name is not None:
                raise TypeError(
                    f"Resource {cls.__name__!r} defines relationships "
                    f"{previous_name!r} and {name!r} with the same "
                    f"public name {public_name!r}.",
                )

            relationship_public_names[public_name] = name

        # ------------------------------------------------------------------
        # Field/relationship collisions
        # ------------------------------------------------------------------

        collisions = (
                field_public_names.keys()
                & relationship_public_names.keys()
        )

        if collisions:
            names = ", ".join(
                repr(name)
                for name in sorted(collisions)
            )

            raise TypeError(
                f"Resource {cls.__name__!r} has field/relationship "
                f"public-name collision(s): {names}.",
            )


class Resource(metaclass=ResourceMeta):
    """
    Base declarative JSON:API resource.

    This class is independent of:

    - FastAPI
    - SQLAlchemy
    - Pydantic
    - Marshmallow

    Concrete subclasses require a nonempty ``type`` and register it in
    ``registry`` unless ``register = False``. A default registry is shared;
    assign a ResourceRegistry on an abstract base to isolate an application.
    Duplicate type registrations raise ValueError. Abstract bases use
    ``abstract = True``; abstractness is not inherited. Identifiers come from ``id_attribute``
    (default ``id``) or ``id_resolver`` when supplied.

    Examples:
        >>> from jsonapy.resource import String
        >>> class ArticleResource(Resource):
        ...     type = "example-articles"
        ...     register = False
        ...     title = String(public_name="headline", required=True)
        >>> ArticleResource.public_field_name("title")
        'headline'
        >>> ArticleResource.field_for_public_name("headline")[0]
        'title'
    """

    model: Any = None
    abstract: ClassVar[bool] = True
    type: str | None = None
    id_attribute: str = "id"
    id_resolver: ClassVar[Callable[[Any], Any] | None] = None
    name_style: str = "identity"
    register: ClassVar[bool] = True

    _declared_fields: dict[str, Field]
    _declared_relationships: dict[str, Relationship]
    registry: ClassVar[ResourceRegistry] = ResourceRegistry()

    @classmethod
    def get_resource(cls, type_name: str) -> Type["Resource"] | None:
        """Look up a JSON:API type in this resource's registry."""
        return cls.registry.get(type_name)

    @classmethod
    def registered_types(cls) -> frozenset[str]:
        """Return a snapshot of type names in this resource's registry."""
        return cls.registry.registered_types()

    @classmethod
    def resolve_id(cls, obj: Any) -> Any:
        """Resolve an object's JSON:API identifier."""
        if cls.id_resolver is not None:
            return cls.id_resolver(obj)
        return getattr(obj, cls.id_attribute)

    @classmethod
    def validate(cls) -> None:
        """Resolve deferred relationships and validate their targets."""
        for relationship in cls._declared_relationships.values():
            relationship.resolve_resource()

    @classmethod
    def validate_all(cls) -> None:
        """Validate every resource in this class's registry after imports."""
        cls.registry.validate_all()

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    @classmethod
    def fields(cls) -> dict[str, Field]:
        return dict(cls._declared_fields)

    @classmethod
    def field(cls, name: str) -> Field:
        try:
            return cls._declared_fields[name]
        except KeyError:
            raise KeyError(
                f"Resource {cls.__name__!r} has no field {name!r}.",
            ) from None

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return tuple(cls._declared_fields)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    @classmethod
    def relationships(cls) -> dict[str, Relationship]:
        return dict(cls._declared_relationships)

    @classmethod
    def relationship(cls, name: str) -> Relationship:
        try:
            return cls._declared_relationships[name]
        except KeyError:
            raise KeyError(
                f"Resource {cls.__name__!r} has no relationship "
                f"{name!r}.",
            ) from None

    @classmethod
    def relationship_names(cls) -> tuple[str, ...]:
        return tuple(cls._declared_relationships)

    # ------------------------------------------------------------------
    # Public names
    # ------------------------------------------------------------------

    @classmethod
    def public_field_name(cls, name: str) -> str:
        return cls.field(name).public_name

    @classmethod
    def public_relationship_name(cls, name: str) -> str:
        return cls.relationship(name).public_name

    @classmethod
    def field_for_public_name(
            cls,
            public_name: str,
    ) -> tuple[str, Field] | None:
        for name, field in cls._declared_fields.items():
            if field.public_name == public_name:
                return name, field

        return None

    @classmethod
    def relationship_for_public_name(
            cls,
            public_name: str,
    ) -> tuple[str, Relationship] | None:
        for name, relationship in cls._declared_relationships.items():
            if relationship.public_name == public_name:
                return name, relationship

        return None

    # ------------------------------------------------------------------
    # Query capabilities
    # ------------------------------------------------------------------

    @classmethod
    def sortable_fields(cls) -> dict[str, Field]:
        return {
            name: field
            for name, field in cls._declared_fields.items()
            if field.options.sortable
        }

    @classmethod
    def filterable_fields(cls) -> dict[str, Field]:
        return {
            name: field
            for name, field in cls._declared_fields.items()
            if field.options.filterable is not None
        }

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @classmethod
    def resolve_path(
            cls,
            path: str,
    ) -> "ResolvedFieldPath":
        # Imported lazily to keep the declarative Resource base independent
        # from the path resolver during module initialization.
        from .paths import resolve_field_path

        return resolve_field_path(
            cls,
            path,
        )
