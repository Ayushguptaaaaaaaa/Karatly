"""Demo jewellery shop with 12 months of realistic history (button-triggered only) + reset."""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import today as _today
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    Category,
    ChatMessage,
    ChatSession,
    Design,
    InsightRun,
    Job,
    PurchasePlan,
    PurchasePlanItem,
    StockMovement,
    Subcategory,
    User,
)
from app.models.enums import Metal, MovementSource, MovementType, direction
from app.services import audit_service, data_version_service

CATS = [
    # name, prefix, icon, subcategories, count, cost range, metal, purities, rate multiplier
    ("Necklaces", "NK", "necklace", ["Choker", "Long haar", "Mangalsutra"], 14, (60000, 400000), "GOLD", ["22K"], 0.55),
    ("Earrings", "ER", "earring", ["Studs", "Jhumkas", "Hoops"], 20, (15000, 80000), "GOLD", ["22K", "18K"], 1.2),
    ("Bangles", "BG", "bangle", ["Kada", "Thin bangles"], 14, (40000, 200000), "GOLD", ["22K"], 0.75),
    ("Bracelets", "BR", "bracelet", ["Chain bracelet", "Charm"], 12, (25000, 120000), "GOLD", ["18K", "22K"], 0.8),
    ("Anklets", "AN", "anklet", ["Silver payal", "Gold anklets"], 14, (1200, 4000), "SILVER", ["925"], 1.6),
    ("Rings", "RG", "ring", ["Ladies", "Gents", "Engagement"], 18, (8000, 60000), "GOLD", ["22K", "18K"], 1.3),
    ("Chains", "CH", "chain", ["Rope", "Box"], 12, (30000, 150000), "GOLD", ["22K"], 0.8),
    ("Pendants", "PD", "pendant", ["Religious", "Fashion"], 16, (6000, 45000), "GOLD", ["22K", "18K"], 1.1),
]
ADJ = ["Kundan", "Temple", "Antique", "Polki", "Floral", "Peacock", "Lakshmi", "Meenakari", "Filigree", "Rose",
       "Classic", "Twisted", "Leaf", "Mango", "Coin", "Bridal", "Royal", "Lotus", "Paisley", "Navratna"]
SINGULAR = {"Choker": "choker", "Long haar": "haar", "Mangalsutra": "mangalsutra", "Studs": "studs",
            "Jhumkas": "jhumka", "Hoops": "hoops", "Kada": "kada", "Thin bangles": "bangle pair",
            "Chain bracelet": "chain bracelet", "Charm": "charm bracelet", "Silver payal": "payal",
            "Gold anklets": "anklet", "Ladies": "ring", "Gents": "gents ring", "Engagement": "engagement ring",
            "Rope": "rope chain", "Box": "box chain", "Religious": "pendant", "Fashion": "pendant"}


def _season(month: int, cat: str) -> float:
    if month in (10, 11):
        return 1.8
    if month in (12, 1, 2):
        return 1.4 if cat in ("Necklaces", "Bangles") else 1.15
    if month in (4, 5):
        return 1.3
    if month in (6, 7, 8):
        return 0.75
    return 1.0


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    l_, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l_:
            return k
        k += 1


def _round_price(v: float) -> Decimal:
    step = 100 if v >= 10000 else 10
    return Decimal(int(round(v / step) * step))


