import pytest

from jsonapy.query.include import IncludeResolutionError, IncludeSpecList, resolve_includes
from jsonapy.resource import Relationship, Resource


class OrganizationResource(Resource):
    type = "organizations"


class PersonResource(Resource):
    type = "people"
    organization = Relationship(OrganizationResource)


class CommentResource(Resource):
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
