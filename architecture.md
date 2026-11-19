# Architecture
### Kraftly — AI Accountant & Inventory Management System for Jewelers (POC)

> **Implementation detail now lives in [backend/backend_plan.md](backend/backend_plan.md) and [frontend/frontend_plan.md](frontend/frontend_plan.md); where they differ from this file, the plans win.** Main updates: Owner/Admin username-password logins, subcategories, the shop starts blank, a live dashboard over SSE, `mantine-datatable` instead of Mantine React Table, and month/quarter periods computed on the fly (Indian financial-year quarters).
>
> Companion to [problem_statement.md](problem_statement.md) and [solution.md](solution.md).
> Scope: **POC, run locally**. Deployment and production hardening are covered only as a "path to production" at the end.

---

## 1. Tech Stack

| Layer | Choice |
|-------|--------|
| Frontend | React + TypeScript + Vite, Mantine (UI, charts, forms), Mantine React Table, TanStack Query, React Router |
| API client | Typed client generated from FastAPI's OpenAPI schema (`openapi-typescript` / `orval`) |
| Backend | Python, **FastAPI** |
| AI / agents | **CrewAI**: Crews (agents + tasks in YAML), Flows (orchestration), custom Tools, Skill files |
| LLM | **Google Gemini, free tier** (API key from Google AI Studio): **Gemini 3.6 Flash** as primary, Gemini 3.1 Flash Lite as quota fallback, called through CrewAI's `LLM` wrapper. Swappable via `.env`; Claude Sonnet / Haiku 5.5 are candidates for the client demo and production |
| Database | SQLite for the POC, accessed through SQLAlchemy (swap to PostgreSQL later without code changes) |
| Validation / schemas | Pydantic (API schemas and structured agent outputs) |
| Background jobs | FastAPI background tasks + a `jobs` table (POC) |
| Live progress | Server-Sent Events (SSE) |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND  (React + Mantine)                     │
│  Dashboard · Categories · Labels · Stock Entry · Period View · Reorder  │
│  Reports · AI Accountant (insights + chat) · Approvals · Settings       │
└───────────────┬───────────────────────────────────────▲─────────────────┘
                │ REST (JSON)                           │ SSE (job progress,
                ▼                                       │      chat answers)
┌─────────────────────────────────────────────────────────────────────────┐
│                         API LAYER  (FastAPI routers)                    │
│  /categories /designs /stock /periods /alerts /reports /purchase-plans  │
│  /insights /chat /jobs /settings                                        │
└───────┬───────────────────────────────────────────────┬─────────────────┘
        │                                               │ starts job
        ▼                                               ▼
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│   SERVICE LAYER (pure Python)│        │   AI LAYER (CrewAI)              │
│   Deterministic business     │◄───────│                                  │
│   logic: "the numbers"       │ tools  │   Flows ──► Crews ──► Agents     │
│                              │ call   │              │         │         │
│ · inventory_service          │services│           tasks.yaml agents.yaml │
│ · period_service             │(read-  │                        + skills/ │
│ · costing_service            │ only)  │   Tools (read-only wrappers      │
│ · alert_service              │        │   around services)               │
│ · metrics_service            │        │                                  │
│ · report_service             │        │   Output: structured insights    │
│ · purchase_plan_service      │        │   (Pydantic) ──► saved to DB     │
│ · job_service                │        └───────────────┬──────────────────┘
└──────────────┬───────────────┘                        │
               ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     DATA LAYER  (SQLAlchemy → SQLite)                   │
│  categories · designs · stock_movements · periods · settings · users    │
│  purchase_plans · purchase_plan_items · jobs · insights · chat · audit  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Design Principles

1. **Code calculates, AI interprets.**
   Stock counts, closing balances, costs, budgets and sales velocity are calculated by the **service layer** in plain Python. Agents never compute or guess these numbers. They call tools that return exact figures, then reason, explain and recommend.

2. **Agents are read-only.**
   Every CrewAI tool is a read-only wrapper over a service. No agent can create a stock entry, change a cost or approve a purchase. Agent output is stored as an *insight* or a *draft* purchase plan that a human reviews.

