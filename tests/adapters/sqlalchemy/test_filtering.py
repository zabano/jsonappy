from sqlalchemy import select

from jsonapy.adapters.sqlalchemy.filtering import resolve_sqlalchemy_filter_spec
from jsonapy.query.filtering import FilterSpec

def test_coerces_integer_filter_and_applies_expression(article_types):
    Article, ArticleResource = article_types
    resolved = resolve_sqlalchemy_filter_spec(
        ArticleResource,
        FilterSpec("rank", "7"),
    )
    stmt = select(Article).where(resolved.expression)
    compiled = stmt.compile(compile_kwargs={"literal_binds": True})

    assert "articles.rank = 7" in str(compiled)
