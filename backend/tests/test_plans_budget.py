from datetime import date, timedelta


def _setup(api):
    """Two categories; designs opened yesterday with 10 pieces and sold out (the '102 pieces' scenario)."""
    nk = api.category("Necklaces", label_prefix="NL", icon="necklace")
    er = api.category("Earrings", label_prefix="ER")
    y = str(date.today() - timedelta(days=1))
    n1 = api.designs(nk["id"], [{"label": "NL-1", "cost_price": 300000, "selling_price": 360000, "opening_stock": 10}],
                     opening_date=y)[0]
    n2 = api.designs(nk["id"], [{"label": "NL-2", "cost_price": 35000, "selling_price": 45000, "opening_stock": 10}],
                     opening_date=y)[0]
    e1 = api.designs(er["id"], [{"label": "ER-1", "cost_price": 5000, "selling_price": 6500, "opening_stock": 10,
                                 "min_stock": 4}], opening_date=y)[0]
    api.move(n1["id"], "SALE", 10)
    api.move(n2["id"], "SALE", 10)
    api.move(e1["id"], "SALE", 7)
    return nk, er


def test_no_extrapolation_and_usual_stock_cap(api):
    _setup(api)
    items = {i["design"]["label"]: i for i in api.get("/reorder/baseline").json()["items"]}
    # sold 10 in a day: old maths said ~68/month -> 102 pieces. Now: capped at 1.5x usual stock (10) = 15
    assert items["NL-1"]["suggested_qty"] == 15 and items["NL-1"]["usual_stock"] == 10
    assert "capped at 15" in items["NL-1"]["reason"]
    assert items["ER-1"]["suggested_qty"] == 12  # target ceil(7*1.5)+4 = 15, capped 15, minus 3 in stock


def test_monthly_budget_trims_lowest_priority_first(api):
    _setup(api)
    api.patch("/settings", {"monthly_purchase_budget": 1000000})  # ₹10 L
    plan = api.post("/purchase-plans", {"from_baseline": True}).json()
    assert plan["scope"] == "ALL" and plan["budget_limit"] == 1000000
    assert plan["total_capital_required"] <= 1000000
    assert plan["budget_note"] and "Fitted" in plan["budget_note"]
    assert "Buying everything suggested would need" in plan["budget_note"]
    # lines that don't fit stay in the plan at 0 so the owner can still choose to buy them
    assert len(plan["items"]) == 3
    # the owner cuts the expensive necklace: refreshing gives the freed money to the other designs
    nl1 = next(i for i in plan["items"] if i["design"]["label"] == "NL-1")
    api.patch(f"/purchase-plans/{plan['id']}/items/{nl1['id']}", {"final_qty": 1})
    again = api.post("/purchase-plans", {"from_baseline": True}).json()
    q = {i["design"]["label"]: i["final_qty"] for i in again["items"]}
    assert q["NL-1"] == 1 and q["NL-2"] == 15 and q["ER-1"] == 12
    assert again["total_capital_required"] <= 1000000
    # a trimmed line keeps the system's original suggestion so the owner sees what was cut
    assert any(i["suggested_qty"] > i["final_qty"] for i in plan["items"])


def test_one_plan_refresh_keeps_human_edits(api):
    _setup(api)
    plan = api.post("/purchase-plans", {"from_baseline": True}).json()
    assert plan["title"].startswith("Purchase plan")
    items = {i["design"]["label"]: i for i in plan["items"]}
    # owner decides: 3 of NL-1, none of ER-1 (0 = not buying this month)
    api.patch(f"/purchase-plans/{plan['id']}/items/{items['NL-1']['id']}", {"final_qty": 3})
    r = api.patch(f"/purchase-plans/{plan['id']}/items/{items['ER-1']['id']}", {"final_qty": 0}).json()
    assert r["total_capital_required"] < plan["total_capital_required"]  # budget drops with the edit
    # creating again (or an AI run) refreshes the SAME plan and keeps the edits
    again = api.post("/purchase-plans", {"from_baseline": True}).json()
    assert again["id"] == plan["id"]
    assert len([p for p in api.get("/purchase-plans").json() if p["status"] in ("DRAFT", "SUBMITTED")]) == 1
    q = {i["design"]["label"]: i["final_qty"] for i in again["items"]}
    assert q["NL-1"] == 3 and q["ER-1"] == 0 and q["NL-2"] == 15
    # lines grouped by category
    order = [i["design"]["category_name"] for i in again["items"]]
    cats = [c["category"] for c in again["by_category"]]
    assert order == sorted(order, key=lambda c: cats.index(c))
    # approve the whole plan: qty > 0 bought, qty 0 skipped
    done = api.post(f"/purchase-plans/{plan['id']}/decide", {"approve_all": True}).json()
    dec = {i["design"]["label"]: i["decision"] for i in done["items"]}
    assert done["status"] == "DECIDED" and dec == {"NL-1": "APPROVED", "NL-2": "APPROVED", "ER-1": "REJECTED"}
    # what is on order is not suggested again
    base = {i["design"]["label"]: i for i in api.get("/reorder/baseline").json()["items"]}
    assert "NL-2" not in base
    assert base["NL-1"]["on_order"] == 3 and base["NL-1"]["suggested_qty"] == 12