3. **Humans approve.**
   AI draft → accountant review → owner approval. Every state change goes in the audit log.

4. **Structured outputs.**
   Each CrewAI task declares a Pydantic `output_pydantic` model, so results are typed JSON that can be saved, charted and shown in the UI, not free text.

5. **Long work runs as a job.**
   Crew runs take seconds to minutes, so they run as background jobs. The frontend gets a `job_id` immediately and follows progress over SSE.

6. **Configuration over code.**
   Agents and tasks live in YAML, and domain rules live in skill files. Changing prompts or business rules does not require touching Python.

---

## 4. Backend Folder Structure

```
backend/
├── pyproject.toml
├── .env.example                      # LLM keys/model, DB URL, settings defaults
├── app/
│   ├── main.py                       # FastAPI app, router registration, CORS
│   ├── core/
│   │   ├── config.py                 # Settings loaded from .env (pydantic-settings)
│   │   ├── database.py               # Engine, session, Base
│   │   └── events.py                 # In-process event bus for SSE progress
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── category.py
│   │   ├── design.py
│   │   ├── stock_movement.py
│   │   ├── period.py
│   │   ├── purchase_plan.py
│   │   ├── insight.py
│   │   ├── job.py
│   │   ├── chat.py
│   │   ├── setting.py
│   │   └── audit_log.py
│   │
│   ├── schemas/                      # Pydantic request/response models
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── categories.py
│   │       ├── designs.py
│   │       ├── stock.py
│   │       ├── periods.py
│   │       ├── alerts.py
│   │       ├── reports.py
│   │       ├── purchase_plans.py
│   │       ├── insights.py
│   │       ├── chat.py
│   │       ├── jobs.py
│   │       └── settings.py
│   │
│   ├── services/                     # Deterministic business logic (no LLM)
│   │   ├── inventory_service.py      # Categories, designs, labels, stock movements
│   │   ├── period_service.py         # Opening/closing per label, period close & lock
│   │   ├── metrics_service.py        # Sales velocity, turnover, dead stock, trends
│   │   ├── alert_service.py          # In / low / out / dead stock status
│   │   ├── costing_service.py        # Last cost × (1 + inflation%) × qty, budgets
│   │   ├── purchase_plan_service.py  # Draft → review → approve workflow
│   │   ├── report_service.py         # Chart datasets, PDF/Excel export
│   │   ├── job_service.py            # Job lifecycle + progress events
│   │   └── audit_service.py
│   │
│   └── ai/                           # ───────── CrewAI ─────────
│       ├── runner.py                 # Runs flows/crews as jobs, wires callbacks → SSE
│       ├── llm.py                    # LLM factory from config
│       ├── skill_loader.py           # Loads skills/*.md into agent context
│       │
│       ├── tools/                    # Shared read-only CrewAI tools
│       │   ├── stock_tools.py
│       │   ├── sales_tools.py
│       │   ├── costing_tools.py
│       │   └── report_tools.py
│       │
│       ├── outputs/                  # Pydantic models for task outputs
│       │   ├── stock_position.py
│       │   ├── demand.py
│       │   ├── purchase_plan.py
│       │   ├── anomaly.py
│       │   └── summary.py
│       │
│       ├── flows/
│       │   └── period_insights_flow.py   # Orchestrates the month/quarter-end run
│       │
│       └── crews/
│           ├── inventory_analysis_crew/
│           │   ├── config/
│           │   │   ├── agents.yaml
│           │   │   └── tasks.yaml
│           │   ├── skills/
│           │   │   ├── stock_status_rules.md
│           │   │   └── demand_classification.md
│           │   └── crew.py
│           │
│           ├── purchase_planning_crew/
│           │   ├── config/
│           │   │   ├── agents.yaml
│           │   │   └── tasks.yaml
│           │   ├── skills/
│           │   │   ├── reorder_quantity_rules.md
│           │   │   └── costing_rules.md
│           │   └── crew.py
│           │
│           ├── audit_crew/
│           │   ├── config/
│           │   │   ├── agents.yaml
│           │   │   └── tasks.yaml
│           │   ├── skills/
│           │   │   └── anomaly_checks.md
│           │   └── crew.py
│           │
│           ├── reporting_crew/
│           │   ├── config/
│           │   │   ├── agents.yaml
│           │   │   └── tasks.yaml
│           │   ├── skills/
│           │   │   └── report_style_guide.md
│           │   └── crew.py
│           │
│           └── assistant_crew/
│               ├── config/
│               │   ├── agents.yaml
│               │   └── tasks.yaml
│               ├── skills/
│               │   └── answering_guidelines.md
│               └── crew.py
│
├── data/
│   └── seed/                         # Demo jewelry shop: categories, labels, 12 months of movements
└── tests/
    ├── services/                     # Unit tests for the numbers (must be exact)
    └── ai/                           # Tool tests + crew smoke tests
```

