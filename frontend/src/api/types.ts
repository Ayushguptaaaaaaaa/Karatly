// Mirrors backend/backend_plan.md §8 (API contract). Keep field names identical.

export type Role = "OWNER" | "ADMIN";
export type StockStatus = "IN" | "LOW" | "OUT" | "DEAD";
export type DemandClass = "HIGH" | "STEADY" | "LOW" | "DEAD" | "NEW";
export type MovementType =
  | "OPENING" | "PURCHASE" | "CUSTOMER_RETURN" | "ADJUSTMENT_IN" | "SALE" | "SUPPLIER_RETURN" | "ADJUSTMENT_OUT";
export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type Decision = "PENDING" | "APPROVED" | "REJECTED";
export type PlanStatus = "DRAFT" | "SUBMITTED" | "DECIDED" | "RECEIVED";
export type PeriodType = "day" | "month" | "quarter" | "custom";

export interface User { id: number; username: string; display_name: string; role: Role }
export interface LoginResponse { access_token: string; token_type: string; expires_at: string; user: User }

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface SubRef { id: number; name: string }
export interface Subcategory {
  id: number; category_id: number; name: string; description: string | null; is_active: boolean; sort_order: number;
  design_count?: number | null; total_pieces?: number | null;
  net_revenue_30d?: number | null; net_profit_30d?: number | null; margin_pct_30d?: number | null;
}
export interface CategoryCard {
  id: number; name: string; label_prefix: string; icon: string; description: string | null; is_active: boolean;
  sort_order: number; inflation_pct_override: number | null; subcategory_count: number; subcategories: SubRef[];
  design_count: number; total_pieces: number; stock_value_cost: number; in_stock_count: number;
  out_of_stock_count: number; low_stock_count: number; dead_stock_count: number; sold_last_30d: number;
  net_revenue_30d: number; net_profit_30d: number; margin_pct_30d: number | null;
}
export interface CategoryDetail extends Omit<CategoryCard, "subcategories"> { subcategories: Subcategory[] }

export interface DesignListItem {
  id: number; label: string; name: string | null; category: { id: number; name: string; icon: string };
  subcategory: SubRef | null; metal: string; purity: string | null; weight_g: number | null; cost_price: number;
  selling_price: number; last_unit_cost: number; min_stock: number; current_stock: number; status: StockStatus;
  demand_class: DemandClass; sold_last_30d: number; stock_value_cost: number; photo_url: string | null;
  is_active: boolean; updated_at: string | null;
}
export interface DesignDetail extends DesignListItem {
  description: string | null; supplier: string | null; inflation_pct_override: number | null;
  custom_fields: Record<string, unknown>; velocity_30d: number; days_since_last_sale: number | null;
  first_movement_on: string | null; last_sale_on: string | null; created_at: string | null;
  avg_unit_cost: number | null; net_revenue_30d: number; net_profit_30d: number; margin_pct_30d: number | null;
}
export interface DesignSearchHit {
  id: number; label: string; name: string | null; category_name: string; current_stock: number; status: StockStatus;
  photo_url: string | null; selling_price: number; cost_price: number; min_stock: number;
}
export interface DesignCreateRow {
  label: string; name?: string | null; metal?: string | null; purity?: string | null; weight_g?: number | string | null;
  cost_price?: number | string | null; selling_price?: number | string | null; min_stock?: number | string | null;
  opening_stock?: number | string | null; supplier?: string | null;
}

export interface Movement {
  id: number; design: { id: number; label: string; name: string | null; photo_url: string | null };
  type: MovementType; direction: "IN" | "OUT"; quantity: number; unit_price: number | null; value: number | null;
  occurred_on: string; note: string | null; source: string; created_by: { id: number; display_name: string } | null;
  created_at: string | null; is_void: boolean; voided_at: string | null; void_reason: string | null;
}
export interface DesignBrief { id: number; label: string; current_stock: number; status: StockStatus; demand_class: DemandClass }
export interface MovementResult { movement: Movement; design: DesignBrief }

export interface PeriodInfo {
  period_type: PeriodType; start: string; end: string; effective_end: string; label: string; short_label: string;
  is_current: boolean; previous: { start: string; end: string; label: string; short_label: string };
}
export interface PeriodOption { period_type: PeriodType; anchor: string; label: string; start: string; end: string }

