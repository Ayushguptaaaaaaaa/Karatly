"""Excel template, design import and generic xlsx export helpers."""
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Subcategory, User
from app.models.enums import MovementSource
from app.services import audit_service, category_service, data_version_service, design_service, settings_service

COLUMNS = ["category", "subcategory", "label", "name", "metal", "purity", "weight_g", "cost_price", "selling_price",
           "min_stock", "opening_stock", "dealer", "dealer_city", "dealer_state"]
INR_FORMAT = '[$₹-4009]#,##,##0.00'


def template_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Designs"
    ws.append(COLUMNS)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="F4E9C9")
    ws.append(["Earrings", "Jhumkas", "ER-1001", "Kundan jhumka", "GOLD", "22K", 8.5, 42000, 52000, 3, 6, "Shree Ornaments",
               "Ahmedabad", "Gujarat"])
    for c in ws[2]:
        c.font = Font(italic=True, color="888888")
    dv_metal = DataValidation(type="list", formula1='"GOLD,SILVER,PLATINUM,IMITATION,OTHER"', allow_blank=True)
    dv_purity = DataValidation(type="list", formula1='"24K,22K,18K,14K,925,950,Other"', allow_blank=True)
    ws.add_data_validation(dv_metal)
    ws.add_data_validation(dv_purity)
    dv_metal.add("E2:E2000")
    dv_purity.add("F2:F2000")
    for i, w in enumerate([14, 14, 12, 26, 10, 8, 10, 12, 13, 10, 13, 20, 14, 14], start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A2"
    help_ws = wb.create_sheet("Help")
    rows = [
        ("Column", "Meaning"),
        ("category", "Category name (created if missing), e.g. Earrings"),
        ("subcategory", "Optional subcategory name (created if missing)"),
        ("label", "Unique design label, e.g. ER-1012"),
        ("name", "Optional design name"),
        ("metal", "GOLD, SILVER, PLATINUM, IMITATION (AD, Kundan, plated) or OTHER"),
        ("purity", "e.g. 22K, 18K, 925"),
        ("weight_g", "Optional weight in grams"),
        ("cost_price", "Cost per piece in ₹ (required)"),
        ("selling_price", "Selling price per piece in ₹ (required)"),
        ("min_stock", "Alert when stock is at or below this (optional)"),
        ("opening_stock", "Pieces in stock now (optional, default 0)"),
        ("dealer", "Optional dealer / supplier / karigar the stock came from (created if new)"),
        ("dealer_city", "Optional dealer city"),
        ("dealer_state", "Optional dealer state"),
        ("Note", "Delete the grey example row before importing."),
    ]
    for r in rows:
        help_ws.append(r)
    help_ws["A1"].font = Font(bold=True)
    help_ws["B1"].font = Font(bold=True)
    help_ws.column_dimensions["A"].width = 16
    help_ws.column_dimensions["B"].width = 60
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _read_rows(content: bytes) -> list[tuple[int, dict]]:
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
    except Exception:
        raise AppError("INVALID_FILE", "Could not read the Excel file. Please use the template (.xlsx).", 422)
    ws = wb["Designs"] if "Designs" in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(h or "").strip().lower() for h in rows[0]]
    missing = [c for c in ("category", "label", "cost_price", "selling_price") if c not in header]
    if missing:
        raise AppError("INVALID_FILE", f"Missing columns: {', '.join(missing)}", 422)
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if r is None or all(v in (None, "") for v in r):
            continue
        out.append((i, {header[j]: r[j] for j in range(min(len(header), len(r))) if header[j]}))
    return out


