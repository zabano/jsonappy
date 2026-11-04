from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from .pydantic import (
    ErrorObject,
    ErrorSource,
    JSONAPIDocument,
    JSONAPIErrorDocument,
    JSONAPIRequestDocument,
    ResourceRequestError,
    ValidatedResourceRequest,
    serialize_collection,
    serialize_document,
    validate_request_document,
)
from ..query.fieldsets import FieldsetSpec, FieldsetSpecList
from ..query.fieldsets import FieldsetResolutionError
from ..query.filtering import FilterSpec, FilterSpecList
from ..query.pagination import PaginationMeta
from ..query.spec import QuerySpec
from ..query.include import IncludeResolutionError
from ..resource.base import Resource

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"


def _accepts_jsonapi(request: Request) -> bool:
    accept = request.headers.get("accept")
    if not accept:
        return True

    media_types = {
        item.split(";", 1)[0].strip().lower()
        for item in accept.split(",")
    }
    return JSONAPI_MEDIA_TYPE in media_types or "*/*" in media_types


def require_jsonapi_accept(
        request: Request,
        accept: Annotated[
            str | None,
            Header(
                alias="Accept",
                description="Accepted response media types.",
            ),
        ] = None,
) -> None:
    """Require an Accept header compatible with JSON:API responses."""
    del accept  # FastAPI/OpenAPI declaration; Request preserves raw syntax.
    if not _accepts_jsonapi(request):
        raise JSONAPIHTTPException(
            406,
            title="Not acceptable",
            detail=(
                "The Accept header must allow "
                f"{JSONAPI_MEDIA_TYPE}."
            ),
            code="not-acceptable",
            source=ErrorSource(header="Accept"),
        )


def _require_jsonapi_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()

    if media_type != JSONAPI_MEDIA_TYPE:
        raise JSONAPIHTTPException(
            415,
            title="Unsupported media type",
            detail=(
                "JSON:API request documents require Content-Type "
                f"{JSONAPI_MEDIA_TYPE}."
            ),
            code="unsupported-media-type",
            source=ErrorSource(header="Content-Type"),
        )


JSONAPIAccept = Annotated[None, Depends(require_jsonapi_accept)]


def jsonapi_fieldset_openapi(
        *resources: type[Resource],
) -> dict[str, list[dict[str, Any]]]:
    """Build OpenAPI parameters for JSON:API sparse fieldsets."""
    parameters: list[dict[str, Any]] = []

    for resource in resources:
        resource_type = resource.type
        if resource_type is None:
            continue

        members = sorted({
            *(field.public_name for field in resource.fields().values()),
            *(
                relationship.public_name
                for relationship in resource.relationships().values()
            ),
        })
        parameters.append({
            "name": f"fields[{resource_type}]",
            "in": "query",
            "required": False,
            "description": (
                f"Comma-separated sparse fieldset for `{resource_type}`. "
                f"Available fields: {', '.join(members)}."
            ),
            "schema": {"type": "string"},
        })

    return {"parameters": parameters}


def validate_response_query(
        resource: type[Resource],
        query: QuerySpec,
) -> None:
    """Validate response-shaping options before performing side effects."""
    try:
        serialize_document(
            None,
            resource,
            include=query.include,
            fieldsets=query.fieldsets,
        )
    except (FieldsetResolutionError, IncludeResolutionError) as exc:
        raise JSONAPIHTTPException(
            400,
            title="Invalid query parameter",
            detail=str(exc),
            code="invalid-query-parameter",
        ) from exc


def jsonapi_error_responses(
        *status_codes: int,
) -> dict[int, dict[str, Any]]:
    """Build reusable OpenAPI declarations for JSON:API errors."""
    descriptions = {
        400: "Invalid request",
        401: "Authentication required",
        403: "Access denied",
        404: "Resource not found",
        406: "Not acceptable",
        409: "Resource conflict",
        415: "Unsupported media type",
        422: "Request validation failed",
    }
    return {
        status_code: {
            "description": descriptions.get(status_code, "JSON:API error"),
            "model": JSONAPIErrorDocument,
        }
        for status_code in status_codes
    }


COMMON_JSONAPI_ERROR_RESPONSES = jsonapi_error_responses(
    400,
    401,
    403,
    404,
    406,
    409,
    415,
    422,
)


class JSONAPIResponse(JSONResponse):
    """JSON response using the JSON:API media type."""

    media_type = JSONAPI_MEDIA_TYPE

    def __init__(
            self,
            content: JSONAPIDocument | JSONAPIErrorDocument | Mapping[str, Any],
            *,
            status_code: int = 200,
            headers: Mapping[str, str] | None = None,
    ) -> None:
        if isinstance(content, (JSONAPIDocument, JSONAPIErrorDocument)):
            serialized: Any = content.to_payload()
        else:
            serialized = dict(content)

        super().__init__(
            content=serialized,
            status_code=status_code,
            headers=headers,
            media_type=self.media_type,
        )


