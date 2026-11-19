from datetime import date

from app.services import period_service


def test_financial_quarters(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        p = period_service.resolve(db, "quarter", date(2027, 1, 15))
        assert (p.start, p.end) == (date(2027, 1, 1), date(2027, 3, 31))
        assert p.short_label == "Q4 FY2026-27"
        p = period_service.resolve(db, "quarter", date(2026, 4, 1))
        assert p.short_label == "Q1 FY2026-27" and p.end == date(2026, 6, 30)
        p = period_service.resolve(db, "quarter", date(2026, 11, 19))
        assert p.short_label == "Q3 FY2026-27" and p.start == date(2026, 10, 1)
        prev = period_service.previous(db, p)
        assert prev.start == date(2026, 7, 1)
        m = period_service.resolve(db, "month", date(2026, 2, 10))
        assert m.end == date(2026, 2, 28) and m.label == "February 2026"
