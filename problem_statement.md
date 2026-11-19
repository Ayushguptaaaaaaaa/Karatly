# Problem Statement
### Kraftly — AI Accountant & Inventory Management System for Jewelers

---

## 1. Background: How a Jeweler's Stock Is Organized

1. A jeweler sells items across several **categories**, for example:
   - Necklaces
   - Anklets
   - Bangles
   - Bracelets
   - Earrings
   - Rings, Chains, Pendants, Nose pins, etc.
2. Each category has many **designs**. One jeweler might carry 10, 50 or 200 earring designs.
3. Every design has a **unique label (design code)**, such as `ER-1012`, which is physically tagged on the item.
4. Each label has its own **stock count (pieces)**. For example, in the Earrings category:

   | Label   | Pieces in stock | Status          |
   |---------|-----------------|-----------------|
   | ER-1012 | 13              | In stock        |
   | ER-1013 | 12              | In stock        |
   | ER-1014 | 4               | Low stock       |
   | ER-1015 | 0               | **Out of stock** |

5. Stock changes every day through sales, new purchases, returns and exchanges. The jeweler needs to know the position for **each label** across a **month** or a **quarter**.

---

## 2. Problem 1: Inventory Is Hard to Track at the Label Level

1. Stock is often kept in **Excel sheets, paper registers or generic software** that is not built for jewelry.
2. There is **no simple way** to:
   - Pick a category, enter how many designs it has, and record each design's label.
   - See at a glance how many pieces are left for **each label**.
   - Compare stock **month on month** or **quarter on quarter**.
3. Out-of-stock designs are **noticed late**, sometimes only when a customer asks for them, which means lost sales.
4. Slow-moving designs **sit in stock for months** and tie up money, but nobody flags them in time.
5. Records from different people, sheets and registers often **don't match**, so someone has to reconcile them by hand.

---

## 3. Problem 2: Heavy Dependence on a Large Accounting Team

1. A typical jeweler employs **4 to 5 human accountants** just to manage stock and purchase planning.
2. Their work is **repetitive and manual**:
   - Open the inventory system (Excel or software).
   - Go through every label and count what is left.
   - List which labels are **out of stock (nil)** and which are **running low**.
   - Report to the owner: *"These labels are finished, we need to buy them."*
3. They **estimate purchase costs by hand**:
   - Last month's cost of one piece = ₹100
   - Add roughly 5% inflation → ₹105 per piece
   - Need 10 pieces → **₹1,050** needed for that label
   - Repeat this for every label that needs restocking.
4. They give **insights from experience**:
   - *"This label is in high demand, buy more of it."*
   - *"This label is slow, buy less or skip it."*
5. That insight depends on **each accountant's memory and judgment**, so it is inconsistent and leaves with the person when they leave.
6. The owner pays **4 to 5 salaries** for work that is mostly counting, calculating and summarising.

---

## 4. Current Working (Before Implementation)

| Step | What happens today | Who does it | Pain point |
|------|-------------------|-------------|------------|
| 1 | Sales and purchases are written into Excel or a register | Staff / accountants | Manual entry, frequent mistakes |
| 2 | At month or quarter end, accountants go through every label | 4–5 accountants | Slow, takes days |
| 3 | They list out-of-stock and low-stock labels | Accountants | Easy to miss labels |
| 4 | They work out purchase cost (last price + ~5% inflation × quantity) | Accountants | Manual arithmetic, inconsistent assumptions |
| 5 | They judge which designs sell fast or slow | Senior accountant | Based on gut feeling and memory |
| 6 | They prepare a report and present it to the owner | Accountants | Plain tables, no charts, hard to read |
| 7 | The owner decides what to buy and how much | Owner | Decides on incomplete or late information |

**Result:** high staff cost, slow reporting, human error, missed sales on out-of-stock designs and money stuck in slow-moving stock.

---

## 5. Working After Implementation

| Step | What happens with our application | Who does it | Benefit |
|------|-----------------------------------|-------------|---------|
| 1 | The jeweler sets up categories, designs and labels once, in a simple interface | Owner / 1 accountant | One-time, guided setup |
| 2 | Sales, purchases and returns are recorded against each label | Staff / accountant | Stock updates instantly |
| 3 | The system shows live stock for every label, by month and by quarter | Automatic | No manual counting |
| 4 | Out-of-stock and low-stock labels are flagged automatically | Automatic | Nothing gets missed |
| 5 | Purchase cost is worked out automatically (last cost + inflation × quantity) | Automatic | Consistent, error-free |
| 6 | The **AI Accountant** points out high-demand and low-demand designs and suggests quantities | AI | Insight based on data, not memory |
| 7 | Charts and dashboards show trends, top sellers, slow movers and stock value | Automatic | Easy to read and act on |
| 8 | The 1–2 remaining accountants review the AI's insights and present them to the owner | 1–2 accountants | They check and advise instead of counting |
| 9 | **The owner makes the final decision** | Owner | Better decisions, faster |

> **Important:** the AI **does not make decisions**. It counts, calculates, analyses and suggests. Humans approve.

---

## 6. Before vs After at a Glance

| Area | Before | After |
|------|--------|-------|
| Accountants needed | 4–5 | **1–2** |
| Stock check per label | Manual, takes days | **Instant** |
| Out-of-stock detection | Late, often missed | **Automatic alerts** |
| Purchase cost estimate | Hand-calculated | **Auto-calculated** |
| Demand insights | Gut feeling | **AI, based on data** |
| Reports | Plain tables | **Charts and dashboards** |
| Month and quarter comparison | Difficult | **One click** |
| Knowledge retention | Leaves with the staff member | **Stays in the system** |

---

## 7. Goals

1. **Simplify inventory management** for jewelers: category → design → label → stock.
2. **Automate the repetitive work** of human accountants: counting, flagging and costing.
3. **Give clear visual insights** (charts, graphs, dashboards) to the remaining accountants.
4. **Provide an AI Accountant** that thinks like an experienced accountant and gives insights, **without taking decisions**.
5. **Cut operating cost** by reducing the accounting team from 4–5 people to 1–2.

---

## 8. Scope

- **Phase 1 (Demo):** a working showcase of inventory management, automatic insights and the AI Accountant on sample data.
- **Phase 2 (Final product):** a production-ready application built on the demo, using the technology choices to be decided later.
