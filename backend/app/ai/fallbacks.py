"""Deterministic (no-LLM) outputs for every AI step, built from the analysis pack."""
from __future__ import annotations

from app.ai import outputs as o
from app.services.costing_service import format_inr_compact


def _rows(pack, **filt):
    out = []
    for r in pack["designs_of_interest"]:
        if all(r.get(k) == v for k, v in filt.items()):
            out.append(r)
    return out


def stock_position(pack: dict) -> o.StockPositionOutput:
    k = pack["kpis"]
    outs = _rows(pack, status="OUT")[:15]
    lows = _rows(pack, status="LOW")[:15]
    dead = _rows(pack, status="DEAD")[:15]
    summary = (f"{k['total_designs']} designs with {k['total_pieces']} pieces in stock "
               f"(worth {format_inr_compact(k['stock_value_cost'])} at cost). "
               f"{k['out_of_stock']} sold out, {k['low_stock']} running low and {k['dead_stock']} not selling "
               f"({format_inr_compact(k['dead_stock_value'])} tied up).")
    notes = []
    for c in pack["categories"]:
        n_out = sum(1 for r in outs if r["category"] == c["name"])
        if n_out:
            notes.append(o.CategoryNote(category=c["name"], note=f"{n_out} design(s) sold out"))
    return o.StockPositionOutput(
        summary=summary,
        out_of_stock=[o.LabelNote(label=r["label"], category=r["category"], stock=r["stock"],
                                  note=f"Sold {r['sold_30d']} in last 30 days") for r in outs],
        low_stock=[o.LabelNote(label=r["label"], category=r["category"], stock=r["stock"],
                               note=f"{r['stock']} left (min {r['min_stock']})") for r in lows],
        dead_stock=[o.LabelNote(label=r["label"], category=r["category"], stock=r["stock"],
                                note=f"No sale for {r['days_since_last_sale']} days · {format_inr_compact(r['value_tied_up'])} tied up")
                    for r in dead],
        category_notes=notes[:6],
    )


def demand(pack: dict) -> o.DemandOutput:
    rows = pack["designs_of_interest"]
    high = sorted([r for r in rows if r["demand"] == "HIGH"], key=lambda r: -r["velocity_30d"])[:10]
    low = sorted([r for r in rows if r["demand"] in ("LOW", "DEAD")], key=lambda r: r["velocity_30d"])[:10]
    dc = pack["demand_counts"]
    trends = []
    for c in pack["categories"]:
        if c["change_pct"] is not None and abs(c["change_pct"]) >= 15:
            trends.append(f"{c['name']}: {c['sold_period']} sold vs {c['sold_prev_period']} in {pack['period']['previous_label']} ({c['change_pct']:+.0f}%).")
    return o.DemandOutput(
        summary=f"{dc.get('HIGH', 0)} designs in high demand, {dc.get('STEADY', 0)} steady, "
                f"{dc.get('LOW', 0)} slow and {dc.get('DEAD', 0)} not selling.",
        high_demand=[o.DemandNote(label=r["label"], category=r["category"], sold_period=r["sold_period"],
                                  velocity_30d=r["velocity_30d"],
                                  reason=f"Sold {r['sold_period']} this period, pace {r['velocity_30d']:.1f}/month")
                     for r in high],
        low_demand=[o.DemandNote(label=r["label"], category=r["category"], sold_period=r["sold_period"],
                                 velocity_30d=r["velocity_30d"],
                                 reason=(f"No sale for {r['days_since_last_sale']} days" if r["demand"] == "DEAD"
                                         else f"Only {r['sold_period']} sold this period"))
                    for r in low],
        seasonal_notes=[pack.get("upcoming_season", "")] if pack.get("upcoming_season") else [],
        trend_notes=trends[:4],
    )


def anomalies(pack: dict) -> o.AnomalyOutput:
    items = [o.AnomalyItem(label=c.get("label"), severity=c["severity"], issue=c["message"],
                           evidence=", ".join(f"{k}: {v}" for k, v in (c.get("evidence") or {}).items()),
                           suggested_check={"BIG_SALE": "Confirm the bill and quantity.",
                                            "COST_JUMP": "Check the supplier invoice and the cost typed.",
                                            "PRICE_BELOW_COST": "Review the selling price.",
                                            "FREQUENT_UNDO": "Check entries for this design with staff.",
                                            "SALE_AND_RETURN_SAME_DAY": "Confirm whether this was an exchange.",
                                            "BACKDATED_ENTRIES": "Make sure old entries were intended.",
                                            "ZERO_MIN_STOCK": "Set a minimum stock so you get alerts."}.get(c["rule"], "Review the entry."))
             for c in pack["anomaly_candidates"][:10]]
    return o.AnomalyOutput(summary=(f"{len(items)} entr{'ies' if len(items) != 1 else 'y'} worth a quick check."
                                    if items else "No unusual entries found."), items=items)


def reorder(pack: dict) -> o.ReorderOutput:
    items = [o.ReorderLine(label=r["label"], suggested_qty=r["suggested_qty"], priority=r["priority"],
                           reason=r["reason"]) for r in pack["reorder_baseline"]]
    return o.ReorderOutput(summary=f"{len(items)} designs need restocking (rule-based suggestion).", items=items)


