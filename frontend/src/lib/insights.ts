/**
 * Expense Intelligence engine — pure, dependency-free functions that turn a set of expense
 * sheets into KPIs, business-language AI insights, anomaly findings, and a directional forecast.
 *
 * Deterministic and side-effect-free so it's fast, cacheable, testable, and identical on
 * server or client. It ADVISES only — it never approves/rejects (RBAC + workflow are untouched).
 */
import type { ExpenseSheet } from "@/data/types";

const HIGH_VALUE = 1000; // sheet total considered high-value
const STALE_DAYS = 5; // pending longer than this is flagged

// ── KPIs ──
export interface AnalyticsKpis {
  total: number;
  count: number;
  pending: number;
  returned: number;
  avgValue: number;
  topCategory: { category: string; amount: number; share: number } | null;
  byCategory: { category: string; amount: number }[];
  byMonth: { month: string; amount: number }[];
}

const PENDING_STATUSES = new Set(["SUBMITTED", "IN_MANAGER_REVIEW", "IN_FINANCE_REVIEW"]);
const RETURNED_STATUSES = new Set(["RETURNED_TO_EMPLOYEE", "MANAGER_REJECTED"]);

export function computeKpis(sheets: ExpenseSheet[]): AnalyticsKpis {
  const total = sheets.reduce((s, x) => s + (x.total || 0), 0);
  const count = sheets.length;

  const catMap = new Map<string, number>();
  for (const sh of sheets) {
    for (const li of sh.lineItems ?? []) {
      const c = li.category || "Other";
      catMap.set(c, (catMap.get(c) ?? 0) + (li.amount || 0));
    }
  }
  const byCategory = [...catMap.entries()]
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount);
  const catTotal = byCategory.reduce((s, x) => s + x.amount, 0) || 1;
  const topCategory = byCategory[0]
    ? { ...byCategory[0], share: byCategory[0].amount / catTotal }
    : null;

  const monthMap = new Map<string, number>();
  for (const sh of sheets) {
    const m = sh.period || (sh.submittedAt ?? sh.updatedAt ?? "").slice(0, 7);
    if (m) monthMap.set(m, (monthMap.get(m) ?? 0) + (sh.total || 0));
  }
  const byMonth = [...monthMap.entries()]
    .map(([month, amount]) => ({ month, amount }))
    .sort((a, b) => a.month.localeCompare(b.month));

  return {
    total,
    count,
    pending: sheets.filter((s) => PENDING_STATUSES.has(s.status)).length,
    returned: sheets.filter((s) => RETURNED_STATUSES.has(s.status)).length,
    avgValue: count ? total / count : 0,
    topCategory,
    byCategory,
    byMonth,
  };
}

// ── AI insights (business language) ──
export interface Insight {
  text: string;
  tone: "neutral" | "positive" | "warning";
  icon: string;
}

function pct(n: number): string {
  return `${Math.abs(Math.round(n))}%`;
}

export function computeInsights(sheets: ExpenseSheet[]): Insight[] {
  const k = computeKpis(sheets);
  const out: Insight[] = [];
  if (k.count === 0) return out;

  if (k.topCategory) {
    out.push({
      text: `${k.topCategory.category} accounts for ${pct(k.topCategory.share * 100)} of all expenses.`,
      tone: "neutral",
      icon: "donut_small",
    });
  }

  // Month-over-month change in total spend.
  if (k.byMonth.length >= 2) {
    const cur = k.byMonth[k.byMonth.length - 1];
    const prev = k.byMonth[k.byMonth.length - 2];
    if (prev.amount > 0) {
      const change = ((cur.amount - prev.amount) / prev.amount) * 100;
      const dir = change >= 0 ? "increased" : "decreased";
      // A tiny previous month makes the % explode (e.g. "8054%") and reads as broken — phrase
      // those qualitatively instead of showing a misleading number.
      const text =
        Math.abs(change) > 300
          ? `Spend ${change >= 0 ? "rose" : "fell"} sharply in ${cur.month} compared to ${prev.month} (low prior-month base).`
          : `Spend ${dir} by ${pct(change)} in ${cur.month} compared to ${prev.month}.`;
      out.push({
        text,
        tone: change > 15 ? "warning" : "neutral",
        icon: change >= 0 ? "trending_up" : "trending_down",
      });
    }
  }

  // Stale pending approvals.
  const now = Date.now();
  const stale = sheets.filter(
    (s) =>
      PENDING_STATUSES.has(s.status) &&
      s.submittedAt &&
      (now - new Date(s.submittedAt).getTime()) / 86_400_000 > STALE_DAYS,
  ).length;
  if (stale > 0) {
    out.push({
      text: `${stale} expense ${stale === 1 ? "sheet is" : "sheets are"} awaiting approval for more than ${STALE_DAYS} days.`,
      tone: "warning",
      icon: "schedule",
    });
  }

  // Missing receipts.
  const missing = sheets.reduce(
    (s, sh) => s + (sh.lineItems ?? []).filter((li) => (li.attachments ?? []).length === 0).length,
    0,
  );
  if (missing > 0) {
    out.push({
      text: `${missing} line ${missing === 1 ? "item is" : "items are"} missing a receipt.`,
      tone: "warning",
      icon: "receipt_long",
    });
  }

  if (out.length < 2) {
    out.push({
      text: `Average expense value is ${Math.round(k.avgValue).toLocaleString()} across ${k.count} sheets.`,
      tone: "neutral",
      icon: "insights",
    });
  }
  return out;
}

// ── Anomaly detection (advisory) ──
export interface Anomaly {
  sheetId: string;
  title: string;
  employeeName: string;
  risk: number; // 0–100
  confidence: number; // 0–1
  reason: string;
  action: string;
  href?: string;
}

