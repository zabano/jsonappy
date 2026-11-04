from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from jsonapy.adapters.sqlalchemy.paths import resolve_sqlalchemy_path
from jsonapy.resource import Integer as IntegerField
from jsonapy.resource import Relationship, Resource
from jsonapy.resource import String as StringField


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    author: Mapped[Author] = relationship()


class AuthorResource(Resource):
    type = "authors"
    model = Author
    name = StringField(sortable=True, filterable=True)


class ArticleResource(Resource):
    type = "articles"
    model = Article
    rank = IntegerField(sortable=True, filterable=True)
    author = Relationship(lambda: AuthorResource)


def test_resolves_direct_column():
    path = resolve_sqlalchemy_path(ArticleResource, "rank")
    assert path.attribute is Article.rank
    assert path.relationships == ()


def test_resolves_deferred_nested_relationship_path():
    path = resolve_sqlalchemy_path(ArticleResource, "author.name")
    assert path.attribute is Author.name
    assert len(path.relationships) == 1
    assert path.target_resource is AuthorResource
