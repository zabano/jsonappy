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


def test_datetime_range_executes_with_timestamp_boundaries():
    from datetime import datetime
    from sqlalchemy import DateTime, create_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
    from jsonapy.adapters.sqlalchemy.query import build_sqlalchemy_query
    from jsonapy.query.filtering import FilterSpecList
    from jsonapy.resource import DateTime as DateTimeField, RangeFilter, Resource

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