---

## 5. AI Layer (CrewAI)

### 5.1 Building blocks

| CrewAI concept | How we use it |
|----------------|---------------|
| **Agent** (`agents.yaml`) | A role with a goal and backstory, e.g. *Inventory Analyst* or *Cost Accountant* |
| **Task** (`tasks.yaml`) | One unit of work with a description, expected output and Pydantic output model |
| **Crew** (`crew.py`) | Agents + tasks for one job area, using the `@CrewBase` pattern |
| **Tool** (`ai/tools/`) | Read-only Python functions agents call to get exact data from services |
| **Skill** (`skills/*.md`) | Domain rules and know-how for an agent (thresholds, formulas, tone), loaded into the agent's context |
| **Flow** (`ai/flows/`) | Chains crews into a pipeline with state (e.g. the month-end run) |

### 5.2 Crews, agents, tasks, tools and skills

| Crew | Agent(s) | Tasks | Tools used | Skills |
|------|----------|-------|------------|--------|
| **inventory_analysis_crew** | `stock_analyst`: Inventory Analyst<br>`demand_analyst`: Demand & Trend Analyst | `analyse_stock_position`: status of every label, out/low/dead stock<br>`classify_demand`: high / steady / low / dead per label, with reasons and seasonal trends | `get_stock_snapshot`, `get_stock_alerts`, `get_sales_velocity`, `compare_periods`, `get_label_history` | `stock_status_rules.md`, `demand_classification.md` |
| **purchase_planning_crew** | `procurement_planner`: Purchase Planner<br>`cost_accountant`: Cost Accountant | `recommend_reorders`: which labels to buy and how many, with reasons<br>`estimate_budget`: per-label cost and total budget by category and supplier | `get_stock_alerts`, `get_sales_velocity`, `get_cost_history`, `calculate_purchase_cost`, `get_inflation_settings` | `reorder_quantity_rules.md`, `costing_rules.md` |
| **audit_crew** | `stock_auditor`: Stock Auditor | `detect_anomalies`: negative stock, unusual drops, cost jumps, count mismatches | `get_anomaly_candidates`, `get_label_history`, `get_cost_history` | `anomaly_checks.md` |
| **reporting_crew** | `report_writer`: Accounts Report Writer | `write_period_summary`: owner-friendly summary of the period, built from the other crews' outputs | `get_period_kpis`, `compare_periods` | `report_style_guide.md` |
| **assistant_crew** | `accountant_assistant`: AI Accountant (chat) | `answer_question`: answers a user question from data, optionally with a chart spec | All read-only tools | `answering_guidelines.md` |

### 5.3 Example: `inventory_analysis_crew/config/agents.yaml`

