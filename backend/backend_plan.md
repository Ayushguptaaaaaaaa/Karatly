# Backend Plan: Kraftly — AI Accountant for Jewellers (POC)

> **Audience:** the engineer or AI model implementing the backend. Follow this document **exactly and in order**.
> **Related docs:** `../problem_statement.md`, `../solution.md`, `../architecture.md` (high level), `../frontend/frontend_plan.md` (the UI that consumes this API).
> Where this plan and `architecture.md` differ, **this plan wins**. It reflects the owner's later decisions: owner/admin logins, subcategories, the shop starts blank, live dashboard, and the Gemini free tier.

---

## 0. How to Use This Document

1. Build in the **phases of Section 17**, in order. Do not start a phase until the previous phase's acceptance checks pass.
2. Names given here are **contracts** shared with the frontend: endpoints, JSON field names, enum values, file paths. Do not rename them.
3. **Never** commit `backend/.env`. It already exists with real values. Create `backend/.env.example` with the same keys and placeholder values.
4. All numbers (stock, money, costs, budgets) are calculated in **Python services**. The AI only **reads and explains** them (Section 11). Never let AI output change data without passing through a service that re-validates and recalculates.
5. If a library API differs from what is written here (CrewAI changes quickly), keep the **behaviour** described here and adapt the call. Note the difference in `backend/README.md`.
6. Windows is the development machine (PowerShell). Every command in this plan is given for PowerShell.

---

## 1. What the Backend Must Do (Summary)

- Serve a REST API under **`/api/v1`** for a React frontend running at `http://localhost:5173`.
- Provide **username/password login** for two roles: **OWNER** (`owner`/`owner`) and **ADMIN** (`admin`/`admin`).
- Let users build the shop's inventory **from a blank state**: categories → subcategories → designs (unique labels such as `ER-1012`) → stock.
- Record every stock change as a **movement** (sale, new stock, return, correction) that is easy to **undo**.
- Calculate stock for **any month or quarter** (Indian financial year by default), with alerts (low, out, dead stock).
- Feed a **live dashboard** (an at-a-glance view). Every change bumps a `data_version` and is pushed to the frontend over **Server-Sent Events (SSE)**.
- Run an **AI Accountant** (CrewAI + Gemini) that writes a full **Insights report** (conclusion, demand, risks, anomalies, purchase plan), and a **chatbot** that answers the owner's or admin's questions from real data.
- Generate **purchase plans** (cost = last cost × (1 + inflation %)) that the owner approves, then optionally "receive" into stock.
- Stay inside the **Gemini free tier** (rate limits, automatic fallback model, rule-based fallback, mock mode).

---

## 2. Tech Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | **Python 3.12** (3.13 also OK) | CrewAI supports Python ≥3.10, <3.14. The machine has 3.13. Prefer `uv` to create a 3.12 venv |
| Package/env manager | **uv** (installed, v0.12) | `pip` works too |
| Web framework | **FastAPI** + **uvicorn[standard]** | |
| ORM | **SQLAlchemy 2.x** (typed `Mapped[...]`) | Sync engine (simpler with CrewAI threads) |
| DB | **SQLite** file `backend/data/jeweler.db` | WAL mode, `check_same_thread=False` |
| Validation | **Pydantic v2**, **pydantic-settings** | |
| Auth | **bcrypt** (password hashing), **PyJWT** (tokens) | Do **not** use passlib |
| AI | **crewai** (+ Gemini provider support) | Install `crewai`. If constructing a `gemini/...` LLM fails for a missing provider, install `crewai[google-genai]` (or `litellm`) and retry |
| SSE | **sse-starlette** | `EventSourceResponse` |
| Uploads | **python-multipart** | Photos + Excel import |
| Excel | **openpyxl** | Import template, import, exports |
| Tests | **pytest**, **httpx** (FastAPI `TestClient`) | |
| Lint (optional) | ruff | |

`requirements.txt` (unpinned first; after a successful install run `uv pip freeze > requirements.lock.txt`):

```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
pydantic>=2
pydantic-settings
crewai
bcrypt
pyjwt
python-multipart
sse-starlette
openpyxl
python-dateutil
tzdata
pytest
httpx
```

Setup commands (PowerShell, from `backend/`):

