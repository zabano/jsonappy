import pytest

from jsonapy.query.filtering import FilterOp, FilterResolutionError, FilterSpecList, resolve_filters
from jsonapy.resource import Boolean, Integer, Relationship, Resource, String
from jsonapy.resource.options import BooleanFilter, MultiValueFilter, RangeFilter


class CategoryResource(Resource):
    type = "categories"
    code = String(filterable=MultiValueFilter())


class ProductResource(Resource):
    type = "products"
    price = Integer(filterable=RangeFilter())
    active = Boolean(filterable=BooleanFilter())
    category = Relationship(CategoryResource)


def test_parse_and_resolve_filter_operations():
    specs = FilterSpecList.parse({
        "filter[price]": "10:20",
        "filter[active]": "TRUE",
        "filter[category.code]": "a,b",
        "ignored": "value",
    })

    resolved = resolve_filters(ProductResource, specs)

    assert [item.operation for item in resolved] == [FilterOp.RANGE, FilterOp.EQ, FilterOp.IN]
    assert resolved[0].values == ("10", "20")
    assert resolved[1].values == ("true",)
    assert resolved[2].values == ("a", "b")


def test_rejects_invalid_boolean():
    specs = FilterSpecList.parse({"filter[active]": "sometimes"})
    with pytest.raises(FilterResolutionError, match="Invalid boolean"):
        resolve_filters(ProductResource, specs)


def test_rejects_relationship_as_terminal_filter_path():
    specs = FilterSpecList.parse({"filter[category]": "x"})
    with pytest.raises(FilterResolutionError, match="ends at relationship"):
        resolve_filters(ProductResource, specs)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("10:", ("10", "")), (":20", ("", "20"))],
)
def test_range_filter_allows_one_open_boundary(value, expected):
    specs = FilterSpecList.parse({"filter[price]": value})

    resolved = resolve_filters(ProductResource, specs)

    assert resolved[0].values == expected


@pytest.mark.parametrize(('value', 'expected'), [
    ('2026-01-01T10:00:00+01:00..2026-01-02T12:30:00Z',
     ('2026-01-01T10:00:00+01:00', '2026-01-02T12:30:00Z')),
    ('2026-01-01T10:00:00..', ('2026-01-01T10:00:00', '')),
    ('..2026-01-02T12:30:00Z', ('', '2026-01-02T12:30:00Z')),
])
def test_datetime_range_preserves_timestamp_colons(value, expected):
    from jsonapy.resource import DateTime

    class EventResource(Resource):
        type = 'filter-events'
        starts_at = DateTime(filterable=RangeFilter())

    resolved = resolve_filters(EventResource, FilterSpecList.parse({
        'filter[starts_at]': value,
    }))
    assert resolved[0].values == expected


@pytest.mark.parametrize('value', ['..', '1..2..3', '1:2:3'])
def test_rejects_empty_or_ambiguous_ranges(value):
    with pytest.raises(FilterResolutionError):
        resolve_filters(ProductResource, FilterSpecList.parse({'filter[price]': value}))
