import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jsonappy.adapters.sqlalchemy.query import (
    SQLAlchemyQueryError,
    build_sqlalchemy_count_query,
    build_sqlalchemy_query,
    build_sqlalchemy_query_from_spec,
)
from jsonappy.query.filtering import FilterSpecList
from jsonappy.query.include import IncludeSpecList
from jsonappy.query.pagination import PageSpec
from jsonappy.query.sorting import SortSpecList
from jsonappy.query.spec import QuerySpec


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


def test_distinct_paths_to_same_table_filter_sort_and_count():
    from sqlalchemy import ForeignKey, String
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
    from jsonappy.resource import Resource, Relationship, String as StringField

    class Base(DeclarativeBase):
        pass

    class Person(Base):
        __tablename__ = 'review_people'
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String)
        manager_id: Mapped[int | None] = mapped_column(ForeignKey('review_people.id'))
        manager: Mapped['Person | None'] = relationship(remote_side=[id])

    class Article(Base):
        __tablename__ = 'review_articles'
        id: Mapped[int] = mapped_column(primary_key=True)
        author_id: Mapped[int] = mapped_column(ForeignKey('review_people.id'))
        editor_id: Mapped[int | None] = mapped_column(ForeignKey('review_people.id'))
        author: Mapped[Person] = relationship(foreign_keys=[author_id])
        editor: Mapped[Person | None] = relationship(foreign_keys=[editor_id])

    class PersonResource(Resource):
        type = 'query-people'
        model = Person
        name = StringField(sortable=True, filterable=True)
        manager = Relationship(lambda: PersonResource)

    class ArticleResource(Resource):
        type = 'query-articles'
        model = Article
        author = Relationship(PersonResource)
        editor = Relationship(PersonResource)

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        boss = Person(name='Boss')
        alice = Person(name='Alice', manager=boss)
        bob = Person(name='Bob', manager=alice)
        session.add_all([
            Article(id=1, author=alice, editor=bob),
            Article(id=2, author=bob, editor=alice),
            Article(id=3, author=alice, editor=None),
        ])
        session.commit()
        stmt = build_sqlalchemy_query(
            select(Article), ArticleResource,
            filters=FilterSpecList.parse({
                'filter[author.name]': 'Alice', 'filter[editor.name]': 'Bob',
            }),
            sorts=SortSpecList.parse('editor.name,author.name'),
        )
        assert [row.id for row in session.scalars(stmt)] == [1]
        assert session.scalar(build_sqlalchemy_count_query(stmt)) == 1

        stmt = build_sqlalchemy_query(
            select(Article), ArticleResource,
            sorts=SortSpecList.parse('author.manager.name,editor.manager.name'),
            page=PageSpec(size=2),
        )
        assert len(session.scalars(stmt).all()) == 2
        assert session.scalar(build_sqlalchemy_count_query(stmt)) == 3

        stmt = build_sqlalchemy_query(
            select(Person), PersonResource,
            filters=FilterSpecList.parse({'filter[manager.manager.name]': 'Boss'}),
            sorts=SortSpecList.parse('manager.name'),
        )
        assert [row.name for row in session.scalars(stmt)] == ['Bob']
