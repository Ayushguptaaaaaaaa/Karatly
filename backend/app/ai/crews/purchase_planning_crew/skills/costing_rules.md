# Skill: Costing rules
- Expected cost per piece = last purchase cost × (1 + inflation % / 100), rounded to paise.
- Inflation comes from the design override, else the category override, else the shop default.
- Line total = expected cost per piece × quantity.
- Always use calculate_purchase_cost; never compute these yourself.
- Write rupee totals with Indian grouping (₹1,05,000) or lakh/crore (₹1.05 L).
