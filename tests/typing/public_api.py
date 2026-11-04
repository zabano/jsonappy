"""Consumer examples checked by mypy; these functions need not execute."""

from typing import Any, assert_type

from jsonappy import Resource, ResourceRegistry
from jsonappy.adapters.pydantic import (
    JSONAPIDocument,
    JSONAPIRequestDocument,
    ValidatedResourceRequest,
    serialize_document,
    validate_request_document,
)
from jsonappy.query import QuerySpec, ResolvedQuery, resolve_query
from jsonappy.resource import Field, Relationship, String


class ArticleResource(Resource):
    type = "typing-articles"
    register = False
    title = String(sortable=True, required=True)


def core_contracts(resource: type[Resource]) -> None:
    assert_type(resource.registry, ResourceRegistry)
    assert_type(resource.get_resource("articles"), type[Resource] | None)
    registry = ResourceRegistry()
    assert_type(registry.get("articles"), type[Resource] | None)
    assert_type(registry.registered_types(), frozenset[str])
    assert_type(resource.fields(), dict[str, Field])
    assert_type(resource.relationships(), dict[str, Relationship])
    query = QuerySpec.parse(sort="title")
    assert_type(query, QuerySpec)
    assert_type(resolve_query(ArticleResource, query), ResolvedQuery)
    assert_type(Relationship(ArticleResource).resolve_resource(), type[Resource])


def adapter_contracts(obj: object, request: JSONAPIRequestDocument) -> None:
    document = serialize_document(obj, ArticleResource)
    assert_type(document, JSONAPIDocument)
    assert_type(document.to_payload(), dict[str, Any])
    assert_type(
        validate_request_document(request, ArticleResource, operation="create"),
        ValidatedResourceRequest,
    )
