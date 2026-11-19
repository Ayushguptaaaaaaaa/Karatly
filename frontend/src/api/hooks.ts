import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { usePeriod } from "../stores";
import { api } from "./client";
import type {
  AiStatus,
  AlertItem,
  CategoryCard,
  CategoryDetail,
  ChatMessage,
  ChatSessionInfo,
  Dashboard,
  DesignCreateRow,
  DesignDetail,
  DesignListItem,
  DesignSearchHit,
  InsightRun,
  Job,
  Movement,
  MovementResult,
  MovementType,
  Page,
  PeriodOption,
  PeriodStock,
  PlanDetail,
  PlanSummary,
  ReorderItem,
  RunListItem,
  Settings,
  Subcategory,
} from "./types";

// ---- invalidation ----------------------------------------------------------------------
const DATA_KEYS = [
  "dashboard", "categories", "category", "designs", "design", "designHistory", "designSearch", "movements",
  "stockToday", "periodStock", "alerts", "reports", "reorder", "insightsLatest", "chatSuggestions", "plans", "plan",
];

export function invalidateData(qc: QueryClient, entity?: string) {
  const keys = entity === "purchase_plan" ? ["plans", "plan", "dashboard"] : entity === "settings"
    ? [...DATA_KEYS, "settings"] : DATA_KEYS;
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function usePeriodParams() {
  const { period_type, anchor } = usePeriod();
  return { period_type, anchor: anchor ?? undefined };
}

// ---- dashboard -------------------------------------------------------------------------
export function useDashboard() {
  const p = usePeriodParams();
  return useQuery({
    queryKey: ["dashboard", p],
    queryFn: () => api<Dashboard>("/dashboard/overview", { query: p }),
    placeholderData: keepPreviousData,
  });
}

export function useAlerts(status?: string) {
  return useQuery({ queryKey: ["alerts", status], queryFn: () => api<AlertItem[]>("/alerts", { query: { status } }) });
}

// ---- periods -----------------------------------------------------------------------------
export function usePeriodOptions() {
  return useQuery({
    queryKey: ["periodOptions"],
    queryFn: () => api<{ days: PeriodOption[]; months: PeriodOption[]; quarters: PeriodOption[] }>("/periods/options"),
    staleTime: 10 * 60_000,
  });
}

export function usePeriodStock(params: Record<string, string | number | undefined>) {
  return useQuery({
    queryKey: ["periodStock", params],
    queryFn: () => api<PeriodStock>("/periods/stock", { query: params }),
    placeholderData: keepPreviousData,
  });
}

// ---- categories --------------------------------------------------------------------------
export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: () => api<CategoryCard[]>("/categories") });
}

export function useCategory(id: number | undefined) {
  return useQuery({
    queryKey: ["category", id],
    queryFn: () => api<CategoryDetail>(`/categories/${id}`),
    enabled: !!id,
  });
}

function useDataMutation<TVars, TRes>(fn: (v: TVars) => Promise<TRes>, entity?: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => invalidateData(qc, entity) });
}

export interface CategoryInput {
  name?: string; label_prefix?: string | null; icon?: string; description?: string | null;
  inflation_pct_override?: number | null; subcategories?: string[]; is_active?: boolean;
}
export const useCreateCategory = () =>
  useDataMutation((b: CategoryInput) => api<CategoryDetail>("/categories", { method: "POST", body: b }));
export const useUpdateCategory = () =>
  useDataMutation(({ id, ...b }: CategoryInput & { id: number }) =>
    api<CategoryDetail>(`/categories/${id}`, { method: "PATCH", body: b }));
export const useDeleteCategory = () =>
  useDataMutation((id: number) => api<void>(`/categories/${id}`, { method: "DELETE" }));
export const useCreateSubcategory = () =>
  useDataMutation(({ categoryId, name }: { categoryId: number; name: string }) =>
    api<Subcategory>(`/categories/${categoryId}/subcategories`, { method: "POST", body: { name } }));
export const useUpdateSubcategory = () =>
  useDataMutation(({ id, name }: { id: number; name: string }) =>
    api<Subcategory>(`/subcategories/${id}`, { method: "PATCH", body: { name } }));
export const useDeleteSubcategory = () =>
  useDataMutation((id: number) => api<void>(`/subcategories/${id}`, { method: "DELETE" }));

export async function suggestPrefix(name: string) {
  return api<{ prefix: string }>("/categories/suggest-prefix", { query: { name } });
}

