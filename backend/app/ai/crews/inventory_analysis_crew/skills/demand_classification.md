# Skill: Demand classification
The system computes demand classes from sales velocity (pieces sold per 30 days over the last 90 days):
- HIGH: top 20% velocity in its category, or sold out while selling 3+ in the last 30 days.
- STEADY: middle of the range.
- LOW: bottom 20% velocity, or no sales recently but not yet dead.
- DEAD: no sale for dead_stock_days or more.
- NEW: added less than 14 days ago with no sales yet.

Indian jewellery seasonality:
- Oct–Nov: Dhanteras and Diwali, the strongest gold-buying period.
- Nov–Feb: wedding season; necklaces, bangles, sets and mangalsutras sell more.
- Apr–May: Akshaya Tritiya.
- Jun–Aug: monsoon, usually slower.
Do not call a design LOW only because it is off-season; mention the season instead.
