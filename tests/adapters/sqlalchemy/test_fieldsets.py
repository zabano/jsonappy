from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from jsonapy.adapters.sqlalchemy.fieldsets import resolve_sqlalchemy_fieldset
from jsonapy.adapters.sqlalchemy.query import build_sqlalchemy_query
from jsonapy.query.fieldsets import FieldsetSpec, FieldsetSpecList
from jsonapy.query.include import IncludeSpecList

def test_builds_load_only_option(article_types):
    _, ArticleResource = article_types
    resolved = resolve_sqlalchemy_fieldset(
        ArticleResource,
        FieldsetSpec.parse("articles", "rank"),
    )

    assert [field.public_name for field in resolved.fields] == ["rank"]
    assert len(resolved.options) == 1


def test_empty_root_fieldset_loads_identity_only(mapped_types):
    Base, Author, Article, ArticleResource = mapped_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Article(rank=1, author=Author(name="Omar")))
        session.commit()

        stmt = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            fieldsets=FieldsetSpecList.from_iterable([
                FieldsetSpec.parse("articles", ""),
            ]),
        )
        article = session.scalars(stmt).one()
        unloaded = inspect(article).unloaded

    assert "id" not in unloaded
    assert "rank" in unloaded
    assert "author_id" in unloaded


def test_included_fieldset_defers_excluded_attributes(mapped_types):
    Base, Author, Article, ArticleResource = mapped_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Article(
            rank=1,
            author=Author(name="Omar", biography="Long biography"),
        ))
        session.commit()

        stmt = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            includes=IncludeSpecList.parse("author"),
            fieldsets=FieldsetSpecList.from_iterable([
                FieldsetSpec.parse("authors", "name"),
            ]),
        )
        article = session.scalars(stmt).one()
        author = article.author
        unloaded = inspect(author).unloaded

    assert author.name == "Omar"
    assert "biography" in unloaded


def test_empty_included_fieldset_loads_identity_only(mapped_types):
    Base, Author, Article, ArticleResource = mapped_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Article(rank=1, author=Author(name="Omar")))
        session.commit()

        stmt = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            includes=IncludeSpecList.parse("author"),
            fieldsets=FieldsetSpecList.from_iterable([
                FieldsetSpec.parse("authors", ""),
            ]),
        )
        article = session.scalars(stmt).one()
        unloaded = inspect(article.author).unloaded

    assert "id" not in unloaded
    assert "name" in unloaded
    assert "biography" in unloaded


def test_nested_included_fieldsets_defer_each_resources_exclusions(
        nested_types,
):
    Base, Organization, Author, Article, ArticleResource = nested_types
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        organization = Organization(name="Acme", description="Publishing")
        author = Author(
            name="Omar",
            biography="Long biography",
            organization=organization,
        )
        session.add(Article(rank=1, author=author))
        session.commit()

        stmt = build_sqlalchemy_query(
            select(Article),
            ArticleResource,
            includes=IncludeSpecList.parse("author.organization"),
            fieldsets=FieldsetSpecList.from_iterable([
                FieldsetSpec.parse("authors", "name,organization"),
                FieldsetSpec.parse("organizations", "name"),
            ]),
        )
        article = session.scalars(stmt).one()
        loaded_author = article.author
        loaded_organization = loaded_author.organization

        author_unloaded = inspect(loaded_author).unloaded
        organization_unloaded = inspect(loaded_organization).unloaded

    assert loaded_organization.name == "Acme"
    assert "biography" in author_unloaded
    assert "description" in organization_unloaded
