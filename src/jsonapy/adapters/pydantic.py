from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field as PydanticField
from pydantic_core import to_jsonable_python

from ..query.fieldsets import FieldsetSpecList, resolve_fieldsets
from ..query.include import IncludeSpecList, resolve_includes
from ..resource.base import Resource
from ..resource.fields import ComputedField, Field


class JSONAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-compatible data while preserving required nulls."""

        return _model_payload(self)


class ResourceIdentifier(JSONAPIModel):
    type: str
    id: str
    meta: dict[str, Any] | None = None


class RelationshipObject(JSONAPIModel):
    data: ResourceIdentifier | list[ResourceIdentifier] | None
    links: dict[str, Any] | str | None = None
    meta: dict[str, Any] | None = None


class ResourceRequestObject(JSONAPIModel):
    type: str
    id: str | None = None
    attributes: dict[str, Any] | None = None
    relationships: dict[str, RelationshipObject] | None = None


class JSONAPIRequestDocument(JSONAPIModel):
    data: ResourceRequestObject


class ResourceObject(ResourceIdentifier):
    attributes: dict[str, Any] | None = None
    relationships: dict[str, RelationshipObject] | None = None
    links: dict[str, Any] | str | None = None


class JSONAPIVersion(JSONAPIModel):
    version: str = "1.1"
    meta: dict[str, Any] | None = None


class JSONAPIDocument(JSONAPIModel):
    data: ResourceObject | list[ResourceObject] | None
    included: list[ResourceObject] | None = None
    links: dict[str, Any] | str | None = None
    meta: dict[str, Any] | None = None
    jsonapi: JSONAPIVersion | None = None


class ErrorSource(JSONAPIModel):
    pointer: str | None = None
    parameter: str | None = None
    header: str | None = None


class ErrorObject(JSONAPIModel):
    id: str | None = None
    status: str | None = None
    code: str | None = None
    title: str | None = None
    detail: str | None = None
    source: ErrorSource | None = None
    links: dict[str, Any] | str | None = None
    meta: dict[str, Any] | None = None


class JSONAPIErrorDocument(JSONAPIModel):
    errors: list[ErrorObject] = PydanticField(min_length=1)
    links: dict[str, Any] | str | None = None
    meta: dict[str, Any] | None = None
    jsonapi: JSONAPIVersion | None = None


class SerializationError(ValueError):
    """Raised when an object cannot be represented as JSON:API."""


class ResourceRequestError(ValueError):
    """Semantic error in a JSON:API create or update document."""

    def __init__(
            self,
            detail: str,
            *,
            pointer: str,
            code: str,
            status_code: int = 400,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.pointer = pointer
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ValidatedResourceRequest:
    """Request values resolved from public names to model attribute names."""

    id: str | None
    attributes: dict[str, Any]
    relationships: dict[str, RelationshipObject]


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _request_value(field: Field, value: Any, pointer: str) -> Any:
    if value is None:
        if not field.options.nullable:
            raise ResourceRequestError(
                f"Attribute {field.public_name!r} cannot be null.",
                pointer=pointer,
                code="null-not-allowed",
                status_code=422,
            )
        return None

    expected = field.python_type

    if expected is Any or expected is None:
        return value
    if expected is str and isinstance(value, str):
        return value
    if expected is bool and isinstance(value, bool):
        return value
    if expected is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if expected is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    try:
        if isinstance(expected, type) and issubclass(expected, Enum):
            return expected(value)
        if expected is UUID and isinstance(value, str):
            return UUID(value)
        if expected is datetime and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if expected is date and isinstance(value, str):
            return date.fromisoformat(value)
    except (TypeError, ValueError):
        pass

    expected_name = getattr(expected, "__name__", str(expected))
    raise ResourceRequestError(
        f"Attribute {field.public_name!r} must be a valid {expected_name}.",
        pointer=pointer,
        code="invalid-attribute-value",
        status_code=422,
    )


def validate_request_document(
        document: JSONAPIRequestDocument,
        resource: type[Resource],
        *,
        operation: Literal["create", "update"],
        expected_id: str | None = None,
) -> ValidatedResourceRequest:
    """Validate and resolve a JSON:API mutation document."""
    data = document.data

    if data.type != resource.type:
        raise ResourceRequestError(
            f"Expected resource type {resource.type!r}, received {data.type!r}.",
            pointer="/data/type",
            code="type-conflict",
            status_code=409,
        )
    if operation == "update" and data.id is None:
        raise ResourceRequestError(
            "Update documents must include the resource id.",
            pointer="/data/id",
            code="id-required",
            status_code=422,
        )
    if expected_id is not None and data.id != expected_id:
        raise ResourceRequestError(
            f"Request resource id {data.id!r} does not match {expected_id!r}.",
            pointer="/data/id",
            code="id-conflict",
            status_code=409,
        )

    fields = {field.public_name: field for field in resource.fields().values()}
    relationships = {
        relationship.public_name: relationship
        for relationship in resource.relationships().values()
    }
    resolved_attributes: dict[str, Any] = {}
    resolved_relationships: dict[str, RelationshipObject] = {}

    for public_name, value in (data.attributes or {}).items():
        pointer = f"/data/attributes/{_pointer_part(public_name)}"
        field = fields.get(public_name)
        if field is None:
            raise ResourceRequestError(
                f"Unknown attribute {public_name!r}.",
                pointer=pointer,
                code="unknown-attribute",
            )
        if not field.options.writable:
            raise ResourceRequestError(
                f"Attribute {public_name!r} is read-only.",
                pointer=pointer,
                code="read-only-field",
            )
        if field.name is None:
            raise RuntimeError("Resource field has no declaration name.")
        resolved_attributes[field.name] = _request_value(field, value, pointer)

    for public_name, value in (data.relationships or {}).items():
        pointer = f"/data/relationships/{_pointer_part(public_name)}"
        relationship = relationships.get(public_name)
        if relationship is None:
            raise ResourceRequestError(
                f"Unknown relationship {public_name!r}.",
                pointer=pointer,
                code="unknown-relationship",
            )
        if not relationship.writable:
            raise ResourceRequestError(
                f"Relationship {public_name!r} is read-only.",
                pointer=pointer,
                code="read-only-field",
            )

        linkage = value.data
        if linkage is None and not relationship.nullable:
            raise ResourceRequestError(
                f"Relationship {public_name!r} cannot be null.",
                pointer=f"{pointer}/data",
                code="null-not-allowed",
                status_code=422,
            )
        if relationship.many and not isinstance(linkage, list):
            raise ResourceRequestError(
                f"Relationship {public_name!r} requires an array of identifiers.",
                pointer=f"{pointer}/data",
                code="invalid-relationship-cardinality",
            )
        if not relationship.many and isinstance(linkage, list):
            raise ResourceRequestError(
                f"Relationship {public_name!r} requires one identifier or null.",
                pointer=f"{pointer}/data",
                code="invalid-relationship-cardinality",
            )

        target_type = relationship.resolve_resource().type
        identifiers = linkage if isinstance(linkage, list) else (
            [] if linkage is None else [linkage]
        )
        for index, identifier in enumerate(identifiers):
            if identifier.type != target_type:
                suffix = f"/{index}" if isinstance(linkage, list) else ""
                raise ResourceRequestError(
                    f"Expected relationship type {target_type!r}, "
                    f"received {identifier.type!r}.",
                    pointer=f"{pointer}/data{suffix}/type",
                    code="type-conflict",
                    status_code=409,
                )

        if relationship.name is None:
            raise RuntimeError("Resource relationship has no declaration name.")
        resolved_relationships[relationship.name] = value

    if operation == "create":
        for field in fields.values():
            if field.options.required and field.name not in resolved_attributes:
                raise ResourceRequestError(
                    f"Attribute {field.public_name!r} is required.",
                    pointer=f"/data/attributes/{_pointer_part(field.public_name)}",
                    code="required-field",
                    status_code=422,
                )
        for relationship in relationships.values():
            if relationship.required and relationship.name not in resolved_relationships:
                raise ResourceRequestError(
                    f"Relationship {relationship.public_name!r} is required.",
                    pointer=(
                        "/data/relationships/"
                        f"{_pointer_part(relationship.public_name)}"
                    ),
                    code="required-field",
                    status_code=422,
                )

    return ValidatedResourceRequest(
        id=data.id,
        attributes=resolved_attributes,
        relationships=resolved_relationships,
    )


def _identifier(obj: Any, resource: type[Resource]) -> ResourceIdentifier:
    resource_type = resource.type

    if not resource_type:
        raise SerializationError(
            f"Resource {resource.__name__!r} has no JSON:API type.",
        )

    try:
        value = resource.resolve_id(obj)
    except AttributeError as exc:
        raise SerializationError(
            f"Object for Resource {resource.__name__!r} has no "
            f"{resource.id_attribute!r} attribute.",
        ) from exc

    if value is None:
        raise SerializationError("JSON:API resource identifiers cannot be null.")

    return ResourceIdentifier(type=resource_type, id=str(value))


def _payload_value(value: Any) -> Any:
    if isinstance(value, JSONAPIModel):
        return _model_payload(value)
    if isinstance(value, list):
        return [_payload_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _payload_value(item) for key, item in value.items()}
    return value


def _model_payload(model: JSONAPIModel) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    for name, definition in type(model).model_fields.items():
        value = getattr(model, name)

        if value is None and not definition.is_required():
            continue

        payload[name] = _payload_value(value)

    # Convert datetime, UUID, Enum, and other Pydantic-supported values.
    return to_jsonable_python(payload)


def _fieldset_names(
        resource: type[Resource],
        fieldsets: FieldsetSpecList,
) -> set[str] | None:
    if resource.type is None:
        return None

    spec = fieldsets.get(resource.type)
    return set(spec.fields) if spec is not None else None


class _DocumentSerializer:
    def __init__(
            self,
            *,
            includes: IncludeSpecList,
            fieldsets: FieldsetSpecList,
            context: Mapping[str, Any] | None,
    ) -> None:
        self.include_paths = tuple(spec.parts for spec in includes)
        self.fieldsets = fieldsets
        self.context = context or {}
        self.processed_includes: dict[tuple[str, str], set[tuple[str, ...]]] = {}
        self.primary: set[tuple[str, str]] = set()
        self.included: dict[tuple[str, str], ResourceObject | None] = {}

    def identifier_key(
            self,
            obj: Any,
            resource: type[Resource],
    ) -> tuple[ResourceIdentifier, tuple[str, str]]:
        identifier = _identifier(obj, resource)
        return identifier, (identifier.type, identifier.id)

    def serialize(
            self,
            obj: Any,
            resource: type[Resource],
            include_paths: tuple[tuple[str, ...], ...],
    ) -> ResourceObject:
        identifier, _ = self.identifier_key(obj, resource)
        selected = _fieldset_names(resource, self.fieldsets)
        attributes: dict[str, Any] = {}

        for field in resource.fields().values():
            public_name = field.public_name

            if selected is not None and public_name not in selected:
                continue

            if isinstance(field, ComputedField):
                value = field.get_value(obj, self.context)
            else:
                if field.name is None:
                    raise SerializationError(
                        "Resource field has no declaration name.",
                    )
                try:
                    value = getattr(obj, field.name)
                except AttributeError as exc:
                    raise SerializationError(
                        f"Object for Resource {resource.__name__!r} has no "
                        f"attribute {field.name!r}.",
                    ) from exc

            attributes[public_name] = value

            if value is None and not field.options.nullable:
                raise SerializationError(
                    f"Non-nullable field {public_name!r} on Resource "
                    f"{resource.__name__!r} resolved to null.",
                )

        relationships: dict[str, RelationshipObject] = {}

        for relationship in resource.relationships().values():
            public_name = relationship.public_name
            child_paths = tuple(
                path[1:]
                for path in include_paths
                if path and path[0] == public_name
            )
            should_include = bool(child_paths)
            relationship_selected = (
                selected is None or public_name in selected
            )

            if not relationship_selected and not should_include:
                continue

            if relationship.name is None:
                raise SerializationError(
                    "Resource relationship has no declaration name.",
                )

            try:
                value = getattr(obj, relationship.name)
            except AttributeError as exc:
                raise SerializationError(
                    f"Object for Resource {resource.__name__!r} has no "
                    f"relationship attribute {relationship.name!r}.",
                ) from exc

            target = relationship.resolve_resource()

            if relationship.many:
                related = [] if value is None else list(value)
                linkage = [
                    self.identifier_key(item, target)[0]
                    for item in related
                ]
                if relationship_selected:
                    relationships[public_name] = RelationshipObject(data=linkage)

                if should_include:
                    for item in related:
                        self.add_included(item, target, child_paths)
            else:
                linkage = None if value is None else self.identifier_key(value, target)[0]
                if relationship_selected:
                    relationships[public_name] = RelationshipObject(data=linkage)

                if should_include and value is not None:
                    self.add_included(value, target, child_paths)

        return ResourceObject(
            type=identifier.type,
            id=identifier.id,
            attributes=attributes or None,
            relationships=relationships or None,
        )

    def add_included(
            self,
            obj: Any,
            resource: type[Resource],
            include_paths: tuple[tuple[str, ...], ...],
    ) -> None:
        _, key = self.identifier_key(obj, resource)

        processed = self.processed_includes.setdefault(key, set())
        pending = tuple(path for path in include_paths if path and path not in processed)
        processed.update(pending)

        if key in self.primary or key in self.included:
            # Identity deduplication must still traverse newly requested paths.
            for relationship in resource.relationships().values():
                child_paths = tuple(
                    path[1:] for path in pending
                    if path[0] == relationship.public_name
                )
                if not child_paths:
                    continue
                try:
                    value = getattr(obj, relationship.name)
                except AttributeError as exc:
                    raise SerializationError(
                        f"Object for Resource {resource.__name__!r} has no "
                        f"relationship attribute {relationship.name!r}.",
                    ) from exc
                target = relationship.resolve_resource()
                related = ([] if value is None else value) if relationship.many else (
                    [] if value is None else [value]
                )
                for item in related:
                    self.add_included(item, target, child_paths)
            return

        # Reserve before recursion to break relationship cycles.
        self.included[key] = None
        self.included[key] = self.serialize(obj, resource, include_paths)


def _normalize_includes(
        include: IncludeSpecList | str | None,
) -> IncludeSpecList:
    if isinstance(include, IncludeSpecList):
        return include
    return IncludeSpecList.parse(include)


def _validate_document_query(
        resource: type[Resource],
        includes: IncludeSpecList,
        fieldsets: FieldsetSpecList,
) -> None:
    resolved_includes = resolve_includes(resource, includes)
    resources: set[type[Resource]] = {resource}

    for include in resolved_includes:
        resources.update(
            relationship.resolve_resource()
            for relationship in include.relationships
        )

    for included_resource in resources:
        resolve_fieldsets(included_resource, fieldsets)


def serialize_resource(
        obj: Any,
        resource: type[Resource],
        *,
        fieldsets: FieldsetSpecList | None = None,
        context: Mapping[str, Any] | None = None,
) -> ResourceObject:
    """Serialize one resource object without a top-level document."""

    normalized_fieldsets = fieldsets or FieldsetSpecList()
    _validate_document_query(
        resource,
        IncludeSpecList(),
        normalized_fieldsets,
    )
    serializer = _DocumentSerializer(
        includes=IncludeSpecList(),
        fieldsets=normalized_fieldsets,
        context=context,
    )
    return serializer.serialize(obj, resource, ())


def serialize_document(
        obj: Any | None,
        resource: type[Resource],
        *,
        include: IncludeSpecList | str | None = None,
        fieldsets: FieldsetSpecList | None = None,
        context: Mapping[str, Any] | None = None,
        links: dict[str, Any] | str | None = None,
        meta: dict[str, Any] | None = None,
) -> JSONAPIDocument:
    """Build a single-resource JSON:API document."""

    includes = _normalize_includes(include)
    normalized_fieldsets = fieldsets or FieldsetSpecList()
    _validate_document_query(resource, includes, normalized_fieldsets)
    serializer = _DocumentSerializer(
        includes=includes,
        fieldsets=normalized_fieldsets,
        context=context,
    )

    if obj is None:
        data = None
    else:
        _, key = serializer.identifier_key(obj, resource)
        serializer.primary.add(key)
        data = serializer.serialize(obj, resource, serializer.include_paths)

    included = [item for item in serializer.included.values() if item is not None]
    return JSONAPIDocument(
        data=data,
        included=included or None,
        links=links,
        meta=meta,
    )


def serialize_collection(
        objects: Iterable[Any],
        resource: type[Resource],
        *,
        include: IncludeSpecList | str | None = None,
        fieldsets: FieldsetSpecList | None = None,
        context: Mapping[str, Any] | None = None,
        links: dict[str, Any] | str | None = None,
        meta: dict[str, Any] | None = None,
) -> JSONAPIDocument:
    """Build a collection JSON:API document with deduplicated includes."""

    values = list(objects)
    includes = _normalize_includes(include)
    normalized_fieldsets = fieldsets or FieldsetSpecList()
    _validate_document_query(resource, includes, normalized_fieldsets)
    serializer = _DocumentSerializer(
        includes=includes,
        fieldsets=normalized_fieldsets,
        context=context,
    )

    for obj in values:
        _, key = serializer.identifier_key(obj, resource)
        serializer.primary.add(key)

    data = [
        serializer.serialize(obj, resource, serializer.include_paths)
        for obj in values
    ]
    included = [item for item in serializer.included.values() if item is not None]

    return JSONAPIDocument(
        data=data,
        included=included or None,
        links=links,
        meta=meta,
    )


__all__ = [
    "ErrorObject",
    "ErrorSource",
    "JSONAPIDocument",
    "JSONAPIErrorDocument",
    "JSONAPIRequestDocument",
    "JSONAPIModel",
    "JSONAPIVersion",
    "RelationshipObject",
    "ResourceRequestError",
    "ResourceRequestObject",
    "ResourceIdentifier",
    "ResourceObject",
    "SerializationError",
    "ValidatedResourceRequest",
    "serialize_collection",
    "serialize_document",
    "serialize_resource",
    "validate_request_document",
]
