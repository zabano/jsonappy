"""Isolated resource type registration and deferred-target validation.

ResourceRegistry maps JSON:API type names to declarations and rejects duplicate
types. Assign a registry to a Resource or abstract application base to scope
string relationship targets. A registry does not load application objects.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Resource


class ResourceRegistry:
    """Resource declarations sharing one namespace of JSON:API type names.

    Each instance starts empty. Registration of the same class is idempotent;
    a different class with an existing type raises ValueError. Applications
    can discard an instance to release its registrations without changing any
    other registry, including Resource.registry, the default registry.

    Examples:
        >>> from jsonapy import Resource
        >>> catalog = ResourceRegistry()
        >>> class AuthorResource(Resource):
        ...     registry = catalog
        ...     type = "authors"
        >>> catalog.get("authors") is AuthorResource
        True
        >>> catalog.registered_types() == frozenset({"authors"})
        True
    """

    def __init__(self) -> None:
        self._resources: dict[str, type[Resource]] = {}

    def register(self, resource: type["Resource"]) -> None:
        """Register a concrete declaration, rejecting invalid or duplicate types.

        Raises:
            TypeError: The argument is not a concrete Resource with a type.
            ValueError: The resource belongs to another registry, or a different
                class already owns this type.
        """
        from .base import Resource

        if (
            not isinstance(resource, type)
            or not issubclass(resource, Resource)
            or resource.abstract
            or not resource.type
        ):
            raise TypeError("Only concrete Resource classes with a type can be registered.")
        if resource.registry is not self:
            raise ValueError(
                f"Resource {resource.__name__!r} belongs to another registry; "
                "assign registry on its declaration or abstract base.",
            )
        existing = self._resources.get(resource.type)
        if existing is not None and existing is not resource:
            raise ValueError(
                f"Resource type {resource.type!r} is already registered by "
                f"{existing.__module__}.{existing.__qualname__}; cannot register "
                f"{resource.__module__}.{resource.__qualname__} in the same registry.",
            )
        self._resources[resource.type] = resource

    def get(self, type_name: str) -> type["Resource"] | None:
        """Return the declaration for a type, or None if it is not registered."""
        return self._resources.get(type_name)

    def registered_types(self) -> frozenset[str]:
        """Return a snapshot of the type names registered in this instance."""
        return frozenset(self._resources)

    def validate_all(self) -> None:
        """Resolve targets on all registered declarations after resource imports.

        Target errors propagate from Resource.validate. Other registries are
        not visited; string targets must exist in each resource's registry.
        """
        for resource in tuple(self._resources.values()):
            resource.validate()