```yaml
stock_analyst:
  role: >
    Inventory Analyst for a jewelry store
  goal: >
    Give an accurate, label-by-label picture of stock for {period_label},
    highlighting out-of-stock, low-stock and dead-stock designs.
  backstory: >
    You have years of experience managing jewelry inventory across categories
    like necklaces, bangles and earrings. You never guess numbers: you always
    use the tools to fetch exact stock figures and only interpret them.

demand_analyst:
  role: >
    Demand & Trend Analyst for a jewelry store
  goal: >
    Classify every design label by demand (high, steady, low, dead) for
    {period_label} and explain the reasoning using sales history and seasonality.
  backstory: >
    You understand jewelry buying patterns in India, including festive and
    wedding seasons. You base every conclusion on sales data from the tools.
```

### 5.4 Example: `inventory_analysis_crew/config/tasks.yaml`

```yaml
analyse_stock_position:
  description: >
    For period {period_label} ({period_start} to {period_end}), fetch the stock
    snapshot and alerts for all categories. Identify out-of-stock, low-stock
    and dead-stock labels. Follow the rules in your stock status skill.
  expected_output: >
    A structured stock position: counts per status, list of affected labels
    with category, closing stock and a one-line note for each.
  agent: stock_analyst

classify_demand:
  description: >
    Using sales velocity for {period_label} and the previous periods, classify
    each label as high, steady, low or dead demand. Mention seasonal effects
    where visible. Follow the thresholds in your demand classification skill.
  expected_output: >
    A list of labels with demand class, key numbers (units sold, velocity,
    change vs previous period) and a short reason.
  agent: demand_analyst
  context:
    - analyse_stock_position
```

### 5.5 Example: `inventory_analysis_crew/crew.py`

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from app.ai.llm import get_llm
from app.ai.skill_loader import load_skills
from app.ai.tools.stock_tools import GetStockSnapshot, GetStockAlerts, GetLabelHistory
from app.ai.tools.sales_tools import GetSalesVelocity, ComparePeriods
from app.ai.outputs.stock_position import StockPosition
from app.ai.outputs.demand import DemandReport


@CrewBase
class InventoryAnalysisCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _with_skills(self, name: str, skills: list[str]) -> dict:
        cfg = dict(self.agents_config[name])
        cfg["backstory"] += "\n\n" + load_skills(__file__, skills)  # see 5.6
        return cfg

    @agent
    def stock_analyst(self) -> Agent:
        return Agent(
            config=self._with_skills("stock_analyst", ["stock_status_rules.md"]),
            tools=[GetStockSnapshot(), GetStockAlerts(), GetLabelHistory()],
            llm=get_llm(),
        )

    @agent
    def demand_analyst(self) -> Agent:
        return Agent(
            config=self._with_skills("demand_analyst", ["demand_classification.md"]),
            tools=[GetSalesVelocity(), ComparePeriods(), GetLabelHistory()],
            llm=get_llm(),
        )

    @task
    def analyse_stock_position(self) -> Task:
        return Task(config=self.tasks_config["analyse_stock_position"],
                    output_pydantic=StockPosition)

    @task
    def classify_demand(self) -> Task:
        return Task(config=self.tasks_config["classify_demand"],
                    output_pydantic=DemandReport)

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential)
```

> Illustrative only: exact skill-injection wiring is decided during implementation (see 5.6).

### 5.6 Skill files

Each crew has a `skills/` folder of markdown files holding **domain rules and know-how** that would otherwise be hard-coded in prompts. Accountants or business analysts can edit them without touching Python.

**Example: `inventory_analysis_crew/skills/demand_classification.md`**

```markdown
# Skill: Demand Classification

## Inputs (from tools)
- units_sold in current period, units_sold in previous 3 periods
- sales_velocity = units_sold / days_in_period
- days_since_last_sale

## Rules
- HIGH:   velocity in top 20% of the category OR sold out within the period
- STEADY: velocity between 20th and 80th percentile
- LOW:    velocity in bottom 20% and days_since_last_sale < dead_stock_days
- DEAD:   days_since_last_sale >= dead_stock_days (from settings, default 90)

## Seasonality
- Oct–Nov (Dhanteras/Diwali) and Nov–Feb (wedding season): expect higher sales
  of bangles, necklaces and sets. Flag if a label is LOW only because it is off-season.

