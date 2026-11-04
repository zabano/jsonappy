from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from jsonapy.adapters.pydantic import (
    JSONAPIRequestDocument,
    ResourceRequestError,
    serialize_collection,
    serialize_document,
    validate_request_document,
)
from jsonapy.query.fieldsets import FieldsetSpec, FieldsetSpecList
from jsonapy.resource import (
    ComputedField,
    DateTime,
    JSON,
    Integer,
    Relationship,
    Resource,
    String,
)


@dataclass
class Person:
    id: int
    name: str
    created_at: datetime
    manager: "Person | None" = None
    reports: list["Person"] = field(default_factory=list)


class PersonResource(Resource):
    type = "people"

    name = String()
    created_at = DateTime(public_name="createdAt")
    display_name = ComputedField(
        lambda person, context: f"{context.get('prefix', '')}{person.name}",
        public_name="displayName",
    )
    manager = Relationship(lambda: PersonResource)
    reports = Relationship(lambda: PersonResource, many=True)


@dataclass
class Metadata:
    id: int
    content: object


class MetadataResource(Resource):
    type = "metadata"

    content = JSON(nullable=True)


class TeamResource(Resource):
    type = "teams"


class WritablePersonResource(Resource):
    type = "writable-people"
    name_style = "camelcase"

    first_name = String(required=True)
    age = Integer(nullable=True)
    display_name = ComputedField(lambda person, context: person.first_name)
    team = Relationship(TeamResource, required=True, nullable=False)
    reports = Relationship(lambda: WritablePersonResource, many=True)


def test_serializes_attributes_linkage_and_json_values():
    manager = Person(1, "Omar", datetime(2026, 1, 1, tzinfo=timezone.utc))
    person = Person(
        2,
        "Sara",
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        manager=manager,
    )

    document = serialize_document(
        person,
        PersonResource,
        context={"prefix": "Dr. "},
    )
    payload = document.model_dump(mode="json", exclude_none=True)

    assert payload["data"]["id"] == "2"
    assert payload["data"]["attributes"] == {
        "name": "Sara",
        "createdAt": "2026-02-01T00:00:00Z",
        "displayName": "Dr. Sara",
    }
    assert payload["data"]["relationships"]["manager"]["data"] == {
        "type": "people",
        "id": "1",
    }
    assert "included" not in payload


def test_builds_deduplicated_compound_document():
    manager = Person(1, "Omar", datetime.now(timezone.utc))
    people = [
        Person(2, "Sara", datetime.now(timezone.utc), manager=manager),
        Person(3, "Ali", datetime.now(timezone.utc), manager=manager),
    ]

    document = serialize_collection(
        people,
        PersonResource,
        include="manager",
    )

    assert len(document.included or []) == 1
    assert document.included[0].id == "1"


def test_sparse_fieldsets_control_attributes_and_relationships():
    manager = Person(1, "Omar", datetime.now(timezone.utc))
    person = Person(2, "Sara", datetime.now(timezone.utc), manager=manager)
    fieldsets = FieldsetSpecList.from_iterable([
        FieldsetSpec.parse("people", "name"),
    ])

    document = serialize_document(
        person,
        PersonResource,
        include="manager",
        fieldsets=fieldsets,
    )
    payload = document.model_dump(mode="json", exclude_none=True)

    assert payload["data"]["attributes"] == {"name": "Sara"}
    assert "relationships" not in payload["data"]
    assert payload["included"][0]["id"] == "1"


def test_primary_resources_are_not_duplicated_in_included():
    first = Person(1, "One", datetime.now(timezone.utc))
    second = Person(2, "Two", datetime.now(timezone.utc), manager=first)
    first.manager = second

    document = serialize_collection(
        [first, second],
        PersonResource,
        include="manager",
    )

    assert document.included is None


def test_required_null_relationship_linkage_is_preserved():
    person = Person(1, "Omar", datetime.now(timezone.utc))

    payload = serialize_document(person, PersonResource).to_payload()

    assert payload["data"]["relationships"]["manager"]["data"] is None


def test_serializes_json_objects_arrays_scalars_and_null():
    values = [
        {"sections": {"news": {"article_count": 42}}},
        ["PASS", 42, True],
        "document-v1",
        None,
    ]

    payload = serialize_collection(
        [Metadata(index, value) for index, value in enumerate(values)],
        MetadataResource,
    ).to_payload()

    assert [item["attributes"]["content"] for item in payload["data"]] == values


def test_validates_and_resolves_declarative_create_document():
    document = JSONAPIRequestDocument.model_validate({
        "data": {
            "type": "writable-people",
            "attributes": {"firstName": "Sara", "age": 30},
            "relationships": {
                "team": {"data": {"type": "teams", "id": "7"}},
                "reports": {"data": []},
            },
        },
    })

    result = validate_request_document(
        document,
        WritablePersonResource,
        operation="create",
    )

    assert result.attributes == {"first_name": "Sara", "age": 30}
    assert result.relationships["team"].data.id == "7"


@pytest.mark.parametrize(
    ("payload", "code", "pointer"),
    [
        (
            {"attributes": {"unknown": "value"}},
            "unknown-attribute",
            "/data/attributes/unknown",
        ),
        (
            {"attributes": {"displayName": "read only"}},
            "read-only-field",
            "/data/attributes/displayName",
        ),
        (
            {
                "attributes": {"firstName": "Sara"},
                "relationships": {
                    "team": {"data": {"type": "wrong", "id": "7"}},
                },
            },
            "type-conflict",
            "/data/relationships/team/data/type",
        ),
    ],
)
def test_request_errors_include_json_pointers(payload, code, pointer):
    document = JSONAPIRequestDocument.model_validate({
        "data": {"type": "writable-people", "id": "1", **payload},
    })

    with pytest.raises(ResourceRequestError) as caught:
        validate_request_document(
            document,
            WritablePersonResource,
            operation="update",
        )

    assert caught.value.code == code
    assert caught.value.pointer == pointer


def test_create_requires_declaratively_required_members():
    document = JSONAPIRequestDocument.model_validate({
        "data": {"type": "writable-people", "attributes": {}},
    })

    with pytest.raises(ResourceRequestError) as caught:
        validate_request_document(
            document,
            WritablePersonResource,
            operation="create",
        )

    assert caught.value.code == "required-field"
    assert caught.value.pointer == "/data/attributes/firstName"
