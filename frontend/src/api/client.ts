import { notifications } from "@mantine/notifications";
import { useAuth } from "../stores";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get fields(): Record<string, string> {
    return (this.details?.fields as Record<string, string>) ?? {};
  }

  get rows(): { index: number; field: string; message: string }[] {
    return (this.details?.rows as { index: number; field: string; message: string }[]) ?? [];
  }
}

let redirecting = false;

function handleUnauthorized(path: string) {
  if (path.startsWith("/auth/login")) return;
  const { token, clear } = useAuth.getState();
  if (!token || redirecting) return;
  redirecting = true;
  clear();
  notifications.show({ color: "red", title: "Session expired", message: "Please log in again." });
  setTimeout(() => {
    redirecting = false;
    window.location.assign("/");
  }, 400);
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(q?: Query): string {
  if (!q) return "";
  const p = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(
  path: string,
  opts: { method?: string; body?: unknown; query?: Query; form?: FormData; raw?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = useAuth.getState().token;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, { method: opts.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "NETWORK", "Can't reach the server. Is the backend running?");
  }
  if (res.status === 401) handleUnauthorized(path);
  if (!res.ok) {
    let payload: { error?: { code?: string; message?: string; details?: Record<string, unknown> } } = {};
    try {
      payload = await res.json();
    } catch {
      /* not json */
    }
    const e = payload.error ?? {};
    throw new ApiError(res.status, e.code ?? "HTTP_ERROR", e.message ?? `Request failed (${res.status})`, e.details ?? {});
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

export async function download(path: string, query?: Query, fallbackName = "export.xlsx") {
  const res = await api<Response>(path, { query, raw: true });
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") ?? "";
  const m = cd.match(/filename="?([^";]+)"?/);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = m?.[1] ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}

export function notifyError(e: unknown, title = "Couldn't save") {
  notifications.show({ color: "red", title, message: errorMessage(e) });
}
