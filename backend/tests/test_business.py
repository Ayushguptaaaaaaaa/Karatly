from datetime import date, timedelta
from decimal import Decimal

from app.services import costing_service


def test_costing_formula_and_rounding():
    assert costing_service.expected_unit_cost(100, 5) == Decimal("105.00")
    assert costing_service.expected_unit_cost(99.99, 5) == Decimal("104.99")  # 104.9895 -> half up
    line = costing_service.line(100, 5, 10)
    assert line["line_total"] == Decimal("1050.00")
    assert "₹1,050.00" in line["formula_text"]
    assert costing_service.format_inr(1234567) == "₹12,34,567.00"
    assert costing_service.format_inr_compact(184000) == "₹1.84 L"


def test_inflation_override_precedence(api):
    c = api.category("Bangles", label_prefix="BG", icon="bangle", inflation_pct_override=8)
    d = api.designs(c["id"], [{"label": "BG-1", "cost_price": 100, "selling_price": 150, "opening_stock": 0}])[0]
    r = api.post("/purchase-plans", {"from_baseline": True}).json()
    item = r["items"][0]
    assert item["inflation_pct"] == 8 and item["expected_unit_cost"] == 108
    api.patch(f"/designs/{d['id']}", {"inflation_pct_override": 2})
    r2 = api.get("/reorder/baseline").json()
    assert r2["items"][0]["expected_unit_cost"] == 102


def test_reorder_baseline_and_status(api):
    c = api.category("Earrings", label_prefix="ER")
    start = str(date.today() - timedelta(days=60))
    d = api.designs(c["id"], [{"label": "ER-1", "cost_price": 100, "selling_price": 150, "opening_stock": 10,
                               "min_stock": 3}], opening_date=start)[0]
    for i in range(5):
        api.move(d["id"], "SALE", 2, occurred_on=str(date.today() - timedelta(days=i * 5)))
    det = api.get(f"/designs/{d['id']}").json()
    assert det["current_stock"] == 0 and det["status"] == "OUT" and det["demand_class"] == "HIGH"
    base = api.get("/reorder/baseline").json()
    it = base["items"][0]
    # velocity: 10 sold over 60 days -> 5/month; target ceil(5*1.5)+3 = 11
    assert it["suggested_qty"] == 11 and it["priority"] == "HIGH"
    assert it["line_total"] == 11 * 105


def test_dashboard_blank_and_after_data(api):
    ov = api.get("/dashboard/overview").json()
    assert ov["setup"]["completed_steps"] == 0 and ov["kpis"]["total_designs"] == 0
    assert ov["instant_insights"][0]["id"] == "setup_category"
    assert ov["latest_ai"] is None and len(ov["kpi_sparklines"]["sales_value"]) == 6
    c = api.category("Rings", label_prefix="RG", icon="ring")
    d = api.designs(c["id"], [{"label": "RG-1", "cost_price": 1000, "selling_price": 1300, "opening_stock": 4}])[0]
    api.move(d["id"], "SALE", 3)
    ov = api.get("/dashboard/overview").json()
    assert ov["kpis"]["sales_units"] == 3 and ov["kpis"]["sales_value"] == 3900
    assert ov["kpis"]["low_stock"] == 1 and ov["setup"]["has_sale"] is True
    assert ov["top_sellers"][0]["label"] == "RG-1"


def test_purchase_plan_flow_and_permissions(api, admin_api):
    c = api.category("Chains", label_prefix="CH", icon="chain")
    d = api.designs(c["id"], [{"label": "CH-1", "cost_price": 200, "selling_price": 260, "opening_stock": 1}])[0]
    plan = admin_api.post("/purchase-plans", {"from_baseline": True}).json()
    pid = plan["id"]
    assert plan["status"] == "DRAFT" and plan["source"] == "MANUAL"
    assert admin_api.post(f"/purchase-plans/{pid}/decide", {"approve_all": True}).status_code == 403
    item = plan["items"][0]
    r = admin_api.patch(f"/purchase-plans/{pid}/items/{item['id']}", {"final_qty": 5}).json()
    assert r["total_estimated"] == 5 * 210
    assert admin_api.post(f"/purchase-plans/{pid}/submit").json()["status"] == "SUBMITTED"
    r = api.post(f"/purchase-plans/{pid}/decide", {"approve_all": True}).json()
    assert r["status"] == "DECIDED" and r["total_approved"] == 1050
    r = api.post(f"/purchase-plans/{pid}/receive", {"items": [{"item_id": item["id"], "quantity": 5}]}).json()
    assert r["status"] == "RECEIVED"
    assert api.get(f"/designs/{d['id']}").json()["current_stock"] == 6


def test_reset_owner_only(api, admin_api):
    api.category("Rings", label_prefix="RG", icon="ring")
    assert admin_api.post("/admin/reset", {"confirm": "RESET"}).status_code == 403
    assert api.post("/admin/reset", {"confirm": "nope"}).status_code == 422
    assert api.post("/admin/reset", {"confirm": "RESET"}).status_code == 200
    assert api.get("/categories").json() == []