class JSONAPIEmptyResponse(Response):
    """Bodyless response class retaining JSON:API OpenAPI error media types."""

    media_type = JSONAPI_MEDIA_TYPE


class JSONAPIHTTPException(HTTPException):
    """HTTP exception carrying a JSON:API error document."""

    def __init__(
            self,
            status_code: int,
            *,
            title: str,
            detail: str,
            code: str | None = None,
            source: ErrorSource | None = None,
            headers: dict[str, str] | None = None,
    ) -> None:
        self.error_document = JSONAPIErrorDocument(errors=[
            ErrorObject(
                status=str(status_code),
                code=code,
                title=title,
                detail=detail,
                source=source,
            ),
        ])
        super().__init__(status_code=status_code, detail=detail, headers=headers)


async def jsonapi_exception_handler(
        request: Request,
        exc: JSONAPIHTTPException,
) -> JSONAPIResponse:
    del request
    return JSONAPIResponse(
        exc.error_document,
        status_code=exc.status_code,
        headers=exc.headers,
    )


def _validation_source(location: tuple[Any, ...]) -> ErrorSource:
    if location and location[0] == "body":
        parts = (
            str(part).replace("~", "~0").replace("/", "~1")
            for part in location[1:]
        )
        return ErrorSource(pointer="/" + "/".join(parts))

    parameter = str(location[-1]) if location else None
    return ErrorSource(parameter=parameter)


async def jsonapi_request_validation_handler(
        request: Request,
        exc: RequestValidationError,
) -> JSONAPIResponse:
    del request
    document = JSONAPIErrorDocument(errors=[
        ErrorObject(
            status="422",
            code="request-validation-error",
            title="Invalid request document",
            detail=error["msg"],
            source=_validation_source(tuple(error.get("loc", ()))),
        )
        for error in exc.errors()
    ])
    return JSONAPIResponse(document, status_code=422)


def install_jsonapi_exception_handlers(app: FastAPI) -> None:
    """Install handlers for exceptions raised by this adapter."""

    app.add_exception_handler(JSONAPIHTTPException, jsonapi_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        jsonapi_request_validation_handler,
    )


def validate_resource_request(
        document: JSONAPIRequestDocument,
        resource: type[Resource],
        *,
        operation: Literal["create", "update"],
        expected_id: str | None = None,
) -> ValidatedResourceRequest:
    """Validate a mutation document and expose failures as JSON:API errors."""
    try:
        return validate_request_document(
            document,
            resource,
            operation=operation,
            expected_id=expected_id,
        )
    except ResourceRequestError as exc:
        raise JSONAPIHTTPException(
            exc.status_code,
            title="Invalid resource document",
            detail=exc.detail,
            code=exc.code,
            source=ErrorSource(pointer=exc.pointer),
        ) from exc


class ResourceRequestDependency:
    """FastAPI dependency for one declarative mutation operation."""

    def __init__(
            self,
            resource: type[Resource],
            *,
            operation: Literal["create", "update"],
            id_parameter: str | None = None,
    ) -> None:
        if operation == "update" and not id_parameter:
            raise ValueError("Update request dependencies require id_parameter.")

        self.resource = resource
        self.operation = operation
        self.id_parameter = id_parameter

    async def __call__(
            self,
            request: Request,
            document: Annotated[
                JSONAPIRequestDocument,
                Body(media_type=JSONAPI_MEDIA_TYPE),
            ],
    ) -> ValidatedResourceRequest:
        require_jsonapi_accept(request)
        _require_jsonapi_content_type(request)

        expected_id = None
        if self.id_parameter is not None:
            value = request.path_params.get(self.id_parameter)
            if value is None:
                raise RuntimeError(
                    f"Path parameter {self.id_parameter!r} is unavailable.",
                )
            expected_id = str(value)

        return validate_resource_request(
            document,
            self.resource,
            operation=self.operation,
            expected_id=expected_id,
        )


def resource_request(
        resource: type[Resource],
        *,
        operation: Literal["create", "update"],
        id_parameter: str | None = None,
) -> ResourceRequestDependency:
    """Create a FastAPI dependency for a Resource mutation."""
    return ResourceRequestDependency(
        resource,
        operation=operation,
        id_parameter=id_parameter,
    )


