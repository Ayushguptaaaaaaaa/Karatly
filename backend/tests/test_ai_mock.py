import time


def _wait(api, job_id, timeout=60):
    for _ in range(timeout * 4):
        j = api.get(f"/jobs/{job_id}").json()
        if j["status"] in ("SUCCEEDED", "FAILED"):
            return j
        time.sleep(0.25)
    raise AssertionError("job did not finish")


def test_demo_data_insights_and_chat(api):
    r = api.post("/insights/runs", {})
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_DATA"
    demo = api.post("/admin/demo-data", {}).json()
    assert demo["designs"] == 120
    assert api.post("/admin/demo-data", {}).status_code == 409
    ov = api.get("/dashboard/overview").json()
    assert ov["kpis"]["out_of_stock"] >= 6 and ov["kpis"]["low_stock"] >= 8 and ov["kpis"]["dead_stock"] >= 10
    rules = {c["rule"] for c in __import__("app.services.anomaly_service", fromlist=["x"]).candidates(
        __import__("app.core.database", fromlist=["x"]).SessionLocal())}
    assert {"BIG_SALE", "COST_JUMP", "PRICE_BELOW_COST"} <= rules

    run = api.post("/insights/runs", {}).json()
    job = _wait(api, run["job_id"])
    assert job["status"] == "SUCCEEDED"
    assert [s["status"] for s in job["steps"]] == ["DONE"] * 7
    latest = api.get("/insights/latest").json()
    assert latest["status"] == "PARTIAL" and latest["report"]["headline"]
    plan = api.get(f"/purchase-plans/{latest['purchase_plan']['id']}").json()
    assert plan["source"] == "AI" and plan["items"]
    assert abs(sum(i["line_total"] for i in plan["items"]) - plan["total_estimated"]) < 0.05
    assert latest["is_stale"] is False

    s = api.post("/chat/sessions", {}).json()
    m = api.post(f"/chat/sessions/{s['id']}/messages", {"text": "Which designs are sold out?"}).json()
    assert _wait(api, m["job_id"])["status"] == "SUCCEEDED"
    msgs = api.get(f"/chat/sessions/{s['id']}").json()["messages"]
    assert msgs[-1]["status"] == "COMPLETE" and msgs[-1]["payload"]["table"]
    assert api.get("/chat/suggestions").json()["questions"]