```powershell
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 3. Folder Structure (create exactly this)

```
backend/
├── backend_plan.md            # this file
├── .env                       # EXISTS: real secrets, never commit
├── .env.example               # same keys, placeholder values
├── requirements.txt
├── README.md                  # how to run, test, reset, load demo data
├── data/                      # created at runtime (db + photos), gitignored
│   └── photos/
├── app/
│   ├── __init__.py
│   ├── main.py                # app factory, routers, CORS, static /media, startup
│   ├── core/
│   │   ├── config.py          # Settings (pydantic-settings) reading .env
│   │   ├── database.py        # engine, SessionLocal, Base, get_db, sqlite pragmas
│   │   ├── security.py        # hash/verify password, create/decode JWT
│   │   ├── deps.py            # get_current_user, require_roles(...)
│   │   ├── errors.py          # AppError + exception handlers (uniform error JSON)
│   │   ├── events.py          # EventBus (thread-safe pub/sub for SSE)
│   │   └── clock.py           # today() / now() in Asia/Kolkata
│   ├── models/                # SQLAlchemy models (Section 5)
│   │   ├── __init__.py        # import all models
│   │   ├── user.py
│   │   ├── category.py        # Category, Subcategory
│   │   ├── design.py
│   │   ├── stock_movement.py
│   │   ├── setting.py
│   │   ├── purchase_plan.py   # PurchasePlan, PurchasePlanItem
│   │   ├── job.py
│   │   ├── insight.py         # InsightRun
│   │   ├── chat.py            # ChatSession, ChatMessage
│   │   └── audit_log.py
│   ├── schemas/               # Pydantic request/response models (Section 9)
│   │   ├── common.py          # Page[T], ErrorBody, PeriodQuery, Money
│   │   ├── auth.py  category.py  design.py  stock.py  period.py
│   │   ├── dashboard.py  report.py  purchase_plan.py
│   │   ├── insight.py  chat.py  job.py  setting.py
│   ├── api/
│   │   ├── router.py          # includes all route modules under /api/v1
│   │   └── routes/
│   │       ├── auth.py  categories.py  designs.py  stock.py  periods.py
│   │       ├── dashboard.py  alerts.py  reports.py  reorder.py
│   │       ├── purchase_plans.py  insights.py  chat.py  jobs.py
│   │       ├── events.py  settings.py  admin_tools.py  health.py
│   ├── services/              # ALL business logic + calculations (Section 6, 7)
│   │   ├── auth_service.py
│   │   ├── settings_service.py
│   │   ├── data_version_service.py
│   │   ├── audit_service.py
│   │   ├── category_service.py
│   │   ├── design_service.py
│   │   ├── stock_service.py
│   │   ├── period_service.py
│   │   ├── metrics_service.py
│   │   ├── alert_service.py
│   │   ├── costing_service.py
│   │   ├── reorder_service.py
│   │   ├── dashboard_service.py
│   │   ├── instant_insights_service.py
│   │   ├── report_service.py
│   │   ├── purchase_plan_service.py
│   │   ├── import_export_service.py
│   │   ├── job_service.py
│   │   ├── chat_service.py
│   │   └── demo_data_service.py
│   └── ai/                    # CrewAI layer (Sections 11–13)
│       ├── llm.py             # ModelManager: primary/fallback/cooldown, LLM factory
│       ├── runner.py          # run_crew_step(): retries, fallback, parse, progress
│       ├── analysis_pack.py   # builds compact facts JSON for the AI
│       ├── fallbacks.py       # rule-based outputs (no LLM) for every step
│       ├── skill_loader.py
│       ├── smoke_test.py      # python -m app.ai.smoke_test
│       ├── outputs/           # Pydantic output models for tasks
│       │   ├── stock_position.py  demand.py  anomaly.py
│       │   ├── reorder.py  budget.py  report.py  chat.py
│       ├── tools/             # read-only CrewAI tools wrapping services
│       │   ├── base.py        # JsonTool base: own DB session, size cap
│       │   ├── shop_tools.py  stock_tools.py  sales_tools.py
│       │   ├── demand_tools.py  costing_tools.py  audit_tools.py
│       ├── flows/
│       │   └── insights_flow.py
│       └── crews/
│           ├── inventory_analysis_crew/{config/agents.yaml, config/tasks.yaml, skills/*.md, crew.py}
│           ├── audit_crew/{...}
│           ├── purchase_planning_crew/{...}
│           ├── reporting_crew/{...}
│           └── assistant_crew/{...}
└── tests/
    ├── conftest.py            # temp DB, client, auth headers, factories
    ├── test_auth.py  test_categories.py  test_designs.py  test_stock.py
    ├── test_periods.py  test_metrics.py  test_costing.py  test_reorder.py
    ├── test_dashboard.py  test_purchase_plans.py
    ├── test_ai_mock.py        # insights + chat in LLM_MOCK_MODE
    └── test_demo_data.py
```

---

## 4. Configuration (`app/core/config.py`)

`Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`. Fields (the names match `backend/.env`):

| Field | Type | Default | Meaning |
|---|---|---|---|
| APP_NAME | str | "Kraftly" | |
| APP_ENV | str | "development" | |
| LOG_LEVEL | str | "INFO" | |
| API_HOST / API_PORT | str / int | 127.0.0.1 / 8000 | |
| CORS_ORIGINS | list[str] (comma-separated) | http://localhost:5173 | |
| SHOP_NAME / OWNER_NAME | str | "Demo Jewellers" / "Shop Owner" | initial values copied into settings table |
| CURRENCY | str | INR | |
| TIMEZONE | str | Asia/Kolkata | |
| JWT_SECRET | str | required | |
| JWT_ALGORITHM | str | HS256 | |
| ACCESS_TOKEN_EXPIRE_MINUTES | int | 720 | |
| SEED_OWNER_USERNAME / SEED_OWNER_PASSWORD | str | owner / owner | |
| SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD | str | admin / admin | |
| PHOTO_DIR | str | ./data/photos | |
| MAX_PHOTO_MB | int | 3 | |
| DATABASE_URL | str | sqlite:///./data/jeweler.db | |
| LLM_MODEL | str | gemini/gemini-3.6-flash | primary |
| LLM_FALLBACK_MODEL | str | gemini/gemini-3.1-flash-lite | |
| GEMINI_API_KEY / GOOGLE_API_KEY | str | required | set both env vars at startup if only one is given |
| LLM_MAX_RPM | int | 4 | |
| AGENT_MAX_ITER | int | 5 | |
| LLM_TIMEOUT_SECONDS | int | 120 | |
| LLM_MAX_RETRIES | int | 2 | |
| LLM_FALLBACK_ON_STATUS | list[int] | 429,503 | |
| LLM_MOCK_MODE | bool | false | |
| DEFAULT_INFLATION_PCT | float | 5 | |
| DEFAULT_MIN_STOCK | int | 3 | |
| DEAD_STOCK_DAYS | int | 90 | |
| REORDER_COVER_MONTHS | float | 1.5 | |
| QUARTER_SYSTEM | "FINANCIAL" \| "CALENDAR" | FINANCIAL | |
| CREWAI_DISABLE_TELEMETRY / OTEL_SDK_DISABLED | bool | true | |

Note: `.env` values may carry inline `# comments` (e.g. `LLM_MAX_RPM=4   # ...`). Make sure they parse. If pydantic-settings doesn't strip inline comments, **remove the inline comments from `.env`** and move them to their own line above the key.

Expose `get_settings()` with `@lru_cache`. At import time of `app.main`, call `os.environ.setdefault(...)` for `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `CREWAI_DISABLE_TELEMETRY` and `OTEL_SDK_DISABLED` so CrewAI and its providers see them.

---

## 5. Database Design

General rules:
- SQLAlchemy 2 declarative `Base` with `id: Mapped[int] = mapped_column(primary_key=True)` (except `jobs.id`, a string UUID).
- Timestamps `created_at` / `updated_at` are UTC `DateTime(timezone=True)`, default now; `updated_at` uses `onupdate`.
- Business dates (`occurred_on`, period boundaries) are `Date` in **shop local time** (Asia/Kolkata, via `core/clock.py`).
- Money is `Numeric(12, 2)` in DB, `Decimal` in Python, serialized as JSON **number** rounded to 2 decimals.
- Create tables with `Base.metadata.create_all()` at startup (no Alembic in the POC). Document in the README: "delete `data/jeweler.db` after schema changes".
- SQLite pragmas on connect: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`.

### 5.1 Tables

**users**
| column | type | rules |
|---|---|---|
| id | int pk | |
| username | str(50) unique, lowercase | |
| password_hash | str | bcrypt |
| role | enum `OWNER` \| `ADMIN` | |
| display_name | str(100) | "Owner" / "Admin" |
| is_active | bool | default true |
| last_login_at | datetime null | |
| created_at, updated_at | | |

**categories**
| column | type | rules |
|---|---|---|
| id | int pk | |
| name | str(60) | unique (case-insensitive: store `name_key = lower(trim(name))` unique) |
| label_prefix | str(5) | uppercase letters only, 1–5 chars, unique (e.g. `ER`) |
| icon | str(30) | one of: `necklace, earring, ring, bangle, bracelet, anklet, chain, pendant, nosepin, set, coin, other` |
| description | str(300) null | |
| inflation_pct_override | Numeric(5,2) null | |
| sort_order | int | default = next |
| is_active | bool | default true |
| timestamps | | |

**subcategories**
| column | type | rules |
|---|---|---|
| id | int pk | |
| category_id | fk categories, cascade restrict | |
| name | str(60) | unique within category (case-insensitive) |
| description | str(300) null | |
| sort_order | int | |
| is_active | bool | |
| timestamps | | |

**designs**
| column | type | rules |
|---|---|---|
| id | int pk | |
| category_id | fk | required |
| subcategory_id | fk null | must belong to `category_id` |
| label | str(20) unique | normalized `upper(trim())`, regex `^[A-Z0-9][A-Z0-9\-\/]{1,19}$` |
| name | str(100) null | e.g. "Kundan jhumka" |
| description | str(500) null | |
| metal | enum `GOLD, SILVER, PLATINUM, OTHER` | default GOLD |
| purity | str(10) null | free text, UI offers `24K, 22K, 18K, 14K, 925, 950, Other` |
| weight_g | Numeric(8,3) null | |
| cost_price | Numeric(12,2) | ≥ 0, required (₹ per piece) |
| selling_price | Numeric(12,2) | ≥ 0, required |
| supplier | str(100) null | |
| min_stock | int | ≥ 0, default from settings `default_min_stock` |
| inflation_pct_override | Numeric(5,2) null | |
| photo_filename | str null | file in PHOTO_DIR |
| custom_fields | JSON | default `{}` |
| is_active | bool | archived = false |
| timestamps | | |

Index: `(category_id, subcategory_id)`, `label` unique.

**stock_movements**
| column | type | rules |
|---|---|---|
| id | int pk | |
| design_id | fk | indexed |
| type | enum (below) | |
| quantity | int | > 0 always |
| signed_qty | int | +quantity or −quantity by type (stored for fast sums) |
| unit_price | Numeric(12,2) null | SALE: selling price per piece (default design.selling_price). PURCHASE / OPENING: cost per piece (default design.cost_price). Others: null |
| occurred_on | date | default today; may be in the past (backdating allowed), never in the future |
| note | str(300) null | |
| source | enum `MANUAL, OPENING, PURCHASE_PLAN, IMPORT, DEMO` | |
| purchase_plan_item_id | fk null | when received from a plan |
| created_by | fk users | |
| is_void | bool default false | the "Undo" |
| voided_at / voided_by / void_reason | | |
| created_at | | |

Index: `(design_id, occurred_on)`, `(type, occurred_on)`, `is_void`.

Movement types and their direction (constants in `stock_service.py`):

| type | direction | UI label (frontend uses these) |
|---|---|---|
| OPENING | + | Opening stock |
| PURCHASE | + | New stock received |
| CUSTOMER_RETURN | + | Customer return |
| ADJUSTMENT_IN | + | Correction (+) |
| SALE | − | Sale |
| SUPPLIER_RETURN | − | Return to supplier |
| ADJUSTMENT_OUT | − | Correction (−) (damage / loss / count fix) |

**settings** (key/value)
| column | type |
|---|---|
| key | str pk |
| value | JSON |
| updated_at, updated_by | |

Keys and defaults (seeded at startup if missing, from `.env`): `shop_name`, `owner_name`, `inflation_pct_global` (5), `default_min_stock` (3), `dead_stock_days` (90), `reorder_cover_months` (1.5), `quarter_system` ("FINANCIAL"), `data_version` (0), `milestones` ({}).

**purchase_plans**
| column | type | rules |
|---|---|---|
| id | int pk | |
| title | str(120) | default "Purchase plan – Nov 2026" |
| status | enum `DRAFT, SUBMITTED, DECIDED, RECEIVED` | |
| source | enum `AI, MANUAL` | |
| insight_run_id | fk null | |
| period_start, period_end | date null | |
| notes | text null | |
| total_estimated | Numeric(14,2) | Σ line_total of all items (recalculated) |
| total_approved | Numeric(14,2) | Σ line_total of APPROVED items |
| created_by, submitted_by, decided_by | fk users null | |
| submitted_at, decided_at, received_at | datetime null | |
| timestamps | | |

**purchase_plan_items**
| column | type | rules |
|---|---|---|
| id | int pk | |
| plan_id | fk cascade delete | |
| design_id | fk | unique per plan |
| current_stock_at_creation | int | |
| suggested_qty | int ≥ 0 | from AI/baseline |
| final_qty | int ≥ 0 | editable; defaults to suggested |
| last_unit_cost | Numeric(12,2) | |
| inflation_pct | Numeric(5,2) | resolved value used |
| expected_unit_cost | Numeric(12,2) | = round(last × (1 + infl/100), 2) |
| line_total | Numeric(14,2) | = expected_unit_cost × final_qty |
| priority | enum `HIGH, MEDIUM, LOW` | |
| reason | text | AI or rule-based explanation |
| decision | enum `PENDING, APPROVED, REJECTED` | |
| decision_note | str null | |
| received_qty | int default 0 | |

**jobs**
| column | type |
|---|---|
| id | str(36) pk (uuid4) |
| type | enum `INSIGHTS_RUN, CHAT_ANSWER` |
| status | enum `QUEUED, RUNNING, SUCCEEDED, FAILED` |
| steps | JSON list of `{key, label, status: PENDING\|RUNNING\|DONE\|FAILED\|SKIPPED, started_at, finished_at, model_used, note}` |
| result_type / result_id | str / int null (`insight_run` / `chat_message`) |
| error | text null |
| created_by | fk users |
| created_at, started_at, finished_at | |

**insight_runs**
| column | type |
|---|---|
| id | int pk |
| job_id | fk jobs |
| period_type | `MONTH` \| `QUARTER` \| `CUSTOM` |
| period_start, period_end | date |
| period_label | str ("November 2026", "Q3 FY2026-27") |
| data_version | int (value when the run started) |
| status | `RUNNING`, `COMPLETE`, `PARTIAL`, `FAILED` |
| models_used | JSON list, e.g. `["gemini/gemini-3.6-flash", "rule-based"]` |
| analysis_pack | JSON (facts given to the AI) |
| stock_position, demand, anomalies, reorder, budget, report | JSON (task outputs) |
| purchase_plan_id | fk null |
| created_by, created_at, finished_at | |

**chat_sessions**: id, user_id fk, title (first question truncated to 60 chars), created_at, updated_at.
**chat_messages**: id, session_id fk cascade, role `USER` \| `ASSISTANT`, content (markdown text), payload JSON (`table`, `chart`, `follow_up_questions`, `used_tools`, `model_used`), status `PENDING` \| `COMPLETE` \| `FAILED`, job_id null, created_at.

**audit_logs**: id, user_id, action (`CREATE`, `UPDATE`, `DELETE`, `ARCHIVE`, `VOID`, `LOGIN`, `SUBMIT`, `DECIDE`, `RECEIVE`, `IMPORT`, `RESET`, `DEMO_LOAD`), entity_type, entity_id, before JSON, after JSON, created_at.

### 5.2 Startup seeding (`main.py` lifespan)
1. Create `data/` and `data/photos/` if missing; `create_all()`.
2. Seed users if their username is missing: `owner` (OWNER, display "Owner") and `admin` (ADMIN, display "Admin"), with passwords from `.env`, bcrypt-hashed.
3. Seed missing settings keys.
4. **Do not seed any inventory.** The shop starts **blank** (owner requirement). Demo data is only loaded through `POST /admin/demo-data` (Section 8.15).

---

## 6. Core Business Rules and Formulas

All in services. Every service function takes `db: Session` as its first argument. **Pure calculation helpers must be unit-tested** (Section 16).

### 6.1 Stock
- `current_stock(design)` = Σ `signed_qty` of non-void movements (all dates).
- `stock_as_of(design, date)` = Σ `signed_qty` of non-void movements with `occurred_on ≤ date`.
- **No negative stock:** an OUT movement of quantity q on date d is rejected (`409 INSUFFICIENT_STOCK`) if `stock_as_of(d) − q < 0` **or** `current_stock − q < 0`.
- **Voiding** (undo) an IN movement is rejected under the same rule.
- Voiding an already-void movement → `409 ALREADY_VOID`. OPENING can be voided only if no other non-void movement exists for that design.
- `occurred_on` in the future → `422 FUTURE_DATE`.
- Archived design (`is_active=false`) → movements rejected `409 DESIGN_ARCHIVED`.

### 6.2 Stock status (per design, "now")
Evaluate in this order:
1. `OUT`: current_stock == 0
2. `DEAD`: current_stock > 0 **and** days_since_last_sale ≥ `dead_stock_days`, where days_since_last_sale counts from the last SALE date, or from the first movement date if never sold. Only applies if the design's first movement is at least `dead_stock_days` old.
3. `LOW`: current_stock ≤ min_stock
4. `IN`: otherwise

(Dead has priority over Low because money is tied up.)

### 6.3 Periods (`period_service.py`)
- Inputs: `period_type` (`month` | `quarter` | `custom`) and `anchor` (ISO date, default today), or `start` + `end` for custom.
- Month: first to last day of the anchor's month. Label `"November 2026"`.
- Quarter with `quarter_system=FINANCIAL` (default): FY runs Apr–Mar. Q1 Apr–Jun, Q2 Jul–Sep, Q3 Oct–Dec, Q4 Jan–Mar. Label `"Q3 FY2026-27 (Oct–Dec 2026)"`. With `CALENDAR`: Q1 Jan–Mar, etc. Label `"Q4 2026 (Oct–Dec)"`.
- `effective_end = min(end, today)`. Periods ending in the future are "in progress", flag `is_current=true`.
- `previous_period(p)` = the same-length period immediately before.
- `GET /periods/options` returns the last 24 months and last 8 quarters (newest first) as `{period_type, anchor, label, start, end}`.

**Period stock row** (per design, period P):
- `opening` = stock_as_of(P.start − 1 day)
- `received` = Σ qty of PURCHASE in P
- `sold` = Σ qty of SALE in P
- `customer_returns` = Σ CUSTOMER_RETURN in P
- `supplier_returns` = Σ SUPPLIER_RETURN in P
- `adjustments_net` = Σ ADJUSTMENT_IN − Σ ADJUSTMENT_OUT in P
- `opening_added` = Σ OPENING in P (designs created during the period)
- `closing` = opening + opening_added + received + customer_returns − sold − supplier_returns + adjustments_net (must equal stock_as_of(effective_end); assert in tests)
- `sales_value` = Σ (qty × unit_price) of SALE in P

Implement period aggregation with **one grouped SQL query** per period (GROUP BY design_id, type), not per-design loops.

### 6.4 Metrics (`metrics_service.py`)
- `last_unit_cost(design)` = unit_price of the latest non-void PURCHASE; if none, the latest OPENING unit_price; else design.cost_price.
- Stock value at cost = Σ current_stock × last_unit_cost. At selling price = Σ current_stock × selling_price.
- `velocity_30d(design, lookback=90)`: window = last `min(90, days since first movement)` days (minimum 7). velocity = units sold in window ÷ window_days × 30. Round to 2 decimals.
- `sold_last_30d`, `sold_period`, `sold_prev_period`.
- Sales trend: units and value per month for the last N months (default 12), optionally per category.
- Category breakdown: pieces, stock value (cost), sold units and value in the period, share %.
- Top / bottom sellers in a period by units (ties broken by value).
- Stock turnover (period) = units sold ÷ average stock ((opening + closing) / 2); 0 if average stock is 0.

### 6.5 Demand classification (deterministic code; the AI only explains it)
For each active design:
1. `NEW`: first movement < 14 days ago and no sales yet.
2. `DEAD`: stock status DEAD (6.2).
3. `HIGH`: (stock status OUT **and** sold ≥ 3 in the last 30 days), **or** velocity in the top 20% of its comparison group.
4. `LOW`: velocity == 0 (not dead yet), **or** velocity in the bottom 20% of its group.
5. `STEADY`: otherwise.

Comparison group: designs of the same category with velocity > 0. If fewer than 5 such designs, use all shop designs with velocity > 0. Percentile by rank. If the group has fewer than 3 designs, mark everything non-zero as `STEADY` and set `data_sufficiency="LOW"`.

Return `DemandItem{design_id, label, category, demand_class, velocity_30d, sold_last_30d, sold_period, sold_prev_period, change_pct, days_since_last_sale}`.

### 6.6 Costing (`costing_service.py`)
- `resolve_inflation(design)` = design.inflation_pct_override ?? category.inflation_pct_override ?? settings.inflation_pct_global.
- `expected_unit_cost = round_half_up(last_unit_cost × (1 + inflation/100), 2)`.
- `line_total = expected_unit_cost × qty`.
- `calculate_purchase_cost(label, qty)` returns `{label, quantity, last_unit_cost, inflation_pct, expected_unit_cost, line_total, formula_text}` where formula_text is e.g. `"₹100.00 × (1 + 5%) = ₹105.00 per piece × 10 = ₹1,050.00"`.
- Indian number formatting helper `format_inr(x)` (12,34,567.00) for texts.

### 6.7 Reorder baseline (`reorder_service.py`)
For each active design with status OUT or LOW (never DEAD):
- `monthly_rate = velocity_30d`
- `target_stock = ceil(monthly_rate × reorder_cover_months) + min_stock`
- `suggested_qty = max(target_stock − current_stock, 0)`. If status is OUT and the result is 0 → `max(min_stock, 1)`.
- `priority`: HIGH if demand HIGH, or (OUT and demand in {HIGH, STEADY}). MEDIUM if OUT or demand STEADY. LOW otherwise.
- `reason` (rule text): e.g. `"Out of stock. Sold 8 in last 30 days (high demand). Target 1.5 months cover + min 3."`
- Attach costing (6.6). Sort by priority, then line_total desc.

### 6.8 Anomaly candidates (rule-based; the AI reviews and explains)
In the analysis window (default last 90 days):
1. **Big sale:** a single SALE qty > max(5, 3 × average sale qty for that design).
2. **Cost jump:** a PURCHASE unit_price differs > 20% from the previous purchase/opening cost of that design.
3. **Price below cost:** design selling_price < last_unit_cost.
4. **Frequent undo:** > 3 voided movements on the same design in 7 days.
5. **Same-day sale and return:** SALE and CUSTOMER_RETURN of the same design on the same day.
6. **Backdated entries:** movements created > 30 days after their `occurred_on` (count per user).
7. **Zero minimum:** min_stock == 0 on a design with HIGH demand.

Output `{rule, severity (HIGH/MEDIUM/LOW), label?, evidence (dict), message}`.

### 6.9 Instant insights (rule-based, live, no AI; shown on the Dashboard)
`instant_insights_service.build(db, period)` returns at most **6** items `{id, severity: critical|warning|info|success, icon, title, detail, action: {label, route}}`, ordered by severity:
1. Setup prompts (only when relevant): no categories → "Add your first category" (route `/app/inventory`). No designs → "Add designs to {first category}". No sales ever → "Record your first sale".
2. OUT count > 0 → "{n} designs are sold out", detail lists up to 3 labels (route `/app/inventory?status=OUT`).
3. Of those OUT, HIGH-demand count → "{n} best-sellers need restocking · ≈ ₹X" (route `/app/purchase-plans`).
4. LOW count → "{n} designs running low".
5. Sales change: period sales value vs the same number of days in the previous period → "Sales up 12% vs last month" (success) / "down" (warning). Only if both periods have sales.
6. Best seller last 7 days → "ER-1012 is flying: 8 sold this week".
7. Dead stock value > 0 → "₹2.3 L tied up in 22 slow designs".
8. Top category share → "Earrings brought 41% of this month's sales".

### 6.10 Data version and live updates
- `data_version_service.bump(db, entity, action, entity_id)` increments `settings.data_version` inside the same transaction as any mutation of categories, subcategories, designs, movements (incl. void), settings, imports, demo load and reset.
- After the commit, the route publishes the SSE event `data_changed` `{data_version, entity, action, entity_id, at}` via `EventBus`.
- An insights run stores the `data_version` it started with. `changes_since = current_data_version − run.data_version`. `is_stale = changes_since > 0`.

---

## 7. Auth and Permissions

### 7.1 Login
- `POST /api/v1/auth/login` body `{username, password, role}` where `role` ∈ `OWNER` | `ADMIN` (the frontend sends the role picked on the front page).
  - Lowercase and trim the username. Unknown user or wrong password → `401 INVALID_CREDENTIALS` with message "Incorrect username or password".
  - Correct password but `user.role != role` → `403 ROLE_MISMATCH` "This account is not an {Owner|Admin} account. Go back and choose the right login."
  - Success → `{access_token, token_type: "bearer", expires_at, user: {id, username, display_name, role}}`. Update `last_login_at`. Write audit `LOGIN`.
- JWT claims: `sub` (user id as str), `role`, `exp`, `iat`. HS256 with `JWT_SECRET`.
- `GET /api/v1/auth/me` → user.
- `POST /api/v1/auth/logout` → 204 (stateless; the frontend discards the token).

### 7.2 Dependencies (`core/deps.py`)
- `get_current_user` reads `Authorization: Bearer <token>`. For SSE endpoints it **also** accepts the header only (the frontend uses fetch-based SSE that can send headers). Do **not** accept tokens in query strings.
- `require_roles(*roles)` → 403 `FORBIDDEN`.

### 7.3 Permission matrix
| Capability | OWNER | ADMIN |
|---|---|---|
| View everything (dashboard, inventory, stock, reports, insights) | ✅ | ✅ |
| Create/edit categories, subcategories, designs; record/undo movements; import | ✅ | ✅ |
| Generate AI insights, use chat | ✅ | ✅ |
| Create/edit purchase plans, submit | ✅ | ✅ |
| **Approve/reject purchase plan items** | ✅ | ❌ |
| Mark plan received (creates stock) | ✅ | ✅ (only after owner decided) |
| Edit settings, load demo data | ✅ | ✅ |
| **Reset all inventory data** | ✅ | ❌ |

The owner can approve a plan directly from `DRAFT`, since they may test alone. The admin must `submit` first.

---

## 8. API Contract (all under `/api/v1`, JSON, auth required unless noted)

**Conventions**
- List endpoints with pagination take `page` (1-based, default 1) and `page_size` (default 25, max 200), and return `{items: [...], total, page, page_size}`.
- Errors return `{"error": {"code": "SNAKE_UPPER", "message": "Human friendly text", "details": {...}}}` with the proper HTTP status. 422 validation errors are converted to this shape with `details.fields: {field: message}`. Bulk rows use `details.rows: [{index, field, message}]`.
- Period query params (wherever "period params" appear): `period_type` (`month` default | `quarter` | `custom`), `anchor` (date, default today), `start`, `end` (custom only).
- Money fields are numbers (2 decimals). Dates are `YYYY-MM-DD`. Datetimes are ISO 8601 UTC.
- Every mutating endpoint: validate → service → audit → bump data_version → commit → publish `data_changed`.

### 8.1 Health (no auth)
`GET /health` → `{status: "ok", version, db: "ok", ai: {mock_mode, primary_model, fallback_model}}`

### 8.2 Auth
As in Section 7.

### 8.3 Categories and subcategories
| Method & path | Body / params | Response |
|---|---|---|
| GET `/categories` | `include_inactive=false` | `[CategoryCard]` |
| POST `/categories` | `{name, label_prefix?, icon, description?, inflation_pct_override?}` | `CategoryCard` (201) |
| GET `/categories/{id}` | | `CategoryDetail` |
| PATCH `/categories/{id}` | any of the above + `is_active`, `sort_order` | `CategoryCard` |
| DELETE `/categories/{id}` | | 204 if it has no designs. Else `409 CATEGORY_NOT_EMPTY` ("Archive it instead") |
| GET `/categories/suggest-prefix?name=Earrings` | | `{prefix: "ER", available: true}` |
| GET `/categories/{id}/subcategories` | | `[Subcategory]` |
| POST `/categories/{id}/subcategories` | `{name, description?}` | `Subcategory` (201) |
| PATCH `/subcategories/{id}` | `{name?, description?, is_active?, sort_order?}` | `Subcategory` |
| DELETE `/subcategories/{id}` | | 204 if no designs, else `409 SUBCATEGORY_NOT_EMPTY` |

`label_prefix` auto-suggestion: the first two letters of the name, uppercase. If taken, the first letter + the next consonant, then add digits. If the client omits the prefix, use the suggestion.

`CategoryCard` = `{id, name, label_prefix, icon, description, is_active, sort_order, inflation_pct_override, subcategory_count, design_count, total_pieces, stock_value_cost, out_of_stock_count, low_stock_count, dead_stock_count, sold_last_30d}`
`CategoryDetail` = CategoryCard + `subcategories: [Subcategory + {design_count, total_pieces}]`
`Subcategory` = `{id, category_id, name, description, is_active, sort_order}`

### 8.4 Designs
| Method & path | Body / params | Response |
|---|---|---|
| GET `/designs` | `category_id, subcategory_id, status (IN/LOW/OUT/DEAD, comma list), demand (HIGH/STEADY/LOW/DEAD/NEW), search (label/name contains), include_inactive, sort (label, -current_stock, -sold_last_30d, name, -stock_value…), page, page_size` | `Page[DesignListItem]` |
| GET `/designs/next-labels?category_id=&count=10` | | `{labels: ["ER-1001", …]}`: prefix + "-" + next free numbers, starting at 1001 or max existing + 1 |
| GET `/designs/check-label?label=ER-1012` | | `{label: "ER-1012", valid: bool, available: bool, message?}` |
| POST `/designs/bulk` | `{category_id, subcategory_id?, opening_date? (default today), designs: [DesignCreateRow]}` (1–100 rows) | 201 `{created: [DesignListItem]}`. **All or nothing.** On error `422 BULK_VALIDATION_FAILED` with `details.rows` |
| GET `/designs/{id}` | | `DesignDetail` |
| GET `/designs/by-label/{label}` | | `DesignDetail` (404 `DESIGN_NOT_FOUND`) |
| PATCH `/designs/{id}` | any editable field; changing the label re-validates uniqueness | `DesignDetail` |
| POST `/designs/{id}/photo` | multipart `file` (jpg/png/webp, ≤ MAX_PHOTO_MB) | `{photo_url}`. Saved as `{design_id}_{uuid8}.{ext}`, the old file deleted |
| DELETE `/designs/{id}/photo` | | 204 |
| POST `/designs/{id}/archive` / `/unarchive` | | `DesignDetail` |
| DELETE `/designs/{id}` | | 204 only if its only movements are OPENING (hard delete incl. movements), else `409 DESIGN_HAS_HISTORY` ("Archive instead") |
| GET `/designs/{id}/history?months=12` | | `{monthly: [{month: "2026-11", sold, received, sales_value}], movements: [Movement] (latest 50)}` |
| GET `/designs/search?q=ER-10&limit=8` | | `[DesignSearchHit]` for autocomplete/spotlight: `{id, label, name, category_name, current_stock, status, photo_url, selling_price, cost_price}` |
| GET `/designs/import-template` | | xlsx download |
| POST `/designs/import?dry_run=true` | multipart xlsx (columns of the template: category, subcategory, label, name, metal, purity, weight_g, cost_price, selling_price, min_stock, opening_stock, supplier) | `{valid_rows, errors: [{row, field, message}], will_create: {categories, subcategories, designs}}`. With `dry_run=false` it creates everything (auto-creating missing categories/subcategories) in one transaction |

`DesignCreateRow` = `{label, name?, metal? = GOLD, purity?, weight_g?, cost_price, selling_price, min_stock? (default setting), opening_stock (≥0, default 0), supplier?, description?}`. If `opening_stock > 0`, create an OPENING movement (unit_price = cost_price, occurred_on = opening_date, source OPENING).

`DesignListItem` = `{id, label, name, category: {id, name, icon}, subcategory: {id, name} | null, metal, purity, weight_g, cost_price, selling_price, last_unit_cost, min_stock, current_stock, status, demand_class, sold_last_30d, stock_value_cost, photo_url, is_active, updated_at}`
`DesignDetail` = DesignListItem + `{description, supplier, inflation_pct_override, custom_fields, velocity_30d, days_since_last_sale, first_movement_on, last_sale_on, created_at}`

`photo_url` = `/media/photos/{filename}` (static mount, no auth, POC only) or null.

### 8.5 Stock movements
| Method & path | Body / params | Response |
|---|---|---|
| POST `/stock/movements` | `{design_id? , label?, type, quantity, occurred_on?, unit_price?, note?}` (one of design_id/label) | 201 `{movement: Movement, design: {id, label, current_stock, status, demand_class}}` |
| POST `/stock/movements/batch` | `{items: [same as above]}` (1–100), all or nothing | 201 `{movements: [...], designs: [...]}` |
| GET `/stock/movements` | `design_id, label, category_id, type (comma), from, to, include_void=true, created_by, page, page_size` | `Page[Movement]` newest first |
| POST `/stock/movements/{id}/void` | `{reason?}` | `{movement, design}` |
| GET `/stock/today` | | `{entries: [Movement] (today, by the current user, newest first), totals: {sold_units, sold_value, received_units}}` |

`Movement` = `{id, design: {id, label, name, photo_url}, type, direction: "IN"|"OUT", quantity, unit_price, value, occurred_on, note, source, created_by: {id, display_name}, created_at, is_void, voided_at, void_reason}`

### 8.6 Periods
| GET `/periods/resolve` | period params | `{period_type, start, end, effective_end, label, is_current, previous: {start, end, label}}` |
| GET `/periods/options` | | `{months: [...], quarters: [...]}` |
| GET `/periods/stock` | period params + `category_id, subcategory_id, status, search, sort, page, page_size` | `{period, rows: Page[PeriodStockRow], totals: {opening, received, sold, customer_returns, supplier_returns, adjustments_net, opening_added, closing, sales_value}}` |

`PeriodStockRow` = `{design: {id, label, name, category_name, subcategory_name, photo_url}, opening, opening_added, received, sold, customer_returns, supplier_returns, adjustments_net, closing, sales_value, status_now}`

### 8.7 Dashboard (one call, an eagle's-eye view)
`GET /dashboard/overview` (period params, default current month) →
```json
{
  "period": {...resolve...},
  "data_version": 42,
  "setup": {"has_category": true, "has_designs": true, "has_opening_stock": true,
            "has_sale": false, "has_insights": false, "completed_steps": 3, "total_steps": 5},
  "kpis": {
    "total_designs": 120, "total_pieces": 1248,
    "stock_value_cost": 4860000.00, "stock_value_selling": 6120000.00,
    "sales_units": 142, "sales_value": 912000.00, "sales_change_pct": 12.4,
    "out_of_stock": 9, "low_stock": 14, "dead_stock": 22, "dead_stock_value": 230000.00,
    "needs_attention": 23
  },
  "kpi_sparklines": {"sales_value": [..6 months..], "stock_value_cost": [..6..], "sales_units": [..6..]},
  "stock_health": {"IN": 75, "LOW": 14, "OUT": 9, "DEAD": 22},
  "sales_trend": [{"month": "2026-06", "label": "Jun", "units": 90, "value": 610000}],
  "category_breakdown": [{"category_id": 1, "name": "Earrings", "icon": "earring", "pieces": 380,
                          "stock_value_cost": 900000, "sold_units": 48, "sales_value": 210000, "share_pct": 23.0}],
  "top_sellers": [{"design_id": 5, "label": "ER-1012", "name": "...", "photo_url": null, "sold_units": 8, "sales_value": 52000}],
  "alerts": [{"design_id": 9, "label": "ER-1015", "name": "...", "status": "OUT", "current_stock": 0, "min_stock": 3, "demand_class": "HIGH"}],
  "instant_insights": [{"id": "out_of_stock", "severity": "critical", "icon": "alert-triangle",
                        "title": "9 designs are sold out", "detail": "ER-1015, NK-2041, BG-3002 and 6 more",
                        "action": {"label": "View", "route": "/app/inventory?status=OUT"}}],
  "latest_ai": {"run_id": 3, "created_at": "...", "period_label": "November 2026", "headline": "...",
                "conclusion_short": "first 220 chars", "is_stale": true, "changes_since": 12, "status": "COMPLETE"} ,
  "recent_activity": [Movement x 10],
  "pending_approvals": 1
}
```
`pending_approvals` = number of plans in `SUBMITTED`, plus `DRAFT` plans with `source=AI` (both await the owner). `latest_ai` is `null` if there is no run yet. Sparklines are always 6 numbers (zeros allowed). The response must stay fast (< 300 ms on 120 designs / 5k movements). Reuse one aggregation pass.

### 8.8 Alerts
`GET /alerts?status=OUT,LOW,DEAD&category_id=` → `[AlertItem]` (= DesignListItem subset + `days_since_last_sale`, `value_tied_up`).

### 8.9 Reports
| GET `/reports/sales-trend?months=12&category_id=&group_by=total\|category` | `{series: [{key, name, points: [{month, label, units, value}]}]}` |
| GET `/reports/category-breakdown` + period params | `[CategoryBreakdownRow]` |
| GET `/reports/top-sellers` + period params + `limit=10&order=desc\|asc` | `[{design…, sold_units, sales_value, current_stock, demand_class}]` |
| GET `/reports/period-comparison?period_type=month&anchor_a=&anchor_b=&group_by=category` | `{a: {label}, b: {label}, rows: [{key, name, a_units, b_units, a_value, b_value, change_pct}]}` |
| GET `/reports/dead-stock` | `{total_value, items: [{design…, current_stock, days_since_last_sale, value_tied_up}]}` |
| GET `/reports/stock-turnover` + period params | `[{category, opening, closing, sold, turnover}]` |
| GET `/reports/export?report=period_stock\|sales_trend\|top_sellers\|dead_stock\|purchase_plan&format=xlsx&...` | xlsx file. Filename `"{report}_{label}.xlsx"`. Header row bold, ₹ number formats, frozen header |

### 8.10 Reorder (live, no AI)
`GET /reorder/baseline?category_id=` → `{items: [ReorderItem], total_estimated, by_category: [{category, amount}]}`
`ReorderItem` = `{design: {...}, current_stock, min_stock, status, demand_class, velocity_30d, suggested_qty, priority, reason, last_unit_cost, inflation_pct, expected_unit_cost, line_total, formula_text}`

### 8.11 Purchase plans
| Method & path | Who | Body | Response |
|---|---|---|---|
| GET `/purchase-plans?status=` | both | | `[PlanSummary]` |
| POST `/purchase-plans` | both | `{title?, from_baseline: true, category_id?}` | 201 `PlanDetail` (MANUAL, items from 6.7) |
| GET `/purchase-plans/{id}` | both | | `PlanDetail` |
| PATCH `/purchase-plans/{id}` | both (DRAFT/SUBMITTED) | `{title?, notes?}` | `PlanDetail` |
| POST `/purchase-plans/{id}/items` | both (DRAFT) | `{design_id, final_qty}` | `PlanDetail` |
| PATCH `/purchase-plans/{id}/items/{item_id}` | both: `final_qty` (DRAFT/SUBMITTED). Owner: `decision`, `decision_note` | | `PlanDetail` (totals recalculated) |
| DELETE `/purchase-plans/{id}/items/{item_id}` | both (DRAFT) | | `PlanDetail` |
| POST `/purchase-plans/{id}/submit` | both | | DRAFT → SUBMITTED |
| POST `/purchase-plans/{id}/decide` | **owner** | `{approve_all?: bool, decisions?: [{item_id, decision, final_qty?, decision_note?}]}` | → DECIDED (every item must end APPROVED or REJECTED. With `approve_all` every PENDING item becomes APPROVED) |
| POST `/purchase-plans/{id}/receive` | both (DECIDED) | `{occurred_on?, items: [{item_id, quantity, unit_cost}]}` | creates PURCHASE movements (source PURCHASE_PLAN). Updates received_qty. When all approved items are fully received → RECEIVED |
| DELETE `/purchase-plans/{id}` | both (DRAFT only) | | 204 |
| GET `/purchase-plans/{id}/export` | both | | xlsx |

`PlanSummary` = `{id, title, status, source, created_at, created_by, item_count, total_estimated, total_approved, approved_count, rejected_count, pending_count}`
`PlanDetail` = PlanSummary + `{notes, period_label, insight_run_id, items: [PlanItem], by_category: [{category, amount_estimated, amount_approved}]}`
`PlanItem` = `{id, design: {id, label, name, photo_url, category_name}, current_stock (live), current_stock_at_creation, status, demand_class, suggested_qty, final_qty, last_unit_cost, inflation_pct, expected_unit_cost, line_total, priority, reason, decision, decision_note, received_qty, formula_text}`

### 8.12 Insights (AI)
| POST `/insights/runs` | `{period_type, anchor}` | 202 `{job_id, run_id}`. `409 AI_BUSY` if an insights job is QUEUED/RUNNING. `422 NO_DATA` if there are no designs |
| GET `/insights/latest` | | `InsightRunDetail` or `null` |
| GET `/insights/runs?limit=20` | | `[{id, period_label, status, created_at, models_used, headline}]` |
| GET `/insights/runs/{id}` | | `InsightRunDetail` |

`InsightRunDetail` = `{id, job_id, status, period_type, period_label, period_start, period_end, created_at, finished_at, models_used, is_stale, changes_since, data_sufficiency: "GOOD"|"LIMITED"|"LOW", report: InsightsReport, stock_position: StockPositionOutput, demand: DemandOutput, anomalies: AnomalyOutput, reorder: ReorderOutput, budget: BudgetOutput (service-validated), purchase_plan: PlanSummary|null, facts: {kpis, sales_trend_by_category, demand_counts}}`. The `facts` part comes from the analysis pack and lets the UI draw charts without extra calls.

### 8.13 Chat
| GET `/chat/sessions` | | `[{id, title, updated_at, message_count}]` (current user only) |
| POST `/chat/sessions` | `{title?}` | 201 session |
| GET `/chat/sessions/{id}` | | `{session, messages: [ChatMessage]}` |
| DELETE `/chat/sessions/{id}` | | 204 |
| POST `/chat/sessions/{id}/messages` | `{text}` (1–1000 chars) | 202 `{user_message, assistant_message (PENDING), job_id}` |
| GET `/chat/suggestions` | | `{questions: [str]}` (Section 13.4) |

`ChatMessage` = `{id, role, content, status, payload: {table?, chart?, follow_up_questions?, used_tools?, model_used?}, created_at}`

### 8.14 Jobs and events (SSE)
- `GET /jobs/{id}` → `{id, type, status, steps, error, result_type, result_id, created_at, started_at, finished_at}`
- `GET /jobs/{id}/events` (SSE): on connect, **first replay** the current job state as an event `snapshot`. Then stream:
  - `step` `{key, label, status, model_used?, note?}`
  - `tool` `{label}` (friendly tool label, for chat "Checking stock levels…")
  - `done` `{status, result_type, result_id}` (then close)
  - `error` `{message}` (then close)
  - keep-alive comment every 15 s.
- `GET /events/stream` (SSE, global per user): `hello` `{data_version}`, `data_changed` `{...}` (6.10), `job_finished` `{job_id, type, result_id}`, `ai_status` `{primary_available, cooldown_until}`, and a ping every 20 s.

`EventBus` (`core/events.py`): an in-memory registry of subscriber `asyncio.Queue`s (global + per job). Its `publish(topic, event)` must be **thread-safe** (it is called from CrewAI worker threads): store the main loop at startup and use `loop.call_soon_threadsafe(queue.put_nowait, event)`. Each queue has max size 100; drop the oldest on overflow.

### 8.15 Settings and admin tools
| GET `/settings` | | `{shop_name, owner_name, inflation_pct_global, default_min_stock, dead_stock_days, reorder_cover_months, quarter_system}` |
| PATCH `/settings` | same fields (validated: inflation 0–50, min stock 0–1000, dead days 15–730, cover 0.5–6) | updated settings |
| GET `/settings/ai-status` | | `{mock_mode, primary_model, fallback_model, primary_available, primary_cooldown_until, fallback_available, last_error, runs_today, chat_answers_today}` |
| POST `/admin/demo-data` | `{force?: false}` | Loads the demo shop (Section 15). If designs exist and `force=false` → `409 DATA_EXISTS` |
| POST `/admin/reset` | **owner**, body `{confirm: "RESET"}` | Deletes all inventory data (categories, subcategories, designs, movements, plans, insight runs, chat, jobs, photos). Keeps users and settings. Bumps data_version |

---

## 9. Pydantic Schemas
- One module per area (Section 3). Use `model_config = ConfigDict(from_attributes=True)`.
- Request models: `extra="forbid"`; strip strings; uppercase labels/prefixes via validators.
- Enums are Python `StrEnum`, shared by models and schemas (`app/models/enums.py`).
- Write `Page[T]` as a generic.
- Money: use `Annotated[Decimal, PlainSerializer(lambda v: float(round(v, 2)), return_type=float)]`.

---

## 10. Services: Responsibilities (function list)

Implement at least these public functions (names are guidance; keep them consistent):

- `auth_service`: `authenticate(db, username, password, role) -> User`, `create_token(user) -> (token, expires_at)`.
- `settings_service`: `get_all(db)`, `get(db, key)`, `update(db, user, patch)`.
- `data_version_service`: `current(db)`, `bump(db, entity, action, entity_id)`.
- `audit_service`: `log(db, user, action, entity_type, entity_id, before, after)`.
- `category_service`: `list_cards`, `create`, `update`, `delete`, `suggest_prefix`, `list_subcategories`, `create_subcategory`, `update_subcategory`, `delete_subcategory`.
- `design_service`: `list`, `get_detail`, `get_by_label`, `next_labels`, `check_label`, `bulk_create`, `update`, `archive`, `unarchive`, `delete`, `save_photo`, `delete_photo`, `history`, `search`.
- `stock_service`: `record`, `record_batch`, `void`, `list_movements`, `today_entries`, `current_stock_map(db, design_ids=None) -> dict[id, int]` (single grouped query), `stock_as_of_map(db, date)`.
- `period_service`: `resolve`, `previous`, `options`, `period_stock`.
- `metrics_service`: `last_unit_cost_map`, `velocity_map`, `sales_trend`, `category_breakdown`, `top_sellers`, `stock_turnover`, `kpis`.
- `alert_service`: `status_map(db) -> dict[id, Status]`, `alerts(db, statuses)`.
- `costing_service`: `resolve_inflation`, `expected_unit_cost`, `calculate_purchase_cost`, `format_inr`.
- `reorder_service`: `baseline(db, category_id=None)`.
- `demand` (in metrics_service or its own module): `classify_all(db) -> dict[id, DemandItem]`.
- `dashboard_service`: `overview(db, period)`.
- `instant_insights_service`: `build(db, period, ctx)` (reuses the dashboard ctx; no extra queries).
- `report_service`: report functions for 8.9 + `export_xlsx`.
- `purchase_plan_service`: `create_from_baseline`, `create_from_ai(db, run, reorder_output)`, `get_detail`, `update_item`, `add_item`, `remove_item`, `submit`, `decide`, `receive`, `recalc_totals`, `export_xlsx`.
- `import_export_service`: `template_xlsx`, `import_designs(db, file, dry_run, user)`.
- `job_service`: `create`, `start`, `update_step`, `tool_event`, `finish`, `fail`, `get`.
- `chat_service`: `create_session`, `list_sessions`, `get_session`, `post_message` (creates job), `suggestions`.
- `demo_data_service`: `load(db, user, force)`.

**Performance rule:** services that need per-design numbers must use the `*_map` functions (one grouped SQL query each), never N+1 loops.

---

## 11. AI Layer: Principles
1. **Code computes, AI interprets.** Every figure the AI sees comes from the **analysis pack** or a **tool**. Both are built from services.
2. **Read-only.** Tools never write. The AI's purchase suggestions become a DRAFT plan only after `purchase_plan_service.create_from_ai` **recalculates every cost** with `costing_service`, clamps quantities to 0–500, ignores unknown labels, and drops DEAD designs.
3. **Always produce a result.** Every AI step has a rule-based fallback (`ai/fallbacks.py`), so the Insights page always renders. Mark it `PARTIAL` and record `"rule-based"` in `models_used`.
4. **Quota-aware.** One LLM job at a time globally (`threading.Semaphore(1)`), `max_rpm` on every crew, a cap on agent iterations, automatic fallback model, cooldowns.
5. **Mock mode** (`LLM_MOCK_MODE=true`): no network calls. Every step uses the rule-based fallback. Tests use this.

---

## 12. AI Layer: Implementation

### 12.1 `ai/llm.py`: ModelManager
- Holds `primary = LLM_MODEL`, `fallback = LLM_FALLBACK_MODEL`.
- `get_llm(kind="primary"|"fallback") -> crewai.LLM`: `LLM(model=..., api_key=settings.GEMINI_API_KEY, timeout=LLM_TIMEOUT_SECONDS)`. Do **not** pass temperature or other sampling params. Cache instances.
- State (in memory, thread-safe with a Lock): `primary_cooldown_until`, `fallback_cooldown_until`, `last_error`, counters `runs_today`, `chat_answers_today` (reset when the date changes).
- `current_kind()`: primary if it isn't cooling down, else fallback if it isn't cooling down, else `"rule-based"`.
- `report_failure(kind, exc)`: classify:
  - **Quota** (text contains `429`, `RESOURCE_EXHAUSTED`, `quota`): cooldown until the next midnight **US/Pacific** (when Gemini daily quotas reset) if the message mentions "per day"/"daily", else 65 seconds.
  - **Overload** (`503`, `UNAVAILABLE`, `overloaded`, `high demand`): cooldown 10 minutes.
  - **Other**: no cooldown.
  - Publish an `ai_status` event when availability changes.
- `is_retryable_on_fallback(exc)` → True for quota/overload.

### 12.2 `ai/runner.py`: `run_crew_step(...)`
```
run_crew_step(job_id, step_key, step_label, crew_factory, inputs, output_model, fallback_fn) -> (output_model_instance, model_used)
```
1. `job_service.update_step(job_id, step_key, RUNNING)`.
2. If mock mode → `fallback_fn()`, mark DONE with model "rule-based".
3. `kind = model_manager.current_kind()`. If "rule-based" → fallback_fn.
4. Build the crew with `crew_factory(llm=model_manager.get_llm(kind))` and call `crew.kickoff(inputs=inputs)`.
5. Parse: `result.pydantic` if present, else `output_model.model_validate_json(extract_json(result.raw))`. `extract_json` strips markdown fences and takes the outermost `{...}`.
6. On exception: `report_failure`. If retryable and kind == primary → retry once with fallback. If it's a parse error → retry once with the same model and the instruction "Return ONLY valid JSON matching the schema." Otherwise → fallback_fn.
7. Update the step DONE (or DONE with note "rule-based fallback") with `model_used`. Return.
8. Never raise to the caller unless fallback_fn itself fails (that is a bug).

Tool progress: pass `step_callback` to the Crew. It maps tool names to friendly labels (`get_label_details` → "Looking up design details…", etc.) and calls `job_service.tool_event(job_id, label)`.

### 12.3 `ai/analysis_pack.py`
`build_pack(db, period) -> dict` (target < 12k tokens; serialize with `json.dumps(separators=(",", ":"))`):
```
{
 "shop": {"name", "currency": "INR", "today", "quarter_system"},
 "period": {label, start, end, is_current, previous_label},
 "data_sufficiency": {"level": GOOD|LIMITED|LOW, "months_of_history", "total_sales", "designs"},
   # LOW: <20 sales or <1 month history; LIMITED: <3 months; GOOD otherwise
 "kpis": {...dashboard kpis...},
 "categories": [{name, designs, pieces, stock_value_cost, sold_period, sold_prev_period, sales_value_period, change_pct}],
 "monthly_sales_by_category": {"Earrings": [[ "2026-01", units, value ], ...], ...}  # last 12 months
 "designs_of_interest": [ # max 60, priority: OUT, LOW, HIGH demand, DEAD (top value), LOW demand
   {label, name, category, subcategory, stock, min_stock, status, demand, sold_30d, sold_period, sold_prev_period,
    velocity_30d, days_since_last_sale, last_cost, selling_price, value_tied_up}
 ],
 "demand_counts": {HIGH, STEADY, LOW, DEAD, NEW},
 "reorder_baseline": [ {label, suggested_qty, priority, expected_unit_cost, line_total, reason} ],   # max 40
 "reorder_total": number,
 "anomaly_candidates": [ ... max 20 ... ],
 "settings": {inflation_pct_global, dead_stock_days, reorder_cover_months, default_min_stock}
}
```
The pack is saved on the run (`analysis_pack`). The run also exposes `facts` built from it for the UI.

### 12.4 Tools (`ai/tools/`): all read-only
Base class `JsonTool(BaseTool)` (`from crewai.tools import BaseTool`): `_run` opens its **own** `SessionLocal()` (it runs in a worker thread), calls a service, returns `json.dumps(result, default=str)`. Output is capped at 6,000 characters (lists truncated with `"truncated": true`). Errors return `{"error": "..."}` instead of raising.

| Tool name | Args | Returns |
|---|---|---|
| `get_shop_overview` | – | kpis + stock_health + data_sufficiency |
| `search_designs` | `query?, category?, status?, demand?, limit≤20` | design list items (compact) |
| `get_label_details` | `label` | detail + last 10 movements + 6-month monthly sold |
| `get_period_stock` | `period_type, anchor?, category?` | top 40 rows by sold + totals |
| `get_sales_summary` | `period_type, anchor?, group_by (category\|design\|subcategory), limit≤20` | grouped sales |
| `compare_periods` | `period_type, anchor_a, anchor_b, group_by` | comparison rows |
| `get_stock_alerts` | `status? (OUT\|LOW\|DEAD)` | alerts (max 30) |
| `get_demand_classification` | `category?, demand_class?` | demand items (max 30) |
| `get_reorder_baseline` | `category?` | baseline items (max 30) + total |
| `calculate_purchase_cost` | `label, quantity` | exact cost (6.6) |
| `get_anomaly_candidates` | `days? = 90` | candidates |
| `get_sales_trend` | `months ≤ 24, category?` | monthly units/value |

Every tool has a Pydantic `args_schema` with clear field descriptions, and a `description` explaining when to use it and that the numbers are authoritative.

### 12.5 Output models (`ai/outputs/`)
```python
class LabelNote(BaseModel): label: str; category: str; stock: int; note: str
class StockPositionOutput(BaseModel):
    summary: str                       # 2-4 sentences
    out_of_stock: list[LabelNote]      # ≤ 15
    low_stock: list[LabelNote]         # ≤ 15
    dead_stock: list[LabelNote]        # ≤ 15 (note mentions value tied up)
    category_notes: list[dict[str, str]]  # [{"category": "...", "note": "..."}]

class DemandNote(BaseModel): label: str; category: str; sold_period: int; velocity_30d: float; reason: str
class DemandOutput(BaseModel):
    summary: str
    high_demand: list[DemandNote]      # ≤ 10
    low_demand: list[DemandNote]       # ≤ 10
    seasonal_notes: list[str]          # ≤ 4
    trend_notes: list[str]             # ≤ 4

class AnomalyItem(BaseModel): label: str | None; severity: Literal["HIGH","MEDIUM","LOW"]; issue: str; evidence: str; suggested_check: str
class AnomalyOutput(BaseModel): summary: str; items: list[AnomalyItem]   # ≤ 10

class ReorderLine(BaseModel): label: str; suggested_qty: int; priority: Literal["HIGH","MEDIUM","LOW"]; reason: str
class ReorderOutput(BaseModel): summary: str; items: list[ReorderLine]; skipped: list[dict[str,str]]   # [{"label","reason"}]

class BudgetLine(BaseModel): label: str; quantity: int; expected_unit_cost: float; line_total: float
class BudgetOutput(BaseModel): items: list[BudgetLine]; total_budget: float; by_category: list[dict]; notes: str

class KeyNumber(BaseModel): label: str; value: str           # value pre-formatted e.g. "₹1.84 L"
class Action(BaseModel):
    title: str; why: str; priority: Literal["HIGH","MEDIUM","LOW"]
    target: Literal["PURCHASE_PLAN","OUT_OF_STOCK","LOW_STOCK","DEAD_STOCK","ANOMALIES","INVENTORY","REPORTS"]
class InsightsReport(BaseModel):
    headline: str                      # ≤ 120 chars, plain language
    conclusion: str                    # 3-6 sentences, the "accountant's conclusion"
    confidence: Literal["HIGH","MEDIUM","LOW"]; confidence_reason: str
    key_numbers: list[KeyNumber]       # 4-6
    recommended_actions: list[Action]  # 3-6
    whats_selling: str; whats_not_selling: str; money_view: str; risks: str
    data_quality_notes: list[str]

class ChartPoint(BaseModel): label: str; value: float
class ChatChart(BaseModel): type: Literal["bar","line","pie"]; title: str; data: list[ChartPoint]; value_format: Literal["number","inr"] = "number"
class ChatTable(BaseModel): columns: list[str]; rows: list[list[str | float | int]]
class ChatAnswer(BaseModel):
    answer_markdown: str
    table: ChatTable | None = None
    chart: ChatChart | None = None
    follow_up_questions: list[str] = []   # ≤ 3
```

### 12.6 `ai/fallbacks.py` (rule-based outputs)
For each output model, build a sensible deterministic version from the pack:
- StockPosition: lists from pack statuses. Summary sentence from counts.
- Demand: top HIGH and bottom LOW by velocity. Reasons like "Sold 8 in the period, 2.7/month pace".
- Anomaly: candidates mapped 1:1.
- Reorder: the baseline.
- Budget: computed by costing_service.
- InsightsReport: a templated headline (e.g. "Sales ₹9.1 L this month (+12%); 9 designs sold out") and a conclusion from KPIs. Confidence LOW, reason "Generated automatically (AI unavailable)".
- ChatAnswer: "The AI assistant is unavailable right now (free quota reached). Here are the latest numbers: …" plus the KPI table.

---

## 13. Crews (YAML + skills) and the Insights Flow

All crews follow the `@CrewBase` pattern:
```python
@CrewBase
class InventoryAnalysisCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    def __init__(self, llm): self.llm = llm
    def _cfg(self, name, skills):   # append skill files to backstory
        cfg = dict(self.agents_config[name]); cfg["backstory"] += "\n\n" + load_skills(__file__, skills); return cfg
    @agent
    def stock_analyst(self) -> Agent:
        return Agent(config=self._cfg("stock_analyst", ["stock_status_rules.md", "output_rules.md"]),
                     tools=[GetStockAlerts(), GetLabelDetails()], llm=self.llm,
                     max_iter=settings.AGENT_MAX_ITER, allow_delegation=False, verbose=False)
    ...
    @task
    def analyse_stock_position(self) -> Task:
        return Task(config=self.tasks_config["analyse_stock_position"], output_pydantic=StockPositionOutput)
    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential,
                    max_rpm=settings.LLM_MAX_RPM, verbose=False)
```
`skill_loader.load_skills(crew_file, names)` reads `skills/<name>` next to the crew file, plus the shared `app/ai/crews/_shared_skills/output_rules.md`, and joins them with headings.

**Shared skill `_shared_skills/output_rules.md`** (create it):
```markdown
# Output rules (all agents)
- Use ONLY numbers present in the provided facts or returned by tools. Never invent or estimate figures.
- Money is Indian Rupees. Write amounts like ₹1,05,000 or ₹1.05 L (lakh) / ₹1.2 Cr (crore).
- Refer to designs by their label (e.g. ER-1012) and category.
- Be concise, plain and practical: write for a jewellery shop owner, not an analyst.
- You give insights and recommendations; the owner decides. Never say an action has been taken.
- If data is limited (data_sufficiency LOW/LIMITED), say so clearly and soften conclusions.
- Return ONLY valid JSON matching the requested schema. No markdown fences, no extra text.
```

### 13.1 `inventory_analysis_crew`
`config/agents.yaml`
```yaml
stock_analyst:
  role: >
    Inventory Analyst for {shop_name}, a jewellery store
  goal: >
    Explain the stock position for {period_label}: which designs are sold out, running low,
    or stuck as dead stock, and what that means for the shop.
  backstory: >
    You have managed jewellery inventory for years across necklaces, earrings, bangles and more.
    Stock figures, statuses and values are already calculated exactly by the system and given
    to you as facts. Your job is to interpret them clearly. Use tools only to look deeper at a
    specific design when it helps your explanation.

demand_analyst:
  role: >
    Demand and Trend Analyst for {shop_name}
  goal: >
    Explain which designs and categories are in high and low demand in {period_label},
    and any seasonal or month-on-month trends visible in the sales history.
  backstory: >
    You understand Indian jewellery buying patterns: Dhanteras and Diwali (Oct–Nov), the wedding
    season (Nov–Feb), Akshaya Tritiya (Apr–May) and the quieter monsoon months. Demand classes
    (HIGH, STEADY, LOW, DEAD, NEW) are pre-computed by the system using sales velocity; you explain
    them with evidence and add seasonal context.
```
`config/tasks.yaml`
```yaml
analyse_stock_position:
  description: >
    Facts for {period_label} (JSON): {analysis_pack}

    Using these facts (status, stock, min_stock, value_tied_up in designs_of_interest, and the
    kpis), describe the stock position. List sold-out, low-stock and dead-stock designs with a
    short practical note each, and add one note per category that has an issue.
    Follow your skills.
  expected_output: >
    JSON matching StockPositionOutput: summary, out_of_stock, low_stock, dead_stock, category_notes.
  agent: stock_analyst

classify_demand:
  description: >
    Using the same facts, explain demand for {period_label}. Pick up to 10 HIGH demand and up to
    10 LOW/DEAD demand designs, each with a reason quoting the numbers (sold_period, velocity_30d,
    change vs previous period). Add seasonal notes and month-on-month trend notes from
    monthly_sales_by_category.
  expected_output: >
    JSON matching DemandOutput: summary, high_demand, low_demand, seasonal_notes, trend_notes.
  agent: demand_analyst
  context:
    - analyse_stock_position
```
Skills: `stock_status_rules.md` (definitions of IN/LOW/OUT/DEAD from 6.2, why dead stock matters: money tied up, suggest discount/remake/exchange ideas as *options*), `demand_classification.md` (definitions from 6.5 and the Indian seasonality calendar above, "don't call a design LOW only because it is off-season").

### 13.2 `audit_crew`
Agent `stock_auditor`: role "Stock Auditor for {shop_name}". Goal: "Review the rule-detected anomaly candidates for {period_label} and explain which ones need the owner's attention and what to check." Backstory: a careful auditor who knows the common data-entry mistakes in jewellery shops (wrong quantity, sale entered twice, cost typed wrong, returns not recorded) and never accuses staff, only suggests checks.
Task `detect_anomalies`: input `{anomaly_candidates}` (JSON) + `{period_label}`. It may call `get_label_details` for at most 3 labels. Output `AnomalyOutput` (≤ 10 items, severity justified). If there are no candidates, return an empty list and a summary "No unusual entries found."
Skill: `anomaly_checks.md` (the rules in 6.8 and what to check for each).

### 13.3 `purchase_planning_crew`
Agents:
- `procurement_planner`: role "Purchase Planner". Goal: "Decide which designs to restock for {period_label} and how many, using the system's reorder baseline, demand and seasonality." Backstory: an experienced buyer who balances not missing sales against not tying up money. Skill: `reorder_quantity_rules.md`. They may adjust the baseline quantity by at most ±50% with a stated reason (e.g. festive season coming → more). They must not reorder DEAD designs, and must skip LOW-demand items unless they are sold out with a reason.
- `cost_accountant`: role "Cost Accountant". Goal: "Calculate the expected purchase cost of each recommended line and the total budget." Backstory: "You never do arithmetic in your head; you always call calculate_purchase_cost for each line." Tools: `calculate_purchase_cost`. Skill: `costing_rules.md` (formula 6.6, inflation resolution, rupee formatting).
Tasks: `recommend_reorders` (input `{reorder_baseline}`, `{demand_summary}`, `{period_label}`, `{upcoming_season}` → `ReorderOutput`), then `estimate_budget` (context: recommend_reorders → `BudgetOutput`).
**After the crew:** `purchase_plan_service.create_from_ai(db, run, reorder_output)` creates the DRAFT plan with costs **recomputed by code**. The stored `budget` output is replaced by the service-computed totals. Keep the AI's `notes` text.
`upcoming_season` is computed in Python from today's month: e.g. Sep → "Dhanteras/Diwali in Oct–Nov", Oct–Jan → "wedding season", Mar → "Akshaya Tritiya in Apr–May", Jun–Aug → "monsoon (usually slower)".

### 13.4 `reporting_crew`
Agent `report_writer`: role "Chief Accountant writing the owner's insights report". Goal: "Write a clear, honest, actionable insights report for {period_label} with a conclusion the owner can act on today." Backstory: "You have been the trusted accountant of jewellery shops for 20 years. Owners rely on you to tell them, in simple words, what is happening, what to worry about and what to do next. You write short paragraphs, use rupee figures, and always end with clear recommendations — but the owner makes the decisions." Skill: `report_style_guide.md` (tone, length limits per field, the headline formula "what changed + biggest issue", map each recommended action to a `target`).
Task `write_insights_report`: inputs `{kpis}`, `{stock_summary}`, `{demand_summary}`, `{anomaly_summary}`, `{plan_summary}` (total budget, item count, top 5 lines), `{data_sufficiency}`, `{period_label}` → `InsightsReport`.

### 13.5 `assistant_crew` (chatbot)
Agent `accountant_assistant`: role "AI Accountant for {shop_name}". Goal: "Answer the {user_role}'s question accurately using the shop's real data, explain the reasoning in simple words, and suggest useful follow-up questions." Backstory: "You are the shop's accountant. You always look up the numbers with your tools before answering, and you say clearly when the data doesn't contain the answer. You reply in the same language the user writes in (English, Hindi or Hinglish). You never make purchases, edit stock or decide for the owner; you advise." Tools: all tools in 12.4. `max_iter = AGENT_MAX_ITER`. Skill: `answering_guidelines.md`:
- Start with the direct answer in 1–2 sentences, then the supporting numbers.
- Use a table when listing more than 3 designs. Use a chart only when comparing ≥ 3 values over categories or time.
- For "should I…" questions, give the considerations and a recommendation, and state that the owner decides.
- Refuse unrelated requests politely ("I can help with your shop's stock, sales and purchases").
- Follow-up questions are short and specific to the data.

Task `answer_question`: inputs `{question}`, `{chat_history}` (last 6 messages, "role: text" lines), `{shop_snapshot}` (kpis + top alerts + latest insights headline, compact JSON), `{today}`, `{user_role}` → `ChatAnswer`.

**Suggestions** (`GET /chat/suggestions`), built in Python with no AI. Mix 4 static + up to 4 dynamic:
- Static (owner): "What should I restock this month and how much money do I need?", "Which designs are not selling?", "How are sales this month compared to last month?", "Which category earns the most?"
- Static (admin): "Which designs are running low?", "Show today's sales", "Are there any unusual entries I should check?", "Summarise stock by category"
- Dynamic: "Why is {top OUT HIGH label} selling so fast?", "Should I reorder {LOW label}?", "How much money is stuck in dead stock?" (if dead > 0), "How did {top category} do this quarter?"
- If the shop has no designs: "How do I get started?", "What will the AI insights show me?"

### 13.6 Insights Flow (`ai/flows/insights_flow.py`)
Use a CrewAI `Flow[InsightsState]` (state: run_id, job_id, period, pack, outputs) with these steps. Each step calls `run_crew_step`, so it never raises:

| # | step key | label (shown in UI) | does |
|---|---|---|---|
| 1 | `prepare` | Preparing your shop data | Python: build pack, save to run (no LLM) |
| 2 | `stock` | Analysing stock levels | inventory_analysis_crew (task 1) |
| 3 | `demand` | Understanding demand and trends | inventory_analysis_crew (task 2): run as one crew kickoff with both tasks; mark both steps from the task callbacks |
| 4 | `audit` | Checking records for anything unusual | audit_crew (skip the LLM if there are no candidates → instant rule-based) |
| 5 | `plan` | Planning purchases and budget | purchase_planning_crew → create the DRAFT plan |
| 6 | `report` | Writing the accountant's conclusion | reporting_crew |
| 7 | `save` | Saving insights | Python: persist, status COMPLETE (or PARTIAL if any step used rule-based), publish `job_finished` |

Steps run **sequentially** (free-tier rate limits). Expected LLM requests per run ≈ 8–14.

**Starting a run** (`POST /insights/runs`): create the job + the run (status RUNNING) → start a background thread: `threading.Thread(target=run_insights, daemon=True)`. Inside it, acquire the global AI semaphore, open its own DB session, run the flow, and release in `finally`. Jobs left RUNNING at server startup are marked FAILED ("Server restarted").

**Chat job:** the same pattern. Job steps: `think` ("Reading your question"), `answer` ("Preparing the answer"). Tool events stream as `tool`. On finish, update the assistant message (COMPLETE, content = answer_markdown, payload = the rest) and publish `done`. If the semaphore is busy (an insights run is going), the job step note says "Waiting for the AI to finish the insights report…".

---

## 14. Excel Import/Export
- Template: sheet "Designs" with headers in row 1 (as in 8.4), data validation lists for metal and purity, an example row in grey italic, and a "Help" sheet explaining the columns.
- Import: read with openpyxl. Skip fully empty rows. Validate every row (same rules as bulk create, label uniqueness within the file and against the DB). Dry-run returns errors with Excel row numbers. Commit creates everything in a single transaction.
- Exports: as listed in 8.9 and the plan export. Number format `₹#,##,##0.00` (Indian grouping) for money columns, column widths auto-fit (approximate), freeze panes at A2.

---

## 15. Demo Data Generator (`demo_data_service.load`), optional, button-triggered
Purpose: lets the owner see a full demo instantly. **Never runs automatically.**
- Fixed `random.Random(42)` → reproducible.
- 8 categories: Necklaces `NK` (necklace), Earrings `ER` (earring), Bangles `BG` (bangle), Bracelets `BR` (bracelet), Anklets `AN` (anklet), Rings `RG` (ring), Chains `CH` (chain), Pendants `PD` (pendant).
- 2–3 subcategories each (e.g. Earrings: Studs, Jhumkas, Hoops; Necklaces: Choker, Long haar, Mangalsutra; Bangles: Kada, Thin bangles; Rings: Ladies, Gents, Engagement; Anklets: Silver payal, Gold anklets; Chains: Rope, Box; Pendants: Religious, Fashion; Bracelets: Chain bracelet, Charm).
- ~120 designs (12–20 per category). Realistic ₹ cost ranges per category (e.g. silver anklets ₹1,200–4,000; gold earrings ₹15,000–80,000; necklaces ₹60,000–4,00,000). Selling price = cost × 1.15–1.35. Purity 22K/18K for gold, 925 for silver. Weights consistent with the price.
- History: OPENING stock 12 months ago (5–20 pieces). Monthly sales per design from a popularity weight (a few stars, many average, ~15% duds) × seasonality (Oct–Nov ×1.8, Dec–Feb ×1.4 for necklaces/bangles/sets, Apr–May ×1.3, Jun–Aug ×0.75). Sales spread over random days. PURCHASE restocks when stock falls below min (with ~4% cost increase every few months). A few customer returns and corrections.
- Guaranteed situations: ≥ 6 HIGH-demand designs currently OUT; ≥ 10 LOW stock; ≥ 15 DEAD (no sale for 100+ days); 1 cost jump of +30%; 1 big sale (12 pieces); 1 design priced below cost.
- All movements `source=DEMO`, created_by = the requesting user. Bump data_version once at the end. Must finish in < 5 s.

---

## 16. Testing
- `conftest.py`: temp SQLite file per test session (`tmp_path`), override `get_db`, `LLM_MOCK_MODE=true`, client fixtures `owner_client` and `admin_client` (logged-in headers), factories `make_category`, `make_design(stock=…)`, `record(...)`.
- Required tests:
  1. Auth: correct login per role. Wrong password 401. Role mismatch 403. Protected route without token 401.
  2. Categories: create, duplicate name 409, prefix suggestion, delete non-empty 409.
  3. Designs: bulk create with opening stock. Duplicate label in batch → 422 with row index. next-labels sequence. Archive.
  4. Stock: sale reduces stock. Cannot oversell (409). Void restores stock. Cannot void an IN that would go negative. Backdated sale respects stock_as_of. Future date 422.
  5. Periods: financial-year quarter boundaries (Jan → Q4 of the previous FY). The closing = stock_as_of identity holds for random data.
  6. Status and demand: OUT/LOW/DEAD precedence. NEW rule. Small group → STEADY.
  7. Costing: 100 × 1.05 = 105.00. Overrides precedence. Rounding half-up.
  8. Reorder baseline formula (incl. OUT with no velocity → min_stock).
  9. Dashboard: blank shop returns zeros + setup steps; after data, counts match.
  10. Purchase plans: admin cannot decide (403). Owner approve_all. Receive creates PURCHASE movements and moves the status to RECEIVED.
  11. AI (mock mode): an insights run completes with status PARTIAL, all sections present, and a DRAFT plan whose totals equal the service calculation. A chat message completes with a ChatAnswer.
  12. Demo data loads and the guaranteed situations exist. Second load without force → 409.
- Command: `pytest -q`. All tests must pass before the frontend is integrated.

---

## 17. Implementation Phases and Acceptance Checks

| Phase | Build | Done when |
|---|---|---|
| **B1 Skeleton** | folders, requirements, config, database, errors, clock, `/health`, CORS, `.env.example`, README | `uvicorn` starts. `GET /api/v1/health` → ok. `/docs` loads |
| **B2 Auth** | users model, seeding, security, login/me/logout, deps, permissions helper | owner/owner and admin/admin log in. Role mismatch 403. Tests 1 pass |
| **B3 Catalogue** | categories, subcategories, designs (bulk, labels, photos, archive, search), audit, data_version | Tests 2–3 pass. Photos served at `/media/photos/...` |
| **B4 Stock and periods** | movements, void, batch, today, periods resolve/options/stock | Tests 4–5 pass |
| **B5 Metrics and dashboard** | metrics, status, demand, alerts, instant insights, dashboard overview, reports, EventBus + `/events/stream` | Tests 6, 9 pass. SSE `data_changed` received after a sale (manual test with curl) |
| **B6 Costing and plans** | costing, reorder baseline, purchase plans (all endpoints), exports | Tests 7, 8, 10 pass |
| **B7 AI foundation** | ModelManager, smoke test, tools, outputs, fallbacks, runner, jobs + `/jobs/{id}/events` | `python -m app.ai.smoke_test` prints a valid JSON answer from Gemini (or reports a cooldown cleanly). Mock-mode test 11 (insights part) passes |
| **B8 Crews and flow** | all crews' YAML + skills + crew.py, insights flow, `/insights/*` | A real run on demo data finishes in < 3 min with a COMPLETE or PARTIAL status, the report makes sense, and the plan is created |
| **B9 Chat** | assistant crew, chat endpoints, suggestions | Asking "Which designs are sold out?" on demo data returns a correct table |
| **B10 Data tools** | import/export, demo data, reset, ai-status | Tests 12 pass. Import template round-trips |
| **B11 Hardening** | full test suite, logging, README | `pytest -q` green. README documents run/test/reset/demo/troubleshooting (quota, model IDs, `.env` comments) |

`app/ai/smoke_test.py`: build one Agent ("You are a test assistant") + one Task ("Return JSON {\"ok\": true, \"model\": \"<your model>\"}") with the primary LLM, kick it off, and print the result and elapsed time. On a quota/overload error, print a clear message and try the fallback model.

---

## 18. Logging, Errors, Misc
- Standard `logging` with format `%(asctime)s %(levelname)s %(name)s: %(message)s`. Log every AI step start/end, the model used, its duration and any fallback reason. **Never log the API key or JWT.**
- `AppError(code, message, status, details)` raised by services. Handlers convert AppError, HTTPException, RequestValidationError and unhandled exceptions (500 `INTERNAL_ERROR` with a generic message; details logged).
- CORS: allow the origins from settings, the methods `*` and the headers `*`, with credentials false.
- Static files: `app.mount("/media", StaticFiles(directory=PHOTO_DIR parent), name="media")` so `/media/photos/x.jpg` works.
- Timezone: `clock.today()` uses `zoneinfo.ZoneInfo(settings.TIMEZONE)`. On Windows, `zoneinfo` needs the **`tzdata`** package. Add `tzdata` to requirements.
- Keep every endpoint handler thin: parse → call service → map to schema.

---

## 19. Definition of Done (Backend)
- All phases accepted, `pytest -q` green.
- With the shop blank: login works, the dashboard returns zeros and setup steps, and the insights endpoint returns `422 NO_DATA` with the message "Add some designs and stock first".
- After adding a category, designs and some sales, the dashboard numbers update and a `data_changed` event arrives within 1 s.
- An insights run produces a report, a chat answer works, and the purchase plan approve → receive cycle updates stock.
- Turning Gemini off (invalid key or `LLM_MOCK_MODE=true`) still produces rule-based insights and a polite chat fallback, with no 500 errors.
