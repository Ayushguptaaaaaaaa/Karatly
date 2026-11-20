"""Add realistic test activity to an imported shop (sales on bills, restocks from dealers, a few returns).

Usage (from the backend folder):
    .venv/Scripts/python.exe scripts/simulate_activity.py [--start 2026-08-01] [--seed 11]

What it does to designs that only have imported opening stock:
  * moves their opening stock date back to --start, so there are months of history
  * gives every design a different story: sells nothing / a little / most / everything /
    sells out, gets restocked from its dealer and sells again (best-sellers)
  * sales go on real bills to ~45 customers (Indian cities + a few NRI), 1-3 designs per bill,
    Indian season pattern (Navratri, Dhanteras/Diwali, wedding season), some discounts and returns
Everything goes through the app's own services (stock checks, bills, GST), so numbers stay consistent.
"""
from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import update  # noqa: E402

from app.core.clock import today as _today  # noqa: E402
from app.core.database import SessionLocal, create_all  # noqa: E402
from app.models import Design, StockMovement, User  # noqa: E402
from app.models.enums import MovementSource, MovementType, Role  # noqa: E402
from app.services import billing_service, contacts_service, data_version_service, stock_service  # noqa: E402

FIRST = ["Priya", "Anjali", "Rohit", "Neha", "Amit", "Kavita", "Suresh", "Pooja", "Vikram", "Sneha", "Rahul", "Meera",
         "Arjun", "Divya", "Karan", "Riya", "Sanjay", "Isha", "Manish", "Lakshmi", "Farah", "Harpreet", "Nisha",
         "Deepak", "Aditi", "Tanvi", "Rekha", "Gauri", "Simran", "Zoya", "Bhavna", "Ritu", "Payal", "Shalini"]
LAST = ["Sharma", "Patel", "Mehta", "Iyer", "Gupta", "Reddy", "Shah", "Nair", "Singh", "Joshi", "Kapoor", "Desai",
        "Agarwal", "Bose", "Khanna", "Malhotra", "Chopra", "Rao", "Pillai", "Banerjee"]
PLACES = [("Mumbai", "Maharashtra", "India", 10), ("Pune", "Maharashtra", "India", 4), ("Delhi", "Delhi", "India", 9),
          ("Jaipur", "Rajasthan", "India", 6), ("Ahmedabad", "Gujarat", "India", 5), ("Surat", "Gujarat", "India", 3),
          ("Bengaluru", "Karnataka", "India", 5), ("Chennai", "Tamil Nadu", "India", 4),
          ("Hyderabad", "Telangana", "India", 4), ("Kolkata", "West Bengal", "India", 4),
          ("Lucknow", "Uttar Pradesh", "India", 3), ("Chandigarh", "Punjab", "India", 2),
          ("Dubai", "Dubai", "United Arab Emirates", 2), ("London", "England", "United Kingdom", 1),
          ("Edison", "New Jersey", "United States", 1), ("Singapore", "Singapore", "Singapore", 1)]
PAYMENT = ["UPI", "UPI", "UPI", "Card", "Card", "Cash", "Bank transfer"]


def season_weight(d: date) -> float:
    """Indian jewellery demand: Navratri, Karwa Chauth, Dhanteras/Diwali peak, then wedding season."""
    if date(2026, 11, 4) <= d <= date(2026, 11, 9):     # Dhanteras / Diwali week
        return 3.0
    if date(2026, 10, 11) <= d <= date(2026, 10, 20):   # Navratri / Dussehra
        return 1.8
    if date(2026, 9, 26) <= d <= date(2026, 10, 10):    # Pitru Paksha: people avoid buying
        return 0.4
    if d.month == 11 and d.day > 15:                    # wedding season starts
        return 1.9
    if d.month == 10 or d.month == 11:
        return 1.4
    if d.month == 8:
        return 0.8                                       # monsoon
    return 1.0


