"""Instant chat answers (no LLM) for common questions, built from the exact shop snapshot.

Used first for clear, common questions (so the chat feels instant) and as the fallback whenever
the AI model is busy or over quota. Questions that need reasoning ("why…", "should I…") or a
specific label go to the AI.
"""
from __future__ import annotations

import re

from app.ai.outputs import ChatAnswer, ChatChart, ChartPoint, ChatTable
from app.services.costing_service import format_inr_compact as inr

LABEL_RE = re.compile(r"\b[A-Za-z]{1,5}-\d{2,}\b")
FILTER_RE = re.compile(r"\b(in|from|for|during)\s+(?!this\b|the\b|my\b|me\b|total\b)[a-z]")
REASONING = ("why", "should i", "should we", "how can", "how do i improve", "advise", "suggest", "recommend", "kyun", "kya karu")


def _has(q: str, *words: str) -> bool:
    return any(w in q for w in words)


def _profit_table(rows: list[dict], first: str) -> ChatTable:
    return ChatTable(columns=[first, "Net revenue (₹)", "Net profit (₹)", "Margin %"],
                     rows=[[r["name"], round(r["net_revenue"]), round(r["net_profit"]),
                            r["margin_pct"] if r["margin_pct"] is not None else "—"] for r in rows[:12]])


def _bar(title: str, rows: list[dict], key: str) -> ChatChart | None:
    pts = [ChartPoint(label=str(r["name"]), value=float(r[key])) for r in rows[:10] if r.get(key)]
    return ChatChart(type="bar", title=title, data=pts, value_format="inr") if len(pts) >= 2 else None


