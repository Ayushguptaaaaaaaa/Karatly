from datetime import date, timedelta

from app.services import period_service


def test_day_period(client):
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        p = period_service.resolve(db, "day", date(2026, 11, 19))
        assert (p.start, p.end) == (date(2026, 11, 19), date(2026, 11, 19))
        assert p.short_label == "19 Nov 2026" and p.label.startswith("Thu, 19 November")
        prev = period_service.previous(db, p)
        assert prev.start == date(2026, 11, 18) and prev.period_type == "day"
        assert len(period_service.options(db)["days"]) == 31


def _shop(api):
    c = api.category("Earrings", label_prefix="ER", subcategories=["Studs", "Hoops"])
    subs = {s["name"]: s["id"] for s in api.get(f"/categories/{c['id']}").json()["subcategories"]}
    start = str(date.today() - timedelta(days=10))
    a = api.designs(c["id"], [{"label": "ER-1", "cost_price": 100, "selling_price": 150, "opening_stock": 10}],
                    subcategory_id=subs["Studs"], opening_date=start)[0]
    b = api.designs(c["id"], [{"label": "ER-2", "cost_price": 200, "selling_price": 300, "opening_stock": 5}],
                    subcategory_id=subs["Hoops"], opening_date=start)[0]
    return c, a, b


def test_net_revenue_and_profit(api):
    c, a, b = _shop(api)
    api.move(a["id"], "SALE", 4)                     # 4 × 150 = 600
    api.move(a["id"], "CUSTOMER_RETURN", 1)          # return value 150
    api.move(a["id"], "PURCHASE", 10, unit_price=130)  # avg cost (10×100 + 10×130)/20 = 115
    api.move(b["id"], "SALE", 2, unit_price=280)     # 560, cost 200 each

    rep = api.get("/reports/profitability?period_type=day&group_by=design").json()
    rows = {r["label"]: r for r in rep["rows"]}
    ra, rb = rows["ER-1"], rows["ER-2"]
    assert ra["net_units"] == 3 and ra["net_revenue"] == 450.0
    assert ra["cogs"] == 345.0 and ra["net_profit"] == 105.0 and ra["margin_pct"] == 23.3
    assert rb["net_revenue"] == 560.0 and rb["net_profit"] == 160.0
    assert rep["totals"]["net_profit"] == 265.0

    subs = {r["name"]: r for r in api.get("/reports/profitability?period_type=month&group_by=subcategory").json()["rows"]}
    assert subs["Studs"]["net_profit"] == 105.0 and subs["Hoops"]["net_profit"] == 160.0
    cats = api.get("/reports/profitability?period_type=quarter&group_by=category").json()["rows"]
    assert cats[0]["name"] == "Earrings" and cats[0]["net_revenue"] == 1010.0

    # profit also flows into the period stock view, dashboard, category card and design detail
    ps = api.get("/periods/stock?period_type=day").json()
    assert ps["totals"]["net_profit"] == 265.0
    assert api.get("/dashboard/overview?period_type=day").json()["kpis"]["net_profit"] == 265.0
    assert api.get(f"/categories/{c['id']}").json()["net_profit_30d"] == 265.0
    det = api.get(f"/designs/{a['id']}").json()
    assert det["net_profit_30d"] == 105.0 and det["avg_unit_cost"] == 115.0
    hist = api.get(f"/designs/{a['id']}/history").json()["monthly"][-1]
    assert hist["net_profit"] == 105.0


def test_profit_export_and_bad_group(api):
    _shop(api)
    r = api.get("/reports/export?report=profitability&group_by=subcategory&period_type=month")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert api.get("/reports/profitability?group_by=foo").status_code == 422