def pick_dates(rng: random.Random, start: date, end: date, n: int) -> list[date]:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if not days or n <= 0:
        return []
    return sorted(rng.choices(days, weights=[season_weight(d) for d in days], k=n))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None, help="opening stock date, default 111 days ago")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    end = _today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=111)
    create_all()
    db = SessionLocal()
    user = db.query(User).filter(User.role == Role.OWNER).first()

    # designs whose only history is the imported opening stock
    moves = defaultdict(list)
    for m in db.query(StockMovement).filter(StockMovement.is_void.is_(False)).all():
        moves[m.design_id].append(m)
    designs = [d for d in db.query(Design).filter(Design.is_active.is_(True)).all()
               if moves[d.id] and all(m.type == MovementType.OPENING for m in moves[d.id])]
    if not designs:
        print("Nothing to do: no designs with only opening stock.")
        return
    ids = [d.id for d in designs]
    db.execute(update(StockMovement).where(StockMovement.design_id.in_(ids), StockMovement.type == MovementType.OPENING)
               .values(occurred_on=start))
    db.commit()

    # customers (a few loyal ones buy much more)
    customers, used = [], set()
    while len(customers) < 45:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name in used:
            continue
        used.add(name)
        city, state, country, _ = rng.choices(PLACES, [p[3] for p in PLACES])[0]
        customers.append(contacts_service.create_customer(db, user, {
            "name": name, "city": city, "state": state, "country": country,
            "phone": f"9{rng.randint(100000000, 999999999)}"}, commit=False))
    db.commit()
    cust_weights = [8 if i < 8 else 3 if i < 20 else 1 for i in range(len(customers))]

    # every design gets a story
    story_counts = defaultdict(int)
    sale_units: list[tuple[date, Design]] = []
    restocks: list[tuple[date, Design, int]] = []
    mid = start + (end - start) * 2 // 3
    for d in designs:
        opening = sum(m.quantity for m in moves[d.id])
        story = rng.choices(["none", "few", "most", "all", "star"], [18, 30, 25, 15, 12])[0]
        if opening <= 1 and story in ("few", "most"):
            story = rng.choice(["none", "all"])
        story_counts[story] += 1
        if story == "none":
            continue
        if story == "few":
            n = max(1, round(opening * rng.uniform(0.1, 0.35)))
        elif story == "most":
            n = min(opening - 1, max(1, round(opening * rng.uniform(0.55, 0.9))))
        else:
            n = opening
        if story == "star":   # sells out by ~2/3 of the way, restocked, sells again
            sale_units += [(dt, d) for dt in pick_dates(rng, start + timedelta(days=1), mid - timedelta(days=4), n)]
            dealer_id = next((m.dealer_id for m in moves[d.id] if m.dealer_id), None)
            back = max(2, math.ceil(opening * rng.uniform(0.8, 1.5)))
            arrive = mid + timedelta(days=rng.randint(0, 4))
            restocks.append((arrive, d, back, dealer_id))
            again = round(back * rng.uniform(0.3, 0.9))
            sale_units += [(dt, d) for dt in pick_dates(rng, arrive + timedelta(days=1), end, again)]
        else:
            sale_units += [(dt, d) for dt in pick_dates(rng, start + timedelta(days=1), end, n)]

    # group units into bills: same day, 1-3 designs, cheap pieces sometimes 2-3 at once
    by_day: dict[date, list[Design]] = defaultdict(list)
    for dt, d in sale_units:
        by_day[dt].append(d)
    events: list[tuple[date, str, object]] = [(dt, "restock", (d, q, dl)) for dt, d, q, dl in restocks]
    for dt, ds in by_day.items():
        rng.shuffle(ds)
        counts = defaultdict(int)
        for d in ds:
            counts[d.id] += 1
        lines = [(next(x for x in ds if x.id == did), q) for did, q in counts.items()]
        i = 0
        while i < len(lines):
            size = rng.choices([1, 2, 3], [70, 22, 8])[0]
            events.append((dt, "bill", lines[i:i + size]))
            i += size
    events.sort(key=lambda e: (e[0], 0 if e[1] == "restock" else 1))

    bills = returns = 0
    for n, (dt, kind, payload) in enumerate(events, start=1):
        if kind == "restock":
            d, q, dealer_id = payload
            m = stock_service._add_movement(db, user, d, MovementType.PURCHASE, q, dt,
                                            Decimal(d.cost_price) * Decimal(str(round(rng.uniform(1.0, 1.06), 3))),
                                            note="Restock", source=MovementSource.MANUAL)
            m.dealer_id = dealer_id
            continue
        walk_in = rng.random() < 0.25
        cust = None if walk_in else rng.choices(customers, cust_weights)[0]
        items = [{"design_id": d.id, "quantity": q, "unit_price": float(d.selling_price)} for d, q in payload]
        value = sum(float(d.selling_price) * q for d, q in payload)
        discount = round(value * rng.choice([0.02, 0.03, 0.05]), -1) if value > 20000 and rng.random() < 0.35 else 0
        bill = billing_service.create_bill(db, user, {
            "bill_date": dt, "customer_id": cust.id if cust else None, "items": items, "discount": discount,
            "payment_mode": rng.choice(PAYMENT)}, commit=False, source=MovementSource.MANUAL)
        bills += 1
        ret_on = dt + timedelta(days=rng.randint(2, 6))
        if rng.random() < 0.012 and ret_on <= end:   # a few customer returns
            d, _q = payload[0]
            stock_service._add_movement(db, user, d, MovementType.CUSTOMER_RETURN, 1, ret_on,
                                        None, note=f"Returned from {bill.number}", source=MovementSource.MANUAL)
            returns += 1
        if n % 200 == 0:
            db.commit()
    ev = data_version_service.bump(db, "shop", "simulated_activity")
    db.commit()
    data_version_service.publish(ev)
    sold = sum(1 for _ in sale_units)
    print(f"Designs: {len(designs)} | stories: {dict(story_counts)}")
    print(f"Opening stock dated {start} | {bills} bills, {sold} pieces sold, {len(restocks)} restocks, "
          f"{returns} returns, {len(customers)} customers")
    db.close()


if __name__ == "__main__":
    main()
