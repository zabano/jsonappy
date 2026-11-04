"""Relationship declarations and deferred target resolution.

Relationship targets may be Resource classes, registered JSON:API type
strings, or zero-argument callables. Declarations describe cardinality and
mutation requirements. Adapters inspect linkage; applications resolve ids,
authorize related objects, and persist relationship changes.
"""

from collections.abc import Callable
from copy import copy
from typing import TYPE_CHECKING, TypeAlias, cast

from .registry import ResourceRegistry

if TYPE_CHECKING:
    from .base import Resource

if TYPE_CHECKING:
    ResourceReference: TypeAlias = (
            str
            | type[Resource]
            | Callable[[], type[Resource]]
    )
else:
    ResourceReference: TypeAlias = object


class Relationship:
    """
    Declarative JSON:API relationship.

    A relationship may reference a canonical JSON:API resource type,
    a Resource class directly, or a zero-argument callable. Type strings
    avoid imports between resource modules, while callables support forward
    declarations within one module.

    Args:
        resource: Target resource class, registered type, or deferred callable.
        many: Use an array of identifiers for linkage; defaults to false.
        public_name: Client-facing name, separate from the Python attribute.
        writable: Accept the relationship in mutation documents.
        required: Require linkage on create; updates may omit it.
        nullable: Allow null to-one linkage; to-many linkage always needs an
            array, with an empty array representing no related resources.

    Declarations describe linkage only. Applications resolve identifiers,
    enforce permissions, and persist relationship changes.

    Examples:

        author = Relationship(AuthorResource)

        project = Relationship("projects")

        author = Relationship(
            lambda: AuthorResource,
        )

        comments = Relationship(
            lambda: CommentResource,
            many=True,
        )
    """

    def __init__(
            self,
            resource: ResourceReference,
            *,
            many: bool = False,
            public_name: str | None = None,
            writable: bool = True,
            required: bool = False,
            nullable: bool = True,
    ) -> None:
        if isinstance(resource, str) and not resource.strip():
            raise TypeError("Relationship resource type cannot be empty.")

        if (
                not isinstance(resource, (str, type))
                and not callable(resource)
        ):
            raise TypeError(
                "Relationship resource must be a resource type string, "
                "a Resource class, or a zero-argument callable returning "
                "one.",
            )

        self._resource_reference = resource
        self.many = many
        self.public_name_override = public_name
        self.writable = writable
        self.required = required
        self.nullable = nullable

        # Filled by ResourceMeta.
        self.name: str | None = None
        self._registry: ResourceRegistry | None = None

    def _bind(self, name: str, registry: ResourceRegistry) -> "Relationship":
        """Copy a declaration for one owning resource and its registry."""
        bound = copy(self)
        bound.name = name
        bound._registry = registry
        return bound

    def resolve_resource(self) -> type["Resource"]:
        """
        Resolve and return the target Resource class.

        Raises:
            LookupError: A string target is not in the owning resource's registry.
            TypeError: The target or deferred callable is invalid.

        Bound string targets use the owning resource's registry. Unbound
        declarations use Resource.registry. Class and callable targets are
        explicit references and may point to another registry.

        A Resource class is callable too, so we distinguish a Resource
        class from a deferred zero-argument callable explicitly.
        """

        from .base import Resource

        resource = self._resource_reference

        if isinstance(resource, str):
            registry = self._registry if self._registry is not None else Resource.registry
            resolved = registry.get(resource)

            if resolved is None:
                raise LookupError(
                    f"Relationship references unknown resource type "
                    f"{resource!r}.",
                )
        elif isinstance(resource, type):
            resolved = resource
        else:
            try:
                resolved = resource()
            except TypeError as exc:
                raise TypeError(
                    "Relationship resource callable must accept no "
                    "arguments.",
                ) from exc

        if not isinstance(resolved, type) or not issubclass(
                resolved,
                Resource,
        ):
            raise TypeError(
                "Relationship resource callable must return a "
                "Resource class.",
            )

        return cast(
            type["Resource"],
            resolved,
        )

    @property
    def resource(self) -> type["Resource"]:
        """Return the validated target Resource class."""

        return self.resolve_resource()

    @property
    def public_name(self) -> str:
        """
        Return the public JSON:API relationship name.
        """

        if self.public_name_override is not None:
            return self.public_name_override

        if self.name is None:
            raise RuntimeError(
                "Relationship has not been attached to a Resource.",
            )

        return self.name
