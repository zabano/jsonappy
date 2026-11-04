"""Parse and resolve public relationship paths for compound documents.

IncludeSpecList records comma-separated include paths. resolve_includes
requires every path component to be a declared relationship and returns the
traversed declarations. Adapters choose loader strategies and serializers
construct included resource objects; this module performs no object loading.
"""

from dataclasses import dataclass
from typing import Iterable, Iterator

from ..resource.base import Resource
from ..resource.relationships import Relationship


# --------------------------------------------------------------------------
# Include specification
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IncludeSpec:
    """
    A single JSON:API include path.

    Examples:

        IncludeSpec(
            path="author",
        )

        IncludeSpec(
            path="author.organization",
        )

    The path is expressed using the public relationship names exposed
    by the Resource declarations.
    """

    path: str

    def __post_init__(self) -> None:
        path = self.path.strip()

        if not path:
            raise ValueError(
                "Include path cannot be empty.",
            )

        parts = tuple(
            part.strip()
            for part in path.split(".")
        )

        if any(not part for part in parts):
            raise ValueError(
                f"Invalid include path {self.path!r}.",
            )

        object.__setattr__(
            self,
            "path",
            ".".join(parts),
        )

    @property
    def parts(self) -> tuple[str, ...]:
        """
        Individual relationship names making up the path.
        """

        return tuple(self.path.split("."))

    def __str__(self) -> str:
        return self.path


# --------------------------------------------------------------------------
# Include specification collection
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IncludeSpecList:
    """
    An ordered collection of IncludeSpec objects.

    Example:

        IncludeSpecList(
            items=(
                IncludeSpec("author"),
                IncludeSpec("author.organization"),
            ),
        )
    """

    items: tuple[IncludeSpec, ...] = ()

    def __iter__(self) -> Iterator[IncludeSpec]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __getitem__(
            self,
            index: int,
    ) -> IncludeSpec:
        return self.items[index]

    def __contains__(
            self,
            path: str,
    ) -> bool:
        return any(
            item.path == path
            for item in self.items
        )

    def __str__(self) -> str:
        return ",".join(
            str(item)
            for item in self.items
        )

    @classmethod
    def from_iterable(
            cls,
            specs: Iterable[IncludeSpec],
    ) -> "IncludeSpecList":
        """
        Create an IncludeSpecList while removing duplicate paths.

        Original order is preserved.
        """

        seen: set[str] = set()
        result: list[IncludeSpec] = []

        for spec in specs:
            if spec.path in seen:
                continue

            seen.add(spec.path)
            result.append(spec)

        return cls(tuple(result))

    @classmethod
    def parse(
            cls,
            value: str | None,
    ) -> "IncludeSpecList":
        """
        Parse a JSON:API include parameter.

        Examples:

            "author"

                -> author

            "author,author.organization"

                -> author
                -> author.organization

        Empty entries are ignored.
        """

        if value is None:
            return cls()

        value = value.strip()

        if not value:
            return cls()

        specs: list[IncludeSpec] = []

        for raw_path in value.split(","):
            raw_path = raw_path.strip()

            if not raw_path:
                continue

            specs.append(
                IncludeSpec(
                    path=raw_path,
                ),
            )

        return cls.from_iterable(specs)

    def to_query_string(self) -> str:
        return str(self)


# --------------------------------------------------------------------------
# Resolved include
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResolvedInclude:
    """
    A resolved include path.

    ``relationships`` contains the Relationship declaration for every
    component of the include path.

    Example:

        include=author.organization

    resolves to:

        ArticleResource
            author -> AuthorResource
                organization -> OrganizationResource

    and produces:

        relationships = (
            ArticleResource.author,
            AuthorResource.organization,
        )
    """

    spec: IncludeSpec
    resource: type[Resource]
    relationships: tuple[Relationship, ...]

    @property
    def path(self) -> str:
        return self.spec.path

    @property
    def parts(self) -> tuple[str, ...]:
        return self.spec.parts

    @property
    def target_resource(self) -> type[Resource]:
        return self.relationships[-1].resource


class IncludeResolutionError(ValueError):
    """
    Raised when an include path cannot be resolved against a Resource.
    """


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------


def resolve_include(
        resource: type[Resource],
        spec: IncludeSpec,
) -> ResolvedInclude:
    """
    Resolve a single IncludeSpec against a Resource.

    Only declared Resource relationships may be included.

    Examples:

        include=author

        include=author.organization

        include=author.comments
    """

    current_resource = resource
    relationships: list[Relationship] = []

    for index, public_name in enumerate(spec.parts):
        relationship_result = (
            current_resource.relationship_for_public_name(
                public_name,
            )
        )

        if relationship_result is None:
            raise IncludeResolutionError(
                f"Resource {current_resource.__name__!r} has no "
                f"relationship named {public_name!r} while "
                f"resolving include {spec.path!r}.",
            )

        _, relationship = relationship_result

        relationships.append(
            relationship,
        )

        current_resource = relationship.resource

    return ResolvedInclude(
        spec=spec,
        resource=resource,
        relationships=tuple(relationships),
    )


def resolve_includes(
        resource: type[Resource],
        specs: IncludeSpecList,
) -> tuple[ResolvedInclude, ...]:
    """
    Resolve all include paths against a Resource.

    Raises IncludeResolutionError if any include path is invalid.
    """

    return tuple(
        resolve_include(
            resource,
            spec,
        )
        for spec in specs
    )


# --------------------------------------------------------------------------
# Parsing / formatting convenience functions
# --------------------------------------------------------------------------


def parse_include(
        value: str | None,
) -> IncludeSpecList:
    """
    Parse a JSON:API include parameter.

    Example:
        "author,author.organization"

    Returns an IncludeSpecList containing the requested include
    paths.
    """

    return IncludeSpecList.parse(value)


def format_include(
        specs: Iterable[IncludeSpec],
) -> str:
    """
    Convert IncludeSpec objects into a JSON:API include parameter.

    Example:

        format_include([
            IncludeSpec("author"),
            IncludeSpec("author.organization"),
        ])

        -> "author,author.organization"
    """

    return str(
        IncludeSpecList.from_iterable(specs),
    )