def _parse_fieldsets(request: Request) -> FieldsetSpecList:
    specs: list[FieldsetSpec] = []
    seen: set[str] = set()

    for parameter, value in request.query_params.multi_items():
        if not parameter.startswith("fields["):
            continue

        if not parameter.endswith("]"):
            raise ValueError(f"Invalid fieldset parameter {parameter!r}.")

        resource_type = parameter[7:-1].strip()

        if resource_type in seen:
            raise ValueError(
                f"Sparse fieldset for resource type {resource_type!r} "
                "was provided more than once.",
            )

        seen.add(resource_type)
        specs.append(FieldsetSpec.parse(resource_type, value))

    return FieldsetSpecList.from_iterable(specs)


def _parse_filters(request: Request) -> FilterSpecList:
    specs: list[FilterSpec] = []

    for parameter, value in request.query_params.multi_items():
        field = FilterSpecList._extract_field(parameter)

        if field is not None:
            specs.append(FilterSpec(field=field, value=value.strip()))

    return FilterSpecList.from_iterable(specs)


def parse_jsonapi_query(
        request: Request,
        sort: Annotated[
            str | None,
            Query(description="Comma-separated JSON:API sort fields."),
        ] = None,
        include: Annotated[
            str | None,
            Query(description="Comma-separated relationship paths to include."),
        ] = None,
        page_number: Annotated[
            str | None,
            Query(alias="page[number]", description="One-based page number."),
        ] = None,
        page_size: Annotated[
            str | None,
            Query(alias="page[size]", description="Number of resources per page."),
        ] = None,
) -> QuerySpec:
    """FastAPI dependency that parses a request's JSON:API query options."""

    require_jsonapi_accept(request)

    try:
        return QuerySpec.parse(
            sort=sort,
            filters=_parse_filters(request),
            page_number=page_number,
            page_size=page_size,
            fieldsets=_parse_fieldsets(request),
            include=include,
        )
    except ValueError as exc:
        raise JSONAPIHTTPException(
            400,
            title="Invalid query parameter",
            detail=str(exc),
            code="invalid-query-parameter",
        ) from exc


JSONAPIQuery = Annotated[QuerySpec, Depends(parse_jsonapi_query)]


def _pagination_meta(pagination: PaginationMeta | None) -> dict[str, Any] | None:
    if pagination is None:
        return None

    return {
        "page": {
            "total": pagination.total,
            "number": pagination.number,
            "size": pagination.size,
            "pages": pagination.pages,
        },
    }


def resource_response(
        obj: Any | None,
        resource: type[Resource],
        *,
        query: QuerySpec | None = None,
        context: Mapping[str, Any] | None = None,
        links: dict[str, Any] | str | None = None,
        meta: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
) -> JSONAPIResponse:
    """Serialize one object and return a JSON:API FastAPI response."""

    query = query or QuerySpec()
    try:
        document = serialize_document(
            obj,
            resource,
            include=query.include,
            fieldsets=query.fieldsets,
            context=context,
            links=links,
            meta=meta,
        )
    except (FieldsetResolutionError, IncludeResolutionError) as exc:
        raise JSONAPIHTTPException(
            400,
            title="Invalid query parameter",
            detail=str(exc),
            code="invalid-query-parameter",
        ) from exc
    return JSONAPIResponse(document, status_code=status_code, headers=headers)


def collection_response(
        objects: Any,
        resource: type[Resource],
        *,
        query: QuerySpec | None = None,
        pagination: PaginationMeta | None = None,
        context: Mapping[str, Any] | None = None,
        links: dict[str, Any] | str | None = None,
        meta: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
) -> JSONAPIResponse:
    """Serialize an iterable and return a JSON:API collection response."""

    query = query or QuerySpec()
    response_meta = dict(meta or {})
    pagination_value = _pagination_meta(pagination)

    if pagination_value is not None:
        response_meta.update(pagination_value)

    try:
        document = serialize_collection(
            objects,
            resource,
            include=query.include,
            fieldsets=query.fieldsets,
            context=context,
            links=links,
            meta=response_meta or None,
        )
    except (FieldsetResolutionError, IncludeResolutionError) as exc:
        raise JSONAPIHTTPException(
            400,
            title="Invalid query parameter",
            detail=str(exc),
            code="invalid-query-parameter",
        ) from exc
    return JSONAPIResponse(document, status_code=status_code, headers=headers)


def error_response(
        *errors: ErrorObject,
        status_code: int,
        meta: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
) -> JSONAPIResponse:
    """Build a JSON:API error response."""

    document = JSONAPIErrorDocument(errors=list(errors), meta=meta)
    return JSONAPIResponse(document, status_code=status_code, headers=headers)


__all__ = [
    "JSONAPIHTTPException",
    "JSONAPIQuery",
    "JSONAPIResponse",
    "JSONAPI_MEDIA_TYPE",
    "collection_response",
    "error_response",
    "install_jsonapi_exception_handlers",
    "jsonapi_fieldset_openapi",
    "jsonapi_exception_handler",
    "parse_jsonapi_query",
    "resource_response",
    "validate_response_query",
]