// ---- designs -------------------------------------------------------------------------------
export interface DesignFilters {
  category_id?: number; subcategory_id?: number; status?: string; demand?: string; search?: string; sort?: string;
  page?: number; page_size?: number; include_inactive?: boolean;
}
export function useDesigns(f: DesignFilters, enabled = true) {
  return useQuery({
    queryKey: ["designs", f],
    queryFn: () => api<Page<DesignListItem>>("/designs", { query: f as Record<string, string | number | boolean> }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useDesign(id: number | undefined) {
  return useQuery({ queryKey: ["design", id], queryFn: () => api<DesignDetail>(`/designs/${id}`), enabled: !!id });
}

export function useDesignHistory(id: number | undefined) {
  return useQuery({
    queryKey: ["designHistory", id],
    queryFn: () => api<{ monthly: { month: string; label: string; sold: number; received: number; sales_value: number; net_revenue: number; net_profit: number }[]; movements: Movement[] }>(
      `/designs/${id}/history`, { query: { months: 12 } }),
    enabled: !!id,
  });
}

export function useDesignSearch(q: string, enabled = true) {
  return useQuery({
    queryKey: ["designSearch", q],
    queryFn: () => api<DesignSearchHit[]>("/designs/search", { query: { q, limit: 8 } }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export const nextLabels = (category_id: number, count: number) =>
  api<{ labels: string[] }>("/designs/next-labels", { query: { category_id, count } });
export const checkLabel = (label: string) =>
  api<{ label: string; valid: boolean; available: boolean; message: string | null }>("/designs/check-label", { query: { label } });

export const useBulkCreateDesigns = () =>
  useDataMutation((b: { category_id: number; subcategory_id?: number | null; opening_date?: string; designs: DesignCreateRow[] }) =>
    api<{ created: DesignListItem[] }>("/designs/bulk", { method: "POST", body: b }));
export const useUpdateDesign = () =>
  useDataMutation(({ id, ...b }: { id: number } & Record<string, unknown>) =>
    api<DesignDetail>(`/designs/${id}`, { method: "PATCH", body: b }));
export const useArchiveDesign = () =>
  useDataMutation(({ id, archive }: { id: number; archive: boolean }) =>
    api<DesignDetail>(`/designs/${id}/${archive ? "archive" : "unarchive"}`, { method: "POST" }));
export const useDeleteDesign = () => useDataMutation((id: number) => api<void>(`/designs/${id}`, { method: "DELETE" }));
export const useUploadPhoto = () =>
  useDataMutation(({ id, file }: { id: number; file: File }) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ photo_url: string }>(`/designs/${id}/photo`, { method: "POST", form });
  });
export const useDeletePhoto = () => useDataMutation((id: number) => api<void>(`/designs/${id}/photo`, { method: "DELETE" }));
export const useImportDesigns = () =>
  useDataMutation(({ file, dryRun }: { file: File; dryRun: boolean }) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ valid_rows: number; errors: { row: number; field: string; message: string }[]; will_create: { categories: number; subcategories: number; designs: number }; imported: boolean }>(
      "/designs/import", { method: "POST", form, query: { dry_run: dryRun } });
  });

// ---- stock -----------------------------------------------------------------------------------
export interface MovementInput {
  design_id: number; type: MovementType; quantity: number; occurred_on?: string; unit_price?: number | null; note?: string | null;
}
export const useRecordMovement = () =>
  useDataMutation((b: MovementInput) => api<MovementResult>("/stock/movements", { method: "POST", body: b }));
export const useVoidMovement = () =>
  useDataMutation(({ id, reason }: { id: number; reason?: string }) =>
    api<MovementResult>(`/stock/movements/${id}/void`, { method: "POST", body: { reason } }));

export function useMovements(f: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ["movements", f],
    queryFn: () => api<Page<Movement>>("/stock/movements", { query: f }),
    placeholderData: keepPreviousData,
  });
}

export function useStockToday() {
  return useQuery({
    queryKey: ["stockToday"],
    queryFn: () => api<{ entries: Movement[]; totals: { sold_units: number; sold_value: number; received_units: number } }>("/stock/today"),
  });
}

// ---- reports -------------------------------------------------------------------------------
export function useReport<T>(name: string, query: Record<string, string | number | undefined> = {}) {
  return useQuery({
    queryKey: ["reports", name, query],
    queryFn: () => api<T>(`/reports/${name}`, { query }),
    placeholderData: keepPreviousData,
  });
}

export function useReorderBaseline(category_id?: number) {
  return useQuery({
    queryKey: ["reorder", category_id],
    queryFn: () => api<{ items: ReorderItem[]; total_estimated: number; budget: number; by_category: { category: string; amount: number }[] }>(
      "/reorder/baseline", { query: { category_id } }),
  });
}

// ---- purchase plans --------------------------------------------------------------------
export function usePlans() {
  return useQuery({ queryKey: ["plans"], queryFn: () => api<PlanSummary[]>("/purchase-plans") });
}
export function usePlan(id: number | undefined) {
  return useQuery({ queryKey: ["plan", id], queryFn: () => api<PlanDetail>(`/purchase-plans/${id}`), enabled: !!id });
}
function usePlanMutation<TVars>(fn: (v: TVars) => Promise<PlanDetail>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(["plan", data?.id], data);
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
/** Create this month's plan, or refresh the one open plan (keeps quantities a person changed). */
export const useCreatePlan = () =>
  usePlanMutation(() => api<PlanDetail>("/purchase-plans", { method: "POST", body: { from_baseline: true } }));
export const usePatchPlan = () =>
  usePlanMutation(({ id, ...b }: { id: number; title?: string; notes?: string }) =>
    api<PlanDetail>(`/purchase-plans/${id}`, { method: "PATCH", body: b }));
export const usePatchPlanItem = () =>
  usePlanMutation(({ planId, itemId, ...b }: { planId: number; itemId: number; final_qty?: number; decision?: string }) =>
    api<PlanDetail>(`/purchase-plans/${planId}/items/${itemId}`, { method: "PATCH", body: b }));
export const useAddPlanItem = () =>
  usePlanMutation(({ planId, design_id, final_qty }: { planId: number; design_id: number; final_qty: number }) =>
    api<PlanDetail>(`/purchase-plans/${planId}/items`, { method: "POST", body: { design_id, final_qty } }));
export const useRemovePlanItem = () =>
  usePlanMutation(({ planId, itemId }: { planId: number; itemId: number }) =>
    api<PlanDetail>(`/purchase-plans/${planId}/items/${itemId}`, { method: "DELETE" }));
export const useSubmitPlan = () =>
  usePlanMutation((id: number) => api<PlanDetail>(`/purchase-plans/${id}/submit`, { method: "POST" }));
export const useDecidePlan = () =>
  usePlanMutation(({ id, ...b }: { id: number; approve_all?: boolean; decisions?: { item_id: number; decision?: string; final_qty?: number }[] }) =>
    api<PlanDetail>(`/purchase-plans/${id}/decide`, { method: "POST", body: b }));
export function useReceivePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...b }: { id: number; occurred_on?: string; items: { item_id: number; quantity: number; unit_cost?: number }[] }) =>
      api<PlanDetail>(`/purchase-plans/${id}/receive`, { method: "POST", body: b }),
    onSuccess: () => invalidateData(qc),
  });
}
export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/purchase-plans/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["reorder"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// ---- insights + jobs -------------------------------------------------------------------
export function useInsightsLatest() {
  return useQuery({ queryKey: ["insightsLatest"], queryFn: () => api<InsightRun | null>("/insights/latest") });
}
export function useInsightRun(id: number | undefined) {
  return useQuery({ queryKey: ["insightRun", id], queryFn: () => api<InsightRun>(`/insights/runs/${id}`), enabled: !!id });
}
export function useInsightRuns() {
  return useQuery({ queryKey: ["insightRuns"], queryFn: () => api<RunListItem[]>("/insights/runs") });
}
export function useRunningInsights() {
  return useQuery({ queryKey: ["insightsRunning"], queryFn: () => api<Job | null>("/insights/running") });
}
export function useStartInsights() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { period_type?: string; anchor?: string }) =>
      api<{ job_id: string; run_id: number }>("/insights/runs", { method: "POST", body: b }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["insightsRunning"] }),
  });
}
export function useJob(id: string | null | undefined) {
  return useQuery({ queryKey: ["job", id], queryFn: () => api<Job>(`/jobs/${id}`), enabled: !!id });
}

