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
  if (typeof value !== "string") return value;
  // Backend datetimes are UTC but stored without 'Z' (Python naive datetime).
  // parseISO treats a tz-less string as local time, making timestamps appear
  // hours in the past. Append Z so they're correctly parsed as UTC.
  const s =
    /^\d{4}-\d{2}-\d{2}T/.test(value) && !value.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(value)
      ? value + "Z"
      : value;
  return parseISO(s);
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

/**
 * Format a timestamp in Indian Standard Time (IST, UTC+5:30).
 * e.g. "Jun 28, 2026 · 14:32 IST"
 */
export function formatDateTimeIST(value: string | Date): string {
  const d = toDate(value);
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(d)
    .replace(",", "") + " IST";
}

/** Percentage with one decimal, e.g. "92.4%". */
export function formatPercent(value: number, fractionDigits = 1): string {
  return `${value.toFixed(fractionDigits)}%`;
}
