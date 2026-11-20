"""Bills: a sale with a customer, one or more designs, discount and GST, plus a downloadable PDF.

Revenue rule: each line's stock movement stores the price per piece AFTER the bill discount and BEFORE GST,
so every report (profit, explorer, insights) adds up to the bills' taxable value. GST is tax, not revenue.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.clock import now_utc, today as _today
from app.core.errors import AppError
from app.models import Bill, Design, StockMovement, User
from app.models.enums import MovementSource, MovementType
from app.services import (
    audit_service,
    contacts_service,
    costing_service,
    data_version_service,
    settings_service,
)
from app.services.serializers import photo_url

money = costing_service.money
PAYMENT_MODES = ("Cash", "UPI", "Card", "Bank transfer", "Credit")


def _q2(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- output
def bill_out(b: Bill) -> dict:
    lines = []
    for m in b.items:
        d = m.design
        lp = Decimal(m.list_price if m.list_price is not None else (m.unit_price or 0))
        lines.append({
            "movement_id": m.id,
            "design": {"id": d.id, "label": d.label, "name": d.name, "category_name": d.category.name,
                       "metal": d.metal.value, "purity": d.purity, "photo_url": photo_url(d)},
            "quantity": m.quantity, "list_price": float(money(lp)), "unit_price": float(money(m.unit_price or 0)),
            "amount": float(money(lp * m.quantity)), "net_amount": float(money(Decimal(m.unit_price or 0) * m.quantity)),
            "is_void": m.is_void,
        })
    return {
        "id": b.id, "number": b.number, "bill_date": b.bill_date,
        "customer": {"id": b.customer_id, "name": b.customer_name, "phone": b.customer_phone, "city": b.city,
                     "state": b.state, "country": b.country},
        "lines": lines, "pieces": sum(x["quantity"] for x in lines),
        "subtotal": float(b.subtotal), "discount": float(b.discount), "taxable": float(b.taxable),
        "gst_pct": float(b.gst_pct), "gst_amount": float(b.gst_amount), "total": float(b.total),
        "payment_mode": b.payment_mode, "notes": b.notes, "is_void": b.is_void, "voided_at": b.voided_at,
        "created_at": b.created_at,
    }


def bill_summary(b: Bill, pieces: int) -> dict:
    return {"id": b.id, "number": b.number, "bill_date": b.bill_date, "customer_id": b.customer_id,
            "customer_name": b.customer_name, "customer_phone": b.customer_phone, "city": b.city, "state": b.state,
            "country": b.country, "pieces": pieces, "taxable": float(b.taxable), "gst_amount": float(b.gst_amount),
            "total": float(b.total), "payment_mode": b.payment_mode, "is_void": b.is_void}


def _get(db: Session, bill_id: int) -> Bill:
    b = db.get(Bill, bill_id, options=[joinedload(Bill.items).joinedload(StockMovement.design).joinedload(Design.category)])
    if not b:
        raise AppError("BILL_NOT_FOUND", "Bill not found", 404)
    return b


def get_bill(db: Session, bill_id: int) -> dict:
    return bill_out(_get(db, bill_id))


# ---------------------------------------------------------------- create
def create_bill(db: Session, user: User | None, data: dict, *, commit: bool = True,
                source: MovementSource = MovementSource.MANUAL) -> Bill:
    from app.services import stock_service  # local import: stock_service also calls into billing

    items = data.get("items") or []
    if not items:
        raise AppError("VALIDATION_ERROR", "Add at least one design to the bill.", 422)
    on: date = data.get("bill_date") or _today()

    customer = None
    if data.get("customer_id"):
        customer = contacts_service.get_customer(db, int(data["customer_id"]))
    elif (data.get("customer") or {}).get("name"):
        customer = contacts_service.create_customer(db, user, data["customer"], commit=False)

    designs, subtotal = [], Decimal(0)
    for it in items:
        d = stock_service._resolve_design(db, it.get("design_id"), it.get("label"))
        qty = int(it.get("quantity") or 0)
        if qty < 1:
            raise AppError("VALIDATION_ERROR", f"Quantity for {d.label} must be at least 1", 422)
        lp = _q2(it["unit_price"] if it.get("unit_price") is not None else d.selling_price)
        if lp < 0:
            raise AppError("VALIDATION_ERROR", "Price cannot be negative", 422)
        designs.append((d, qty, lp))
        subtotal += lp * qty

    discount = min(max(_q2(data.get("discount") or 0), Decimal(0)), subtotal)
    factor = (subtotal - discount) / subtotal if subtotal else Decimal(1)
    gst_pct = _q2(data["gst_pct"] if data.get("gst_pct") is not None else settings_service.get(db, "gst_pct") or 0)
    if not (0 <= gst_pct <= 28):
        raise AppError("VALIDATION_ERROR", "GST must be between 0% and 28%", 422)
    mode = (data.get("payment_mode") or "").strip() or None

    bill = Bill(bill_date=on, customer_id=customer.id if customer else None,
                customer_name=customer.name if customer else "Walk-in customer",
                customer_phone=customer.phone if customer else None,
                city=customer.city if customer else None, state=customer.state if customer else None,
                country=customer.country if customer else None,
                gst_pct=gst_pct, payment_mode=mode, notes=(data.get("notes") or None),
                created_by=user.id if user else None)
    db.add(bill)
    db.flush()
    bill.number = f"INV-{on.year}-{bill.id:05d}"

    # price per piece after discount; any leftover paisa goes on one line so the bill adds up exactly
    nets = [_q2(lp * factor) for _, _, lp in designs]
    diff = (subtotal - discount) - sum(n * q for n, (_, q, _) in zip(nets, designs))
    if diff:
        for idx in sorted(range(len(designs)), key=lambda i: designs[i][1]):  # smallest quantity first
            qty = designs[idx][1]
            if (diff * 100) % qty == 0:
                nets[idx] += diff / qty
                break
    taxable = Decimal(0)
    for (d, qty, lp), net in zip(designs, nets):
        m = stock_service._add_movement(db, user, d, MovementType.SALE, qty, on, net, data.get("notes"), source=source)
        m.bill_id, m.list_price = bill.id, lp
        taxable += net * qty
    bill.subtotal = _q2(subtotal)
    bill.taxable = _q2(taxable)
    bill.discount = _q2(subtotal - taxable)
    bill.gst_amount = _q2(taxable * gst_pct / 100)
    bill.total = bill.taxable + bill.gst_amount
    db.flush()
    if commit:
        audit_service.log(db, user, "CREATE", "bill", bill.id,
                          after={"number": bill.number, "lines": len(designs), "total": float(bill.total)})
        ev = data_version_service.bump(db, "bill", "create", bill.id)
        db.commit()
        data_version_service.publish(ev)
    return bill


def create(db: Session, user: User, data: dict) -> dict:
    bill = create_bill(db, user, data)
    return get_bill(db, bill.id)


# ---------------------------------------------------------------- list / void
def list_bills(db: Session, *, date_from=None, date_to=None, customer_id=None, q=None, city=None, state=None,
               country=None, include_void=False, page=1, page_size=50) -> dict:
    query = db.query(Bill)
    if date_from:
        query = query.filter(Bill.bill_date >= date_from)
    if date_to:
        query = query.filter(Bill.bill_date <= date_to)
    if customer_id:
        query = query.filter(Bill.customer_id == customer_id)
    for col, val in ((Bill.city, city), (Bill.state, state), (Bill.country, country)):
        if val:
            query = query.filter(col == val)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Bill.number.ilike(like), Bill.customer_name.ilike(like), Bill.customer_phone.like(like)))
    if not include_void:
        query = query.filter(Bill.is_void.is_(False))
    total_count = query.count()
    live = query.filter(Bill.is_void.is_(False)).with_entities(Bill.taxable, Bill.gst_amount, Bill.total).all()
    totals = {"bills": len(live), "taxable": float(sum((Decimal(r[0]) for r in live), Decimal(0))),
              "gst": float(sum((Decimal(r[1]) for r in live), Decimal(0))),
              "total": float(sum((Decimal(r[2]) for r in live), Decimal(0)))}
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    rows = query.order_by(Bill.bill_date.desc(), Bill.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    pieces = {}
    if rows:
        for bid, q_ in (db.query(StockMovement.bill_id, StockMovement.quantity)
                        .filter(StockMovement.bill_id.in_([b.id for b in rows])).all()):
            pieces[bid] = pieces.get(bid, 0) + q_
    return {"items": [bill_summary(b, pieces.get(b.id, 0)) for b in rows], "total": total_count, "page": page,
            "page_size": page_size, "totals": totals}


def void_bill(db: Session, user: User, bill_id: int, reason: str | None = None, commit: bool = True) -> dict:
    b = _get(db, bill_id)
    if b.is_void:
        raise AppError("ALREADY_VOID", "This bill was already cancelled.", 409)
    for m in b.items:
        if not m.is_void:
            m.is_void, m.voided_at, m.voided_by = True, now_utc(), user.id
            m.void_reason = reason or f"Bill {b.number} cancelled"
    b.is_void, b.voided_at = True, now_utc()
    audit_service.log(db, user, "VOID", "bill", b.id, after={"reason": reason})
    if commit:
        ev = data_version_service.bump(db, "bill", "void", b.id)
        db.commit()
        data_version_service.publish(ev)
    return get_bill(db, b.id)


# ---------------------------------------------------------------- PDF
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _words_99(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _words_999(n: int) -> str:
    h, r = divmod(n, 100)
    return " ".join(x for x in ((_ONES[h] + " Hundred") if h else "", _words_99(r) if r else "") if x)


def amount_in_words(v: float) -> str:
    """Indian numbering: 1,23,45,678.50 -> 'One Crore Twenty Three Lakh … Rupees and Fifty Paise Only'."""
    rupees = int(Decimal(str(v)).quantize(Decimal("0.01")))
    paise = int((Decimal(str(v)).quantize(Decimal("0.01")) - rupees) * 100)
    if rupees == 0 and paise == 0:
        return "Zero Rupees Only"
    parts, n = [], rupees
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(f"{_words_999(crore) if crore < 1000 else amount_in_words(crore).replace(' Rupees Only', '')} Crore")
    if lakh:
        parts.append(f"{_words_99(lakh)} Lakh")
    if thousand:
        parts.append(f"{_words_99(thousand)} Thousand")
    if n:
        parts.append(_words_999(n))
    text = " ".join(parts) + " Rupees" if parts else ""
    if paise:
        text = (text + " and " if text else "") + f"{_words_99(paise)} Paise"
    return text + " Only"


def _font_paths() -> tuple[Path, Path] | None:
    """A Unicode font that has the ₹ sign (Windows Arial / Linux DejaVu). None = fall back to 'Rs.'."""
    candidates = [(Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
                  (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                   Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
                  (Path("/Library/Fonts/Arial Unicode.ttf"), Path("/Library/Fonts/Arial Unicode.ttf"))]
    for reg, bold in candidates:
        if reg.exists() and bold.exists():
            try:
                from fontTools.ttLib import TTFont
                if 0x20B9 in TTFont(str(reg), lazy=True).getBestCmap():
                    return reg, bold
            except Exception:  # pragma: no cover
                continue
    return None


def bill_pdf(db: Session, bill_id: int) -> tuple[str, bytes]:
    from fpdf import FPDF

    b = _get(db, bill_id)
    s = settings_service.get_all(db)
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    fonts = _font_paths()
    if fonts:
        pdf.add_font("Inv", "", str(fonts[0]))
        pdf.add_font("Inv", "B", str(fonts[1]))
        family, cur = "Inv", "₹"
    else:
        family, cur = "Helvetica", "Rs. "

    def rs(v) -> str:
        return cur + costing_service.format_inr(v, 2).replace("₹", "")

    gold, grey, dark = (157, 122, 24), (110, 110, 110), (30, 30, 30)
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # header
    pdf.set_text_color(*gold)
    pdf.set_font(family, "B", 20)
    pdf.cell(W * 0.6, 9, s.get("shop_name") or "Jewellery shop")
    pdf.set_font(family, "B", 13)
    pdf.cell(W * 0.4, 9, "CANCELLED BILL" if b.is_void else "TAX INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*grey)
    pdf.set_font(family, "", 9)
    y0 = pdf.get_y()
    for line in [s.get("shop_address"), f"Phone: {s['shop_phone']}" if s.get("shop_phone") else None,
                 f"GSTIN: {s['shop_gstin']}" if s.get("shop_gstin") else None]:
        if line:
            pdf.cell(W * 0.6, 4.6, str(line), new_x="LMARGIN", new_y="NEXT")
    y1 = pdf.get_y()
    pdf.set_xy(pdf.l_margin + W * 0.6, y0)
    pdf.set_text_color(*dark)
    for label, val in (("Bill no.", b.number or ""), ("Date", b.bill_date.strftime("%d %b %Y")),
                       ("Payment", b.payment_mode or "-")):
        pdf.set_x(pdf.l_margin + W * 0.6)
        pdf.set_font(family, "", 9)
        pdf.cell(W * 0.18, 4.8, label, align="R")
        pdf.set_font(family, "B", 9)
        pdf.cell(W * 0.22, 4.8, val, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(y1, pdf.get_y()) + 4)
    pdf.set_draw_color(*gold)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
    pdf.ln(4)

    # bill to
    pdf.set_font(family, "", 8)
    pdf.set_text_color(*grey)
    pdf.cell(0, 4.5, "BILL TO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*dark)
    pdf.set_font(family, "B", 11)
    pdf.cell(0, 6, b.customer_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 9)
    region = ", ".join(x for x in (b.city, b.state, b.country) if x)
    for line in (b.customer_phone and f"Phone: {b.customer_phone}", region):
        if line:
            pdf.cell(0, 4.6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # lines
    cols = [("#", 0.06, "C"), ("Design", 0.46, "L"), ("Qty", 0.1, "R"), ("Rate", 0.18, "R"), ("Amount", 0.2, "R")]
    pdf.set_fill_color(244, 233, 201)
    pdf.set_font(family, "B", 9)
    for title, w, al in cols:
        pdf.cell(W * w, 8, title, align=al, fill=True)
    pdf.ln(8)
    pdf.set_font(family, "", 9)
    pdf.set_draw_color(225, 220, 205)
    pdf.set_line_width(0.2)
    for i, m in enumerate(b.items, start=1):
        d = m.design
        lp = Decimal(m.list_price if m.list_price is not None else (m.unit_price or 0))
        desc = f"{d.label}  {d.name or d.category.name}"
        if d.purity or d.metal:
            desc += f"  ({' '.join(x for x in (d.purity, d.metal.value.title()) if x)})"
        vals = [str(i), desc[:60], str(m.quantity), rs(lp), rs(lp * m.quantity)]
        for (title, w, al), v in zip(cols, vals):
            pdf.cell(W * w, 7.5, v, align=al)
        pdf.ln(7.5)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())

    # totals
    pdf.ln(3)
    tx = pdf.l_margin + W * 0.55
    rows = [("Subtotal", rs(b.subtotal))]
    if Decimal(b.discount) > 0:
        rows.append(("Discount", "- " + rs(b.discount)))
    rows.append(("Taxable value", rs(b.taxable)))
    if Decimal(b.gst_pct) > 0:
        half = Decimal(b.gst_pct) / 2
        rows.append((f"CGST {half.normalize():f}%", rs(Decimal(b.gst_amount) / 2)))
        rows.append((f"SGST {half.normalize():f}%", rs(Decimal(b.gst_amount) - Decimal(b.gst_amount) / 2)))
    for label, val in rows:
        pdf.set_x(tx)
        pdf.set_font(family, "", 9.5)
        pdf.cell(W * 0.25, 6, label)
        pdf.cell(W * 0.2, 6, val, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(tx)
    pdf.set_fill_color(*gold)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(family, "B", 11)
    pdf.cell(W * 0.25, 9, " Total", fill=True)
    pdf.cell(W * 0.2, 9, rs(b.total) + " ", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*dark)
    pdf.ln(3)
    pdf.set_font(family, "", 9)
    pdf.multi_cell(W, 5, f"Amount in words: {amount_in_words(float(b.total))}", new_x="LMARGIN", new_y="NEXT")
    if b.notes:
        pdf.set_text_color(*grey)
        pdf.multi_cell(W, 5, f"Note: {b.notes}", new_x="LMARGIN", new_y="NEXT")

    # footer
    pdf.set_y(-32)
    pdf.set_text_color(*grey)
    pdf.set_font(family, "", 8.5)
    pdf.cell(W / 2, 5, "Thank you for shopping with us!")
    pdf.cell(W / 2, 5, "Authorised signatory", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 7.5)
    pdf.cell(W, 5, "Goods once sold can be exchanged as per shop policy. Computer-generated bill.",
             new_x="LMARGIN", new_y="NEXT")
    return f"{b.number or f'bill_{b.id}'}.pdf", bytes(pdf.output())