export function detectAnomalies(sheets: ExpenseSheet[], sheetHref?: (s: ExpenseSheet) => string): Anomaly[] {
  const found: Anomaly[] = [];
  for (const s of sheets) {
    const reasons: { reason: string; risk: number; action: string }[] = [];

    if ((s.total || 0) >= HIGH_VALUE) {
      reasons.push({ reason: `High-value claim (${Math.round(s.total).toLocaleString()}).`, risk: 55, action: "Review breakdown" });
    }
    const policyErr = (s.lineItems ?? []).some((li) => li.aiFlag?.severity === "error");
    if (policyErr) {
      reasons.push({ reason: "A line item violates policy (AI-flagged).", risk: 80, action: "Explain policy" });
    }
    const missing = (s.lineItems ?? []).filter((li) => (li.attachments ?? []).length === 0).length;
    if (missing > 0) {
      reasons.push({ reason: `${missing} line item(s) missing a receipt.`, risk: 45, action: "Request receipt" });
    }
    if (s.routeReason && /dup/i.test(String(s.routeReason))) {
      reasons.push({ reason: "Possible duplicate detected.", risk: 70, action: "Compare expenses" });
    }
    if (RETURNED_STATUSES.has(s.status)) {
      reasons.push({ reason: "Returned for correction.", risk: 35, action: "Review feedback" });
    }

    if (reasons.length === 0) continue;
    const top = reasons.sort((a, b) => b.risk - a.risk)[0];
    // Blend signals: more concurrent signals → higher risk + confidence.
    const risk = Math.min(100, top.risk + (reasons.length - 1) * 8);
    const confidence = s.llmConfidence != null ? s.llmConfidence : Math.min(0.95, 0.55 + reasons.length * 0.12);
    found.push({
      sheetId: s.id,
      title: s.title || "Untitled sheet",
      employeeName: s.employeeName ?? "",
      risk,
      confidence,
      reason: reasons.map((r) => r.reason).join(" "),
      action: top.action,
      href: sheetHref?.(s),
    });
  }
  return found.sort((a, b) => b.risk - a.risk);
}

// ── Employee-facing tasks (advisory) ──
// A deliberately employee-safe view of the same sheets: only things the *employee* can act on,
// phrased as next steps. It intentionally OMITS reviewer-internal signals — risk scores, AI
// confidence, duplicate-detection findings, and reviewer recommendations — so we never disclose
// the review/anti-fraud playbook to the person being reviewed.
export interface EmployeeTask {
  sheetId: string;
  title: string;
  reason: string;
  action: string;
  tone: "warning" | "error";
  href?: string;
}

export function detectEmployeeTasks(
  sheets: ExpenseSheet[],
  sheetHref?: (s: ExpenseSheet) => string,
): EmployeeTask[] {
  const out: EmployeeTask[] = [];
  for (const s of sheets) {
    const tasks: { reason: string; action: string; tone: "warning" | "error" }[] = [];

    if (RETURNED_STATUSES.has(s.status)) {
      tasks.push({
        reason: "Returned for correction.",
        action: "Review the feedback and resubmit.",
        tone: "error",
      });
    }
    const policyErr = (s.lineItems ?? []).some((li) => li.aiFlag?.severity === "error");
    if (policyErr) {
      tasks.push({
        reason: "A line item needs attention before it passes policy.",
        action: "Review and edit the flagged item.",
        tone: "error",
      });
    }
    const missing = (s.lineItems ?? []).filter((li) => (li.attachments ?? []).length === 0).length;
    if (missing > 0) {
      tasks.push({
        reason: `${missing} line item${missing === 1 ? "" : "s"} missing a receipt.`,
        action: "Attach the missing receipt(s).",
        tone: "warning",
      });
    }
    if ((s.total || 0) >= HIGH_VALUE) {
      tasks.push({
        reason: `Larger claim (${Math.round(s.total).toLocaleString()}).`,
        action: "Consider adding an itemized breakdown or note.",
        tone: "warning",
      });
    }
    // NOTE: duplicate detection and AI risk/confidence are intentionally excluded here.

    if (tasks.length === 0) continue;
    out.push({
      sheetId: s.id,
      title: s.title || "Untitled sheet",
      reason: tasks.map((t) => t.reason).join(" "),
      action: (tasks.find((t) => t.tone === "error") ?? tasks[0]).action,
      tone: tasks.some((t) => t.tone === "error") ? "error" : "warning",
      href: sheetHref?.(s),
    });
  }
  // Errors (things blocking the employee) first.
  return out.sort((a, b) => (a.tone === "error" ? 0 : 1) - (b.tone === "error" ? 0 : 1));
}

// ── Directional forecast (simple linear trend on monthly totals) ──
export interface Forecast {
  month: string;
  value: number;
  low: number;
  high: number;
}

export function forecastNextMonth(sheets: ExpenseSheet[]): Forecast | null {
  const { byMonth } = computeKpis(sheets);
  if (byMonth.length < 2) return null;
  const ys = byMonth.map((m) => m.amount);
  const n = ys.length;
  const xs = ys.map((_, i) => i);
  const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / a.length;
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my);
    den += (xs[i] - mx) ** 2;
  }
  const slope = den ? num / den : 0;
  const intercept = my - slope * mx;
  const next = Math.max(0, intercept + slope * n);
  // Band from residual spread.
  const resid = ys.map((y, i) => Math.abs(y - (intercept + slope * i)));
  const spread = mean(resid) || next * 0.15;
  const [y, m] = (byMonth[n - 1].month.split("-") as [string, string]).map(Number);
  const nextMonth = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
  return { month: nextMonth, value: next, low: Math.max(0, next - spread), high: next + spread };
}
