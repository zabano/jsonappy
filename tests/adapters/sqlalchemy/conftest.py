import pytest
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from jsonapy.resource import Integer as IntegerField
from jsonapy.resource import Relationship, Resource
from jsonapy.resource import String as StringField


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "fixture_organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")


class Author(Base):
    __tablename__ = "fixture_authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    biography: Mapped[str] = mapped_column(String, default="")
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("fixture_organizations.id"),
    )
    organization: Mapped[Organization | None] = relationship()


class Tag(Base):
    __tablename__ = "fixture_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String)
    article_id: Mapped[int] = mapped_column(ForeignKey("fixture_articles.id"))


class Article(Base):
    __tablename__ = "fixture_articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int] = mapped_column(ForeignKey("fixture_authors.id"))
    author: Mapped[Author] = relationship()
    tags: Mapped[list[Tag]] = relationship()


class OrganizationResource(Resource):
    type = "organizations"
    model = Organization
    name = StringField(sortable=True, filterable=True)
    description = StringField()


class AuthorResource(Resource):
    type = "authors"
    model = Author
    name = StringField(sortable=True, filterable=True)
    biography = StringField()
    organization = Relationship(OrganizationResource)


class TagResource(Resource):
    type = "tags"
    model = Tag
    label = StringField(sortable=True, filterable=True)


class ArticleResource(Resource):
    type = "articles"
    model = Article
    rank = IntegerField(sortable=True, filterable=True)
    author = Relationship(lambda: AuthorResource)
    tags = Relationship(TagResource, many=True)


@pytest.fixture
def article_types():
    return Article, ArticleResource


@pytest.fixture
def mapped_types():
    return Base, Author, Article, ArticleResource


@pytest.fixture
def nested_types():
    return Base, Organization, Author, Article, ArticleResource