## Output rules
- Always quote the numbers you used.
- Never recommend a purchase. That belongs to the purchase planning crew.
```

**Loading:** `skill_loader.load_skills(crew_file, [names])` reads the markdown and appends it to the agent's backstory/context when the agent is built. If the CrewAI version in use offers native skill or knowledge-source support, the same files can be plugged into it with no change to their content.

### 5.7 Tools (shared, read-only)

| Tool | Returns | Backed by |
|------|---------|-----------|
| `get_stock_snapshot(period, category?)` | Opening / in / out / closing per label | `period_service` |
| `get_stock_alerts(period?)` | Out / low / dead stock labels | `alert_service` |
| `get_label_history(label)` | All movements + cost history for one label | `inventory_service` |
| `get_sales_velocity(period, category?)` | Units sold, velocity, percentile per label | `metrics_service` |
| `compare_periods(p1, p2)` | Delta per label / category | `metrics_service` |
| `get_cost_history(label)` | Purchase cost over time | `costing_service` |
| `get_inflation_settings()` | Global / category / label inflation % | `costing_service` |
| `calculate_purchase_cost(label, qty)` | Expected unit cost + total (exact) | `costing_service` |
| `get_anomaly_candidates(period)` | Rule-detected suspicious records | `metrics_service` |
| `get_period_kpis(period)` | Dashboard KPIs | `report_service` |

All tools are CrewAI `BaseTool` subclasses with Pydantic `args_schema`. They return compact JSON so the LLM context stays small.

### 5.8 Flow: month/quarter-end insights run

```
PeriodInsightsFlow (CrewAI Flow, state = period + accumulated outputs)

 @start  prepare_context          → validate period, load settings, compute KPIs (Python)
   │
 @listen run_inventory_analysis   → inventory_analysis_crew  → StockPosition, DemandReport
   │
   ├──► @listen run_audit         → audit_crew               → AnomalyReport
   │
   └──► @listen run_purchase_plan → purchase_planning_crew   → PurchasePlanDraft
             │
 @listen(and_(run_audit, run_purchase_plan))
         run_report               → reporting_crew           → PeriodSummary
   │
 @listen persist                  → save insights + draft purchase plan (status = DRAFT)
