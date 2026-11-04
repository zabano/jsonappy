"""Registry isolation, duplicate handling, and relationship ownership."""

import pytest

from jsonapy import Resource, ResourceRegistry
from jsonapy.query import QuerySpec, resolve_query
from jsonapy.resource import Relationship, String


def test_applications_can_reuse_type_names_without_affecting_default_registry():
    def declarations(configured_registry):
        class AppResource(Resource):
            abstract = True
            registry = configured_registry

        class AuthorResource(AppResource):
            type = "authors"
            name = String(sortable=True)

        class ArticleResource(AppResource):
            type = "articles"
            author = Relationship("authors")

        return AppResource, AuthorResource, ArticleResource

    default_types = Resource.registered_types()
    first, second = ResourceRegistry(), ResourceRegistry()
    first_base, first_author, first_article = declarations(first)
    second_base, second_author, second_article = declarations(second)

    assert first_base.registry is first
    assert second_base.registry is second
    assert first.get("authors") is first_author
    assert second.get("authors") is second_author
    assert first_article.get_resource("authors") is first_author
    assert second_article.get_resource("authors") is second_author
    assert first_article.relationship("author").resource is first_author
    assert second_article.relationship("author").resource is second_author
    for base, author, article in [
        (first_base, first_author, first_article),
        (second_base, second_author, second_article),
    ]:
        assert base.registered_types() == frozenset({"authors", "articles"})
        assert article.resolve_path("author.name").target_resource is author
        assert resolve_query(article, QuerySpec.parse(sort="author.name")).sorts[0].resolved_field.target_resource is author
        base.validate_all()
    assert Resource.registered_types() == default_types


def test_duplicate_default_type_raises_without_replacing_original():
    class OriginalResource(Resource):
        type = "registry-duplicate-default"

    with pytest.raises(ValueError, match="already registered.*OriginalResource"):
        class DuplicateResource(Resource):
            type = "registry-duplicate-default"

    assert Resource.get_resource("registry-duplicate-default") is OriginalResource


def test_registry_registration_is_idempotent_and_type_snapshots_are_immutable():
    configured = ResourceRegistry()
    snapshot = configured.registered_types()

    class OriginalResource(Resource):
        registry = configured
        type = "articles"

    configured.register(OriginalResource)
    assert snapshot == frozenset()
    assert configured.registered_types() == frozenset({"articles"})
    assert configured.get("missing") is None

    with pytest.raises(ValueError, match="already registered"):
        class DuplicateResource(OriginalResource):
            pass

    class PrivateResource(OriginalResource):
        register = False

    assert PrivateResource.registry is configured
    assert configured.get("articles") is OriginalResource


def test_inherited_relationships_bind_independently_to_subclass_registries():
    first, second = ResourceRegistry(), ResourceRegistry()

    class FirstAuthor(Resource):
        registry = first
        type = "authors"

    class SecondAuthor(Resource):
        registry = second
        type = "authors"

    class ArticleBase(Resource):
        abstract = True
        registry = first
        created_by = Relationship("authors", public_name="createdBy")

    class FirstArticle(ArticleBase):
        type = "articles"

    class SecondArticle(ArticleBase):
        registry = second
        type = "articles"

    assert ArticleBase.created_by.resource is FirstAuthor
    assert FirstArticle.created_by.resource is FirstAuthor
    assert SecondArticle.created_by.resource is SecondAuthor
    assert FirstArticle.created_by is not ArticleBase.created_by
    assert SecondArticle.created_by is SecondArticle.relationship("created_by")
    assert SecondArticle.created_by.public_name == "createdBy"
    first.validate_all()
    second.validate_all()


def test_reused_relationship_declaration_is_bound_without_mutating_prototype():
    configured = ResourceRegistry()
    prototype = Relationship("authors", public_name="author")

    class AuthorResource(Resource):
        registry = configured
        type = "authors"

    class FirstResource(Resource):
        registry = configured
        type = "first"
        creator = prototype

    class SecondResource(Resource):
        registry = configured
        type = "second"
        writer = prototype

    assert prototype.name is None
    assert FirstResource.creator.name == "creator"
    assert SecondResource.writer.name == "writer"
    assert FirstResource.creator.resource is AuthorResource
    assert SecondResource.writer.resource is AuthorResource


def test_string_targets_do_not_fall_back_to_default_registry():
    class GlobalTarget(Resource):
        type = "registry-global-target"

    class LocalSource(Resource):
        registry = ResourceRegistry()
        type = "sources"
        target = Relationship("registry-global-target")

    assert Relationship("registry-global-target").resource is GlobalTarget
    with pytest.raises(LookupError, match="unknown resource type"):
        LocalSource.target.resolve_resource()
    with pytest.raises(LookupError, match="unknown resource type"):
        LocalSource.validate_all()


def test_circular_string_relationships_resolve_after_registration():
    configured = ResourceRegistry()

    class AuthorResource(Resource):
        registry = configured
        type = "authors"
        articles = Relationship("articles", many=True)

    with pytest.raises(LookupError, match="unknown resource type"):
        AuthorResource.validate()

    class ArticleResource(Resource):
        registry = configured
        type = "articles"
        author = Relationship("authors")

    configured.validate_all()
    assert AuthorResource.articles.resource is ArticleResource
    assert ArticleResource.author.resource is AuthorResource


def test_registry_validation_does_not_visit_another_registry():
    class InvalidResource(Resource):
        registry = ResourceRegistry()
        type = "invalid"
        missing = Relationship("missing")

    class ValidResource(Resource):
        registry = ResourceRegistry()
        type = "valid"

    ValidResource.validate_all()
    with pytest.raises(LookupError):
        InvalidResource.validate_all()


def test_explicit_class_and_callable_targets_can_reference_shared_resources():
    class SharedResource(Resource):
        registry = ResourceRegistry()
        type = "shared"

    class LocalResource(Resource):
        registry = ResourceRegistry()
        type = "local"
        direct = Relationship(SharedResource)
        deferred = Relationship(lambda: SharedResource)

    LocalResource.validate_all()
    assert LocalResource.direct.resource is SharedResource
    assert LocalResource.deferred.resource is SharedResource


def test_invalid_registry_and_manual_foreign_registration_are_rejected():
    with pytest.raises(TypeError, match="must be a ResourceRegistry"):
        class InvalidResource(Resource):
            registry = {}
            type = "invalid-registry"

    with pytest.raises(TypeError, match="concrete Resource"):
        ResourceRegistry().register(Resource)

    class LocalResource(Resource):
        registry = ResourceRegistry()
        type = "local"

    with pytest.raises(ValueError, match="belongs to another registry"):
        ResourceRegistry().register(LocalResource)
