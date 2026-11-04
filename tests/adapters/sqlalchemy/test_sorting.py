from sqlalchemy import select

from jsonapy.adapters.sqlalchemy.sorting import resolve_sqlalchemy_sort_spec
from jsonapy.query.sorting import SortOrder, SortSpec

def test_builds_descending_sort_expression(article_types):
    Article, ArticleResource = article_types
    resolved = resolve_sqlalchemy_sort_spec(
        ArticleResource,
        SortSpec("rank", SortOrder.DESC),
    )
    stmt = select(Article).order_by(resolved.expression)

    assert "articles.rank DESC" in str(stmt)
