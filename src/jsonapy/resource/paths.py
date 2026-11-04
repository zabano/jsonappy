from dataclasses import dataclass
from typing import TYPE_CHECKING

from .fields import Field
from .relationships import Relationship

if TYPE_CHECKING:
    from .base import Resource


# ==========================================================================
# Resolved resource path
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ResolvedFieldPath:
    """
    A Resource field path resolved through Resource declarations.

    The path uses public JSON:API names.

    Example:

        author.organization.sortOrder

    resolves to:

        resource:
            ArticleResource

        relationships:
            (
                ArticleResource.author,
                AuthorResource.organization,
            )

        field:
            OrganizationResource.sort_order

    This object deliberately contains no SQLAlchemy-specific information.
    """

    resource: type["Resource"]
    path: tuple[str, ...]
    relationships: tuple[Relationship, ...]
    field: Field

    @property
    def name(self) -> str:
        """
        Python declaration name of the final Field.
        """
        if self.field.name is None:
            raise RuntimeError(
                "Resolved Field has no declaration name.",
            )

        return self.field.name

    @property
    def public_name(self) -> str:
        """
        Public JSON:API name of the final Field.
        """
        return self.field.public_name

    @property
    def relationship_count(self) -> int:
        """
        Number of relationships traversed before reaching the field.
        """
        return len(self.relationships)

    @property
    def target_resource(self) -> type["Resource"]:
        """
        Resource that owns the resolved Field.
        """
        if self.relationships:
            return self.relationships[-1].resolve_resource()

        return self.resource


# ==========================================================================
# Path resolution errors
# ==========================================================================


class PathResolutionError(ValueError):
    """
    Raised when a Resource field path cannot be resolved.
    """


# ==========================================================================
# Path resolution
# ==========================================================================


def resolve_field_path(
        resource: type["Resource"],
        path: str,
) -> ResolvedFieldPath:
    """
    Resolve a public JSON:API field path against a Resource.

    Examples
    --------

    Simple field:

        resolve_field_path(
            ArticleResource,
            "rating",
        )

    Nested field:

        resolve_field_path(
            ArticleResource,
            "author.name",
        )

    Deeply nested field:

        resolve_field_path(
            ArticleResource,
            "author.organization.sortOrder",
        )

    The returned ResolvedFieldPath contains both:

    - the final Field declaration
    - every Relationship declaration traversed to reach it

    This allows adapters such as SQLAlchemy to map the resolved path
    without having to resolve the Resource hierarchy a second time.
    """

    normalized_path = _normalize_path(
        path,
    )

    current_resource = resource
    relationships: list[Relationship] = []

    for index, public_name in enumerate(normalized_path):
        # ------------------------------------------------------------------
        # Field
        # ------------------------------------------------------------------

        field_result = (
            current_resource.field_for_public_name(
                public_name,
            )
        )

        if field_result is not None:
            _, field = field_result

            if index != len(normalized_path) - 1:
                raise PathResolutionError(
                    f"Path {path!r} is invalid: "
                    f"{public_name!r} is a field on "
                    f"{current_resource.__name__!r}, but additional "
                    "path components follow it.",
                )

            return ResolvedFieldPath(
                resource=resource,
                path=normalized_path,
                relationships=tuple(relationships),
                field=field,
            )

        # ------------------------------------------------------------------
        # Relationship
        # ------------------------------------------------------------------

        relationship_result = (
            current_resource.relationship_for_public_name(
                public_name,
            )
        )

        if relationship_result is None:
            raise PathResolutionError(
                f"Resource {current_resource.__name__!r} has no "
                f"field or relationship named {public_name!r} "
                f"while resolving path {path!r}.",
            )

        _, relationship = relationship_result

        if index == len(normalized_path) - 1:
            raise PathResolutionError(
                f"Path {path!r} ends at relationship "
                f"{public_name!r}; a field is required.",
            )

        relationships.append(
            relationship,
        )

        current_resource = relationship.resolve_resource()

    raise PathResolutionError(
        f"Path {path!r} does not resolve to a field.",
    )


# ==========================================================================
# Path normalization
# ==========================================================================


def _normalize_path(
        path: str,
) -> tuple[str, ...]:
    """
    Normalize and validate a public Resource path.

    Examples:

        "author.name"
            -> ("author", "name")

        " author . name "
            -> ("author", "name")
    """

    path = path.strip()

    if not path:
        raise PathResolutionError(
            "Resource path cannot be empty.",
        )

    parts = tuple(
        part.strip()
        for part in path.split(".")
    )

    if any(not part for part in parts):
        raise PathResolutionError(
            f"Invalid Resource path {path!r}.",
        )

    return parts
