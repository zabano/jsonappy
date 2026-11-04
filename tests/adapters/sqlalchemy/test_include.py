from jsonappy.adapters.sqlalchemy.include import build_include_options
from jsonappy.query.fieldsets import FieldsetSpec, FieldsetSpecList
from jsonappy.query.include import IncludeSpecList

def test_builds_loader_for_deferred_relationship(article_types):
    _, ArticleResource = article_types
    options = build_include_options(
        ArticleResource,
        IncludeSpecList.parse("author"),
    )

    assert len(options) == 1


def test_overlapping_includes_collapse_to_deepest_loader(article_types):
    _, ArticleResource = article_types
    options = build_include_options(
        ArticleResource,
        IncludeSpecList.parse("author,author.organization"),
    )

    assert len(options) == 1


def test_included_fieldsets_are_accepted_at_each_loader_level(article_types):
    _, ArticleResource = article_types
    fieldsets = FieldsetSpecList.from_iterable([
        FieldsetSpec.parse("authors", "name"),
        FieldsetSpec.parse("organizations", "name"),
    ])

    options = build_include_options(
        ArticleResource,
        IncludeSpecList.parse("author.organization"),
        fieldsets,
    )

    assert len(options) == 1
