from datetime import date, timedelta


def _shop(api):
    nk = api.category("Necklaces", label_prefix="NL", icon="necklace")
    fj = api.category("Fashion", label_prefix="FJ", icon="earring")
    y = str(date.today() - timedelta(days=40))
    n1 = api.designs(nk["id"], [{"label": "NL-1", "cost_price": 100000, "selling_price": 120000, "opening_stock": 10}],
                     opening_date=y)[0]
    f1 = api.designs(fj["id"], [{"label": "FJ-1", "cost_price": 500, "selling_price": 900, "opening_stock": 50,
                                 "metal": "IMITATION"}], opening_date=y)[0]
    return n1, f1


def test_bill_with_customer_discount_gst_and_pdf(api):
    n1, f1 = _shop(api)
    r = api.post("/bills", {
        "customer": {"name": "Priya Sharma", "phone": "9876543210", "city": "mumbai", "state": "Maharashtra"},
        "items": [{"design_id": n1["id"], "quantity": 1}, {"design_id": f1["id"], "quantity": 2, "unit_price": 1000}],
        "discount": 2000, "gst_pct": 3, "payment_mode": "UPI",
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["number"].startswith("INV-") and b["customer"]["city"] == "Mumbai" and b["customer"]["country"] == "India"
    assert b["subtotal"] == 122000 and b["discount"] == 2000 and b["taxable"] == 120000
    assert b["gst_amount"] == 3600 and b["total"] == 123600 and b["pieces"] == 3
    # stock went down and revenue in reports = taxable value (after discount, before GST)
    assert api.get(f"/designs/{n1['id']}").json()["current_stock"] == 9
    sales = api.get("/explore/sales").json()
    assert sales["totals"]["value"] == 120000 and sales["totals"]["qty"] == 3
    pdf = api.get(f"/bills/{b['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    # customer was created with totals
    cust = api.get("/customers").json()
    assert cust[0]["name"] == "Priya Sharma" and cust[0]["bills"] == 1 and cust[0]["revenue"] == 120000
    # cancel the bill: stock comes back, sales disappear
    api.post(f"/bills/{b['id']}/void", {"reason": "test"})
    assert api.get(f"/designs/{n1['id']}").json()["current_stock"] == 10
    assert api.get("/explore/sales").json()["totals"]["value"] == 0


def test_every_sale_gets_a_bill_and_dealer_on_purchase(api):
    n1, f1 = _shop(api)
    dl = api.post("/dealers", {"name": "AD Fashion Hub", "city": "Mumbai", "state": "Maharashtra"}).json()
    r = api.post("/stock/movements", {"design_id": f1["id"], "type": "PURCHASE", "quantity": 20, "unit_price": 480,
                                      "dealer_id": dl["id"]}).json()
    assert r["movement"]["dealer"]["name"] == "AD Fashion Hub"
    s = api.post("/stock/movements", {"design_id": f1["id"], "type": "SALE", "quantity": 3}).json()
    assert s["bill_number"].startswith("INV-") and s["movement"]["bill"]["customer_name"] == "Walk-in customer"
    # purchases explorer grouped by dealer
    p = api.get("/explore/purchases", params={"group_by": "dealer", "purchases_only": True}).json()
    assert p["items"][0]["label"] == "AD Fashion Hub" and p["items"][0]["qty"] == 20 and p["items"][0]["value"] == 9600
    assert api.get("/dealers").json()[0]["pieces"] == 20


def test_mix_filters_top_customer_in_country_and_month(api):
    n1, f1 = _shop(api)
    a = api.post("/customers", {"name": "Anjali Mehta", "city": "Delhi", "state": "Delhi", "country": "India"}).json()
    b = api.post("/customers", {"name": "Farah Khan", "city": "Dubai", "state": "Dubai",
                                "country": "United Arab Emirates"}).json()
    c = api.post("/customers", {"name": "Rohit Iyer", "city": "Chennai", "state": "Tamil Nadu"}).json()
    for cust, item, qty in ((a, f1, 5), (b, n1, 2), (c, n1, 1), (a, f1, 3)):
        assert api.post("/bills", {"customer_id": cust["id"], "items": [{"design_id": item["id"], "quantity": qty}]}
                        ).status_code == 201
    today = date.today()
    month = {"date_from": str(today.replace(day=1)), "date_to": str(today)}
    india = api.get("/explore/sales", params={**month, "country": "India", "group_by": "customer"}).json()
    assert india["items"][0]["label"] == "Rohit Iyer"  # ₹1.2 L beats 8 × ₹900
    assert {i["label"] for i in india["items"]} == {"Rohit Iyer", "Anjali Mehta"}
    anj = next(i for i in india["items"] if i["label"] == "Anjali Mehta")
    assert anj["qty"] == 8 and anj["value"] == 7200 and anj["bills"] == 2
    by_country = api.get("/explore/sales", params={"group_by": "country"}).json()
    assert by_country["items"][0]["label"] == "United Arab Emirates"
    # one customer: quantity and revenue per design
    per = api.get("/explore/sales", params={"customer_id": a["id"], "group_by": "design"}).json()
    assert per["items"][0]["label"] == "FJ-1" and per["totals"]["qty"] == 8
    # export works for grouped and detail views
    assert api.get("/explore/sales/export", params={"group_by": "city"}).status_code == 200
    assert api.get("/explore/purchases/export").status_code == 200
    f = api.get("/explore/facets").json()
    assert "Dubai" in f["cities"] and "United Arab Emirates" in f["countries"]


def test_undo_single_sale_cancels_its_bill(api):
    n1, _ = _shop(api)
    s = api.post("/stock/movements", {"design_id": n1["id"], "type": "SALE", "quantity": 1}).json()
    api.post(f"/stock/movements/{s['movement']['id']}/void", {"reason": "Undo"})
    assert api.get(f"/bills/{s['bill_id']}").json()["is_void"] is True
    assert api.get(f"/designs/{n1['id']}").json()["current_stock"] == 10


def test_amount_in_words():
    from app.services.billing_service import amount_in_words
    assert amount_in_words(123600) == "One Lakh Twenty Three Thousand Six Hundred Rupees Only"
    assert amount_in_words(10500000.5) == "One Crore Five Lakh Rupees and Fifty Paise Only"


def test_demo_data_has_customers_dealers_and_bills(api):
    assert api.post("/admin/demo-data").status_code in (200, 201)
    s = api.get("/explore/sales", params={"group_by": "country"}).json()
    assert len(s["items"]) >= 3 and s["totals"]["bills"] > 100
    assert len(api.get("/dealers").json()) == 6
    p = api.get("/explore/purchases", params={"group_by": "dealer"}).json()
    assert p["items"] and p["items"][0]["label"] != "Not set"


def test_chat_instant_answers_for_customers_regions_dealers(api):
    assert api.post("/admin/demo-data").status_code in (200, 201)
    from app.ai import instant_answers
    from app.core.database import SessionLocal
    from app.services import chat_service

    with SessionLocal() as db:
        snap = chat_service.shop_snapshot(db)
    a = instant_answers.answer("Who is my top customer?", snap)
    assert a and "Top customer" in a.answer_markdown and a.table.rows
    assert "leads with" in instant_answers.answer("Which city buys the most?", snap).answer_markdown
    assert "Dealers" in instant_answers.answer("which dealer did I buy most from", snap).answer_markdown
    # filtered questions go to the AI (with the breakdown tool)
    assert instant_answers.answer("Top customer in India in November?", snap) is None
    from app.ai.tools import GetSalesBreakdown

    out = GetSalesBreakdown()._run(group_by="customer", country="india", period_type="all")
    assert '"rows"' in out and "error" not in out
