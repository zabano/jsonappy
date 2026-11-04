from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jsonapy.adapters.fastapi import (
    COMMON_JSONAPI_ERROR_RESPONSES,
    JSONAPIQuery,
    collection_response,
    install_jsonapi_exception_handlers,
    jsonapi_fieldset_openapi,
    resource_response,
    validate_resource_request,
)
from jsonapy.adapters.pydantic import JSONAPIRequestDocument
from jsonapy.query.pagination import PaginationMeta
from jsonapy.resource import Resource, String


@dataclass
class Item:
    id: int
    name: str


class ItemResource(Resource):
    type = "items"
    name = String(sortable=True, filterable=True, required=True)


app = FastAPI()
install_jsonapi_exception_handlers(app)


@app.get(
    "/items",
    openapi_extra=jsonapi_fieldset_openapi(ItemResource),
)
def get_items(query: JSONAPIQuery):
    return collection_response(
        [Item(1, "One")],
        ItemResource,
        query=query,
        pagination=PaginationMeta(total=1, number=1, size=10),
    )


@app.get("/items/{item_id}")
def get_item(item_id: int, query: JSONAPIQuery):
    return resource_response(Item(item_id, "One"), ItemResource, query=query)


@app.post("/items")
def create_item(document: JSONAPIRequestDocument):
    validate_resource_request(document, ItemResource, operation="create")
    return {"ok": True}


client = TestClient(app)


def test_parses_query_and_returns_jsonapi_media_type():
    response = client.get(
        "/items?sort=-name&filter[name]=One&page[number]=1&"
        "page[size]=10&fields[items]=name",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.api+json",
    )
    assert response.json() == {
        "data": [
            {
                "type": "items",
                "id": "1",
                "attributes": {"name": "One"},
            },
        ],
        "meta": {
            "page": {"total": 1, "number": 1, "size": 10, "pages": 1},
        },
    }


def test_invalid_query_uses_jsonapi_error_document():
    response = client.get("/items?page[size]=1000")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(
        "application/vnd.api+json",
    )
    error = response.json()["errors"][0]
    assert error["status"] == "400"
    assert error["code"] == "invalid-query-parameter"


def test_single_resource_response():
    response = client.get("/items/7")

    assert response.json()["data"] == {
        "type": "items",
        "id": "7",
        "attributes": {"name": "One"},
    }


def test_unknown_fieldset_member_returns_jsonapi_error():
    response = client.get("/items?fields[items]=missing")

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid-query-parameter"


def test_semantic_request_error_uses_jsonapi_pointer():
    response = client.post("/items", json={
        "data": {
            "type": "items",
            "attributes": {"unknown": "value"},
        },
    })

    assert response.status_code == 400
    error = response.json()["errors"][0]
    assert error["code"] == "unknown-attribute"
    assert error["source"]["pointer"] == "/data/attributes/unknown"


def test_structural_request_error_uses_jsonapi_pointer():
    response = client.post("/items", json={})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/vnd.api+json"
    )
    error = response.json()["errors"][0]
    assert error["code"] == "request-validation-error"
    assert error["source"]["pointer"] == "/data"


def test_common_openapi_errors_use_jsonapi_models():
    assert set(COMMON_JSONAPI_ERROR_RESPONSES) == {
        400, 401, 403, 404, 406, 409, 415, 422,
    }
    assert all(
        response["model"].__name__ == "JSONAPIErrorDocument"
        for response in COMMON_JSONAPI_ERROR_RESPONSES.values()
    )


def test_sparse_fieldset_is_documented_with_jsonapi_parameter_name():
    operation = app.openapi()["paths"]["/items"]["get"]
    fieldset = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "fields[items]"
    )

    assert fieldset["in"] == "query"
    assert "name" in fieldset["description"]
