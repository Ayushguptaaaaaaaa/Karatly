/** Customers, dealers, bills and the Excel-style explorer: types + React Query hooks. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { invalidateData } from "./hooks";

// ---- types --------------------------------------------------------------------------------
export interface Customer {
  id: number; name: string; phone: string | null; email: string | null; city: string | null; state: string | null;
  country: string | null; notes: string | null; created_at: string;
  bills: number; pieces: number; revenue: number; last_bill_on: string | null;
}
export type CustomerInput = Partial<Pick<Customer, "name" | "phone" | "email" | "city" | "state" | "country" | "notes">>;

export interface Dealer {
  id: number; name: string; phone: string | null; city: string | null; state: string | null; country: string | null;
  gstin: string | null; notes: string | null; created_at: string;
  purchases: number; pieces: number; amount: number; designs: number; last_purchase_on: string | null;
}
export type DealerInput = Partial<Pick<Dealer, "name" | "phone" | "city" | "state" | "country" | "gstin" | "notes">>;

export interface BillLine {
  movement_id: number;
  design: { id: number; label: string; name: string | null; category_name: string; metal: string; purity: string | null; photo_url: string | null };
  quantity: number; list_price: number; unit_price: number; amount: number; net_amount: number; is_void: boolean;
}
export interface Bill {
  id: number; number: string; bill_date: string;
  customer: { id: number | null; name: string; phone: string | null; city: string | null; state: string | null; country: string | null };
  lines: BillLine[]; pieces: number; subtotal: number; discount: number; taxable: number; gst_pct: number;
  gst_amount: number; total: number; payment_mode: string | null; notes: string | null; is_void: boolean; created_at: string;
}
export interface BillSummary {
  id: number; number: string; bill_date: string; customer_id: number | null; customer_name: string;
  customer_phone: string | null; city: string | null; state: string | null; country: string | null; pieces: number;
  taxable: number; gst_amount: number; total: number; payment_mode: string | null; is_void: boolean;
}
export interface BillPage {
  items: BillSummary[]; total: number; page: number; page_size: number;
  totals: { bills: number; taxable: number; gst: number; total: number };
}
export interface BillInput {
  customer_id?: number | null; customer?: CustomerInput | null; bill_date?: string;
  items: { design_id: number; quantity: number; unit_price?: number | null }[];
  discount?: number; gst_pct?: number | null; payment_mode?: string | null; notes?: string | null;
}

export type ExploreKind = "sales" | "purchases";
export interface ExploreFilters {
  date_from?: string; date_to?: string; category_id?: string; label?: string; metal?: string;
  customer_id?: string; walk_in?: boolean; city?: string; state?: string; country?: string; payment_mode?: string;
  dealer_id?: string; no_dealer?: boolean; dealer_city?: string; dealer_state?: string; purchases_only?: boolean;
}
export interface GroupRow {
  key: string; label: string; sub: string | null; qty: number; value: number; entries: number; bills: number;
  customers: number; designs: number; dealers: number; avg_price: number; share_pct: number;
}
export interface SaleRow {
  id: number; date: string; bill_id: number | null; bill_number: string | null; customer_id: number | null; customer: string;
  city: string; state: string; country: string; payment_mode: string; design_id: number; design: string;
  design_name: string | null; category: string; subcategory: string; metal: string; qty: number; unit_price: number; revenue: number;
}
export interface PurchaseRow {
  id: number; date: string; type: string; dealer_id: number | null; dealer: string; dealer_city: string; dealer_state: string;
  design_id: number; design: string; design_name: string | null; category: string; metal: string; qty: number;
  unit_cost: number; amount: number;
}
export interface ExploreResult {
  kind: ExploreKind; group_by: string | null; group_label: string | null;
  items: (GroupRow | SaleRow | PurchaseRow)[]; total: number; page: number; page_size: number;
  totals: { entries: number; qty: number; value: number; designs: number; bills: number | null; customers: number | null; dealers: number | null };
  chart: { label: string; value: number; qty: number }[];
}
type Opt = { value: string; label: string };
export interface Facets {
  cities: string[]; states: string[]; countries: string[]; payment_modes: string[]; dealer_cities: string[];
  dealer_states: string[]; customers: Opt[]; dealers: Opt[]; categories: Opt[]; sales_groups: Opt[]; purchase_groups: Opt[];
}

export const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank transfer", "Credit"];

// ---- helpers ------------------------------------------------------------------------------
export function cleanQuery(o: object): Record<string, string | number | boolean> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== false)) as Record<
    string, string | number | boolean>;
}
function useInvalidate() {
  const qc = useQueryClient();
  return () => invalidateData(qc);
}

// ---- customers ----------------------------------------------------------------------------
export function useCustomers(q?: string) {
  return useQuery({ queryKey: ["customers", q ?? ""], queryFn: () => api<Customer[]>("/customers", { query: { q } }),
    placeholderData: keepPreviousData });
}
export function useSaveCustomer() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...b }: CustomerInput & { id?: number }) =>
      id ? api<Customer>(`/customers/${id}`, { method: "PATCH", body: b }) : api<Customer>("/customers", { method: "POST", body: b }),
    onSuccess: inv,
  });
}
export function useDeleteCustomer() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: number) => api<void>(`/customers/${id}`, { method: "DELETE" }), onSuccess: inv });
}

// ---- dealers ------------------------------------------------------------------------------
export function useDealers(q?: string) {
  return useQuery({ queryKey: ["dealers", q ?? ""], queryFn: () => api<Dealer[]>("/dealers", { query: { q } }),
    placeholderData: keepPreviousData });
}
export function useSaveDealer() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...b }: DealerInput & { id?: number }) =>
      id ? api<Dealer>(`/dealers/${id}`, { method: "PATCH", body: b }) : api<Dealer>("/dealers", { method: "POST", body: b }),
    onSuccess: inv,
  });
}
export function useDeleteDealer() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: number) => api<void>(`/dealers/${id}`, { method: "DELETE" }), onSuccess: inv });
}

// ---- bills --------------------------------------------------------------------------------
export function useBills(params: Record<string, string | number | boolean | undefined>) {
  return useQuery({ queryKey: ["bills", params], queryFn: () => api<BillPage>("/bills", { query: cleanQuery(params) }),
    placeholderData: keepPreviousData });
}
export function useBill(id: number | undefined) {
  return useQuery({ queryKey: ["bill", id], queryFn: () => api<Bill>(`/bills/${id}`), enabled: !!id });
}
export function useCreateBill() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (b: BillInput) => api<Bill>("/bills", { method: "POST", body: b }), onSuccess: inv });
}
export function useVoidBill() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) => api<Bill>(`/bills/${id}/void`, { method: "POST", body: { reason } }),
    onSuccess: inv,
  });
}

// ---- who supplied / bought a design -----------------------------------------------------------
export interface DesignParties {
  dealers: { id: number | null; name: string; pieces: number; amount: number; deliveries: number }[];
  customers: { id: number | null; name: string; pieces: number; revenue: number; bills: number }[];
}
export function useDesignParties(id: number | undefined) {
  return useQuery({ queryKey: ["design", id, "parties"], queryFn: () => api<DesignParties>(`/designs/${id}/parties`), enabled: !!id });
}

// ---- explorer -----------------------------------------------------------------------------
export function useExplore(kind: ExploreKind, params: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ["explore", kind, params],
    queryFn: () => api<ExploreResult>(`/explore/${kind}`, { query: cleanQuery(params) }),
    placeholderData: keepPreviousData,
  });
}
export function useFacets() {
  return useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/explore/facets"), staleTime: 60_000 });
}