def load(db: Session, user: User, force: bool = False) -> dict:
    if db.query(Design.id).first() and not force:
        raise AppError("DATA_EXISTS", "Demo data can only be loaded into an empty shop.", 409)
    if force:
        _wipe(db)
    rng = random.Random(42)
    today = _today()
    start = today - timedelta(days=365)
    min_default = 3

    designs: list[tuple[Design, dict]] = []
    for ci, (name, prefix, icon, subs, count, (lo, hi), metal, purities, mult) in enumerate(CATS, start=1):
        c = Category(name=name, name_key=name.lower(), label_prefix=prefix, icon=icon, sort_order=ci)
        db.add(c)
        db.flush()
        sub_objs = []
        for si, sn in enumerate(subs, start=1):
            s = Subcategory(category_id=c.id, name=sn, name_key=sn.lower(), sort_order=si)
            db.add(s)
            sub_objs.append(s)
        db.flush()
        for i in range(count):
            sub = sub_objs[i % len(sub_objs)]
            cost = rng.uniform(lo, hi)
            cost = _round_price(cost)
            sell = _round_price(float(cost) * rng.uniform(1.15, 1.35))
            gold_rate = 7200 if metal == "GOLD" else 110
            roll = rng.random()
            kind = "star" if roll < 0.18 else ("dud" if roll > 0.83 else "avg")
            rate = {"star": rng.uniform(5, 9), "avg": rng.uniform(1.2, 3.5), "dud": rng.uniform(0.2, 0.6)}[kind] * mult
            d = Design(category_id=c.id, subcategory_id=sub.id, label=f"{prefix}-{1001 + i}",
                       name=f"{rng.choice(ADJ)} {SINGULAR.get(sub.name, sub.name.lower())}",
                       metal=Metal(metal), purity=rng.choice(purities),
                       weight_g=Decimal(str(round(float(cost) / gold_rate, 2))), cost_price=cost, selling_price=sell,
                       supplier=rng.choice(["Shree Ornaments", "Rajkot Karigars", "Mumbai Gold House", "Jaipur Crafts"]),
                       min_stock=min_default if kind != "star" else rng.choice([3, 4, 5]), custom_fields={})
            d.category = c
            db.add(d)
            designs.append((d, {"kind": kind, "rate": rate, "cat": name}))
    db.flush()

    stars = [x for x in designs if x[1]["kind"] == "star"]
    avgs = [x for x in designs if x[1]["kind"] == "avg"]
    for d, meta in rng.sample(stars, min(8, len(stars))):
        meta["no_restock_after"] = today - timedelta(days=55)   # best-sellers that run out
    for d, meta in rng.sample(avgs, min(14, len(avgs))):
        meta["no_restock_after"] = today - timedelta(days=35)   # will drift to low stock
    for d, meta in designs:
        if meta["kind"] == "dud":
            meta["stop_selling"] = today - timedelta(days=rng.randint(110, 200))

    movements: list[StockMovement] = []

    def add(d: Design, mtype: MovementType, qty: int, on: date, price: Decimal | None):
        movements.append(StockMovement(design_id=d.id, type=mtype, quantity=qty, signed_qty=direction(mtype) * qty,
                                       unit_price=price, occurred_on=on, source=MovementSource.DEMO,
                                       created_by=user.id))

    for d, meta in designs:
        stock = rng.randint(6, 18) if meta["kind"] != "dud" else rng.randint(5, 10)
        cost = Decimal(d.cost_price)
        add(d, MovementType.OPENING, stock, start, cost)
        pending: list[tuple[date, int]] = []
        last_order = start - timedelta(days=30)
        for k in range(1, 366):
            day = start + timedelta(days=k)
            if day > today:
                break
            for arr in [p for p in pending if p[0] == day]:
                stock += arr[1]
                pending.remove(arr)
            if day.day == 1 and day.month % 3 == 0 and rng.random() < 0.6:
                cost = _round_price(float(cost) * rng.uniform(1.01, 1.05))
            stop = meta.get("stop_selling")
            lam = 0 if (stop and day >= stop) else meta["rate"] / 30 * _season(day.month, meta["cat"])
            want = _poisson(rng, lam)
            sold = min(want, stock)
            if sold:
                stock -= sold
                add(d, MovementType.SALE, sold, day, Decimal(d.selling_price))
            nra = meta.get("no_restock_after")
            can_restock = meta["kind"] != "dud" and (nra is None or day < nra)
            if can_restock and stock <= d.min_stock and not pending and (day - last_order).days > 10:
                qty = max(d.min_stock * 2, math.ceil(meta["rate"] * 2)) + rng.randint(0, 3)
                arrive = day + timedelta(days=rng.randint(3, 7))
                if arrive <= today:
                    add(d, MovementType.PURCHASE, qty, arrive, cost)
                    pending.append((arrive, qty))
                    last_order = day
            if sold and rng.random() < 0.015:
                ret_day = day + timedelta(days=rng.randint(2, 9))
                if ret_day <= today:
                    add(d, MovementType.CUSTOMER_RETURN, 1, ret_day, None)
                    pending.append((ret_day, 1))
        meta["final_stock"] = stock

    # guaranteed situations: a big sale, a cost jump, one design priced below cost
    candidates = [x for x in avgs if "no_restock_after" not in x[1]]
    if candidates:
        d, meta = candidates[0]
        big_day = today - timedelta(days=40)
        add(d, MovementType.PURCHASE, 15, big_day - timedelta(days=3), Decimal(d.cost_price))
        add(d, MovementType.SALE, 12, big_day, Decimal(d.selling_price))
    if len(candidates) > 1:
        d, meta = candidates[1]
        add(d, MovementType.PURCHASE, 4, today - timedelta(days=25), _round_price(float(d.cost_price) * 1.32))
    if len(candidates) > 2:
        d, meta = candidates[2]
        d.selling_price = _round_price(float(d.cost_price) * 0.92)

    db.add_all(movements)
    audit_service.log(db, user, "DEMO_LOAD", "shop", None, after={"designs": len(designs), "movements": len(movements)})
    ev = data_version_service.bump(db, "shop", "demo_load")
    db.commit()
    data_version_service.publish(ev)
    return {"categories": len(CATS), "designs": len(designs), "movements": len(movements)}


def _wipe(db: Session) -> None:
    db.query(ChatMessage).delete()
    db.query(ChatSession).delete()
    db.query(PurchasePlanItem).delete()
    db.query(PurchasePlan).delete()
    db.query(InsightRun).delete()
    db.query(Job).delete()
    db.query(StockMovement).delete()
    db.query(Design).delete()
    db.query(Subcategory).delete()
    db.query(Category).delete()
    folder = get_settings().photo_dir
    if folder.exists():
        for p in folder.iterdir():
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass


def reset(db: Session, user: User) -> dict:
    _wipe(db)
    audit_service.log(db, user, "RESET", "shop", None)
    ev = data_version_service.bump(db, "shop", "reset")
    db.commit()
    data_version_service.publish(ev)
    return {"ok": True}
