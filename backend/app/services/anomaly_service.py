"""Rule-based anomaly candidates (the AI auditor reviews and explains them)."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import today as _today
from app.models import StockMovement
from app.models.enums import Demand, MovementType
from app.services import metrics_service


def candidates(db: Session, days: int = 90, snap: metrics_service.Snapshot | None = None) -> list[dict]:
    snap = snap or metrics_service.snapshot(db)
    since = _today() - timedelta(days=days)
    movs = (db.query(StockMovement).filter(StockMovement.occurred_on >= since)
            .order_by(StockMovement.occurred_on, StockMovement.id).all())
    out: list[dict] = []
    labels = {i: d.label for i, d in snap.designs.items()}

    # 1. big sale
    sales = defaultdict(list)
    for m in movs:
        if m.type == MovementType.SALE and not m.is_void:
            sales[m.design_id].append(m)
    for did, ms in sales.items():
        avg = sum(m.quantity for m in ms) / len(ms)
        for m in ms:
            if m.quantity > max(5, 3 * avg) or (len(ms) == 1 and m.quantity > 8):
                out.append({"rule": "BIG_SALE", "severity": "MEDIUM", "label": labels.get(did),
                            "evidence": {"quantity": m.quantity, "average_sale": round(avg, 1),
                                         "date": str(m.occurred_on)},
                            "message": f"Unusually large sale of {m.quantity} pieces on {m.occurred_on:%d %b}"})

    # 2. cost jump
    all_costs = (db.query(StockMovement).filter(StockMovement.is_void.is_(False),
                                                StockMovement.type.in_([MovementType.PURCHASE, MovementType.OPENING]),
                                                StockMovement.unit_price.isnot(None))
                 .order_by(StockMovement.design_id, StockMovement.occurred_on, StockMovement.id).all())
    prev: dict[int, Decimal] = {}
    for m in all_costs:
        p = prev.get(m.design_id)
        if p and m.type == MovementType.PURCHASE and m.occurred_on >= since and p > 0:
            change = (Decimal(m.unit_price) - p) / p * 100
            if abs(change) > 20:
                out.append({"rule": "COST_JUMP", "severity": "HIGH" if abs(change) > 35 else "MEDIUM",
                            "label": labels.get(m.design_id),
                            "evidence": {"previous_cost": float(p), "new_cost": float(m.unit_price),
                                         "change_pct": round(float(change), 1), "date": str(m.occurred_on)},
                            "message": f"Purchase cost changed {float(change):+.0f}% (₹{float(p):,.0f} → ₹{float(m.unit_price):,.0f})"})
        prev[m.design_id] = Decimal(m.unit_price)

    # 3. price below cost / 7. zero minimum on high demand
    for did, d in snap.designs.items():
        if not d.is_active:
            continue
        st = snap.states[did]
        if Decimal(d.selling_price) < st.last_unit_cost:
            out.append({"rule": "PRICE_BELOW_COST", "severity": "HIGH", "label": d.label,
                        "evidence": {"selling_price": float(d.selling_price), "last_cost": float(st.last_unit_cost)},
                        "message": f"Selling price ₹{float(d.selling_price):,.0f} is below cost ₹{float(st.last_unit_cost):,.0f}"})
        if d.min_stock == 0 and st.demand == Demand.HIGH:
            out.append({"rule": "ZERO_MIN_STOCK", "severity": "LOW", "label": d.label, "evidence": {"min_stock": 0},
                        "message": "High-demand design has minimum stock set to 0 (no low-stock alerts)"})

    # 4. frequent undo
    voids = defaultdict(list)
    for m in movs:
        if m.is_void and m.voided_at:
            voids[m.design_id].append(m.voided_at)
    for did, ts in voids.items():
        ts.sort()
        for i in range(len(ts)):
            window = [t for t in ts if 0 <= (t - ts[i]).days < 7]
            if len(window) > 3:
                out.append({"rule": "FREQUENT_UNDO", "severity": "LOW", "label": labels.get(did),
                            "evidence": {"undo_count_7d": len(window)},
                            "message": f"{len(window)} entries undone within a week"})
                break

    # 5. same-day sale and return
    by_day = defaultdict(set)
    for m in movs:
        if not m.is_void and m.type in (MovementType.SALE, MovementType.CUSTOMER_RETURN):
            by_day[(m.design_id, m.occurred_on)].add(m.type)
    for (did, day), types in by_day.items():
        if len(types) == 2:
            out.append({"rule": "SALE_AND_RETURN_SAME_DAY", "severity": "LOW", "label": labels.get(did),
                        "evidence": {"date": str(day)}, "message": f"Sale and customer return on the same day ({day:%d %b})"})

    # 6. backdated entries (created > 30 days after occurred_on)
    late = defaultdict(int)
    for m in movs:
        if m.created_at and (m.created_at.date() - m.occurred_on).days > 30 and m.source.value == "MANUAL":
            late[m.created_by] += 1
    for uid, n in late.items():
        out.append({"rule": "BACKDATED_ENTRIES", "severity": "LOW", "label": None, "evidence": {"count": n},
                    "message": f"{n} entries were recorded more than 30 days after the date they describe"})

    sev = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    out.sort(key=lambda x: sev[x["severity"]])
    per_rule: dict[str, int] = defaultdict(int)
    capped = []
    for c in out:  # keep variety: at most 3 per rule
        if per_rule[c["rule"]] < 3:
            capped.append(c)
            per_rule[c["rule"]] += 1
    return capped[:20]
