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
    assert plan["budget_note"] and "Trimmed" in plan["budget_note"]
    # the big necklace (₹3.15 L each) can only be partly funded; nothing exceeds the budget
    assert all(i["final_qty"] > 0 for i in plan["items"])
    assert "Buying everything would need" in plan["budget_note"]
    # a trimmed line keeps the system's original suggestion so the owner sees what was cut
    assert any(i["suggested_qty"] > i["final_qty"] for i in plan["items"])


def test_plans_per_category_and_final_plan(api):
    _setup(api)
    plans = api.post("/purchase-plans/by-category").json()
    names = sorted(p["category_name"] for p in plans)
    assert names == ["Earrings", "Necklaces"] and all(p["scope"] == "CATEGORY" for p in plans)
    final = api.post("/purchase-plans", {"from_baseline": True}).json()
    cats = [c["category"] for c in final["by_category"]]
    assert set(cats) == {"Earrings", "Necklaces"}
    # final plan total = sum of the category plans (no budget set)
    assert abs(final["total_capital_required"] - sum(p["total_estimated"] for p in plans)) < 1
    # lines are grouped by category
    order = [i["design"]["category_name"] for i in final["items"]]
    assert order == sorted(order, key=lambda c: cats.index(c))