def answer(question: str, snap: dict, strict: bool = True) -> ChatAnswer | None:
    """Return an instant answer, or None if the question needs the AI.
    strict=True: only clear, common questions (used before calling the AI)."""
    q = " " + question.lower().strip() + " "
    common = _has(q, "restock", "reorder", "re-order", "budget", "how much money", "sold out", "net profit")
    if strict and (LABEL_RE.search(question) or " why " in q or (_has(q, *REASONING) and not common)):
        return None
    month = snap["this_month"]
    k = month["kpis"]
    period = month["period"]
    today = snap["today"]

    # --- profit -------------------------------------------------------------------------
    if _has(q, "profit", "margin", "munafa", "earn"):
        if _has(q, "today", "aaj"):
            t = today["totals"]
            rows = today["designs_sold_today"]
            text = (f"**Today ({today['date']}):** net revenue **{inr(t['net_revenue'])}**, net profit "
                    f"**{inr(t['net_profit'])}**" + (f" ({t['margin_pct']}% margin)" if t["margin_pct"] is not None else "")
                    + f" from {t['net_units']} net pieces." + ("" if rows else " No sales recorded yet today."))
            return ChatAnswer(answer_markdown=text, table=_profit_table(rows, "Design") if rows else None,
                              follow_up_questions=["What was my net profit this month, by category?",
                                                   "Which designs are sold out?"])
        if _has(q, "subcategor", "sub-categor", "sub categor"):
            rows = month["profit_by_subcategory"]
            return ChatAnswer(answer_markdown=f"**Net profit by subcategory, {period}:** total **{inr(k['net_profit'])}** "
                                              f"on net revenue {inr(k['net_revenue'])}.",
                              table=ChatTable(columns=["Subcategory", "Category", "Net revenue (₹)", "Net profit (₹)", "Margin %"],
                                              rows=[[r["name"], r.get("category", ""), round(r["net_revenue"]),
                                                     round(r["net_profit"]), r["margin_pct"] if r["margin_pct"] is not None else "—"]
                                                    for r in rows[:12]]),
                              chart=_bar("Net profit by subcategory", rows, "net_profit"),
                              follow_up_questions=["Which designs made the most profit this month?"])
        if _has(q, "design", "product", "item", "label", "piece"):
            rows = month["top_designs_by_profit"]
            return ChatAnswer(answer_markdown=f"**Most profitable designs, {period}:**" if rows else f"No sales yet in {period}.",
                              table=_profit_table(rows, "Design") if rows else None,
                              chart=_bar("Net profit by design", rows, "net_profit"),
                              follow_up_questions=["What was my net profit this month, by category?"])
        rows = month["profit_by_category"]
        text = (f"**{period}:** net revenue **{inr(k['net_revenue'])}**, cost of goods {inr(k['cogs'])}, "
                f"net profit **{inr(k['net_profit'])}**"
                + (f" (**{k['profit_margin_pct']}%** margin)" if k.get("profit_margin_pct") is not None else "") + ".")
        if rows:
            best = rows[0]
            text += f" {best['name']} made the most profit ({inr(best['net_profit'])})."
        return ChatAnswer(answer_markdown=text, table=_profit_table(rows, "Category") if rows else None,
                          chart=_bar("Net profit by category", rows, "net_profit"),
                          follow_up_questions=["Show net profit by subcategory", "Which designs made the most profit this month?"])

    # --- customers / regions / dealers (this month) ----------------------------------------
    who = snap.get("customers_regions_dealers_this_month") or {}
    # "top customer in India in November" has a filter -> AI + breakdown tool; "this month" is fine here
    filtered = bool(FILTER_RE.search(q))
    about_who = _has(q, "dealer", "supplier", "vendor", "karigar", "customer", "client", "grahak", "buyer", "who bought",
                     "country", "countries", "state", "city", "cities", "region")
    if strict and filtered and about_who:
        return None
    if _has(q, "dealer", "supplier", "vendor", "karigar") and not (strict and filtered):
        rows = who.get("top_dealers") or []
        if not rows:
            return ChatAnswer(answer_markdown=f"No purchases from dealers recorded in {period} yet.")
        top = rows[0]
        return ChatAnswer(
            answer_markdown=f"**Dealers, {period}:** most bought from **{top['name']}**: {top['pieces']} pieces for "
                            f"**{inr(top['amount'])}** ({top['share_pct']}% of purchases).",
            table=ChatTable(columns=["Dealer", "Pieces", "Amount (₹)", "Designs"],
                            rows=[[r["name"], r["pieces"], round(r["amount"]), r["designs"]] for r in rows]),
            chart=_bar("Purchases by dealer", [{"name": r["name"], "v": r["amount"]} for r in rows], "v"),
            follow_up_questions=["Who is my top customer this month?", "Which city buys the most?"])
    if _has(q, "customer", "client", "grahak", "buyer", "who buys", "who bought") and not (strict and filtered):
        rows = who.get("top_customers") or []
        if not rows:
            return ChatAnswer(answer_markdown=f"No named customers on bills in {period} yet. Add the customer when billing.")
        top = rows[0]
        walk = (who.get("customers") or {}).get("walk_in_share_pct", 0)
        return ChatAnswer(
            answer_markdown=f"**Top customer, {period}:** **{top['name']}**: {top['pieces']} pieces, "
                            f"**{inr(top['revenue'])}** ({top['share_pct']}% of sales). Walk-in customers: {walk}% of sales.",
            table=ChatTable(columns=["Customer", "Pieces", "Revenue (₹)", "Bills"],
                            rows=[[r["name"], r["pieces"], round(r["revenue"]), r["bills"]] for r in rows]),
            chart=_bar("Revenue by customer", [{"name": r["name"], "v": r["revenue"]} for r in rows], "v"),
            follow_up_questions=["Which city buys the most?", "Top customer in India this month?"])
    region = next((k for k, words in (("country", ("country", "countries", "desh", "abroad")),
                                      ("state", ("state", "states", "rajya")),
                                      ("city", ("city", "cities", "shehar", "region", "where do", "location")))
                   if _has(q, *words)), None)
    if region and not (strict and filtered):
        rows = who.get({"city": "top_cities", "state": "top_states", "country": "top_countries"}[region]) or []
        if not rows:
            return ChatAnswer(answer_markdown=f"No sales with a customer {region} in {period} yet.")
        top = rows[0]
        return ChatAnswer(
            answer_markdown=f"**Sales by {region}, {period}:** **{top['name']}** leads with **{inr(top['revenue'])}** "
                            f"({top['share_pct']}% of sales, {top['pieces']} pieces).",
            table=ChatTable(columns=[region.title(), "Pieces", "Revenue (₹)", "Share %"],
                            rows=[[r["name"], r["pieces"], round(r["revenue"]), r["share_pct"]] for r in rows]),
            chart=_bar(f"Revenue by {region}", [{"name": r["name"], "v": r["revenue"]} for r in rows], "v"),
            follow_up_questions=["Who is my top customer this month?", "Which dealer did I buy most from?"])

    # --- restock / budget -----------------------------------------------------------------
    if _has(q, "restock", "reorder", "re-order", "purchase", "buy", "budget", "kharid", "order more"):
        r = snap["restock_suggestion"]
        if not r["lines"]:
            return ChatAnswer(answer_markdown="Nothing needs restocking right now: every design is above its minimum stock.")
        return ChatAnswer(
            answer_markdown=(f"You should restock **{len(r['lines'])}+ designs**, an estimated **{inr(r['total_budget'])}** "
                             "(last purchase cost + inflation). Highest priority first. Open *Purchase Plans* to approve them."),
            table=ChatTable(columns=["Design", "Qty", "Priority", "Est. cost (₹)"],
                            rows=[[x["label"], x["qty"], x["priority"].lower(), round(x["line_total"])] for x in r["lines"]]),
            chart=ChatChart(type="pie", title="Budget by category", value_format="inr",
                            data=[ChartPoint(label=c["category"], value=c["amount"]) for c in r["by_category"]])
            if len(r["by_category"]) >= 2 else None,
            follow_up_questions=["Which designs are sold out?", "How much money is stuck in dead stock?"])

    # --- sold out / low ------------------------------------------------------------------------
    alerts = snap["sold_out_and_low"]
    if _has(q, "sold out", "out of stock", "khatam", "zero stock", "finished"):
        rows = [a for a in alerts if a["status"] == "OUT"]
        text = (f"**{k['out_of_stock']} designs are sold out.**" if k["out_of_stock"] else "No design is sold out right now. 🎉")
        return ChatAnswer(answer_markdown=text + (" High-demand ones should be restocked first." if any(a["demand"] == "HIGH" for a in rows) else ""),
                          table=ChatTable(columns=["Design", "Category", "Demand", "Sold (30d)"],
                                          rows=[[a["label"], a["category"], a["demand"].lower(), a["sold_30d"]] for a in rows]) if rows else None,
                          follow_up_questions=["What should I restock this month and how much money do I need?"])
    if _has(q, "low stock", "running low", "low", "kam"):
        rows = [a for a in alerts if a["status"] == "LOW"]
        return ChatAnswer(answer_markdown=f"**{k['low_stock']} designs are running low** (at or below their minimum stock).",
                          table=ChatTable(columns=["Design", "Category", "In stock", "Demand"],
                                          rows=[[a["label"], a["category"], a["stock"], a["demand"].lower()] for a in rows]) if rows else None,
                          follow_up_questions=["What should I restock this month and how much money do I need?"])

    # --- dead stock ------------------------------------------------------------------------------
    if _has(q, "dead", "not selling", "slow", "stuck", "nahi bik"):
        d = snap["dead_stock"]
        if not d["designs"]:
            return ChatAnswer(answer_markdown="No dead stock: every design with stock has sold recently. 🎉")
        return ChatAnswer(answer_markdown=f"**{inr(d['total_value'])}** is tied up in designs with no sale for {d['not_selling_days']}+ days.",
                          table=ChatTable(columns=["Design", "In stock", "Days since sale", "Value (₹)"],
                                          rows=[[x["label"], x["stock"], x["days_since_sale"], round(x["value"])] for x in d["designs"]]),
                          follow_up_questions=["What was my net profit this month, by category?"])

    # --- today's sales ----------------------------------------------------------------------------
    if _has(q, "today", "aaj"):
        t = today["totals"]
        rows = today["designs_sold_today"]
        return ChatAnswer(answer_markdown=(f"**Today ({today['date']}):** {t['units_sold']} pieces sold, gross {inr(t['gross_sales'])}, "
                                           f"net revenue {inr(t['net_revenue'])}, net profit {inr(t['net_profit'])}.")
                          if rows else f"No sales recorded yet today ({today['date']}).",
                          table=_profit_table(rows, "Design") if rows else None,
                          follow_up_questions=["What was my net profit this month, by category?"])

    # --- best sellers / sales -------------------------------------------------------------------
    if _has(q, "top", "best", "selling", "bestseller", "popular"):
        rows = month["top_sellers"]
        return ChatAnswer(answer_markdown=f"**Top sellers, {period}:**" if rows else f"No sales yet in {period}.",
                          table=ChatTable(columns=["Design", "Pieces sold", "Sales (₹)"],
                                          rows=[[t["label"], t["sold"], round(t["sales_value"])] for t in rows]) if rows else None,
                          follow_up_questions=["Which designs made the most profit this month?"])
    if _has(q, "sales", "revenue", "sold", "compare", "last month"):
        ch = k.get("sales_change_pct")
        text = (f"**{period}:** {k['sales_units']} pieces sold for **{inr(k['sales_value'])}** "
                f"(net revenue {inr(k['net_revenue'])})" + (f", {ch:+.0f}% vs the same days last month" if ch is not None else "") + ".")
        trend = snap["sales_trend_6_months"]
        return ChatAnswer(answer_markdown=text,
                          chart=ChatChart(type="line", title="Sales, last 6 months", value_format="inr",
                                          data=[ChartPoint(label=t["month"], value=t["value"]) for t in trend]),
                          follow_up_questions=["What was my net profit this month, by category?", "Which designs are not selling?"])
    if _has(q, "stock value", "inventory value", "worth", "how much stock", "pieces"):
        return ChatAnswer(answer_markdown=(f"You hold **{k['total_pieces']} pieces** across {k['total_designs']} designs, worth "
                                           f"**{inr(k['stock_value_cost'])}** at cost ({inr(k['stock_value_selling'])} at selling price)."),
                          table=ChatTable(columns=["Category", "Pieces in stock", "Sold this month"],
                                          rows=[[c["name"], c["pieces_in_stock"], c["sold_this_month"]] for c in snap["categories"]]))
    if not strict:
        return ChatAnswer(
            answer_markdown=(f"The AI is busy right now, so here is a quick summary for {period}: sales **{inr(k['sales_value'])}**, "
                             f"net profit **{inr(k['net_profit'])}**, {k['out_of_stock']} sold out, {k['low_stock']} low. "
                             "Ask again in a minute for a full answer."),
            follow_up_questions=["What should I restock this month and how much money do I need?",
                                 "What was my net profit this month, by category?"])
    return None
