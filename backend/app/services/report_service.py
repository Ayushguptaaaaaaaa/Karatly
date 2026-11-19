from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Category
from app.models.enums import StockStatus
from app.services import costing_service, metrics_service, period_service
from app.services.import_export_service import build_xlsx
from app.services.serializers import photo_url

PALETTE_KEYS = ["gold", "teal", "blue", "grape", "orange", "cyan", "pink", "lime", "indigo", "red"]


def sales_trend(db: Session, months: int = 12, category_id: int | None = None, group_by: str = "total") -> dict:
    months = max(1, min(months, 36))
    by_cat = group_by == "category"
    starts, data = metrics_service.monthly_sales(db, months, category_id, by_category=by_cat)
    if not by_cat:
        return {"series": [{"key": "total", "name": "All sales", "points": metrics_service.series_points(starts, data.get("total", {}))}]}
    cats = db.query(Category).order_by(Category.sort_order).all()
    series = []
    for c in cats:
        if category_id and c.id != category_id:
            continue
        series.append({"key": str(c.id), "name": c.name, "color_key": PALETTE_KEYS[(c.id - 1) % len(PALETTE_KEYS)],
                       "points": metrics_service.series_points(starts, data.get(c.id, {}))})
    return {"series": series}


def category_breakdown(db: Session, p: period_service.Period) -> list[dict]:
    snap = metrics_service.snapshot(db)
    sales = metrics_service.sales_by_design(db, p.start, p.effective_end)
    total = float(sum((v for _, v in sales.values()), Decimal("0"))) or 0
    out = []
    for c in db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order):
        mine = [d for d in snap.designs.values() if d.category_id == c.id and d.is_active]
        sv = sum(float(sales.get(d.id, (0, 0))[1]) for d in mine)
        out.append({"category_id": c.id, "name": c.name, "icon": c.icon,
                    "color_key": PALETTE_KEYS[(c.id - 1) % len(PALETTE_KEYS)],
                    "design_count": len(mine),
                    "pieces": sum(snap.states[d.id].current_stock for d in mine),
                    "stock_value_cost": float(sum((snap.states[d.id].stock_value_cost for d in mine), Decimal("0"))),
                    "sold_units": sum(sales.get(d.id, (0, 0))[0] for d in mine),
                    "sales_value": round(sv, 2), "share_pct": round(sv / total * 100, 1) if total else 0.0,
                    "out_of_stock": sum(1 for d in mine if snap.states[d.id].status == StockStatus.OUT),
                    "low_stock": sum(1 for d in mine if snap.states[d.id].status == StockStatus.LOW)})
    return out


def top_sellers(db: Session, p: period_service.Period, limit: int = 10, order: str = "desc") -> list[dict]:
    snap = metrics_service.snapshot(db)
    sales = metrics_service.sales_by_design(db, p.start, p.effective_end)
    rows = []
    for d in snap.designs.values():
        if not d.is_active:
            continue
        q, v = sales.get(d.id, (0, Decimal("0")))
        st = snap.states[d.id]
        if order == "asc" and (st.first_movement_on is None or st.current_stock == 0):
            continue
        rows.append({"design": {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d),
                                "category_name": d.category.name},
                     "sold_units": q, "sales_value": float(v), "current_stock": st.current_stock,
                     "demand_class": st.demand.value})
    rows.sort(key=lambda r: (r["sold_units"], r["sales_value"]), reverse=(order != "asc"))
    if order != "asc":
        rows = [r for r in rows if r["sold_units"] > 0]
    return rows[: max(1, min(limit, 50))]


def period_comparison(db: Session, a: period_service.Period, b: period_service.Period, group_by: str = "category"):
    snap = metrics_service.snapshot(db)
    sa = metrics_service.sales_by_design(db, a.start, a.effective_end)
    sb = metrics_service.sales_by_design(db, b.start, b.effective_end)
    groups: dict = {}
    for d in snap.designs.values():
        if group_by == "design":
            key, name = str(d.id), d.label
        else:
            key, name = str(d.category_id), d.category.name
        g = groups.setdefault(key, {"key": key, "name": name, "a_units": 0, "b_units": 0, "a_value": 0.0,
                                    "b_value": 0.0})
        qa, va = sa.get(d.id, (0, 0))
        qb, vb = sb.get(d.id, (0, 0))
        g["a_units"] += qa
        g["b_units"] += qb
        g["a_value"] += float(va)
        g["b_value"] += float(vb)
    rows = []
    for g in groups.values():
        if group_by == "design" and not (g["a_units"] or g["b_units"]):
            continue
        g["a_value"], g["b_value"] = round(g["a_value"], 2), round(g["b_value"], 2)
        g["change_pct"] = round((g["a_value"] - g["b_value"]) / g["b_value"] * 100, 1) if g["b_value"] else None
        rows.append(g)
    rows.sort(key=lambda r: -(r["a_value"] + r["b_value"]))
    return {"a": {"label": a.label, "start": a.start, "end": a.end},
            "b": {"label": b.label, "start": b.start, "end": b.end}, "rows": rows[:50]}


