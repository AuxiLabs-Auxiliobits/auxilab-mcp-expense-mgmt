import { differenceInHours, parseISO } from "date-fns";

/**
 * SLA / aging for queued items (SCOPING.md §6.4, §8). Aging is measured against the
 * real current time so live backend data reads correctly. `DEMO_NOW` is retained only
 * for tests/storybook that need a fixed anchor — pass it explicitly as the second arg.
 */
export const DEMO_NOW = new Date(2026, 5, 14, 12, 0, 0);

export type AgingLevel = "ok" | "warning" | "escalation";

export interface Aging {
  level: AgingLevel;
  hours: number;
  label: string;
}

export function agingLevel(submittedAt?: string, now: Date = new Date()): Aging {
  if (!submittedAt) return { level: "ok", hours: 0, label: "—" };
  const hours = Math.max(0, differenceInHours(now, parseISO(submittedAt)));
  const days = Math.floor(hours / 24);
  const label = days >= 1 ? `${days}d` : `${hours}h`;
  if (hours >= 24 * 5) return { level: "escalation", hours, label };
  if (hours >= 24 * 2) return { level: "warning", hours, label };
  return { level: "ok", hours, label };
}

export const AGING_CLASS: Record<AgingLevel, string> = {
  ok: "bg-surface-container-highest text-on-surface-variant",
  warning: "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20",
  escalation: "bg-error-container text-error border border-error/20",
};
