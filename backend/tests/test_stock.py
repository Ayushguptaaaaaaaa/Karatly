from datetime import date, timedelta


def _setup(api, stock=10, min_stock=3):
    c = api.category("Earrings", label_prefix="ER")
    return api.designs(c["id"], [{"label": "ER-1", "cost_price": 100, "selling_price": 150,
                                  "opening_stock": stock, "min_stock": min_stock}],
                       opening_date=str(date.today() - timedelta(days=20)))[0]


def test_sale_reduces_and_void_restores(api):
    d = _setup(api)
    r = api.move(d["id"], "SALE", 4)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["design"]["current_stock"] == 6 and body["movement"]["unit_price"] == 150
    r = api.move(d["id"], "SALE", 4)
    assert r.json()["design"]["current_stock"] == 2 and r.json()["design"]["status"] == "LOW"
    r = api.move(d["id"], "SALE", 5)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    mid = body["movement"]["id"]
    r = api.post(f"/stock/movements/{mid}/void", {"reason": "mistake"})
    assert r.json()["design"]["current_stock"] == 6
    assert api.post(f"/stock/movements/{mid}/void").status_code == 409


def test_cannot_void_in_that_goes_negative(api):
    d = _setup(api, stock=2)
    p = api.move(d["id"], "PURCHASE", 5).json()["movement"]["id"]
    api.move(d["id"], "SALE", 6)
    r = api.post(f"/stock/movements/{p}/void")
    assert r.status_code == 409


def test_backdated_and_future(api):
    d = _setup(api, stock=3)
    old = str(date.today() - timedelta(days=30))  # before opening stock existed
    r = api.move(d["id"], "SALE", 1, occurred_on=old)
    assert r.status_code == 409
    fut = str(date.today() + timedelta(days=1))
    assert api.move(d["id"], "SALE", 1, occurred_on=fut).status_code == 422


def test_period_stock_identity(api):
    d = _setup(api, stock=10)
    api.move(d["id"], "SALE", 2)
    api.move(d["id"], "PURCHASE", 5)
    api.move(d["id"], "CUSTOMER_RETURN", 1)
    api.move(d["id"], "ADJUSTMENT_OUT", 1)
    r = api.get("/periods/stock?period_type=month").json()
    row = r["rows"]["items"][0]
    assert row["closing"] == 13
    assert row["closing"] == (row["opening"] + row["opening_added"] + row["received"] + row["customer_returns"]
                              - row["sold"] - row["supplier_returns"] + row["adjustments_net"])
    today = api.get("/stock/today").json()
    assert today["totals"]["sold_units"] == 2
