import io

from openpyxl import Workbook

HEAD = ["category", "subcategory", "label", "name", "metal", "purity", "weight_g", "cost_price", "selling_price",
        "min_stock", "opening_stock", "dealer", "dealer_city", "dealer_state"]


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Designs"
    ws.append(HEAD)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _import(api, content, dry_run):
    return api.c.post(f"/api/v1/designs/import?dry_run={str(dry_run).lower()}", headers=api.h,
                      files={"file": ("shop.xlsx", content,
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def test_big_import_creates_dealers_and_links_stock(api):
    rows = [["Earrings", "Jhumka", f"IER-{1000 + i}", f"Kundan jhumka {i}", "IMITATION", None, None, 600, 1500, 3, 5 + i % 4,
             "Jaipur Kundan Works" if i % 2 else "Mumbai Fashion Mart", "Jaipur" if i % 2 else "Mumbai",
             "Rajasthan" if i % 2 else "Maharashtra"] for i in range(150)]          # > 100 in one subcategory
    rows.append(["Rings", "Silver rings", "PRG-2001", "Solitaire ring", "SILVER", "925", 3.2, 1800, 3499, 2, 4,
                 None, None, None])
    content = _xlsx(rows)
    dry = _import(api, content, True).json()
    assert dry["errors"] == [] and dry["will_create"]["designs"] == 151 and dry["will_create"]["dealers"] == 2
    res = _import(api, content, False).json()
    assert res["imported"] is True, res
    dealers = {d["name"]: d for d in api.get("/dealers").json()}
    assert dealers["Jaipur Kundan Works"]["city"] == "Jaipur" and dealers["Jaipur Kundan Works"]["designs"] == 75
    # stock view shows the dealer of every design
    stock = api.get("/periods/stock", params={"page_size": 500}).json()
    by_label = {r["design"]["label"]: r for r in stock["rows"]["items"]}
    assert by_label["IER-1001"]["dealer"] == "Jaipur Kundan Works" and by_label["PRG-2001"]["dealer"] is None
    # filter the stock view by dealer
    only = api.get("/periods/stock", params={"dealer_id": dealers["Mumbai Fashion Mart"]["id"], "page_size": 500}).json()
    assert only["rows"]["total"] == 75


def test_stock_shows_who_bought_each_design(api):
    rows = [["Necklaces", "Chokers", "INK-1", "Polki choker", "IMITATION", None, None, 4000, 9000, 2, 10,
             "Delhi Polki Studio", "Delhi", "Delhi"]]
    _import(api, _xlsx(rows), False)
    d = api.get("/designs", params={"search": "INK-1"}).json()
    did = (d["items"] if isinstance(d, dict) else d)[0]["id"]
    for name, qty in (("Riya Kapoor", 2), ("Arjun Mehta", 1), ("Riya Kapoor", 1)):
        assert api.post("/bills", {"customer": {"name": name, "city": "Pune"} if name == "Arjun Mehta" else None,
                                   "customer_id": None if name == "Arjun Mehta" else _cust(api, name),
                                   "items": [{"design_id": did, "quantity": qty}]}).status_code == 201
    stock = api.get("/periods/stock").json()
    row = next(r for r in stock["rows"]["items"] if r["design"]["label"] == "INK-1")
    assert row["dealer"] == "Delhi Polki Studio" and row["customers"] == 2 and row["top_customer"] == "Riya Kapoor"
    assert stock["top_customer"]["name"] == "Riya Kapoor"
    parties = api.get(f"/designs/{did}/parties").json()
    assert parties["dealers"][0]["name"] == "Delhi Polki Studio" and parties["dealers"][0]["pieces"] == 10
    assert [c["name"] for c in parties["customers"]] == ["Riya Kapoor", "Arjun Mehta"]
    # stock history can be filtered by customer
    riya = _cust(api, "Riya Kapoor")
    hist = api.get("/stock/movements", params={"customer_id": riya}).json()
    assert hist["total"] == 2 and hist["items"][0]["bill"]["customer_name"] == "Riya Kapoor"


def _cust(api, name):
    found = [c for c in api.get("/customers").json() if c["name"] == name]
    if found:
        return found[0]["id"]
    return api.post("/customers", {"name": name}).json()["id"]


def test_sorting_stock_period_and_history(api):
    rows = [["Rings", "Cocktail", f"IRG-{i}", f"Ring {i}", "IMITATION", None, None, 500, 1000 + i * 100, 1, 10,
             "Mumbai AD Jewels", "Mumbai", "Maharashtra"] for i in range(1, 5)]
    _import(api, _xlsx(rows), False)
    ids = {r["design"]["label"]: r["design"]["id"] for r in api.get("/periods/stock").json()["rows"]["items"]}
    for label, qty in (("IRG-1", 1), ("IRG-2", 5), ("IRG-3", 3)):   # IRG-4 sells nothing
        api.post("/bills", {"items": [{"design_id": ids[label], "quantity": qty}]})
    most = [r["design"]["label"] for r in api.get("/periods/stock", params={"sort": "-sold"}).json()["rows"]["items"]]
    least = [r["design"]["label"] for r in api.get("/periods/stock", params={"sort": "sold"}).json()["rows"]["items"]]
    assert most[:3] == ["IRG-2", "IRG-3", "IRG-1"] and least[0] == "IRG-4"
    profit = api.get("/periods/stock", params={"sort": "-net_profit"}).json()["rows"]["items"]
    assert profit[0]["design"]["label"] == "IRG-2"
    hist = api.get("/stock/movements", params={"sort_by": "value", "sort_dir": "desc", "type": "SALE"}).json()["items"]
    assert [h["design"]["label"] for h in hist] == ["IRG-2", "IRG-3", "IRG-1"]
    by_qty = api.get("/stock/movements", params={"sort_by": "quantity", "sort_dir": "asc", "type": "SALE"}).json()["items"]
    assert by_qty[0]["quantity"] == 1
