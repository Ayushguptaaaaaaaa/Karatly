import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = new Intl.NumberFormat("en-IN");

export function formatINR(value: number | null | undefined, opts: { compact?: boolean; decimals?: 0 | 2 } = {}): string {
  const v = Number(value ?? 0);
  if (opts.compact) {
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e7) return `${sign}₹${trim(a / 1e7)} Cr`;
    if (a >= 1e5) return `${sign}₹${trim(a / 1e5)} L`;
    if (a >= 1e3) return `${sign}₹${trim(a / 1e3, 1)}K`;
  }
  return (opts.decimals === 2 ? inr2 : inr0).format(v);
}

function trim(n: number, digits = 2): string {
  return Number(n.toFixed(digits)).toString();
}

export function formatNumber(n: number | null | undefined): string {
  return num.format(Number(n ?? 0));
}

export function formatPct(p: number | null | undefined, digits = 1): string {
  if (p === null || p === undefined) return "—";
  const s = Math.abs(p).toFixed(digits);
  return `${p >= 0 ? "+" : "−"}${s}%`;
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return "—";
  return dayjs(d).format("D MMM YYYY");
}

export function formatDayWord(d: string): string {
  const day = dayjs(d);
  if (day.isSame(dayjs(), "day")) return "Today";
  if (day.isSame(dayjs().subtract(1, "day"), "day")) return "Yesterday";
  return day.format("ddd, D MMM");
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const s = iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`;
  return dayjs(s).fromNow();
}

export function todayISO(): string {
  return dayjs().format("YYYY-MM-DD");
}

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