def budget(pack: dict) -> o.BudgetOutput:
    lines = [o.BudgetLine(label=r["label"], quantity=r["suggested_qty"], expected_unit_cost=r["expected_unit_cost"],
                          line_total=r["line_total"]) for r in pack["reorder_baseline"]]
    by_cat: dict[str, float] = {}
    for r in pack["reorder_baseline"]:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["line_total"]
    return o.BudgetOutput(items=lines, total_budget=round(sum(x.line_total for x in lines), 2),
                          by_category=[o.CategoryAmount(category=k, amount=round(v, 2)) for k, v in by_cat.items()],
                          notes=f"Cost = last purchase price + {pack['settings']['inflation_pct_global']}% inflation.")


def report(pack: dict, plan_total: float | None = None) -> o.InsightsReport:
    k = pack["kpis"]
    total = plan_total if plan_total is not None else pack["reorder_total"]
    change = k.get("sales_change_pct")
    change_txt = f" ({change:+.0f}% vs last period)" if change is not None else ""
    headline = (f"Sales {format_inr_compact(k['sales_value'])} in {pack['period']['label']}{change_txt}; "
                f"{k['out_of_stock']} designs sold out")[:120]
    high = [r["label"] for r in pack["designs_of_interest"] if r["demand"] == "HIGH"][:3]
    dead_n = k["dead_stock"]
    conclusion = (
        f"You sold {k['sales_units']} pieces worth {format_inr_compact(k['sales_value'])} in {pack['period']['label']}. "
        f"{k['out_of_stock']} designs are sold out and {k['low_stock']} are running low; restocking them needs about "
        f"{format_inr_compact(total)}. "
        + (f"Best sellers include {', '.join(high)}. " if high else "")
        + (f"{dead_n} designs have not sold for a long time, holding {format_inr_compact(k['dead_stock_value'])}. "
           if dead_n else "")
        + "Review the purchase plan and decide what to buy."
    )
    actions = []
    if k["out_of_stock"]:
        actions.append(o.Action(title="Restock sold-out best sellers", why=f"{k['out_of_stock']} designs are at zero.",
                                priority="HIGH", target="PURCHASE_PLAN"))
    if k["low_stock"]:
        actions.append(o.Action(title="Check low-stock designs", why=f"{k['low_stock']} designs are at or below minimum.",
                                priority="MEDIUM", target="LOW_STOCK"))
    if dead_n:
        actions.append(o.Action(title="Act on slow stock", why=f"{format_inr_compact(k['dead_stock_value'])} is tied up.",
                                priority="MEDIUM", target="DEAD_STOCK"))
    if pack["anomaly_candidates"]:
        actions.append(o.Action(title="Double-check unusual entries", why="Some entries look unusual.",
                                priority="LOW", target="ANOMALIES"))
    if not actions:
        actions.append(o.Action(title="Keep recording sales", why="More data gives sharper insights.",
                                priority="LOW", target="INVENTORY"))
    return o.InsightsReport(
        headline=headline,
        conclusion=conclusion,
        confidence="LOW",
        confidence_reason="Generated automatically (AI unavailable). Numbers are exact; explanations are simple.",
        key_numbers=[o.KeyNumber(label="Sales", value=format_inr_compact(k["sales_value"])),
                     o.KeyNumber(label="Pieces sold", value=str(k["sales_units"])),
                     o.KeyNumber(label="Stock value", value=format_inr_compact(k["stock_value_cost"])),
                     o.KeyNumber(label="Restock budget", value=format_inr_compact(total)),
                     o.KeyNumber(label="Sold out", value=str(k["out_of_stock"]))],
        recommended_actions=actions,
        whats_selling=f"High-demand designs: {', '.join(high)}." if high else "No clear best sellers yet.",
        whats_not_selling=(f"{dead_n} designs with no sale for {pack['settings']['dead_stock_days']}+ days."
                           if dead_n else "No dead stock right now."),
        money_view=(f"Stock worth {format_inr_compact(k['stock_value_cost'])} at cost. "
                    f"Suggested restock budget {format_inr_compact(total)}."),
        risks=f"{k['out_of_stock']} sold out and {k['low_stock']} low-stock designs may cost sales.",
        data_quality_notes=(["Limited sales history: insights will improve as you record more sales."]
                            if pack["data_sufficiency"]["level"] != "GOOD" else []),
    )


def chat_answer(snapshot: dict, question: str) -> o.ChatAnswer:
    k = snapshot.get("kpis", {})
    rows = [["Stock value (cost)", format_inr_compact(k.get("stock_value_cost", 0))],
            ["Pieces in stock", str(k.get("total_pieces", 0))],
            ["Sales this month", format_inr_compact(k.get("sales_value", 0))],
            ["Sold out", str(k.get("out_of_stock", 0))],
            ["Low stock", str(k.get("low_stock", 0))]]
    return o.ChatAnswer(
        answer_markdown=("The AI assistant is unavailable right now (free AI quota reached or AI switched off). "
                         "Here are your latest numbers. Try again in a little while for a full answer."),
        table=o.ChatTable(columns=["Metric", "Value"], rows=rows),
        follow_up_questions=[],
    )
