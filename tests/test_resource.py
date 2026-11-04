import pytest

import jsonappy
from jsonappy.resource import Relationship, Resource, ResourceRegistry, String


def test_public_package_exports_are_importable():
    assert jsonappy.Resource is Resource
    assert jsonappy.ResourceRegistry is ResourceRegistry
    assert jsonappy.__all__ == [
        "ComputedField",
        "Field",
        "Relationship",
        "Resource",
        "ResourceRegistry",
    ]


def test_resource_requires_type():
    with pytest.raises(TypeError, match="must define"):
        class MissingTypeResource(Resource):
            value = String()


def test_resource_rejects_public_name_collision():
    with pytest.raises(TypeError, match="same public name"):
        class DuplicateResource(Resource):
            type = "duplicates"
            first = String(public_name="value")
            second = String(public_name="value")


def test_circular_deferred_relationships_resolve():
    class LeftResource(Resource):
        type = "left"
        right = Relationship(lambda: RightResource)

    class RightResource(Resource):
        type = "right"
        label = String()
        left = Relationship(lambda: LeftResource)

    assert LeftResource.relationship("right").resource is RightResource
    assert RightResource.relationship("left").resource is LeftResource
    assert LeftResource.resolve_path("right.label").target_resource is RightResource


def test_relationship_rejects_non_resource_target():
    relationship = Relationship(lambda: str)
    with pytest.raises(TypeError, match="must return a Resource class"):
        relationship.resolve_resource()


def test_relationship_rejects_non_callable_reference():
    with pytest.raises(TypeError, match="must be a resource type string"):
        Relationship(42)


def test_relationship_resolves_canonical_resource_type_string():
    class StringTargetResource(Resource):
        type = "string-targets"

    class StringSourceResource(Resource):
        type = "string-sources"
        target = Relationship("string-targets")

    assert (
        StringSourceResource.relationship("target").resource
        is StringTargetResource
    )


def test_relationship_rejects_unknown_resource_type_string():
    relationship = Relationship("missing-resource-type")

    with pytest.raises(LookupError, match="unknown resource type"):
        relationship.resolve_resource()


@pytest.mark.parametrize("reserved_name", ["id", "type"])
def test_resource_rejects_reserved_attribute_names(reserved_name):
    with pytest.raises(TypeError, match="reserved public name"):
        class ReservedResource(Resource):
            type = "reserved"
            value = String(public_name=reserved_name)


def test_resource_name_style_formats_declarative_names():
    class StyledResource(Resource):
        type = "styled"
        name_style = "camelcase"
        long_name = String()
        related_items = Relationship(lambda: StyledResource, many=True)

    assert StyledResource.field("long_name").public_name == "longName"
    assert StyledResource.relationship("related_items").public_name == (
        "relatedItems"
    )


def test_abstract_resource_provides_inherited_configuration():
    class CamelCaseResource(Resource):
        abstract = True
        name_style = "camelcase"

    class ConcreteResource(CamelCaseResource):
        type = "configured-resources"
        long_name = String()

    assert ConcreteResource.field("long_name").public_name == "longName"
    assert CamelCaseResource.abstract is True
    assert ConcreteResource.abstract is False
    assert Resource.get_resource("configured-resources") is ConcreteResource


def test_resource_is_registered_by_jsonapi_type():
    class RegisteredResource(Resource):
        type = "registered-resources"

    assert Resource.get_resource("registered-resources") is RegisteredResource
    assert "registered-resources" in Resource.registered_types()


def test_resource_can_resolve_a_computed_identifier():
    class CompositeResource(Resource):
        type = "composites"
        id_resolver = lambda obj: f"{obj.left}:{obj.right}"

    value = type("Value", (), {"left": "a", "right": "b"})()

    assert CompositeResource.resolve_id(value) == "a:b"


def test_resource_can_opt_out_of_type_registration():
    class PublicResource(Resource):
        type = "public-resources"

    class PrivateRepresentation(PublicResource):
        register = False

    assert Resource.get_resource("public-resources") is PublicResource
