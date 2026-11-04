import pytest

from jsonappy.query.fieldsets import FieldsetResolutionError, FieldsetSpec, FieldsetSpecList, resolve_fieldsets
from jsonappy.resource import Relationship, Resource, String, ResourceRegistry


TEST_REGISTRY = ResourceRegistry()


class UserResource(Resource):
    registry = TEST_REGISTRY
    type = "users"
    name = String()


class PostResource(Resource):
    registry = TEST_REGISTRY
    type = "posts"
    title = String(public_name="displayTitle")
    author = Relationship(UserResource)


def test_resolves_fields_and_relationships_by_public_name():
    specs = FieldsetSpecList.from_iterable([
        FieldsetSpec.parse("posts", "displayTitle,author"),
    ])

    resolved = resolve_fieldsets(PostResource, specs)

    assert resolved is not None
    assert resolved.field_names == ("displayTitle",)
    assert resolved.relationship_names == ("author",)


def test_ignores_fieldset_for_another_resource_type():
    specs = FieldsetSpecList.from_iterable([FieldsetSpec.parse("users", "name")])
    assert resolve_fieldsets(PostResource, specs) is None


def test_rejects_unknown_field():
    specs = FieldsetSpecList.from_iterable([FieldsetSpec.parse("posts", "missing")])
    with pytest.raises(FieldsetResolutionError, match="no field"):
        resolve_fieldsets(PostResource, specs)
