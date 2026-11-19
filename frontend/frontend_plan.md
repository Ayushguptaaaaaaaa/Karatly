# Frontend Plan: Jeweler AI Accountant (POC)

> **Audience:** the engineer or AI model implementing the frontend. Follow this document **exactly and in order**.
> **API source of truth:** `../backend/backend_plan.md` Section 8 (endpoints, JSON fields, enums). Never invent endpoints or field names. If something is missing, add it to the backend plan first.
> **Related:** `../solution.md` (product), `../architecture.md` (high level).

---

## 0. How to Use This Document

1. Build in the **phases of Section 16**, in order. Each phase has acceptance checks.
2. The **experience goals** (Section 1) matter as much as the functionality. The app must feel **premium, alive and effortless**, so a jeweller wants to open it every day.
3. Keep every screen **simple on the surface**. Advanced options go behind "More options" accordions, not on the main path.
4. The development machine is Windows (PowerShell). Node v24 and npm v11 are installed.
5. The backend runs at `http://127.0.0.1:8000`. The frontend dev server runs at `http://localhost:5173` and proxies `/api` and `/media` to the backend.

---

## 1. Experience Goals (what "hooked" means here)

| Goal | How we achieve it |
|---|---|
| **Instant clarity** | The dashboard answers "How is my shop doing?" in 5 seconds: big numbers, colours, one AI headline |
| **Feels premium** | Ivory + charcoal + **gold** palette, elegant serif headings (jewellery-brand feel), soft shadows, generous spacing |
| **Feels alive** | Numbers count up, the stock count flips when changed, a "Live" pulse when connected, AI progress steps animate, gentle celebration at milestones |
| **Effortless stock changes** | Every design row has **− / +** buttons. Two taps record a sale. Undo is always one click away |
| **Guided from blank** | First login shows a friendly **setup checklist** instead of empty charts. Each step has one big button |
| **Trustworthy AI** | Every AI statement has a **"Why?"** showing the numbers. The AI never acts; the owner approves |
| **Works on phone** | Fully responsive: bottom tab bar, card lists instead of wide tables, chat as a full-screen sheet |
| **Never stuck** | Every loading state has a skeleton, every empty state a call to action, every error a retry |

---

## 2. Tech Stack

