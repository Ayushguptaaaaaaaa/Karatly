def test_category_crud_and_prefix(api):
    assert api.get("/categories/suggest-prefix?name=Earrings").json()["prefix"] == "EA"
    c = api.category("Earrings", label_prefix="ER", subcategories=["Studs", "Jhumkas"])
    assert c["label_prefix"] == "ER" and len(c["subcategories"]) == 2
    r = api.post("/categories", {"name": "earrings", "icon": "earring"})
    assert r.status_code == 409
    r = api.post("/categories", {"name": "Ear cuffs", "label_prefix": "ER", "icon": "earring"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "PREFIX_TAKEN"


def test_bulk_designs_and_labels(api):
    c = api.category("Earrings", label_prefix="ER")
    labels = api.get(f"/designs/next-labels?category_id={c['id']}&count=3").json()["labels"]
    assert labels == ["ER-1001", "ER-1002", "ER-1003"]
    rows = [{"label": l, "cost_price": 100, "selling_price": 130, "opening_stock": 5} for l in labels]
    created = api.designs(c["id"], rows)
    assert len(created) == 3 and created[0]["current_stock"] == 5 and created[0]["status"] == "IN"
    assert api.get(f"/designs/next-labels?category_id={c['id']}&count=1").json()["labels"] == ["ER-1004"]
    # duplicate inside batch + taken label
    r = api.post("/designs/bulk", {"category_id": c["id"], "designs": [
        {"label": "ER-2000", "cost_price": 1, "selling_price": 2},
        {"label": "er-2000", "cost_price": 1, "selling_price": 2},
        {"label": "ER-1001", "cost_price": 1, "selling_price": 2}]})
    assert r.status_code == 422
    rows_err = r.json()["error"]["details"]["rows"]
    assert {e["index"] for e in rows_err} == {1, 2}
    assert api.get("/designs/check-label?label=ER-1001").json()["available"] is False
    # delete category with designs blocked
    assert api.delete(f"/categories/{c['id']}").status_code == 409


def test_archive_and_search(api):
    c = api.category("Rings", label_prefix="RG", icon="ring")
    d = api.designs(c["id"], [{"label": "RG-1", "name": "Solitaire", "cost_price": 10, "selling_price": 12}])[0]
    assert api.get("/designs/search?q=solit").json()[0]["label"] == "RG-1"
    assert api.post(f"/designs/{d['id']}/archive").json()["is_active"] is False
    assert api.get("/designs").json()["total"] == 0
    # design with only opening can be deleted
    assert api.delete(f"/designs/{d['id']}").status_code == 204
