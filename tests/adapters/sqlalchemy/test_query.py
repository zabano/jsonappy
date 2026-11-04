import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jsonapy.adapters.sqlalchemy.query import (
    SQLAlchemyQueryError,
    build_sqlalchemy_count_query,
    build_sqlalchemy_query,
    build_sqlalchemy_query_from_spec,
)
from jsonapy.query.filtering import FilterSpecList
from jsonapy.query.include import IncludeSpecList
from jsonapy.query.pagination import PageSpec
from jsonapy.query.sorting import SortSpecList
from jsonapy.query.spec import QuerySpec


def test_builds_complete_root_column_query(article_types):
    Article, ArticleResource = article_types
    stmt = build_sqlalchemy_query(
        select(Article),
        ArticleResource,
        filters=FilterSpecList.parse({"filter[rank]": "3"}),
        sorts=SortSpecList.parse("-rank"),
        includes=IncludeSpecList.parse("author"),
        page=PageSpec(number=2, size=5),
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "WHERE fixture_articles.rank = 3" in compiled
    assert "ORDER BY fixture_articles.rank DESC" in compiled
    assert "LIMIT 5 OFFSET 5" in compiled


def test_wraps_invalid_include_as_query_error(article_types):
    Article, ArticleResource = article_types
    with pytest.raises(SQLAlchemyQueryError, match="no relationship"):
        build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            includes=IncludeSpecList.parse("missing"),
        )


def test_nested_filter_adds_join_and_returns_matching_roots(mapped_types):
    Base, Author, Article, ArticleResource = mapped_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            Article(rank=2, author=Author(name="Omar")),
            Article(rank=1, author=Author(name="Sara")),
        ])
        session.commit()

        stmt = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            filters=FilterSpecList.parse({"filter[author.name]": "Omar"}),
        )
        rows = session.scalars(stmt).all()

    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert compiled.count("JOIN fixture_authors") == 1
    assert [row.rank for row in rows] == [2]


def test_shared_nested_filter_and_sort_join_once(article_types):
    Article, ArticleResource = article_types
    stmt = build_sqlalchemy_query(
        select(Article),
        ArticleResource,
        filters=FilterSpecList.parse({"filter[author.name]": "Omar"}),
        sorts=SortSpecList.parse("author.name"),
    )

    compiled = str(stmt)
    assert compiled.count("JOIN fixture_authors") == 1
    assert "ORDER BY fixture_authors.name ASC" in compiled


def test_multi_level_sort_applies_each_join_once(article_types):
    Article, ArticleResource = article_types
    stmt = build_sqlalchemy_query(
        select(Article),
        ArticleResource,
        sorts=SortSpecList.parse("author.organization.name"),
    )

    compiled = str(stmt)
    assert compiled.count("JOIN fixture_authors") == 1
    assert compiled.count("JOIN fixture_organizations") == 1
    assert compiled.count("LEFT OUTER JOIN") == 2
    assert "ORDER BY fixture_organizations.name ASC" in compiled


def test_nested_sort_preserves_root_pagination_and_count(mapped_types):
    Base, Author, Article, ArticleResource = mapped_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            Article(rank=3, author=Author(name="C")),
            Article(rank=1, author=Author(name="A")),
            Article(rank=2, author=Author(name="B")),
        ])
        session.commit()

        unpaginated = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            sorts=SortSpecList.parse("author.name"),
        )
        paginated = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            sorts=SortSpecList.parse("author.name"),
            page=PageSpec(number=2, size=2),
        )

        total = session.scalar(build_sqlalchemy_count_query(unpaginated))
        rows = session.scalars(paginated).all()

    assert total == 3
    assert [row.rank for row in rows] == [3]


@pytest.mark.parametrize(
    ("filters", "sorts", "message"),
    [
        (
            FilterSpecList.parse({"filter[tags.label]": "urgent"}),
            None,
            "Filtering through to-many",
        ),
        (
            None,
            SortSpecList.parse("tags.label"),
            "Sorting through to-many",
        ),
    ],
)
def test_rejects_to_many_query_paths(
        article_types,
        filters,
        sorts,
        message,
):
    Article, ArticleResource = article_types
    with pytest.raises(SQLAlchemyQueryError, match=message):
        build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            filters=filters,
            sorts=sorts,
        )


def test_builds_query_directly_from_query_spec(article_types):
    Article, ArticleResource = article_types
    spec = QuerySpec.parse(
        sort="-rank",
        filters=FilterSpecList.parse({"filter[rank]": "3"}),
        page_size=5,
    )

    stmt = build_sqlalchemy_query_from_spec(
        select(Article),
        ArticleResource,
        spec,
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "WHERE fixture_articles.rank = 3" in compiled
    assert "ORDER BY fixture_articles.rank DESC" in compiled
    assert "LIMIT 5" in compiled
