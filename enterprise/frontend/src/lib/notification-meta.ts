/**
 * Derives a business category + priority for a notification from its severity (`kind`),
 * originating entity, icon, and text — so the Notification Center can group, filter, and
 * color-code without requiring a schema change to every event producer.
 */
import type { AppNotification, NotificationKind } from "@/data/types";

export type NotifCategory = "expenses" | "approvals" | "finance" | "ai" | "security" | "system";

export const CATEGORY_META: Record<NotifCategory, { label: string; icon: string }> = {
  expenses: { label: "Expenses", icon: "description" },
  approvals: { label: "Approvals", icon: "fact_check" },
  finance: { label: "Finance", icon: "gavel" },
  ai: { label: "AI", icon: "smart_toy" },
  security: { label: "Security", icon: "security" },
  system: { label: "System", icon: "settings" },
};

export const CATEGORY_ORDER: NotifCategory[] = [
  "expenses",
  "approvals",
  "finance",
  "ai",
  "security",
  "system",
];

export function categoryOf(n: AppNotification): NotifCategory {
  const t = `${n.title} ${n.body}`.toLowerCase();
  const e = (n.entity ?? "").toLowerCase();
  if (n.icon === "smart_toy" || t.includes("recommendation") || t.includes("ai ") || t.includes("summary"))
    return "ai";
  if (t.includes("security") || t.includes("login") || t.includes("password") || t.includes("session"))
    return "security";
  if (
    t.includes("approval") || t.includes("await") || t.includes("review") ||
    t.includes("returned") || t.includes("approved") || t.includes("rejected")
  )
    return "approvals";
  if (t.includes("finance") || t.includes("duplicate") || t.includes("risk") || t.includes("reimburse"))
    return "finance";
  if (e.startsWith("expense") || t.includes("expense") || t.includes("receipt") || t.includes("sheet"))
    return "expenses";
  return "system";
}

export type Priority = "high" | "medium" | "low";

export function priorityOf(n: AppNotification): Priority {
  if (n.kind === "error") return "high";
  if (n.kind === "warning") return "medium";
  return "low";
}

/** Icon tile classes by severity. */
export const KIND_CLASS: Record<NotificationKind, string> = {
  success: "text-success-green bg-success-green/10",
  warning: "text-yellow-600 bg-yellow-500/10",
  error: "text-error bg-error-container",
  info: "text-tertiary bg-tertiary/10",
};

/** Left priority bar color. */
export const PRIORITY_BAR: Record<Priority, string> = {
  high: "bg-error",
  medium: "bg-yellow-500",
  low: "bg-transparent",
};

/** Date bucket label for grouping. */
export function dateBucket(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(d)) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return "This week";
  return "Earlier";
}

export const BUCKET_ORDER = ["Today", "Yesterday", "This week", "Earlier"];
