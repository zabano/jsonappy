from jsonapy.query.fieldsets import FieldsetSpec, FieldsetSpecList
from jsonapy.query.filtering import FilterSpecList
from jsonapy.query.spec import QuerySpec, resolve_query
from jsonapy.resource import Integer, Resource


class ItemResource(Resource):
    type = "items"
    rank = Integer(sortable=True, filterable=True)


def test_query_spec_round_trip():
    spec = QuerySpec.parse(
        sort="-rank",
        filters=FilterSpecList.parse({"filter[rank]": "2"}),
        page_number="3",
        page_size="20",
        fieldsets=FieldsetSpecList.from_iterable([
            FieldsetSpec.parse("items", "rank"),
        ]),
    )

    assert spec.to_query_parameters() == {
        "sort": "-rank",
        "filter[rank]": "2",
        "page[number]": 3,
        "page[size]": 20,
        "fields[items]": "rank",
    }


def test_complete_query_resolution():
    spec = QuerySpec.parse(
        sort="rank",
        filters=FilterSpecList.parse({"filter[rank]": "2"}),
    )

    resolved = resolve_query(ItemResource, spec)

    assert resolved.has_sort
    assert resolved.has_filters
    assert resolved.pagination.number == 1
