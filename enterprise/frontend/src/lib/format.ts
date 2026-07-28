import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

/** Format a numeric amount as currency (defaults to USD, the platform base). */
export function formatCurrency(
  amount: number,
  currency = "USD",
  opts: Intl.NumberFormatOptions = {},
): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    ...opts,
  }).format(amount);
}

/** Compact currency for KPI tiles (e.g. $4.2k). */
export function formatCompactCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(amount);
}

function toDate(value: string | Date): Date {
  return typeof value === "string" ? parseISO(value) : value;
}

/** e.g. "Oct 12, 2026" */
export function formatDate(value: string | Date): string {
  return format(toDate(value), "MMM d, yyyy");
}

/** e.g. "Oct 12" */
export function formatShortDate(value: string | Date): string {
  return format(toDate(value), "MMM d");
}

/** e.g. "Oct 12, 2026 · 14:32" */
export function formatDateTime(value: string | Date): string {
  return format(toDate(value), "MMM d, yyyy · HH:mm");
}

/** e.g. "2 hours ago" */
export function formatRelative(value: string | Date): string {
  return `${formatDistanceToNowStrict(toDate(value))} ago`;
}

/** Percentage with one decimal, e.g. "92.4%". */
export function formatPercent(value: number, fractionDigits = 1): string {
  return `${value.toFixed(fractionDigits)}%`;
}
