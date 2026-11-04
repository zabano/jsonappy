import pytest

from jsonappy.query.include import IncludeResolutionError, IncludeSpecList, resolve_includes
from jsonappy.resource import Relationship, Resource, ResourceRegistry


TEST_REGISTRY = ResourceRegistry()


class OrganizationResource(Resource):
    registry = TEST_REGISTRY
    type = "organizations"


class PersonResource(Resource):
    registry = TEST_REGISTRY
    type = "people"
    organization = Relationship(OrganizationResource)


class CommentResource(Resource):
    registry = TEST_REGISTRY
    type = "comments"
    author = Relationship(lambda: PersonResource)


def test_parse_deduplicates_and_resolves_deferred_include():
    resolved = resolve_includes(
        CommentResource,
        IncludeSpecList.parse("author,author.organization,author"),
    )

    assert [item.path for item in resolved] == ["author", "author.organization"]
    assert resolved[1].target_resource is OrganizationResource


def test_rejects_unknown_include():
    with pytest.raises(IncludeResolutionError, match="no relationship"):
        resolve_includes(CommentResource, IncludeSpecList.parse("missing"))