def dead_stock(db: Session) -> dict:
    snap = metrics_service.snapshot(db)
    items = []
    for d in snap.designs.values():
        st = snap.states[d.id]
        if d.is_active and st.status == StockStatus.DEAD:
            items.append({"design": {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d),
                                     "category_name": d.category.name},
                          "current_stock": st.current_stock, "days_since_last_sale": st.days_since_last_sale,
                          "last_sale_on": st.last_sale_on, "value_tied_up": float(st.stock_value_cost)})
    items.sort(key=lambda r: -r["value_tied_up"])
    return {"total_value": round(sum(i["value_tied_up"] for i in items), 2), "dead_stock_days": snap.dead_days,
            "items": items}


def stock_turnover(db: Session, p: period_service.Period) -> list[dict]:
    snap = metrics_service.snapshot(db)
    rows_map = period_service.period_rows(db, p)
    out = []
    for c in db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order):
        ids = [d.id for d in snap.designs.values() if d.category_id == c.id]
        opening = sum(rows_map[i]["opening"] for i in ids if i in rows_map)
        closing = sum(rows_map[i]["closing"] for i in ids if i in rows_map)
        sold = sum(rows_map[i]["sold"] for i in ids if i in rows_map)
        avg = (opening + closing) / 2
        out.append({"category_id": c.id, "category": c.name, "opening": opening, "closing": closing, "sold": sold,
                    "turnover": round(sold / avg, 2) if avg else 0.0})
    return out


def export(db: Session, report: str, p: period_service.Period, **kw) -> tuple[str, bytes]:
    if report == "period_stock":
        from app.api.routes.periods import period_stock

        data = period_stock(db, p, kw.get("category_id"), None, kw.get("status"), None, "label", 1, 100000)
        heads = ["Label", "Name", "Category", "Subcategory", "Opening", "Added (new designs)", "Received", "Sold",
                 "Customer returns", "Supplier returns", "Corrections", "Closing", "Sales value", "Net revenue",
                 "Net profit", "Margin %", "Status now"]
        rows = [[r["design"]["label"], r["design"]["name"], r["design"]["category_name"], r["design"]["subcategory_name"],
                 r["opening"], r["opening_added"], r["received"], r["sold"], r["customer_returns"],
                 r["supplier_returns"], r["adjustments_net"], r["closing"], r["sales_value"], r["net_revenue"],
                 r["net_profit"], r["margin_pct"], r["status_now"]]
                for r in data["rows"]["items"]]
        return f"stock_{p.short_label}.xlsx", build_xlsx("Stock", heads, rows, {12, 13, 14})
    if report == "profitability":
        from app.services import profit_service

        gb = kw.get("group_by") or "category"
        data = profit_service.profitability(db, p, gb, kw.get("category_id"))
        first = {"design": ["Label", "Name", "Category", "Subcategory"], "subcategory": ["Subcategory", "Category"],
                 "category": ["Category"]}[gb]
        heads = first + ["Pieces sold", "Returned", "Net pieces", "Gross sales", "Returns", "Net revenue",
                         "Cost of goods", "Net profit", "Margin %"]

        def lead(r):
            if gb == "design":
                return [r["label"], r["design_name"], r["category"], r["subcategory"]]
            if gb == "subcategory":
                return [r["name"], r["category"]]
            return [r["name"]]

        rows = [lead(r) + [r["units_sold"], r["units_returned"], r["net_units"], r["gross_sales"], r["returns_value"],
                           r["net_revenue"], r["cogs"], r["net_profit"], r["margin_pct"]] for r in data["rows"]]
        t = data["totals"]
        rows.append(["TOTAL"] + [""] * (len(first) - 1) + [t["units_sold"], t["units_returned"], t["net_units"],
                                                            t["gross_sales"], t["returns_value"], t["net_revenue"],
                                                            t["cogs"], t["net_profit"], t["margin_pct"]])
        n = len(first)
        return f"profit_by_{gb}_{p.short_label}.xlsx", build_xlsx("Profitability", heads, rows, set(range(n + 3, n + 8)))
    if report == "sales_trend":
        data = sales_trend(db, 12, group_by="category")
        months = [pt["month"] for pt in data["series"][0]["points"]] if data["series"] else []
        heads = ["Category"] + months
        rows = [[s["name"]] + [pt["value"] for pt in s["points"]] for s in data["series"]]
        return "sales_trend.xlsx", build_xlsx("Sales trend", heads, rows, set(range(1, len(heads))))
    if report == "top_sellers":
        data = top_sellers(db, p, 50, kw.get("order") or "desc")
        heads = ["Label", "Name", "Category", "Sold", "Sales value", "Stock now", "Demand"]
        rows = [[r["design"]["label"], r["design"]["name"], r["design"]["category_name"], r["sold_units"],
                 r["sales_value"], r["current_stock"], r["demand_class"]] for r in data]
        return f"top_sellers_{p.short_label}.xlsx", build_xlsx("Top sellers", heads, rows, {4})
    if report == "dead_stock":
        data = dead_stock(db)
        heads = ["Label", "Name", "Category", "Stock", "Days since last sale", "Last sale", "Value tied up"]
        rows = [[r["design"]["label"], r["design"]["name"], r["design"]["category_name"], r["current_stock"],
                 r["days_since_last_sale"], str(r["last_sale_on"] or ""), r["value_tied_up"]] for r in data["items"]]
        return "dead_stock.xlsx", build_xlsx("Dead stock", heads, rows, {6})
    from app.core.errors import AppError

    raise AppError("UNKNOWN_REPORT", "Unknown report", 422)


def format_money(v) -> str:
    return costing_service.format_inr(v)