export interface PeriodRow {
  design: { id: number; label: string; name: string | null; category_name: string; subcategory_name: string | null; photo_url: string | null };
  opening: number; opening_added: number; received: number; sold: number; customer_returns: number;
  supplier_returns: number; adjustments_net: number; closing: number; sales_value: number; status_now: StockStatus;
  net_revenue: number; net_profit: number; margin_pct: number | null;
}
export interface PeriodStock {
  period: PeriodInfo; rows: Page<PeriodRow>;
  totals: Record<"opening" | "opening_added" | "received" | "sold" | "customer_returns" | "supplier_returns" | "adjustments_net" | "closing" | "sales_value" | "net_revenue" | "net_profit", number> & { margin_pct: number | null };
}

export interface InstantInsight {
  id: string; severity: "critical" | "warning" | "info" | "success"; icon: string; title: string; detail: string;
  action: { label: string; route: string };
}
export interface AlertItem {
  design_id: number; label: string; name: string | null; photo_url: string | null; category_name: string;
  status: StockStatus; current_stock: number; min_stock: number; demand_class: DemandClass; sold_last_30d: number;
  days_since_last_sale: number | null; value_tied_up: number;
  selling_price: number; last_unit_cost: number;
}
export interface Kpis {
  total_designs: number; total_pieces: number; stock_value_cost: number; stock_value_selling: number;
  sales_units: number; sales_value: number; sales_change_pct: number | null; out_of_stock: number; low_stock: number;
  dead_stock: number; dead_stock_value: number; needs_attention: number;
  net_revenue: number; net_profit: number; cogs: number; profit_margin_pct: number | null; net_profit_change_pct: number | null;
}
export interface TrendPoint { month: string; label: string; units: number; value: number }
export interface Dashboard {
  period: PeriodInfo; data_version: number;
  setup: { has_category: boolean; has_designs: boolean; has_opening_stock: boolean; has_sale: boolean; has_insights: boolean; completed_steps: number; total_steps: number };
  kpis: Kpis;
  kpi_sparklines: { sales_value: number[]; sales_units: number[]; stock_value_cost: number[]; net_profit: number[] };
  stock_health: Record<StockStatus, number>;
  sales_trend: TrendPoint[];
  category_breakdown: { category_id: number; name: string; icon: string; pieces: number; stock_value_cost: number; sold_units: number; sales_value: number; share_pct: number; design_count: number; net_revenue: number; net_profit: number }[];
  top_sellers: { design_id: number; label: string; name: string | null; photo_url: string | null; category_name: string; sold_units: number; sales_value: number; current_stock: number }[];
  alerts: AlertItem[];
  instant_insights: InstantInsight[];
  latest_ai: { run_id: number; created_at: string; period_label: string; headline: string; conclusion_short: string; is_stale: boolean; changes_since: number; status: string } | null;
  recent_activity: Movement[];
  pending_approvals: number;
  today: string;
}

export interface ReorderItem {
  design: { id: number; label: string; name: string | null; photo_url: string | null; category_name: string };
  current_stock: number; min_stock: number; status: StockStatus; demand_class: DemandClass; velocity_30d: number;
  suggested_qty: number; priority: Priority; reason: string; last_unit_cost: number; inflation_pct: number;
  usual_stock: number; max_qty: number;
  expected_unit_cost: number; line_total: number; formula_text: string;
}

export interface PlanSummary {
  id: number; title: string; status: PlanStatus; source: "AI" | "MANUAL"; created_at: string; created_by: string | null;
  item_count: number; total_estimated: number; total_approved: number; approved_count: number; rejected_count: number;
  pending_count: number; period_label: string | null;
  scope: "ALL" | "CATEGORY"; category_id: number | null; category_name: string | null;
  budget_limit: number | null; budget_note: string | null;
}
export interface PlanItem {
  id: number; design: { id: number; label: string; name: string | null; photo_url: string | null; category_name: string };
  current_stock: number; current_stock_at_creation: number; status: StockStatus; demand_class: DemandClass;
  suggested_qty: number; final_qty: number; last_unit_cost: number; inflation_pct: number; expected_unit_cost: number;
  line_total: number; priority: Priority; reason: string | null; decision: Decision; decision_note: string | null;
  received_qty: number; formula_text: string;
}
export interface PlanDetail extends PlanSummary {
  notes: string | null; insight_run_id: number | null; items: PlanItem[];
  total_capital_required: number; within_budget: boolean | null;
  by_category: { category: string; amount_estimated: number; amount_approved: number }[];
}

