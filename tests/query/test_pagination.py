import pytest

from jsonapy.query.pagination import PageSpec, PaginationError, PaginationMeta


def test_page_parsing_and_offsets():
    page = PageSpec.parse("3", "25")
    assert page.offset == 50
    assert page.limit == 25
    assert page.to_query_parameters() == {"page[number]": 3, "page[size]": 25}


@pytest.mark.parametrize(
    ("number", "size"),
    [(0, 10), (1, 0), (1, 101), (True, 10)],
)
def test_rejects_invalid_pages(number, size):
    with pytest.raises(PaginationError):
        PageSpec.parse(number, size)


def test_pagination_metadata():
    meta = PaginationMeta(total=21, number=2, size=10)
    assert meta.pages == 3
    assert meta.first == 11
    assert meta.last == 20
    assert meta.has_previous
    assert meta.has_next
