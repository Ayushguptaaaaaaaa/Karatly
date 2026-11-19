"""Shared dict builders for API responses (keeps field names consistent everywhere)."""
from __future__ import annotations

from app.models import Category, Design, StockMovement, Subcategory
from app.models.enums import IN_TYPES
from app.services.costing_service import money
from app.services.metrics_service import DesignState


def photo_url(design: Design) -> str | None:
    return f"/media/photos/{design.photo_filename}" if design.photo_filename else None


def subcategory_out(s: Subcategory) -> dict:
    return {"id": s.id, "category_id": s.category_id, "name": s.name, "description": s.description,
            "is_active": s.is_active, "sort_order": s.sort_order}


def design_list_item(d: Design, st: DesignState) -> dict:
    return {
        "id": d.id,
        "label": d.label,
        "name": d.name,
        "category": {"id": d.category.id, "name": d.category.name, "icon": d.category.icon},
        "subcategory": {"id": d.subcategory.id, "name": d.subcategory.name} if d.subcategory else None,
        "metal": d.metal.value,
        "purity": d.purity,
        "weight_g": float(d.weight_g) if d.weight_g is not None else None,
        "cost_price": money(d.cost_price),
        "selling_price": money(d.selling_price),
        "last_unit_cost": st.last_unit_cost,
        "min_stock": d.min_stock,
        "current_stock": st.current_stock,
        "status": st.status.value,
        "demand_class": st.demand.value,
        "sold_last_30d": st.sold_30d,
        "stock_value_cost": st.stock_value_cost,
        "photo_url": photo_url(d),
        "is_active": d.is_active,
        "updated_at": d.updated_at,
    }


def design_detail(d: Design, st: DesignState) -> dict:
    out = design_list_item(d, st)
    out.update(
        {
            "description": d.description,
            "supplier": d.supplier,
            "inflation_pct_override": float(d.inflation_pct_override) if d.inflation_pct_override is not None else None,
            "custom_fields": d.custom_fields or {},
            "velocity_30d": st.velocity_30d,
            "days_since_last_sale": st.days_since_last_sale,
            "first_movement_on": st.first_movement_on,
            "last_sale_on": st.last_sale_on,
            "created_at": d.created_at,
        }
    )
    return out


def design_mini(d: Design) -> dict:
    return {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d)}


def movement_out(m: StockMovement) -> dict:
    value = money((m.unit_price or 0) * m.quantity) if m.unit_price is not None else None
    return {
        "id": m.id,
        "design": design_mini(m.design),
        "type": m.type.value,
        "direction": "IN" if m.type in IN_TYPES else "OUT",
        "quantity": m.quantity,
        "unit_price": money(m.unit_price) if m.unit_price is not None else None,
        "value": value,
        "occurred_on": m.occurred_on,
        "note": m.note,
        "source": m.source.value,
        "created_by": {"id": m.creator.id, "display_name": m.creator.display_name} if m.creator else None,
        "created_at": m.created_at,
        "is_void": m.is_void,
        "voided_at": m.voided_at,
        "void_reason": m.void_reason,
    }


def category_card(c: Category, designs: list[Design], states: dict[int, DesignState]) -> dict:
    mine = [d for d in designs if d.category_id == c.id and d.is_active]
    sts = [states[d.id] for d in mine]
    return {
        "id": c.id,
        "name": c.name,
        "label_prefix": c.label_prefix,
        "icon": c.icon,
        "description": c.description,
        "is_active": c.is_active,
        "sort_order": c.sort_order,
        "inflation_pct_override": float(c.inflation_pct_override) if c.inflation_pct_override is not None else None,
        "subcategory_count": len([s for s in c.subcategories if s.is_active]),
        "subcategories": [{"id": s.id, "name": s.name} for s in c.subcategories if s.is_active],
        "design_count": len(mine),
        "total_pieces": sum(s.current_stock for s in sts),
        "stock_value_cost": money(sum(s.stock_value_cost for s in sts)),
        "in_stock_count": sum(1 for s in sts if s.status.value == "IN"),
        "out_of_stock_count": sum(1 for s in sts if s.status.value == "OUT"),
        "low_stock_count": sum(1 for s in sts if s.status.value == "LOW"),
        "dead_stock_count": sum(1 for s in sts if s.status.value == "DEAD"),
        "sold_last_30d": sum(s.sold_30d for s in sts),
    }