```

Each step sends progress events (`step_started`, `step_completed`, `failed`) to the job, which the frontend shows live.

---

## 6. Key Runtime Flows

### 6.1 Recording stock (no AI)

```
User (Stock Entry screen)
  → POST /stock/movements {label: "ER-1012", type: "SALE", qty: 2}
  → inventory_service validates (label exists, stock won't go negative, period not locked)
  → stock_movements row + audit_log row
  → 201 + updated stock for the label
  → TanStack Query refreshes dashboard / label views
```

### 6.2 Generating period insights (AI, async job)

```
Accountant clicks "Generate insights for Nov 2026"
  → POST /insights/runs {period_id}
  → job_service creates job (QUEUED) → returns {job_id}
  → runner starts PeriodInsightsFlow in background
  → Frontend opens GET /jobs/{job_id}/events (SSE)
        ← step_started: inventory_analysis
        ← step_completed: inventory_analysis
        ← step_started: purchase_planning ...
        ← job_completed {insight_run_id}
  → Frontend loads GET /insights/runs/{id} → shows summary, demand, anomalies
  → Draft purchase plan appears in Reorder & Budget screen
```

### 6.3 Purchase plan approval (human)

```
DRAFT (AI-generated)
  → accountant edits quantities/costs, adds notes   PATCH /purchase-plans/{id}
  → accountant submits                             POST  /purchase-plans/{id}/submit   → IN_REVIEW
  → owner approves / rejects lines                 POST  /purchase-plans/{id}/approve  → APPROVED
  → export purchase order                          GET   /purchase-plans/{id}/export
(each transition → audit_log)
```

### 6.4 Chat with the AI Accountant

```
User: "Which earrings should I reorder this month?"
  → POST /chat/messages {session_id, text}  → returns {job_id}
  → assistant_crew runs: agent calls get_stock_alerts + get_sales_velocity (category=Earrings)
  → SSE: thinking / tool_called / answer
  → answer saved to chat history, optionally with a chart spec the UI renders
```

---

## 7. Data Model

| Entity | Key fields |
|--------|------------|
| **Category** | id, name, label_prefix, is_active |
| **Design** | id, category_id, label (unique), name, photo_url, metal, purity, weight_g, cost_price, selling_price, supplier, min_stock, custom_fields (JSON), is_active |
| **StockMovement** | id, design_id, type (OPENING, PURCHASE, SALE, CUSTOMER_RETURN, SUPPLIER_RETURN, ADJUSTMENT), qty, unit_cost, reason, created_by, created_at |
| **Period** | id, type (MONTH / QUARTER / CUSTOM), start_date, end_date, status (OPEN / CLOSED / LOCKED) |
| **Setting** | key, value (inflation %, low-stock default, dead_stock_days, category overrides, …) |
| **PurchasePlan** | id, period_id, status (DRAFT, IN_REVIEW, APPROVED, REJECTED), total_budget, source (AI / MANUAL), notes |
| **PurchasePlanItem** | id, plan_id, design_id, suggested_qty, final_qty, expected_unit_cost, total_cost, ai_reason, decision |
| **Job** | id, type (INSIGHTS_RUN, CHAT), status (QUEUED, RUNNING, SUCCEEDED, FAILED), progress (JSON), error, started_at, finished_at |
| **InsightRun** | id, period_id, job_id, stock_position (JSON), demand (JSON), anomalies (JSON), summary (JSON), created_at |
| **ChatSession / ChatMessage** | id, session_id, role, content, data (JSON chart spec), job_id |
| **User** | id, name, role (OWNER, ACCOUNTANT, STAFF) |
| **AuditLog** | id, user_id, entity, entity_id, action, before (JSON), after (JSON), at |

Stock on hand is **derived** from movements (sum by label up to a date) rather than stored as a mutable counter. That keeps history exact for any month or quarter. Period close can save a snapshot to keep reads fast.

---

## 8. API Overview

| Area | Endpoints |
|------|-----------|
| Categories | `GET/POST /categories`, `PATCH/DELETE /categories/{id}` |
| Designs | `GET/POST /designs`, `POST /designs/bulk` (create N labels), `POST /designs/import` (Excel), `GET/PATCH /designs/{id}`, `GET /designs/by-label/{label}` |
| Stock | `POST /stock/movements`, `GET /stock/movements?label=&period=`, `GET /stock/current?category=` |
| Periods | `GET/POST /periods`, `GET /periods/{id}/stock`, `POST /periods/{id}/close` |
| Alerts | `GET /alerts?status=low|out|dead` |
| Reports | `GET /reports/kpis`, `GET /reports/{chart_name}?period=`, `GET /reports/export?format=pdf|xlsx` |
| Purchase plans | `GET/POST /purchase-plans`, `PATCH /purchase-plans/{id}`, `POST .../submit`, `POST .../approve`, `GET .../export` |
| Insights | `POST /insights/runs`, `GET /insights/runs`, `GET /insights/runs/{id}`, `GET /insights/latest` |
| Chat | `POST /chat/sessions`, `POST /chat/messages`, `GET /chat/sessions/{id}` |
| Jobs | `GET /jobs/{id}`, `GET /jobs/{id}/events` (SSE) |
| Settings | `GET/PATCH /settings` |

FastAPI auto-generates OpenAPI docs at `/docs`. The frontend's typed client is generated from it.

---

## 9. Frontend Architecture

```
frontend/
├── src/
│   ├── api/            # Generated typed client + TanStack Query hooks
│   ├── app/            # Router, layout shell (sidebar + header), Mantine theme
│   ├── pages/
│   │   ├── Dashboard/
│   │   ├── Categories/
│   │   ├── Designs/          # list + bulk "add N labels" form
│   │   ├── LabelDetail/
│   │   ├── StockEntry/
│   │   ├── PeriodView/
│   │   ├── Reorder/          # draft purchase plan, edit, submit
│   │   ├── Reports/
│   │   ├── AIAccountant/     # insight feed + chat
│   │   ├── Approvals/
│   │   └── Settings/
│   ├── components/     # KPI cards, StatusBadge, charts, DataTable, JobProgress
│   └── hooks/          # useJobEvents (SSE), usePeriod, etc.
└── vite.config.ts      # Dev proxy → FastAPI
```

- **Server state:** TanStack Query (caching and refetching after mutations).
- **Live updates:** `useJobEvents(jobId)` hook built on `EventSource`.
- **Charts:** Mantine Charts fed by `/reports/*` datasets. AI chat answers can include a chart spec rendered by the same components.

---

## 10. Configuration (`.env`)

```
DATABASE_URL=sqlite:///./data/jeweler.db
# LLM: Gemini free tier for the POC (verify exact IDs with the models-list API call)
LLM_MODEL=gemini/gemini-3.6-flash          # most capable free model; free tier 5 RPM / 20 RPD
LLM_FALLBACK_MODEL=gemini/gemini-3.1-flash-lite   # used automatically on quota (429) or overload (503) errors (15 RPM / 500 RPD)
GEMINI_API_KEY=...
LLM_MAX_RPM=4                  # stay under the 5 RPM free-tier limit
AGENT_MAX_ITER=5               # cap tool-call loops per agent to save daily quota
# Alternatives (switch by changing LLM_MODEL + key):
# LLM_MODEL=anthropic/claude-sonnet-5-5   ANTHROPIC_API_KEY=...
# LLM_MODEL=ollama/qwen3:8b               LLM_BASE_URL=http://localhost:11434
DEFAULT_INFLATION_PCT=5
DEFAULT_MIN_STOCK=3
DEAD_STOCK_DAYS=90
CORS_ORIGINS=http://localhost:5173
```

---

## 11. POC Decisions vs Path to Production

| Concern | POC | Production (later) |
|---------|-----|--------------------|
| Database | SQLite | PostgreSQL + migrations (Alembic) |
| Background jobs | FastAPI background tasks, in-process | Task queue (Celery / RQ / arq) + Redis |
| Live progress | In-process event bus → SSE | Redis pub/sub → SSE / WebSocket |
| Auth | Simple role switch / single user | JWT / OAuth, role-based permissions |
| Multi-tenant (many jewelers) | Single shop | Tenant isolation per jeweler |
| Observability | Logs | Tracing of agent runs, cost per run, error alerts |
| Deployment | Local (`uvicorn` + `vite dev`) | Containers + managed hosting |
| LLM | Gemini free tier: rate-limited, and free-tier data may be used by Google to improve its models, so **sample data only** | Paid model with business data-privacy terms (e.g. Claude via API) |
| Flow concurrency | Crews run one after another, so the free-tier rate limit isn't hit (audit and purchase planning run in sequence, not in parallel) | Parallel crew steps (as in 5.8) |
| LLM request budget | Free tier is limited per model per day. Primary Gemini 3.6 Flash allows only 20/day, so `llm.py` falls back to Gemini 3.1 Flash Lite (500/day) on quota errors (HTTP 429). Every agent step and tool round-trip is one request, so: Python precomputes metrics, agents get compact tool output, `max_iter` is capped, insight runs are cached in the DB, and dev/tests use recorded or mocked LLM responses | No daily cap concerns |
| LLM cost control | None | Caching, token budgets, cheaper model for simple tasks |

---

## 12. Open Decisions

1. ~~LLM provider~~: **Decided: Gemini free tier for the POC.** Still open: which model for the client demo and production, and whether to use one model for all agents or a stronger one for planning/reporting and a cheaper one for chat.
2. Whether demand classification percentiles should be fully computed in code (most consistent) with the agent only explaining them, or partly judged by the agent.
3. Chat: final answer only, or token-by-token streaming.
4. Seed data: size and realism of the demo shop (categories, labels, months of history).