// ---- chat ----------------------------------------------------------------------------------
export function useChatSessions() {
  return useQuery({ queryKey: ["chatSessions"], queryFn: () => api<ChatSessionInfo[]>("/chat/sessions") });
}
export function useChatSession(id: number | null) {
  return useQuery({
    queryKey: ["chatSession", id],
    queryFn: () => api<{ session: ChatSessionInfo; messages: ChatMessage[] }>(`/chat/sessions/${id}`),
    enabled: !!id,
  });
}
export function useChatSuggestions() {
  return useQuery({ queryKey: ["chatSuggestions"], queryFn: () => api<{ questions: string[] }>("/chat/suggestions") });
}
export const createChatSession = () => api<ChatSessionInfo>("/chat/sessions", { method: "POST", body: {} });
export const postChatMessage = (sessionId: number, text: string) =>
  api<{ user_message: ChatMessage; assistant_message: ChatMessage; job_id: string }>(
    `/chat/sessions/${sessionId}/messages`, { method: "POST", body: { text } });

// ---- settings / admin --------------------------------------------------------------------
export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/settings"), staleTime: 60_000 });
}
export const useUpdateSettings = () =>
  useDataMutation((b: Partial<Settings>) => api<Settings>("/settings", { method: "PATCH", body: b }), "settings");
export function useAiStatus() {
  return useQuery({ queryKey: ["aiStatus"], queryFn: () => api<AiStatus>("/settings/ai-status"), refetchInterval: 60_000 });
}
export const useLoadDemo = () =>
  useDataMutation(() => api<{ designs: number }>("/admin/demo-data", { method: "POST", body: { force: false } }));
export const useResetData = () =>
  useDataMutation(() => api<{ ok: boolean }>("/admin/reset", { method: "POST", body: { confirm: "RESET" } }));
