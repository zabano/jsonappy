from sqlalchemy import select

from jsonappy.adapters.sqlalchemy.filtering import resolve_sqlalchemy_filter_spec
from jsonappy.query.filtering import FilterSpec

def test_coerces_integer_filter_and_applies_expression(article_types):
    Article, ArticleResource = article_types
    resolved = resolve_sqlalchemy_filter_spec(
        ArticleResource,
        FilterSpec("rank", "7"),
    )
    stmt = select(Article).where(resolved.expression)
    compiled = stmt.compile(compile_kwargs={"literal_binds": True})

    assert "articles.rank = 7" in str(compiled)


def test_decimal_filter_bindings_preserve_precision_for_all_supported_operations():
    from decimal import Decimal as DecimalValue
    from sqlalchemy import Numeric
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from jsonappy.resource import Decimal, MultiValueFilter, RangeFilter, Resource

    class Base(DeclarativeBase):
        pass

    class Product(Base):
        __tablename__ = "decimal_filter_products"
        id: Mapped[int] = mapped_column(primary_key=True)
        unit_price: Mapped[DecimalValue] = mapped_column(Numeric(40, 20))

    class ProductResource(Resource):
        type = "decimal-filter-products"
        register = False
        model = Product
        unit_price = Decimal(filterable=True)

    class ProductMembershipResource(ProductResource):
        register = False
        unit_price = Decimal(filterable=MultiValueFilter())

    class ProductRangeResource(ProductResource):
        register = False
        unit_price = Decimal(filterable=RangeFilter())

    exact = "12345678901234567890.12345678901234567890"
    for resource, value, expected in [
        (ProductResource, exact, [DecimalValue(exact)]),
        (ProductMembershipResource, f"{exact},19.9900", [DecimalValue(exact), DecimalValue("19.9900")]),
        (ProductRangeResource, f"{exact}:", [DecimalValue(exact)]),
    ]:
        resolved = resolve_sqlalchemy_filter_spec(resource, FilterSpec("unit_price", value))
        # SQLite Numeric storage uses floats, so verify exact bound values
        # before a database driver can impose its own precision limits.
        parameters = list(select(Product).where(resolved.expression).compile().params.values())
        decimals = [
            item
            for parameter in parameters
            for item in (parameter if isinstance(parameter, (tuple, list)) else [parameter])
        ]
        assert all(isinstance(item, DecimalValue) for item in decimals)
        assert [item.as_tuple() for item in decimals] == [item.as_tuple() for item in expected]


def test_datetime_range_executes_with_timestamp_boundaries():
    from datetime import datetime
    from sqlalchemy import DateTime, create_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
    from jsonappy.adapters.sqlalchemy.query import build_sqlalchemy_query
    from jsonappy.query.filtering import FilterSpecList
    from jsonappy.resource import DateTime as DateTimeField, RangeFilter, Resource

    class Base(DeclarativeBase):
        pass

    class Event(Base):
        __tablename__ = 'filter_events'
        id: Mapped[int] = mapped_column(primary_key=True)
        starts_at: Mapped[datetime] = mapped_column(DateTime)

    class EventResource(Resource):
        type = 'sql-filter-events'
        model = Event
        starts_at = DateTimeField(filterable=RangeFilter())

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Event(id=1, starts_at=datetime(2026, 1, 1, 10)),
            Event(id=2, starts_at=datetime(2026, 1, 2, 12, 30)),
            Event(id=3, starts_at=datetime(2026, 1, 3, 10)),
        ])
        session.commit()
        for value, expected in [
            ('2026-01-01T10:00:00..2026-01-02T12:30:00', [1, 2]),
            ('..2026-01-02T12:30:00', [1, 2]),
            ('2026-01-02T12:30:00..', [2, 3]),
        ]:
            stmt = build_sqlalchemy_query(
                select(Event).order_by(Event.id), EventResource,
                filters=FilterSpecList.parse({'filter[starts_at]': value}),
            )
            assert [row.id for row in session.scalars(stmt)] == expected