def import_designs(db: Session, user: User, content: bytes, dry_run: bool) -> dict[str, Any]:
    rows = _read_rows(content)
    if not rows:
        raise AppError("EMPTY_FILE", "The file has no design rows.", 422)
    default_min = int(settings_service.get(db, "default_min_stock") or 3)
    clean, errs = design_service.validate_rows(db, [r for _, r in rows], default_min)
    errors = [{"row": rows[e["index"]][0], "field": e["field"], "message": e["message"]} for e in errs]
    for idx, (rownum, r) in enumerate(rows):
        if not str(r.get("category") or "").strip():
            errors.append({"row": rownum, "field": "category", "message": "Required"})
    existing_cats = {c.name_key: c for c in db.query(Category).all()}
    new_cats, new_subs = set(), set()
    for _, r in rows:
        ck = " ".join(str(r.get("category") or "").strip().lower().split())
        if ck and ck not in existing_cats:
            new_cats.add(ck)
        sub = str(r.get("subcategory") or "").strip()
        if sub:
            new_subs.add((ck, sub.lower()))
    dealers = {" ".join(str(r.get("dealer") or r.get("supplier") or "").lower().split()) for _, r in rows} - {""}
    summary = {"categories": len(new_cats), "subcategories": len(new_subs), "designs": len(rows),
               "dealers": len(dealers), "pieces": sum(int(r.get("opening_stock") or 0) for _, r in rows
                                                      if str(r.get("opening_stock") or "0").isdigit())}
    if dry_run or errors:
        return {"valid_rows": len(rows) - len({e["row"] for e in errors}), "errors": errors, "will_create": summary,
                "imported": False}

    groups: dict[tuple[str, str], list[dict]] = {}
    for (rownum, raw), c in zip(rows, clean):
        cat_name = str(raw.get("category")).strip()
        sub_name = str(raw.get("subcategory") or "").strip()
        c["opening_stock"] = int(raw.get("opening_stock") or 0)
        c["metal"] = c["metal"].value
        groups.setdefault((cat_name, sub_name), []).append(c)
    try:
        from app.services import contacts_service

        for _, raw in rows:
            name = str(raw.get("dealer") or raw.get("supplier") or "").strip()
            if name:
                contacts_service.get_or_create_dealer(db, user, name, str(raw.get("dealer_city") or "").strip() or None,
                                                      str(raw.get("dealer_state") or "").strip() or None)
        db.flush()
        for (cat_name, sub_name), items in groups.items():
            key = " ".join(cat_name.lower().split())
            cat = existing_cats.get(key)
            if not cat:
                prefix = category_service.suggest_prefix(db, cat_name)
                cat = Category(name=cat_name, name_key=key, label_prefix=prefix, icon=_guess_icon(cat_name),
                               sort_order=len(existing_cats) + 1)
                db.add(cat)
                db.flush()
                existing_cats[key] = cat
            sub_id = None
            if sub_name:
                sub = (db.query(Subcategory).filter(Subcategory.category_id == cat.id,
                                                   Subcategory.name_key == sub_name.lower()).first())
                if not sub:
                    sub = Subcategory(category_id=cat.id, name=sub_name, name_key=" ".join(sub_name.lower().split()))
                    db.add(sub)
                    db.flush()
                sub_id = sub.id
            for i in range(0, len(items), 100):
                design_service.bulk_create(db, user, cat.id, sub_id, items[i:i + 100], source=MovementSource.IMPORT,
                                           commit=False)
        audit_service.log(db, user, "IMPORT", "designs", None, after=summary)
        ev = data_version_service.bump(db, "design", "import")
        db.commit()
    except Exception:
        db.rollback()
        raise
    data_version_service.publish(ev)
    return {"valid_rows": len(rows), "errors": [], "will_create": summary, "imported": True}


ICON_GUESS = {"neck": "necklace", "haar": "necklace", "ear": "earring", "jhum": "earring", "ring": "ring",
              "bangle": "bangle", "kada": "bangle", "brace": "bracelet", "ank": "anklet", "payal": "anklet",
              "chain": "chain", "pend": "pendant", "nose": "nosepin", "set": "set", "coin": "coin"}


def _guess_icon(name: str) -> str:
    n = name.lower()
    for k, v in ICON_GUESS.items():
        if k in n:
            return v
    return "other"


def build_xlsx(title: str, headers: list[str], rows: list[list[Any]], money_cols: set[int] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="F4E9C9")
    for r in rows:
        ws.append(r)
    money_cols = money_cols or set()
    for col_idx in money_cols:
        for row in ws.iter_rows(min_row=2, min_col=col_idx + 1, max_col=col_idx + 1):
            for cell in row:
                cell.number_format = INR_FORMAT
    for i, h in enumerate(headers, start=1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:200] if i - 1 < len(r)]) + 2
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(width, 8), 48)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