| Concern | Package | Notes |
|---|---|---|
| Build | **Vite** (React + TS template) | `npm create vite@latest frontend -- --template react-ts` (run from the repo root. The `frontend/` folder already holds this plan, so scaffold into a temp folder and move the files in if the tool refuses a non-empty dir) |
| UI | **React 18+**, **TypeScript** (strict) | |
| Components | **Mantine** (latest stable major): `@mantine/core`, `hooks`, `form`, `notifications`, `modals`, `dates`, `charts`, `dropzone`, `spotlight` | All `@mantine/*` packages must share the **same version**. Needs `postcss-preset-mantine` + `postcss-simple-vars` |
| Charts | `@mantine/charts` (+ its peer `recharts`) | |
| Data tables | **mantine-datatable** | Check its peer-dependency range matches the installed Mantine major. If not, pin Mantine to the newest major it supports |
| Icons | `@tabler/icons-react` | |
| Routing | `react-router` (v7, declarative `BrowserRouter`/`Routes`) | |
| Server state | `@tanstack/react-query` (+ devtools in dev) | |
| Client state | `zustand` (auth, period, UI prefs) | with `persist` middleware |
| API types | `openapi-typescript` (dev) + `openapi-fetch` | generate types from the backend's `/openapi.json` |
| SSE | `@microsoft/fetch-event-source` | sends the `Authorization` header (native EventSource can't) |
| Dates | `dayjs` (+ relativeTime, customParseFormat) and `@mantine/dates` | |
| Motion | `motion` (Framer Motion; import from `motion/react`) | |
| Celebration | `canvas-confetti` | milestones only |
| Markdown | `react-markdown` + `remark-gfm` | chat answers |
| Fonts | `@fontsource/playfair-display` (600, 700), `@fontsource-variable/inter` | self-hosted, no CDN |
| Tests | `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom` | |
| Lint/format | eslint (vite default) + prettier | |

`.env` for the frontend (`frontend/.env`, gitignored, also create `.env.example`):
```
VITE_API_BASE_URL=/api/v1
VITE_SHOW_DEMO_HINT=true
VITE_APP_NAME=Jeweler AI Accountant
```

`vite.config.ts` dev proxy:
```ts
server: { port: 5173, proxy: {
  "/api":   { target: "http://127.0.0.1:8000", changeOrigin: true },
  "/media": { target: "http://127.0.0.1:8000", changeOrigin: true } } }
```
SSE through the Vite proxy works. If buffering is observed, set `proxyTimeout: 0`.

npm scripts: `dev`, `build`, `preview`, `test`, `lint`, `gen:api` = `openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/schema.d.ts`.

---

## 3. Visual Design System

### 3.1 Colours (`src/theme/theme.ts`)
- **gold** (primary, 10 shades for Mantine): `["#fbf6e9","#f4e9c9","#ead7a0","#dfc373","#d5b24e","#cfa636","#c99e2a","#b0891f","#9d7a18","#86670e"]`. `primaryColor: "gold"`, `primaryShade: { light: 7, dark: 5 }` (keeps text contrast on buttons ≥ 4.5:1; use dark text `#1f1d1a` on gold buttons in dark mode).
- **ink** (neutrals): text `#1f1d1a`, secondary text `#6b665e`, borders `#e9e4d8`.
- **Backgrounds:** light page `#faf8f3` (ivory), surface/cards `#ffffff`. Dark page `#121110`, surface `#1b1a18`, border `#2c2a26`, text `#f3efe6`.
- **Status colours** (always paired with an icon + text, never colour alone):
  - IN (In stock): teal `#2b8a3e`, icon `circle-check`
  - LOW (Low stock): amber `#e67700`, icon `alert-circle`
  - OUT (Sold out): red `#c92a2a`, icon `circle-x`
  - DEAD (Not selling): slate `#5c5f66`, icon `zzz`
- **Demand colours:** HIGH flame `#e8590c` (icon `flame`), STEADY blue `#1971c2` (icon `trending-up`), LOW grey `#868e96` (icon `trending-down`), DEAD slate (icon `zzz`), NEW cyan `#0c8599` (icon `sparkles`).
- **Severity** (instant insights/anomalies): critical red, warning amber, info blue, success teal.
- **Gold gradient** (hero titles, AI headline border, primary CTA hover): `linear-gradient(135deg, #f4e9c9 0%, #cfa636 45%, #9d7a18 100%)`.

### 3.2 Typography
- Headings (h1–h3, KPI numbers, AI headline): **Playfair Display** 600/700.
- Everything else: **Inter Variable**.
- Numbers use `font-variant-numeric: tabular-nums` (class `.num`).
- Labels (`ER-1012`) use `font-family: ui-monospace, "JetBrains Mono", Consolas, monospace` with weight 600 and letter-spacing 0.02em (component `LabelCode`).

### 3.3 Shape, depth and spacing
- Radius: `md` 12px default for cards/inputs, `xl` 20px for hero cards, pills for badges.
- Shadows: cards `0 1px 2px rgba(31,29,26,.04), 0 4px 16px rgba(31,29,26,.06)`. Hover `0 8px 28px rgba(31,29,26,.10)`.
- Spacing scale: Mantine defaults. Page padding 24px desktop, 16px mobile. Card padding 20px. Grid gutter 20px.
- Thin 1px borders in light mode. Hairline borders + slightly lighter surface in dark mode.

### 3.4 Motion rules (`src/lib/motion.ts`)
- Durations: micro 120ms, standard 200ms, emphasis 350ms. Easing `[0.22, 1, 0.36, 1]`.
- Page enter: fade + 8px rise (200ms). Lists: stagger children 30ms (max 10 animated, the rest instant).
- KPI numbers: `CountUp` animates from the previous value to the new one over 700ms.
- Stock number change: vertical "flip" (old slides up and fades, new slides in) + brief colour flash (green for +, red for −).
- Cards: hover lift `translateY(-2px)` + shadow.
- AI generation steps: the current step's icon pulses. Done steps check in with a scale-pop.
- "Live" indicator: a 8px green dot with a pulsing ring.
- Celebration (`src/lib/confetti.ts`): gold/ivory confetti burst (~120 particles, 1.2s) **once per milestone**: first category created, first design batch created, first sale recorded, first AI insights generated, first plan approved. Store fired milestones in localStorage `jaa.milestones`.
- **Respect `prefers-reduced-motion`:** disable count-up, flips and confetti, keep instant state changes.

### 3.5 Dark mode
Light by default. A toggle in the header (sun/moon) uses Mantine `useMantineColorScheme`, persisted. All custom colours come from CSS variables defined for both schemes in `global.css`.

### 3.6 Formatting (`src/lib/format.ts`)
- `formatINR(v, {compact?: boolean, decimals?: 0|2})`:
  - full: `Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 0})` → `₹1,84,500`
  - compact: ≥ 1,00,00,000 → `₹1.2 Cr`. ≥ 1,00,000 → `₹1.84 L`. ≥ 1,000 → `₹45.2K`. Else full.
- `formatNumber(n)` → en-IN grouping. `formatPct(p)` → `+12.4%` / `−3.1%` (true minus sign).
- Dates: `formatDate("2026-11-19")` → `19 Nov 2026`. `formatRelative(iso)` → "2 hours ago". Today/Yesterday words for movements.
- Movement type labels and icons map (from backend Section 5.1):
  OPENING "Opening stock" (`package`), PURCHASE "New stock received" (`truck-delivery`), CUSTOMER_RETURN "Customer return" (`arrow-back-up`), ADJUSTMENT_IN "Correction (+)" (`adjustments`), SALE "Sale" (`shopping-bag`), SUPPLIER_RETURN "Return to supplier" (`arrow-forward-up`), ADJUSTMENT_OUT "Correction (−)" (`adjustments`).

---

## 4. Folder Structure (create exactly this)

```
frontend/
├── frontend_plan.md
├── index.html                    # title "Jeweler AI Accountant", favicon gem icon (SVG)
├── package.json  tsconfig.json  tsconfig.node.json  vite.config.ts
├── postcss.config.cjs            # postcss-preset-mantine + simple-vars breakpoints
├── .env  .env.example
├── public/
│   └── gem.svg
└── src/
    ├── main.tsx                  # providers: MantineProvider, QueryClientProvider, Notifications, ModalsProvider, Router
    ├── App.tsx                   # routes
    ├── theme/
    │   ├── theme.ts              # createTheme (colors, fonts, radius, component defaults)
    │   └── global.css            # CSS variables, .num, gold gradient utilities, scrollbar, focus ring
    ├── api/
    │   ├── schema.d.ts           # GENERATED (npm run gen:api), never edit by hand
    │   ├── client.ts             # openapi-fetch client + auth header + error normalisation
    │   ├── errors.ts             # ApiError {status, code, message, details}
    │   ├── queryKeys.ts          # key factory
    │   └── hooks/                # one file per area, React Query hooks
    │       ├── useAuth.ts  useCategories.ts  useDesigns.ts  useStock.ts  usePeriods.ts
    │       ├── useDashboard.ts  useReports.ts  useReorder.ts  usePurchasePlans.ts
    │       ├── useInsights.ts  useChat.ts  useJobs.ts  useSettings.ts  useAdminTools.ts
    │       └── useLiveEvents.ts  # global SSE → invalidations
    ├── stores/
    │   ├── authStore.ts          # token, user, remember flag
    │   ├── periodStore.ts        # {period_type, anchor} shared by pages
    │   └── uiStore.ts            # sidebar collapsed, chat drawer open, live status
    ├── routes/
    │   ├── ProtectedRoute.tsx    # requires token; else redirect "/"
    │   └── RoleGate.tsx          # hides/disables by role
    ├── layouts/
    │   ├── PublicLayout.tsx      # landing/login background
    │   ├── AppLayout.tsx         # AppShell: Sidebar + Header + Outlet + MobileTabBar + QuickStockFab
    │   ├── Sidebar.tsx  Header.tsx  MobileTabBar.tsx  UserMenu.tsx
    ├── pages/
    │   ├── Landing/LandingPage.tsx
    │   ├── Login/LoginPage.tsx
    │   ├── Dashboard/DashboardPage.tsx + components/ (SetupChecklist, KpiRow, AiHeadlineCard, StockHealthDonut,
    │   │                                  SalesTrendCard, InstantInsightsList, TopSellersCard, AlertsCard, ActivityFeed, LockedPreview)
    │   ├── Inventory/CategoriesPage.tsx, CategoryDetailPage.tsx, DesignDetailPage.tsx
    │   │   └── components/ (CategoryCard, AddCategoryModal, IconPicker, SubcategoryBar, DesignsTable, DesignsGrid,
    │   │                    DesignCardMobile, AddDesignsWizard/{StepSetup, StepGrid, StepReview}, EditDesignDrawer,
    │   │                    ImportExcelModal, PhotoUploader, DesignHistoryChart, MovementTimeline)
    │   ├── Stock/StockPage.tsx + components/ (QuickEntryPanel, TodayEntries, MovementsTable, PeriodView)
    │   ├── Insights/InsightsPage.tsx + components/ (InsightsHeader, GenerateHero, GenerationProgress, ReportView,
    │   │        ConclusionCard, ActionsList, DemandSection, StockRiskSection, PlanSummaryCard, AnomaliesSection,
    │   │        TrendsSection, WhyCollapse, PartialBanner, RunHistoryMenu)
    │   │   └── chat/ (ChatPanel, ChatMessageList, ChatBubble, ChatAnswerTable, ChatAnswerChart, SuggestionChips,
    │   │              ChatInput, TypingIndicator, ChatSessionsMenu, MobileChatSheet)
    │   ├── PurchasePlans/PlansListPage.tsx, PlanDetailPage.tsx + components/ (PlanStatusStepper, PlanItemsTable,
    │   │        PlanItemCardMobile, DecisionToggle, PlanTotalsBar, ReceiveModal, CreatePlanButton)
    │   ├── Reports/ReportsPage.tsx + components/ (SalesTab, StockTab, DeadStockTab, CompareTab, ChartCard, ExportButton)
    │   ├── Settings/SettingsPage.tsx + components/ (ShopProfileForm, BusinessRulesForm, AiStatusCard, DataToolsCard)
    │   └── NotFound/NotFoundPage.tsx
    ├── components/               # shared
    │   ├── PageHeader.tsx  SectionCard.tsx  EmptyState.tsx  ErrorState.tsx  LoadingSkeletons.tsx
    │   ├── KpiCard.tsx  CountUp.tsx  MoneyText.tsx  LabelCode.tsx  PhotoThumb.tsx
    │   ├── StatusBadge.tsx  DemandBadge.tsx  SeverityIcon.tsx  CategoryIcon.tsx
    │   ├── StockStepper.tsx      # − [12] + with flip animation, opens QuickStockPopover
    │   ├── QuickStockPopover.tsx # the core add/subtract UI
    │   ├── QuickStockFab.tsx     # floating "Quick stock" button + drawer
    │   ├── LabelSearchSpotlight.tsx
    │   ├── PeriodPicker.tsx  ConfirmModal.tsx  LiveIndicator.tsx  RoleBadge.tsx
    │   └── charts/ (Sparkline, DonutWithLegend, AreaTrend, BarCompare)
    ├── lib/
    │   ├── format.ts  dates.ts  motion.ts  confetti.ts  movementTypes.ts  constants.ts  storage.ts
    └── test/ (setup.ts, utils.tsx, *.test.tsx)
```

---

## 5. App Architecture

### 5.1 Providers (`main.tsx`)
`MantineProvider(theme, defaultColorScheme="light")` → `ModalsProvider` → `Notifications position="top-right"` → `QueryClientProvider` (defaults: `staleTime: 30_000`, `refetchOnWindowFocus: true`, `retry: 1`. No retry on 401/403/404/409/422) → `BrowserRouter` → `App`.

### 5.2 Routes (`App.tsx`)
| Path | Page | Access |
|---|---|---|
| `/` | LandingPage | public (if already logged in → redirect `/app`) |
| `/login/owner` | LoginPage role=OWNER | public |
| `/login/admin` | LoginPage role=ADMIN | public |
| `/app` | DashboardPage | protected |
| `/app/inventory` | CategoriesPage (supports `?status=OUT` → jumps to an "All designs" filtered view) | protected |
| `/app/inventory/:categoryId` | CategoryDetailPage (`?sub=<id>&status=&demand=`) | protected |
| `/app/designs/:designId` | DesignDetailPage | protected |
| `/app/stock` | StockPage (tabs: `?tab=quick\|history\|period`) | protected |
| `/app/insights` | InsightsPage (`?run=<id>` optional) | protected |
| `/app/purchase-plans` | PlansListPage | protected |
| `/app/purchase-plans/:planId` | PlanDetailPage | protected |
| `/app/reports` | ReportsPage (`?tab=sales\|stock\|dead\|compare`) | protected |
| `/app/settings` | SettingsPage | protected |
| `*` | NotFoundPage | |

All `/app/*` pages are lazy-loaded (`React.lazy` + `Suspense` with a page skeleton).

### 5.3 Auth (`authStore.ts`, `client.ts`)
- State: `{token, expiresAt, user: {id, username, display_name, role}, remember}`. With `remember=true`, persist to localStorage; otherwise to sessionStorage (zustand persist with a custom storage).
- `client.ts` attaches `Authorization: Bearer <token>`. On **401** from any call (except login) → clear auth, show the notification "Session expired. Please log in again." and navigate to `/`.
- On app start, if a token exists and `expiresAt` has passed → clear it. Otherwise call `/auth/me` once to validate.
- Logout: `POST /auth/logout` (ignore errors) → clear → `/`.

### 5.4 Data layer
- Typed client: `createClient<paths>({ baseUrl: import.meta.env.VITE_API_BASE_URL })`, plus a middleware for auth and error normalisation. Every hook unwraps `{data, error}` and throws `ApiError` on error.
- `ApiError` carries `status`, `code`, `message`, `details`. The UI shows `message` (the backend writes friendly messages). Bulk-row errors map `details.rows` onto grid cells.
- Query keys (`queryKeys.ts`):
  `['dashboard', period]`, `['categories']`, `['category', id]`, `['designs', filters]`, `['design', id]`, `['designHistory', id]`, `['designSearch', q]`, `['movements', filters]`, `['stockToday']`, `['periodStock', params]`, `['periodOptions']`, `['alerts', status]`, `['reports', name, params]`, `['reorder', categoryId]`, `['plans', status]`, `['plan', id]`, `['insightsLatest']`, `['insightRuns']`, `['insightRun', id]`, `['chatSessions']`, `['chatSession', id]`, `['chatSuggestions']`, `['job', id]`, `['settings']`, `['aiStatus']`.
- **Invalidation map** (call after successful mutations **and** on the SSE `data_changed` event):
  - catalogue/stock change → invalidate `dashboard, categories, category, designs, design, designHistory, movements, stockToday, periodStock, alerts, reports, reorder, insightsLatest (for the stale count), chatSuggestions`.
  - plan change → `plans, plan, dashboard`.
  - settings change → `settings, dashboard, reports, reorder`.
  - Throttle SSE-driven invalidation to at most once per 1.5 s (leading + trailing).

### 5.5 Live events (`useLiveEvents.ts`, mounted once in AppLayout)
- `fetchEventSource("/api/v1/events/stream", {headers: {Authorization}, openWhenHidden: true})`.
- On `hello`: store `data_version` and set `uiStore.live = "connected"`.
- On `data_changed`: if `data_version` > local → run the invalidation map. Keep `lastUpdatedAt` for the "Updated just now" label.
- On `job_finished`: invalidate `insightsLatest`/`insightRuns` or `chatSession`. If the user isn't on the Insights page, show the notification "✨ Your AI insights are ready" with a "View" button.
- On `ai_status`: invalidate `aiStatus`.
- Reconnect with exponential backoff (1s → 30s). While disconnected, the LiveIndicator turns grey "Offline – retrying".

### 5.6 Job progress (`useJobEvents(jobId)`)
Uses fetch-event-source on `/api/v1/jobs/{id}/events`. Returns `{status, steps[], currentTool, error}`. Updates from `snapshot`/`step`/`tool`/`done`/`error`. Closes on `done`/`error`. If the connection drops, fall back to polling `GET /jobs/{id}` every 3 s.

### 5.7 Period state (`periodStore.ts`)
`{period_type: "month" | "quarter", anchor: "YYYY-MM-DD"}`, default the current month. `PeriodPicker` is a segmented control "Month | Quarter" + a select of options from `GET /periods/options` (labels from the backend, e.g. "November 2026", "Q3 FY2026-27 (Oct–Dec 2026)"). Used by Dashboard, Stock › Period view, Reports and Insights (each page reads and writes the same store so the period stays consistent).

### 5.8 Roles in the UI
- `RoleGate allow={["OWNER"]}` wraps owner-only controls: plan approve/reject/approve-all, "Reset all data".
- Admin sees a muted hint where an owner-only action would be: "Waiting for owner approval".
- Header `RoleBadge`: OWNER (gold crown) / ADMIN (blue shield).

---

## 6. Layout Shell (`AppLayout`)

### 6.1 Desktop (≥ 62em)
- **Sidebar** (260px, collapsible to 76px icons-only; state persisted):
  - Top: gem logo + shop name (from settings) in Playfair.
  - Nav items (icon + label, active = gold left bar + tinted background):
    1. Dashboard (`layout-dashboard`)
    2. Inventory (`diamond`)
    3. Stock (`arrows-exchange`)
    4. Insights (`sparkles`): badge "New" when a run finished since the last visit. A spinner badge while a run is in progress
    5. Purchase Plans (`shopping-cart`): count badge = plans awaiting the owner (owner only)
    6. Reports (`chart-bar`)
    7. Settings (`settings`)
  - Bottom: LiveIndicator + "Updated just now".
- **Header** (64px, sticky, translucent background with `backdrop-filter: blur(8px)`):
  - Left: page title (Playfair) + breadcrumb where relevant.
  - Center: the **search box** "Search label or design… (Ctrl K)" opens `LabelSearchSpotlight`.
  - Right: colour-scheme toggle, RoleBadge, UserMenu (name, role, "Log out").

### 6.2 Mobile (< 48em) and tablet
- Header: burger (opens the sidebar as a drawer), title, search icon, avatar.
- **Bottom tab bar** (fixed, 64px + safe-area): Dashboard, Inventory, **center gold round "+/−" button** (QuickStock), Insights, More (opens a sheet: Purchase Plans, Reports, Settings, Log out).
- Content padding 16px. Bottom padding leaves room for the tab bar.

### 6.3 QuickStockFab (desktop) / center tab (mobile)
On desktop, a floating gold button bottom-right "± Quick stock" (hidden on Stock › Quick entry, where it is redundant). It opens a **right drawer** containing the same `QuickEntryPanel` as the Stock page.

### 6.4 LabelSearchSpotlight
- Mantine Spotlight. Its query calls `GET /designs/search?q=` (debounce 200ms).
- Each result: photo thumb, LabelCode, name, category, stock badge with status colour.
- Actions per result: **Enter** → open the design page. **Shift+Enter / "−" button** → QuickStockPopover in sale mode. **"+" button** → new-stock mode.
- Empty query shows "Recent designs" (last 5 opened, localStorage).

---

## 7. Public Pages

### 7.1 Landing page (`/`)
Purpose: the owner's first impression, and choosing how to log in.
- **Layout:** full-height split. Left 55% is the brand panel. Right 45% holds the login choices (on mobile they stack, brand on top, shorter).
- **Brand panel:**
  - Background: deep charcoal `#16140f` with a subtle radial gold glow and slow-floating sparkle particles (CSS-only, 12 small 4-point stars, 6–10s float loops, disabled for reduced motion).
  - Gem logo (SVG) + app name in Playfair 44px with a **gold shimmer** (an animated background-position gradient on the text, 6s loop).
  - Tagline: "Your AI accountant & inventory partner for jewellery."
  - Three feature bullets with icons (stagger in): "Know every label's stock, live", "AI insights & purchase plans in minutes", "Ask questions in plain language".
- **Choice panel** (ivory background):
  - Heading "Welcome back" + subtext "Choose how you want to sign in".
  - **Two large selectable cards** (full width, 96px tall, radius xl, hover glow + lift, keyboard focusable, Enter activates):
    1. **Owner**: crown icon in a gold circle. Title "Owner". Subtitle "Full access, approvals and AI insights". → navigates to `/login/owner`.
    2. **Admin**: shield icon in a blue circle. Title "Admin". Subtitle "Manage stock, reports and purchase plans". → navigates to `/login/admin`.
  - Footer: small muted "Demo version · Data stays on this computer".
- Motion: the panels fade/slide in (left from −16px, right from +16px). The cards stagger in 80ms apart.

### 7.2 Login page (`/login/owner`, `/login/admin`)
- Same split layout (the brand panel is reused, slimmer on desktop).
- Card content:
  - "← Back" link to `/`.
  - Role chip at the top: "Owner login" (gold) / "Admin login" (blue), with the icon.
  - Heading "Sign in as Owner" / "Sign in as Admin".
  - Form (`@mantine/form`): **Username** (TextInput, autofocus, autocomplete username), **Password** (PasswordInput with a show/hide eye, autocomplete current-password), **Remember me** (Checkbox, default on).
  - Validation: both required ("Please enter your username/password").
  - Submit button full width, gold, "Sign in". It shows a loader while pending and is disabled.
  - Errors appear in an Alert above the button, with a shake animation (6px, 300ms):
    - 401 → "Incorrect username or password."
    - 403 ROLE_MISMATCH → the backend message + a link "Switch to {other} login".
    - Network → "Can't reach the server. Is the backend running?"
  - If `VITE_SHOW_DEMO_HINT=true`: a subtle info line under the form, "Demo login: **owner / owner**" (or admin / admin), with a small "Fill" link that fills both fields.
- On success: store auth → toast "Welcome, Owner ✨" → navigate to `/app` (or to the originally requested protected URL).

---

## 8. Dashboard (`/app`): the eagle's-eye view

The data comes from **one call**: `GET /dashboard/overview` with the period from periodStore. `setup.completed_steps < 5` **and** no designs → **Onboarding mode**. Otherwise → **Overview mode**. (If designs exist but setup isn't complete, Overview mode is shown with a slim "Finish setup (3/5)" banner at the top that expands into the checklist.)

### 8.1 Onboarding mode (blank shop)
- **Welcome hero card** (gold gradient border, radius xl): "Welcome to {shop_name}, {owner_name} 👋". Subtext "Let's set up your shop. It takes about 5 minutes." A progress ring on the right (`completed/5`, animated).
- **SetupChecklist** (vertical stepper, each step a row with icon, title, one-line help, status, and the CTA button on the right; the first incomplete step is highlighted and expanded):
  1. **Add your first category**: "Like Earrings, Necklaces or Bangles." CTA "Add category" → opens AddCategoryModal (in place).
  2. **Add designs with their labels**: "Enter how many designs you have and type their labels (e.g. ER-1012)." CTA "Add designs" → opens AddDesignsWizard for the first category.
  3. **Enter opening stock**: done automatically if designs were created with opening stock. CTA "Go to inventory".
  4. **Record your first sale**: "Tap − on any design to record a sale." CTA "Record a sale" → opens the QuickStock drawer in sale mode.
  5. **Generate your first AI insights**: "Your AI accountant will analyse everything." CTA "Generate insights" → `/app/insights`.
  - Completed steps show a green check, strike-through title and "Done" text, with a check-pop animation.
- **"What you'll see" preview** (LockedPreview): 3 cards (KPI row, Stock health donut, AI headline) rendered with **sample placeholder shapes**, blurred (`filter: blur(3px)`, 60% opacity), with a lock icon overlay and the text "Unlocks when you add designs". This creates curiosity.
- Secondary link (owner/admin): "Just exploring? **Load demo data**" → confirm modal → `POST /admin/demo-data` → confetti → overview mode.

### 8.2 Overview mode
Grid (12 columns desktop; 1 column mobile, same order):

**Row 0: Greeting bar** (full width)
- Left: "Good morning/afternoon/evening, {owner_name}" (Playfair 28px) + today's date "Thursday, 19 Nov 2026".
- Right: PeriodPicker (compact) + LiveIndicator ("Live · updated 5s ago").

**Row 1: AI headline card** (full width, `AiHeadlineCard`)
- Gold gradient 1px border, sparkle icon, label "AI Accountant".
- With `latest_ai`: headline (Playfair 20px) + `conclusion_short` (2 lines, ellipsis) + meta "Generated 2 hours ago · November 2026". If `is_stale`: an amber chip "12 changes since" + a small "Refresh" button (starts a run, then goes to Insights). Primary link button "Open full insights →".
- Without `latest_ai`: "Your AI accountant hasn't analysed the shop yet." + gold button "Generate insights" (only if designs exist).
- While a run is in progress: a shimmering progress bar + "Analysing… step 3 of 7" (from useJobEvents).

**Row 2: KPI cards** (4 across desktop, 2×2 tablet, horizontal scroll-snap on mobile) via `KpiCard`:
1. **Stock value**: `formatINR(stock_value_cost, compact)`. Sub-line "{total_pieces} pieces · {total_designs} designs". Sparkline (stock value, 6 months).
2. **Sales {period label}**: `formatINR(sales_value, compact)`. Delta chip `sales_change_pct` (green ↑ / red ↓, "vs last month"). Sub-line "{sales_units} pieces sold". Sparkline.
3. **Needs attention**: `needs_attention` big number in amber/red. Sub-line "{out_of_stock} sold out · {low_stock} low". Click → `/app/inventory?status=OUT,LOW`.
4. **Money stuck**: `formatINR(dead_stock_value, compact)`. Sub-line "{dead_stock} designs not selling for 90+ days". Click → Reports › Dead stock.
- Each card: icon in a tinted circle top-left, a muted label, the CountUp number, a hover lift. Clickable cards show a chevron.

**Row 3:** (8 + 4 columns)
- **Sales trend** (`SalesTrendCard`, 8 columns): an AreaChart of `sales_trend` (value, gold gradient fill). A toggle "₹ value | pieces". Tooltip with formatted values.
- **Stock health** (`StockHealthDonut`, 4 columns): a DonutChart of `stock_health` with the status colours. Centre label = total designs. The legend rows are clickable → inventory filtered by status.

**Row 4:** (6 + 6 columns)
- **Today at a glance** (`InstantInsightsList`): the `instant_insights` items as rows (severity icon in a tinted circle, title bold, detail muted, action button right). Stagger in. Empty → "All good, nothing needs attention right now ✨".
- **Top sellers** (`TopSellersCard`): top 5 with photo thumb, LabelCode, name, a horizontal bar proportional to units, units + ₹. Click → design page.

**Row 5:** (6 + 6 columns)
- **Sold out & low** (`AlertsCard`): up to 8 alerts. Each row has LabelCode, name, StatusBadge, DemandBadge (flame for HIGH) and a small **"+ Add stock"** button opening QuickStockPopover in new-stock mode. Footer link "See all".
- **Recent activity** (`ActivityFeed`): a timeline of the last 10 movements: icon by type, "Sold 2 × ER-1012", user + relative time. Void entries are struck through. Footer link "Open stock history".

**Row 6 (only if `pending_approvals > 0` and owner):** a banner "1 purchase plan is waiting for your approval" + button.

**Live behaviour:** when `data_changed` arrives, the dashboard query refetches. KpiCards animate to the new numbers, changed rows briefly highlight (gold background fade 1.2s), and "Updated just now" resets.

States: skeletons for each card while loading (same shapes). Error → ErrorState card with Retry.

---

## 9. Inventory

### 9.1 Categories page (`/app/inventory`)
- PageHeader: title "Inventory". Subtitle "{n} categories · {designs} designs · {pieces} pieces". Actions: "Import Excel" (secondary), **"+ Add category"** (primary).
- A filter bar (shown only when designs exist): segmented "Categories | All designs". **All designs** shows the full DesignsTable across categories with filters (used for `?status=` links from the dashboard).
- **Category grid** (responsive: 4/3/2/1 columns) of `CategoryCard`:
  - Top: CategoryIcon in a gold-tinted circle, name (Playfair 20px), prefix chip `ER`.
  - Middle: "{design_count} designs · {total_pieces} pcs", stock value (compact ₹).
  - **Status bar:** a thin stacked bar (IN teal / LOW amber / OUT red / DEAD slate) with a tooltip of the counts.
  - Bottom: small badges "{out} sold out" (red) and "{low} low" (amber) if > 0. Subcategory chips (max 3 + "+2").
  - Hover lift. Click → category detail. Kebab menu: Edit, Archive, Delete (only if empty).
  - The last card is a dashed **"+ Add category"** tile.
- **Empty state** (no categories): an illustration (big diamond icon with sparkles), "Start by adding your first category", "Categories group your designs: Earrings, Necklaces, Bangles…", buttons "+ Add category" and "Import from Excel". Quick-add chips under the buttons: `Necklaces` `Earrings` `Bangles` `Bracelets` `Anklets` `Rings` `Chains` `Pendants`. Clicking a chip opens the modal prefilled (name + icon + suggested prefix).

### 9.2 AddCategoryModal (create and edit)
- Fields:
  1. **Name** (required, max 60). On blur → `GET /categories/suggest-prefix?name=` fills Prefix if the user hasn't edited it.
  2. **Icon** (`IconPicker`): a grid of 12 jewellery icons (map backend icon keys to tabler/custom SVGs: necklace → `diamond`, earring → custom SVG, ring → `circle-dot`, bangle → `circle`, bracelet → `link`, anklet → `link`, chain → `chain` / `link`, pendant → `droplet`, nosepin → `point`, set → `stack-2`, coin → `coin`, other → `sparkles`). Selected = gold ring.
  3. **Label prefix** (required, uppercase 1–5 letters, auto-uppercased while typing). Helper "Labels will look like ER-1001".
  4. **Subcategories** (optional, create mode only): a TagsInput "e.g. Studs, Jhumkas, Hoops" (Enter to add). Created after the category in sequence.
  5. "More options" accordion: Description, **Inflation % override** (NumberInput 0–50, placeholder "Uses shop default 5%").
- Footer: Cancel / **Create category**. On success: toast, close, confetti if first category (milestone), navigate to the new category's page with the hint popover "Next: add your designs" pointing at the "+ Add designs" button.
- Errors: 409 duplicate name/prefix → field error under the right input.

### 9.3 Category detail page (`/app/inventory/:categoryId`)
- Breadcrumb: Inventory › Earrings.
- **Header card:** icon, name, prefix, description. Stats row: designs, pieces, stock value, sold (30 days), sold out, low. Actions: "Edit category", "Import Excel", **"+ Add designs"** (primary).
- **SubcategoryBar:** horizontally scrollable chips: "All ({n})", each subcategory "Jhumkas ({n})", then a dashed "+ Add subcategory" chip that turns into an inline TextInput (Enter saves, Esc cancels). Chip kebab menu: Rename, Delete (if empty). The selected chip filters the table (`?sub=`).
- **Toolbar:** search (label/name), Status multi-select (Sold out/Low/In stock/Not selling), Demand select, sort select (Label, Stock low→high, Best selling, Newest), view toggle **Table | Cards** (persisted).
- **DesignsTable** (mantine-datatable, desktop/tablet):
  | Column | Content |
  |---|---|
  | Photo | 40px rounded PhotoThumb (placeholder = CategoryIcon on a tinted bg) |
  | Label | LabelCode (bold mono) + name under it (muted, truncated) |
  | Subcategory | text |
  | **Stock** | **StockStepper**: `[−] 12 [+]`, number in a pill coloured by status |
  | Status | StatusBadge |
  | Demand | DemandBadge |
  | Sold 30d | number |
  | Cost / Selling | ₹ (two lines) |
  | ⋯ | menu: Open, Edit, Upload photo, History, Archive/Delete |
  - Row click (outside the stepper) → design page. Rows with OUT status have a faint red left border. The row being changed flashes.
  - Pagination 25/page, sticky header, total count in the footer.
- **DesignsGrid** (cards view; also the default on mobile via `DesignCardMobile`): photo on top (aspect 4:3), LabelCode + StatusBadge overlay, name, price, a large StockStepper at the bottom.
- **Empty state** (category has no designs): "No designs in Earrings yet", "Add all your earring designs at once: just tell us how many.", button "+ Add designs", secondary "Import Excel".

### 9.4 AddDesignsWizard (modal, size "90%", full-screen on mobile)
Goal: "put in the number of designs, then the labels", and make it fast.

**Step 1: Setup**
- Category (preselected, read-only chip) + **Subcategory** select (optional, with a "+ New" option inline).
- **"How many designs are you adding?"**: a big NumberInput (1–100) with quick chips 5 · 10 · 20 · 50.
- **Opening stock date**: DateInput, default today (helper: "Use an earlier date if this stock was already in your shop").
- **Defaults for all rows** (optional, collapsible): Metal (segmented Gold/Silver/Platinum/Other), Purity select, Min stock, Cost ₹, Selling ₹, Opening stock. These prefill every row.
- Next → calls `GET /designs/next-labels?category_id&count` and builds N rows.

**Step 2: Fill in the grid** (the core)
- An editable table with N rows, sticky header, row numbers. Columns: **Label*** (prefilled `ER-1001…`, editable), Name, **Opening stock*** (stepper input), **Cost ₹***, **Selling ₹***, Weight (g), Purity, Metal, Min stock.
- Above the grid: "Fill down" buttons on numeric/select column headers (a column-header menu → "Apply first row's value to all").
- Keyboard: Tab/Shift+Tab across cells, Enter = the cell below, Ctrl+Enter = submit step. **Paste from Excel:** pasting multi-line tab-separated text into a cell fills the rows/columns starting there (parse `\t` and `\n`).
- Validation, live:
  - Required fields empty → red cell outline + tooltip.
  - Duplicate label within the grid → both cells red, "Duplicate label".
  - Label taken in the shop → debounced (400ms) `GET /designs/check-label` → red "Already used".
  - Selling < cost → amber warning (allowed).
- A counter "{valid}/{N} rows ready". Buttons: "+ Add row", "Remove empty rows", Back, **Review**.

**Step 3: Review**
- A summary card: "{N} designs · {total pieces} pieces · Stock value ₹X (cost)". A list of labels as chips. A note if any selling < cost.
- **Create designs** → `POST /designs/bulk`. While pending, the button loads. On 422, return to Step 2 with the backend row errors mapped onto cells.
- Success: confetti (milestone "first designs"), toast "12 designs added to Earrings ✨". The modal closes and the new rows appear in the table with a staggered highlight.

### 9.5 Design detail page (`/app/designs/:designId`)
- Breadcrumb: Inventory › Earrings › ER-1012.
- **Left column (4/12):** large photo (PhotoUploader: a dropzone "Drop a photo or click to upload". Replace/remove actions), LabelCode (large), name, category/subcategory chips, metal/purity/weight, supplier.
- **Right column (8/12):**
  - **Stock hero card:** the huge current stock number (Playfair 56px, status colour, flip animation) + StatusBadge + DemandBadge + "Min {min_stock}". Big buttons **"− Record sale"** (red outline) and **"+ Add stock"** (teal) → QuickStockPopover. A small link "Other change…" (returns/corrections).
  - **Facts row:** Cost (last cost), Selling, Margin %, Sold 30 days, Velocity "{x}/month", Last sale "{n} days ago".
  - **12-month chart:** a BarChart of sold units per month (gold bars), with received as a muted line.
  - **Movement timeline** (MovementTimeline): grouped by date. Each entry: type icon, "Sale · 2 pcs · ₹12,400", note, user, time, an **Undo** button (void, with a confirm popover "Undo this sale? Stock will go back to 14."). Voided entries are struck through with "Undone by Owner".
- Header actions: Edit (EditDesignDrawer with all fields + inflation override), Archive, Delete (if allowed).

### 9.6 Excel import (ImportExcelModal)
- Step 1: "Download template" link (`/designs/import-template`) + a Dropzone (.xlsx).
- Step 2: dry-run result: "✓ 118 rows ready · 2 errors". A table of errors (row, field, message). "Will create 2 categories, 5 subcategories, 118 designs".
- Step 3: "Import" (dry_run=false) → success toast + confetti for a first import.

---

## 10. Stock: Adding and Subtracting Made Effortless

### 10.1 `StockStepper` (used everywhere a stock number appears in lists)
- Layout: `[−]` round 32px button (red tint), the number pill (min-width 48px, tabular, status colour), `[+]` button (teal tint). On mobile the buttons are 40px.
- **− click** → opens `QuickStockPopover` anchored to the stepper, mode **OUT**, default reason **Sale**, qty 1.
- **+ click** → popover, mode **IN**, default reason **New stock received**, qty 1.
- **Long-press / Shift+click** on − or + → instant ±1 with the default reason (no popover), for speed. Shown in a tooltip: "Shift+click for quick ±1".
- Keyboard: when a table row is focused, `+` and `-` keys open the popover.
- If stock is 0, − is disabled with the tooltip "Nothing to sell, stock is 0".

### 10.2 `QuickStockPopover` (the core interaction, ~280px wide)
```
┌──────────────────────────────┐
│ ER-1012 · Kundan jhumka      │
│ In stock: 12                 │
│ ( Sale | Return to supplier | Correction )   ← reasons for OUT
│        [ − ]  2  [ + ]       │  ← big qty stepper (1..stock)
│ Price per piece  ₹6,200      │  ← only for Sale / New stock, prefilled
│ Date: Today ▾                │  ← click to pick an earlier date
│ Note (optional) …            │  ← collapsed "Add note"
│ [ Cancel ]  [ Record sale ✓ ]│  ← label changes with the reason
│ After this: 10 left          │  ← live preview, red if it would go below 0
└──────────────────────────────┘
```
- IN reasons: **New stock received** (PURCHASE, price = cost per piece prefilled with last cost), **Customer return** (CUSTOMER_RETURN), **Correction (+)** (ADJUSTMENT_IN).
- OUT reasons: **Sale** (SALE, price = selling price), **Return to supplier** (SUPPLIER_RETURN), **Correction (−)** (ADJUSTMENT_OUT, with the note placeholder "e.g. damaged, count fix").
- The submit label is dynamic: "Record sale", "Add 5 pieces", "Save correction". **Enter** submits, **Esc** closes.
- **Optimistic update:** the stepper number flips immediately. On error it rolls back + shows an error toast (e.g. 409 "Only 1 in stock").
- **Success toast** (bottom-left, 8s, with a progress bar): "✓ Sold 2 × ER-1012 · 10 left" + an **Undo** button → `POST /stock/movements/{id}/void` → toast "Undone".
- The first sale ever → confetti milestone.

### 10.3 Stock page (`/app/stock`), three tabs
**Tab 1: Quick entry** (default)
- Two columns (desktop): left `QuickEntryPanel` (60%), right `TodayEntries` (40%). Stacked on mobile.
- **QuickEntryPanel:**
  1. A big **direction switch**: two large toggle cards, **"Stock OUT · Sale"** (red) | **"Stock IN · New stock"** (teal). Keyboard `O` / `I`.
  2. **Find design:** a large Autocomplete with label/name search (`/designs/search`). Each option shows a photo thumb, LabelCode, name and current stock. A barcode-friendly input: typing a full label + Enter selects the exact match (works with USB barcode scanners that type the label).
  3. After selecting: a design mini-card (photo, label, name, current stock big).
  4. Reason chips (as in the popover), a **quantity** big stepper, price, date (default today), note.
  5. **"Record sale"** big button (Ctrl+Enter). After saving: success animation (a check morph), the form keeps the direction and clears the design, and focus returns to search ("ready for the next one"), so a run of sales can be entered quickly.
- **TodayEntries:** a list of today's movements by the current user (`GET /stock/today`), newest first, each with an Undo button. Totals card: "Today: 7 sold · ₹84,000 · 12 received".

**Tab 2: History**
- MovementsTable with filters: date range, type multi-select, category, label search, "Show undone" toggle. Columns: date, type (icon + label), design (thumb + label + name), qty (+/− coloured), price, value, user, note, an Undo action. Server pagination. "Export" button (Excel via the period_stock report where applicable).

**Tab 3: Month / Quarter view** (`PeriodView`)
- Top: PeriodPicker (Month | Quarter + select), category/subcategory selects, status filter, search.
- Summary strip: Opening · Received · Sold · Returns · Corrections · **Closing** · Sales ₹ (totals).
- Table: Label (+ name), Category, Opening, Received, Sold, Customer returns, Supplier returns, Corrections, **Closing (bold)**, Status now. The totals row sticks at the bottom. Zero values are muted.
- "Export to Excel" → `/reports/export?report=period_stock&...`.
- This answers "for this month or quarter, what is the stock left for each label?" directly.

---

## 11. Insights (`/app/insights`): the full AI picture + chatbot

### 11.1 Layout
- Desktop (≥ 75em): **two columns**. Left 8/12 = the report. Right 4/12 = the **ChatPanel**, sticky (`top: header height + 16px`, `height: calc(100vh − header − 32px)`).
- Tablet: the report is full width. Chat is a right Drawer opened by the floating button "Ask AI".
- Mobile: report full width. A floating gold chat button bottom-right (above the tab bar) opens a full-screen `MobileChatSheet`.

### 11.2 InsightsHeader
- Title "Insights" with a sparkles icon. Subtitle "Your AI accountant's analysis of the shop".
- PeriodPicker.
- Meta line (when a run exists): "Generated {relative} · {period_label} · {model badge}". The model badge: "Gemini 3.6 Flash" (gold), "Gemini 3.1 Flash Lite" (blue), "Automatic (AI unavailable)" (grey).
- A stale chip when `changes_since > 0`: "{n} changes since this report" (amber).
- **Primary button "Generate insights"** (first time) / **"Refresh insights"** (later), gold with a sparkle icon. Disabled while a run is in progress. Tooltip: "Uses your free AI quota. Takes about 1–3 minutes."
- RunHistoryMenu (clock icon): the last 20 runs → `?run=<id>`.

### 11.3 States
1. **No designs:** EmptyState "Add your inventory first", "The AI needs some designs and stock to analyse.", button "Go to inventory".
2. **Designs but never generated:** `GenerateHero`, a large gradient card: an animated sparkle illustration, "Meet your AI accountant", 3 bullets (what you'll get: a conclusion, what's selling and what's not, a purchase plan with budget), a big **"Generate my first insights"** button. If `data_sufficiency` would be low (fewer than 20 sales), a soft note: "Tip: insights get sharper as you record more sales. You can still generate now."
3. **Generating:** `GenerationProgress` replaces the report area:
   - A vertical stepper with the 7 steps from the job (`prepare`, `stock`, `demand`, `audit`, `plan`, `report`, `save`) and their labels from the backend. The current step has a pulsing icon + elapsed seconds. Done steps show a ✓ and the model used (small). Steps that fell back show "(automatic)".
   - Rotating tips every 6s ("Did you know? Dead stock is money sitting in your showcase."…).
   - Text: "You can keep working, and we'll notify you when it's ready."
   - On `done` → fetch the run → animate the report in (stagger sections) → confetti on the first run.
   - On `error` → ErrorState with Retry. A 409 AI_BUSY when starting → toast "Insights are already being generated".
4. **Report ready:** `ReportView` (below).

### 11.4 ReportView sections (in order, each a SectionCard with an icon title)
1. **PartialBanner** (only if status PARTIAL): amber "Some parts were generated automatically because the AI quota was reached. Numbers are exact; explanations are simpler."
2. **ConclusionCard** (hero):
   - The `report.headline` in Playfair 26px.
   - `report.conclusion` paragraph (17px, comfortable line-height).
   - A confidence badge (HIGH green / MEDIUM amber / LOW grey) with the tooltip `confidence_reason`.
   - `key_numbers` as 4–6 stat chips (label small, value big).
   - The `data_quality_notes` as a muted list (if any).
3. **Recommended actions** (`ActionsList`): numbered cards with a priority colour stripe, `title`, `why`, and a target button mapped by `target`:
   PURCHASE_PLAN → "Review purchase plan" (`/app/purchase-plans/{plan_id}`), OUT_OF_STOCK → "See sold-out designs" (`/app/inventory?status=OUT`), LOW_STOCK → `?status=LOW`, DEAD_STOCK → Reports › Dead stock, ANOMALIES → scroll to the Anomalies section, INVENTORY → `/app/inventory`, REPORTS → `/app/reports`.
4. **What's selling / What's not** (`DemandSection`): two side-by-side cards.
   - Left "🔥 What's selling": `report.whats_selling` text + the `demand.high_demand` list (LabelCode, category, "sold {n}", a velocity mini-bar, reason).
   - Right "🐢 What's not selling": `report.whats_not_selling` + the `demand.low_demand` list + "₹X tied up" from the stock data.
   - `seasonal_notes` and `trend_notes` as callouts under them.
5. **Stock risks** (`StockRiskSection`): tabs Sold out / Low / Not selling with compact lists from `stock_position` (label, stock, note) + `report.risks` text. Each row has a quick "+ Add stock" (StockStepper).
6. **Purchase plan & budget** (`PlanSummaryCard`): total budget (big ₹), item count, a donut by category, the top 5 lines (label, qty, ₹), `report.money_view` text. Button **"Open purchase plan"** (the DRAFT the run created). The formula hint "Cost = last purchase price + {inflation}% inflation".
7. **Things to double-check** (`AnomaliesSection`): `anomalies.items` with a severity icon, issue, evidence, suggested check. Empty → "No unusual entries found ✓".
8. **Trends** (`TrendsSection`): a stacked AreaChart of `facts.sales_trend_by_category` (12 months) with a legend toggle per category + the AI `trend_notes`.
- Every section has a **"Why?"** (`WhyCollapse`) at the bottom right that expands the exact facts used (e.g. a small table of the designs and numbers from the analysis pack) with the muted caption "Numbers calculated by the system; the AI explains them."
- Footer: "This report gives insights only. All decisions are yours." + "Print / Save as PDF" (`window.print()` with print CSS: hide sidebar/chat, white background).

### 11.5 ChatPanel (the chatbot)
- **Header:** sparkles avatar, "Ask your AI Accountant", a sessions menu (history list, "New chat"), and an expand-to-fullscreen icon.
- **Empty state:** a greeting bubble "Hi {display_name}! Ask me anything about your stock, sales or purchases." + **SuggestionChips** from `GET /chat/suggestions` (wrapping chips, gold outline; clicking sends the question).
- **Message list** (auto-scroll to bottom; a "Jump to latest" button if the user scrolled up):
  - User bubble: right aligned, gold-tinted background, rounded 16px (bottom-right 4px).
  - Assistant bubble: left aligned, surface card with a border, sparkles avatar. Content rendered with react-markdown + remark-gfm (bold, lists, small tables).
  - If `payload.table` → `ChatAnswerTable` (compact mantine Table, ₹ formatting if the column name contains "₹"/"value"/"cost").
  - If `payload.chart` → `ChatAnswerChart` (Bar/Line/Donut from @mantine/charts, height 180, with `value_format` inr → ₹ tick formatting).
  - `follow_up_questions` → small chips under the answer (click = send).
  - Footer meta: time + model badge (small), and a **copy** button.
- **Pending answer:** an assistant bubble with a TypingIndicator (3 bouncing dots) + the live tool status from job events ("Checking stock levels…", "Looking up ER-1012…"). If the AI is busy with insights: "Waiting for the insights report to finish…".
- **Input:** an autosize Textarea (max 5 rows, 1,000 chars), placeholder "Ask about sales, stock, reorders… (English or Hindi)". **Enter sends**, Shift+Enter makes a newline. A send button (gold circle with an arrow). Disabled while an answer is pending for this session.
- Flow: if there is no session → `POST /chat/sessions` → `POST /chat/sessions/{id}/messages` → add the user message optimistically + a pending assistant bubble → `useJobEvents(job_id)` → on done, refetch the session → replace the bubble (fade in).
- Errors: a failed answer shows an inline error bubble "I couldn't answer that right now." + "Try again".

---

## 12. Purchase Plans

### 12.1 Plans list (`/app/purchase-plans`)
- Header: "Purchase Plans". Actions: **"Create plan from current needs"** (`POST /purchase-plans {from_baseline: true}`) and "View reorder suggestions" (a drawer showing `GET /reorder/baseline` live, no AI).
- Owner: a highlighted section "Waiting for your approval" (SUBMITTED + AI DRAFT plans).
- A list of cards/rows: title, source badge (AI ✨ / Manual), status badge (Draft grey, Submitted blue, Decided green, Received gold), created date + by whom, item count, estimated total, approved total. Click → detail.
- Empty: "No purchase plans yet", "Generate AI insights to get a smart plan, or create one from current reorder needs."

### 12.2 Plan detail (`/app/purchase-plans/:planId`)
- **PlanStatusStepper:** Draft → Submitted → Decided → Received, with the current step highlighted.
- **Header:** editable title (inline), source badge, period label, notes (an editable textarea in DRAFT/SUBMITTED).
- **Totals cards:** Estimated total, Approved total, Pending count, plus a by-category donut.
- **PlanItemsTable** (cards on mobile):
  | Column | Content |
  |---|---|
  | Design | thumb + LabelCode + name + category |
  | Now | live current stock + StatusBadge + DemandBadge |
  | Suggested | suggested_qty (muted) |
  | **Qty** | NumberInput (editable in DRAFT/SUBMITTED), changes are saved with a 500ms debounce via PATCH, totals animate |
  | Unit cost | expected_unit_cost with an ⓘ tooltip showing `formula_text` |
  | Line total | ₹ |
  | Priority | badge |
  | Why | an expandable reason (one-line ellipsis → expand) |
  | **Decision** (owner) | `DecisionToggle`: ✓ Approve (green) / ✗ Reject (red) segmented, default Pending (grey). Admin sees a read-only badge |
  | Received | x / final (after decided) |
- Row actions (DRAFT): remove item. "+ Add design" (an autocomplete to add a line).
- **Sticky totals bar** (bottom of the viewport): "Approved ₹X · Pending ₹Y · Rejected ₹Z", plus actions by role and status:
  - Admin, DRAFT: **Submit for approval**.
  - Owner, DRAFT/SUBMITTED: **Approve all** (confirm) / **Save decisions** (sends `decide` with the toggles. It requires every item to be decided; otherwise highlight the undecided rows).
  - After DECIDED: **Mark as received** → ReceiveModal (each approved line: qty received (default final_qty), actual unit cost (default expected), date) → `POST /receive` → toast + confetti (milestone "first plan received") → the stock updates live everywhere.
  - Always: Export Excel, Print.

---

## 13. Reports (`/app/reports`)
Tabs (URL `?tab=`), each tab a responsive grid of `ChartCard`s (title, subtitle, period/filters, chart, "Export" button, a "View table" toggle showing the raw numbers):
- **Sales:** sales trend 12 months (area; group by total/category toggle), sales by category (bar, period), top 10 sellers (horizontal bar), bottom 10 (horizontal bar, muted).
- **Stock:** stock value by category (bar), stock health (donut), stock turnover by category (bar with a "turnover ×" label).
- **Dead stock:** a total-value hero number + table (label, category, stock, days since last sale, value tied up) sorted by value, with export.
- **Compare:** two PeriodPickers (A and B, default this month vs last month) → grouped bar (units or ₹ toggle) + a table with change %.
All charts use the theme colours. Categories get a consistent colour per category (a deterministic palette from the category id: gold, teal, blue, grape, orange, cyan, pink, lime). Tooltips are formatted (₹, pieces).

---

## 14. Settings (`/app/settings`)
- **Shop profile:** shop name, owner name (PATCH /settings). The sidebar shop name updates live.
- **Business rules:** inflation % (slider + number 0–50, helper "Used to estimate purchase cost: last cost + this %"), default min stock, "not selling" days (dead stock days), reorder cover months (0.5–6, helper "How many months of sales the reorder should cover"), quarter system (Financial year Apr–Mar / Calendar). Save button with a dirty-state check.
- **AI status card** (`GET /settings/ai-status`): primary/fallback model names, availability dots (green available, amber cooling down with "until 1:30 PM", red unavailable), mock-mode badge, runs/chats today. A short explanation "Free AI tier: limited requests per day. When the main model is busy, a lighter model or automatic analysis is used."
- **Data tools:**
  - "Load demo data" (visible to both roles; disabled if designs exist, with the tooltip "Only for an empty shop"). A confirm modal explains what it creates.
  - **"Reset all inventory data"** (owner only, red, inside a "Danger zone" card): a modal requiring typing `RESET`. It explains what is deleted and what is kept.
- **About:** version, "Demo/POC" note.

---

## 15. Shared Components (key behaviours)
- `PageHeader {title, subtitle, actions, breadcrumb}`: Playfair title, responsive (actions wrap below on mobile).
- `SectionCard {icon, title, actions, children, why?}`: the standard card.
- `KpiCard {icon, label, value (number), format ("inr"|"number"), delta?, sub, sparkline?, onClick?}`: uses CountUp.
- `CountUp {value, format, duration=700}`: animates from the previous value. Respects reduced motion.
- `StatusBadge {status}`, `DemandBadge {demand}`: colour + icon + label ("Sold out", "Low", "In stock", "Not selling" / "High demand", "Steady", "Low demand", "Not selling", "New").
- `EmptyState {icon, title, text, primaryAction, secondaryAction, chips?}`: centered, with a soft illustration (a big icon in a gold-tinted blob).
- `ErrorState {message, onRetry}`.
- `LoadingSkeletons`: KpiRowSkeleton, CardSkeleton, TableSkeleton(rows), ChartSkeleton.
- `ConfirmModal` via `modals.openConfirmModal` with consistent wording and a red confirm for destructive actions.
- `PhotoThumb {url, icon, size}`: lazy-load img, rounded, fallback to the category icon on a tinted background.
- `LiveIndicator`: green pulse "Live" / grey "Offline".
- Notifications: success (teal, check), error (red, x), info (gold, sparkles). Max 3 visible.

---

## 16. Implementation Phases and Acceptance Checks

| Phase | Build | Done when |
|---|---|---|
| **F1 Scaffold** | Vite app, dependencies, theme (colours, fonts, global.css), providers, router skeleton, proxy, `.env`, `gen:api` | `npm run dev` shows a themed placeholder. `npm run gen:api` generates types from the running backend |
| **F2 Auth** | Landing, Login (both roles), authStore, client auth + 401 handling, ProtectedRoute, AppLayout (sidebar, header, mobile tab bar, user menu, theme toggle) | owner/owner and admin/admin log in from their pages. Wrong password and role mismatch show the right messages. Refresh keeps the session if "remember" is on. Logout works. The layout is responsive at 375px, 768px, 1280px, 1600px |
| **F3 Inventory** | Categories page (+ empty state, quick-add chips), AddCategoryModal (+ subcategories), CategoryDetail (SubcategoryBar, DesignsTable/Grid), AddDesignsWizard (incl. paste from Excel, live label checks), DesignDetail (photo upload, edit, archive), ImportExcelModal | From a blank shop: create "Earrings" with 3 subcategories → add 10 designs with opening stock in under 2 minutes → they appear with correct stock and status |
| **F4 Stock** | StockStepper, QuickStockPopover (optimistic + undo), QuickStockFab/drawer, LabelSearchSpotlight, Stock page (Quick entry, Today, History, Period view) | Recording a sale takes 2 clicks from any list. Undo restores. Overselling shows a friendly error. The month/quarter view totals match the backend |
| **F5 Dashboard + live** | Onboarding mode (checklist, locked preview, demo-data link), Overview mode (all rows), useLiveEvents, invalidation map, milestones confetti | A blank shop shows the checklist. After data, the overview appears. A sale recorded in one tab updates the dashboard in another tab within ~2 s |
| **F6 Insights + chat** | InsightsPage states, GenerationProgress (job SSE), ReportView sections, Why collapses, RunHistory, ChatPanel (sessions, suggestions, markdown, table/chart answers, follow-ups, pending tool status), mobile chat sheet | On demo data: generate insights → the steps animate → the report renders all sections. Asking "Which designs are sold out?" returns a table. Works in mock mode too |
| **F7 Purchase plans** | List, detail, inline qty edit, owner decisions, admin submit, receive modal, export | Admin submits → owner approves → receive → stock increases and the dashboard updates |
| **F8 Reports + settings** | Reports tabs, exports, Settings (profile, rules, AI status, demo data, reset) | Exports download valid xlsx. Changing inflation changes the plan costs. Reset (owner) empties the shop and returns to onboarding |
| **F9 Polish & QA** | Motion pass, reduced motion, dark mode pass, accessibility pass (keyboard, focus, aria-labels), skeletons everywhere, print CSS, component tests | The checklist in Section 17 passes |

---

## 17. Quality Checklist (must all pass)
- [ ] Every page works at **375px** (iPhone SE) with no horizontal scroll (tables become card lists or scroll inside their own container).
- [ ] Every interactive icon button has an `aria-label`. Status is never shown by colour alone.
- [ ] Every page shows skeletons while loading, a meaningful empty state, and an error state with Retry.
- [ ] The keyboard can: open search (Ctrl+K), record a sale from the search result, submit forms with Enter, close dialogs with Esc.
- [ ] Money is always ₹ with Indian grouping. Large values are compact on cards and full in tables/tooltips.
- [ ] Dark mode looks intentional (no white flashes, readable charts).
- [ ] `prefers-reduced-motion` disables count-ups, flips and confetti.
- [ ] No hard-coded API field names outside the generated types (TypeScript catches mismatches).
- [ ] Owner-only controls are hidden for the admin; the API still enforces this (a 403 shows a friendly toast).
- [ ] With the backend in `LLM_MOCK_MODE=true`, Insights and Chat still work end to end.
- [ ] `npm run build` succeeds with zero TypeScript errors. `npm run test` passes. Tests cover: formatINR/compact, the movement type map, the QuickStockPopover preview math, the AddDesignsWizard duplicate detection, ProtectedRoute redirect.

---

## 18. Demo Script (what the owner will experience)
1. Open `http://localhost:5173` → a landing page with the gold shimmer → click **Owner** → log in with `owner` / `owner`.
2. The dashboard welcomes you with the **setup checklist** (blank shop) and a blurred preview of what's coming.
3. **Add category** "Earrings" (icon, prefix ER, subcategories Studs/Jhumkas/Hoops) → confetti.
4. **Add designs** → "10" → the labels ER-1001…ER-1010 prefill → type costs/prices/stock (or paste from Excel) → Create → confetti.
5. Tap **−** on ER-1003 → "Record sale" ×2 → the stock flips 8 → 6 → toast with Undo.
6. Back on the dashboard: the KPIs count up, "Live · updated just now", an instant insight appears.
7. (Optional) **Settings → Load demo data** for a full 12-month shop.
8. **Insights → Generate**: watch the 7 steps → read the conclusion, actions, what's selling/not, the risks, the plan.
9. Ask the chat: "What should I restock this month and how much money do I need?" → an answer with a table and follow-up chips.
10. **Purchase plan** → adjust a quantity → **Approve all** → **Mark as received** → the stock rises everywhere, live.
