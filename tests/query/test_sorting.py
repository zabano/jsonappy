import pytest

from jsonapy.query.sorting import SortOrder, SortResolutionError, SortSpecList, resolve_sorts
from jsonapy.resource import Integer, Relationship, Resource, String, ResourceRegistry


TEST_REGISTRY = ResourceRegistry()


class AuthorResource(Resource):
    registry = TEST_REGISTRY
    type = "authors"
    name = String(sortable=True)


class ArticleResource(Resource):
    registry = TEST_REGISTRY
    type = "articles"
    rank = Integer(sortable=True)
    title = String()
    author = Relationship(AuthorResource)


def test_parse_and_resolve_nested_sorts():
    resolved = resolve_sorts(
        ArticleResource,
        SortSpecList.parse("rank,-author.name"),
    )

    assert [item.spec.order for item in resolved] == [SortOrder.ASC, SortOrder.DESC]
    assert resolved[1].path == ("author", "name")
    assert resolved[1].resolved_field.target_resource is AuthorResource


def test_rejects_non_sortable_field():
    with pytest.raises(SortResolutionError, match="not sortable"):
        resolve_sorts(ArticleResource, SortSpecList.parse("title"))


@pytest.mark.parametrize("value", ["-", " -- "])
def test_rejects_empty_sort_name(value):
    with pytest.raises(ValueError):
        SortSpecList.parse(value)