export interface JobStep { key: string; label: string; status: "PENDING" | "RUNNING" | "DONE" | "FAILED" | "SKIPPED"; started_at: string | null; finished_at: string | null; model_used: string | null; note: string | null }
export interface Job { id: string; type: string; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED"; steps: JobStep[]; error: string | null; result_type: string | null; result_id: number | null }

export interface LabelNote { label: string; category: string; stock: number; note: string }
export interface DemandNote { label: string; category: string; sold_period: number; velocity_30d: number; reason: string }
export interface InsightsReport {
  headline: string; conclusion: string; confidence: Priority; confidence_reason: string;
  key_numbers: { label: string; value: string }[];
  recommended_actions: { title: string; why: string; priority: Priority; target: string }[];
  whats_selling: string; whats_not_selling: string; money_view: string; risks: string; data_quality_notes: string[];
}
export interface InsightRun {
  id: number; job_id: string | null; status: "RUNNING" | "COMPLETE" | "PARTIAL" | "FAILED"; period_type: string;
  period_label: string; period_start: string; period_end: string; created_at: string; finished_at: string | null;
  models_used: string[]; is_stale: boolean; changes_since: number; data_sufficiency: "GOOD" | "LIMITED" | "LOW";
  report: InsightsReport;
  stock_position: { summary: string; out_of_stock: LabelNote[]; low_stock: LabelNote[]; dead_stock: LabelNote[]; category_notes: { category: string; note: string }[] };
  demand: { summary: string; high_demand: DemandNote[]; low_demand: DemandNote[]; seasonal_notes: string[]; trend_notes: string[] };
  anomalies: { summary: string; items: { label: string | null; severity: Priority; issue: string; evidence: string; suggested_check: string }[] };
  reorder: { summary: string; items: { label: string; suggested_qty: number; priority: Priority; reason: string }[] };
  budget: { items: { label: string; quantity: number; expected_unit_cost: number; line_total: number }[]; total_budget: number; by_category: { category: string; amount: number }[]; notes: string };
  purchase_plan: PlanSummary | null;
  facts: {
    sales_trend_by_category?: { name: string; points: { month: string; units: number; value: number }[] }[];
    kpis?: Kpis; demand_counts?: Record<string, number>; stock_health?: Record<string, number>;
  };
  evidence: {
    designs_of_interest: Record<string, unknown>[]; categories: Record<string, unknown>[];
    anomaly_candidates: Record<string, unknown>[]; reorder_baseline: Record<string, unknown>[];
  };
}
export interface RunListItem { id: number; period_label: string; status: string; created_at: string; models_used: string[]; headline: string | null; job_id: string | null }

export interface ChatMessage {
  id: number; role: "USER" | "ASSISTANT"; content: string; status: "PENDING" | "COMPLETE" | "FAILED"; job_id: string | null; created_at: string;
  payload: {
    table?: { columns: string[]; rows: (string | number | null)[][] } | null;
    chart?: { type: "bar" | "line" | "pie"; title: string; data: { label: string; value: number }[]; value_format: "number" | "inr" } | null;
    follow_up_questions?: string[]; model_used?: string; seconds?: number;
  };
}
export interface ChatSessionInfo { id: number; title: string; updated_at: string; message_count: number }

export interface Settings {
  shop_name: string; owner_name: string; inflation_pct_global: number; default_min_stock: number;
  dead_stock_days: number; reorder_cover_months: number; quarter_system: "FINANCIAL" | "CALENDAR";
  monthly_purchase_budget: number; max_stock_multiple: number;
}
export interface AiStatus {
  mock_mode: boolean; primary_model: string; fallback_model: string; primary_available: boolean;
  primary_cooldown_until: string | null; fallback_available: boolean; fallback_cooldown_until: string | null;
  last_error: string | null; runs_today: number; chat_answers_today: number; busy: boolean;
}

export interface ProfitRow {
  key: string; name: string; designs: number;
  label?: string; design_name?: string | null; design_id?: number; category?: string; subcategory?: string | null;
  category_id?: number; subcategory_id?: number | null; icon?: string; photo_url?: string | null; current_stock?: number;
  avg_unit_cost?: number;
  units_sold: number; units_returned: number; net_units: number; gross_sales: number; returns_value: number;
  net_revenue: number; cogs: number; net_profit: number; margin_pct: number | null;
}
export interface Profitability {
  period: PeriodInfo; group_by: "category" | "subcategory" | "design"; rows: ProfitRow[]; total_rows: number;
  totals: Omit<ProfitRow, "key" | "name" | "designs">;
}
