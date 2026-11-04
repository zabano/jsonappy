"""Precision and wire-format contracts for decimal attributes."""

from dataclasses import dataclass
from decimal import Decimal as DecimalValue, localcontext

import pytest

from jsonapy.adapters.pydantic import (
    JSONAPIRequestDocument,
    ResourceRequestError,
    SerializationError,
    serialize_document,
    validate_request_document,
)
from jsonapy.query.fieldsets import FieldsetSpec, FieldsetSpecList
from jsonapy.resource import Decimal, Resource


@dataclass
class Product:
    id: int
    unit_price: object


class ProductResource(Resource):
    type = "decimal-products"
    register = False
    unit_price = Decimal(public_name="unitPrice", required=True, nullable=True)


def request_document(value):
    return JSONAPIRequestDocument.model_validate({
        "data": {
            "type": "decimal-products",
            "id": "1",
            "attributes": {"unitPrice": value},
        },
    })


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize(("value", "expected"), [
    ("12345678901234567890.12345678901234567890", "12345678901234567890.12345678901234567890"),
    ("0.00000000000000000000000000000000000001", "1E-38"),
    ("1.2300", "1.2300"),
    ("-0.00", "-0.00"),
    ("1E+100", "1E+100"),
    (9007199254740993, "9007199254740993"),
    (0, "0"),
    (0.1, "0.1"),
    (DecimalValue("19.9900"), "19.9900"),
])
def test_decimal_request_preserves_digits_and_scale(value, expected, operation):
    with localcontext() as context:
        context.prec = 6
        validated = validate_request_document(
            request_document(value), ProductResource, operation=operation,
        )
        result = validated.attributes["unit_price"]
        assert isinstance(result, DecimalValue)
        assert result.as_tuple() == DecimalValue(expected).as_tuple()
        document = serialize_document(Product(1, result), ProductResource)

    assert document.to_payload()["data"]["attributes"]["unitPrice"] == expected
    assert document.model_dump(mode="json")["data"]["attributes"]["unitPrice"] == expected


@pytest.mark.parametrize("value", [
    True, False, "", "invalid", [], {}, "NaN", "sNaN", "Infinity", "-Infinity",
    float("nan"), float("inf"), float("-inf"), DecimalValue("NaN"),
    DecimalValue("sNaN"), DecimalValue("Infinity"),
])
def test_invalid_decimal_request_reports_public_pointer(value):
    with pytest.raises(ResourceRequestError) as caught:
        validate_request_document(request_document(value), ProductResource, operation="create")
    assert caught.value.code == "invalid-attribute-value"
    assert caught.value.status_code == 422
    assert caught.value.pointer == "/data/attributes/unitPrice"


@pytest.mark.parametrize(("value", "expected"), [
    (DecimalValue("12345678901234567890.123400"), "12345678901234567890.123400"),
    ("19.9900", "19.9900"),
    (9007199254740993, "9007199254740993"),
    (0.1, "0.1"),
])
def test_decimal_model_values_use_json_strings(value, expected):
    document = serialize_document(Product(1, value), ProductResource)
    assert document.to_payload()["data"]["attributes"]["unitPrice"] == expected


@pytest.mark.parametrize("value", [True, "invalid", "NaN", float("inf"), DecimalValue("sNaN")])
def test_invalid_decimal_model_value_raises_serialization_error(value):
    with pytest.raises(SerializationError, match="unitPrice.*finite decimal"):
        serialize_document(Product(1, value), ProductResource)


def test_nullable_decimal_preserves_null():
    validated = validate_request_document(
        request_document(None), ProductResource, operation="create",
    )
    assert validated.attributes["unit_price"] is None
    payload = serialize_document(Product(1, None), ProductResource).to_payload()
    assert payload["data"]["attributes"]["unitPrice"] is None


def test_sparse_fieldset_excludes_decimal_without_coercion():
    fieldsets = FieldsetSpecList.from_iterable([FieldsetSpec.parse("decimal-products", "")])
    payload = serialize_document(Product(1, "invalid"), ProductResource, fieldsets=fieldsets).to_payload()
    assert "attributes" not in payload["data"]


def test_decimal_fastapi_request_and_response_preserve_exact_string():
    from typing import Annotated

    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from jsonapy.adapters.fastapi import (
        JSONAPI_MEDIA_TYPE,
        install_jsonapi_exception_handlers,
        resource_request,
        resource_response,
    )
    from jsonapy.adapters.pydantic import ValidatedResourceRequest

    app = FastAPI()
    install_jsonapi_exception_handlers(app)
    dependency = resource_request(ProductResource, operation="create")

    @app.post("/products")
    def create_product(values: Annotated[ValidatedResourceRequest, Depends(dependency)]):
        assert isinstance(values.attributes["unit_price"], DecimalValue)
        return resource_response(Product(1, values.attributes["unit_price"]), ProductResource)

    exact = "12345678901234567890.12345678901234567890"
    with TestClient(app) as client:
        response = client.post("/products", headers={"Content-Type": JSONAPI_MEDIA_TYPE}, json={
            "data": {"type": "decimal-products", "attributes": {"unitPrice": exact}},
        })
        assert response.status_code == 200
        assert response.headers["content-type"] == JSONAPI_MEDIA_TYPE
        assert response.json()["data"]["attributes"]["unitPrice"] == exact

        response = client.post("/products", headers={"Content-Type": JSONAPI_MEDIA_TYPE}, json={
            "data": {"type": "decimal-products", "attributes": {"unitPrice": "NaN"}},
        })
        assert response.status_code == 422
        error = response.json()["errors"][0]
        assert error["source"]["pointer"] == "/data/attributes/unitPrice"
