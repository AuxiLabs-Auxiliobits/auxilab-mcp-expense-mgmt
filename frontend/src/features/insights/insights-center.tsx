"use client";

/**
 * AI Analytics & Insights Center (advisory). Reuses the existing role-scoped data hooks and
 * the deterministic insight/anomaly/forecast engine. RBAC is inherited from the data layer
 * (each role only loads what it may see); it never mutates workflow state.
 */
import Link from "next/link";
import {
  useCurrentUser,
  useAllSheets,
  useEmployeeSheets,
  useFinanceKpis,
  useManagerQueue,
} from "@/data/hooks";
import type { FinanceKpisResult } from "@/data/api";
import {
  computeInsights,
  computeKpis,
  detectAnomalies,
  detectEmployeeTasks,
  forecastNextMonth,
  type AnalyticsKpis,
  type Anomaly,
  type EmployeeTask,
  type Insight,
} from "@/lib/insights";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Chart } from "@/components/shared/chart";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format";
import { downloadCsv } from "@/lib/export";
import { cn } from "@/lib/utils";
import type { EChartsOption } from "echarts";
import type { ExpenseSheet, Role } from "@/data/types";

const TONE: Record<Insight["tone"], string> = {
  neutral: "text-tertiary bg-tertiary/10",
  positive: "text-success-green bg-success-green/10",
  warning: "text-yellow-600 bg-yellow-500/10",
};

function riskClass(r: number): string {
  if (r >= 70) return "bg-error/15 text-error";
  if (r >= 40) return "bg-yellow-500/15 text-yellow-600";
  return "bg-surface-container-high text-on-surface-variant";
}

function Kpi({ label, value, tone, href }: { label: string; value: string; tone?: string; href?: string }) {
  const inner = (
    <div
      className={cn(
        "px-4 py-3",
        href && "group cursor-pointer transition-colors hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary",
      )}
    >
      <div className="flex items-center gap-1 text-label-sm font-medium text-on-surface-variant">
        {label}
        {href && <Icon name="open_in_new" className="text-[11px] opacity-0 transition-opacity group-hover:opacity-60" />}
      </div>
      <div className={cn("mt-0.5 text-headline-md font-semibold tabular-nums text-on-surface", tone)}>
        {value}
      </div>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

/** Spend-over-time bar chart rendered above the forecast. Requires ≥ 2 months of data. */
function SpendTrendChart({ byMonth }: { byMonth: { month: string; amount: number }[] }) {
  if (byMonth.length < 2) return null;
  const option: EChartsOption = {
    grid: { top: 12, right: 12, bottom: 28, left: 52, containLabel: false },
    xAxis: {
      type: "category",
      data: byMonth.map((m) => m.month),
      axisLabel: { fontSize: 11, color: "#6B7280" },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#E5E7EB" } },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 11,
        color: "#6B7280",
        formatter: (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`),
      },
      splitLine: { lineStyle: { color: "#F3F4F6" } },
    },
    series: [
      {
        type: "bar",
        data: byMonth.map((m) => m.amount),
        itemStyle: { color: "#6750A4", borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 32,
      },
      {
        type: "line",
        data: byMonth.map((m) => m.amount),
        smooth: true,
        lineStyle: { color: "#9C89B8", width: 2 },
        symbol: "none",
        z: 10,
      },
    ],
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const p = (params as { axisValue: string; value: number }[])[0];
        return `${p.axisValue}: $${Number(p.value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      },
    },
  };
  return <Chart option={option} height={150} />;
}

/** Null-safe KPI formatters — a null (backend couldn't compute it) shows an em dash. */
const fmtPct = (v?: number | null) => (v == null ? "—" : `${v}%`);
const fmtHrs = (v?: number | null) => (v == null ? "—" : `${v}h`);

function InsightsView({
  sheets,
  role,
  assistantHref,
  sheetHref,
  csvName,
  financeKpis,
  pendingHref,
  returnedHref,
}: {
  sheets: ExpenseSheet[];
  role: Role;
  assistantHref: string | null;
  sheetHref: (s: ExpenseSheet) => string;
  csvName: string;
  /** AI Approver performance KPIs — finance/admin only. */
  financeKpis?: FinanceKpisResult;
  /** If provided, the "Pending" KPI tile becomes a link. */
  pendingHref?: string;
  /** If provided, the "Returned" KPI tile becomes a link. */
  returnedHref?: string;
}) {
  const isEmployee = role === "employee";
  const kpis: AnalyticsKpis = computeKpis(sheets);
  const insights = computeInsights(sheets);
  // Employees get an action-oriented, disclosure-safe list (no risk/confidence/reviewer
  // recommendations); manager/finance get the full anomaly triage view.
  const anomalies = isEmployee ? [] : detectAnomalies(sheets, sheetHref).slice(0, 8);
  const tasks = isEmployee ? detectEmployeeTasks(sheets, sheetHref).slice(0, 8) : [];
  const forecast = forecastNextMonth(sheets);
  const maxCat = kpis.byCategory[0]?.amount || 1;

  function exportCsv() {
    if (isEmployee) {
      // Employee exports only cover their own sheets — "Employee" column is redundant.
      downloadCsv(
        `${csvName}-${new Date().toISOString().slice(0, 10)}.csv`,
        ["Sheet ID", "Title", "Status", "Total", "Currency"],
        sheets.map((s) => [s.id, s.title, s.status, s.total, s.currency]),
      );
    } else {
      downloadCsv(
        `${csvName}-${new Date().toISOString().slice(0, 10)}.csv`,
        ["Sheet ID", "Title", "Employee", "Status", "Total", "Currency"],
        sheets.map((s) => [s.id, s.title, s.employeeName, s.status, s.total, s.currency]),
      );
    }
  }

  const askAi = (q: string) => `${assistantHref}?q=${encodeURIComponent(q)}`;

  return (
    <PageContainer>
      <PageHeader title="Analytics & Insights" description="AI-assisted spend intelligence — advisory only." size="xl">
        {assistantHref && (
          <Button asChild variant="outline">
            <Link href={askAi("Summarize my expense analytics and any risks")}>
              <Icon name="smart_toy" /> Ask AI
            </Link>
          </Button>
        )}
        <Button variant="outline" onClick={exportCsv} disabled={!sheets.length}>
          <Icon name="download" /> Export CSV
        </Button>
      </PageHeader>

      {/* KPI strip */}
      <Card className="mt-6 grid grid-cols-2 divide-x divide-y divide-outline-variant sm:grid-cols-3 lg:grid-cols-5 lg:divide-y-0">
        <Kpi label="Total spend" value={formatCurrency(kpis.total, "USD")} />
        <Kpi label="Expense sheets" value={String(kpis.count)} />
        <Kpi label="Pending" value={String(kpis.pending)} tone={kpis.pending ? "text-yellow-600" : undefined} href={kpis.pending ? pendingHref : undefined} />
        <Kpi label="Returned" value={String(kpis.returned)} tone={kpis.returned ? "text-error" : undefined} href={kpis.returned ? returnedHref : undefined} />
        <Kpi label="Avg / sheet" value={formatCurrency(kpis.avgValue, "USD")} />
      </Card>

      {/* AI Approver performance — finance/admin only (real metrics; "—" when not computed). */}
      {financeKpis && (
        <Card className="mt-3 overflow-hidden">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <Icon name="smart_toy" className="text-[18px] text-secondary" /> AI Approver performance · 30 days
            </CardTitle>
            <span className="hidden font-mono text-label-sm text-on-surface-variant sm:inline">
              {financeKpis.manualInterventions} manual interventions
              {financeKpis.ragSyncedAgo ? ` · RAG synced ${financeKpis.ragSyncedAgo}` : ""}
            </span>
          </CardHeader>
          <div className="grid grid-cols-2 divide-x divide-y divide-outline-variant sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
            <Kpi label="Auto-approval" value={fmtPct(financeKpis.autoApprovalRate)} />
            <Kpi label="Escalation rate" value={fmtPct(financeKpis.escalationRate)} />
            <Kpi label="Approval accuracy" value={fmtPct(financeKpis.approvalAccuracy)} />
            <Kpi label="False-positive" value={fmtPct(financeKpis.falsePositiveRate)} />
            <Kpi label="SLA compliance" value={fmtPct(financeKpis.slaCompliance)} />
            <Kpi label="Avg resolution" value={fmtHrs(financeKpis.avgResolutionHours)} />
          </div>
        </Card>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {/* AI insights */}
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Icon name="auto_awesome" className="text-[18px] text-primary" /> AI Insights
            </CardTitle>
          </CardHeader>
          <div className="space-y-2 p-4 pt-0">
            {insights.length === 0 ? (
              <p className="py-6 text-center text-body-sm text-on-surface-variant">
                Not enough data yet for insights.
              </p>
            ) : (
              insights.map((it, i) => (
                <div key={i} className="flex items-start gap-3 rounded-lg bg-surface-container-low/60 p-3">
                  <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full", TONE[it.tone])}>
                    <Icon name={it.icon} className="text-[16px]" />
                  </span>
                  <p className="text-body-sm text-on-surface">{it.text}</p>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Category breakdown */}
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Spend by category</CardTitle>
          </CardHeader>
          <div className="space-y-2.5 p-4 pt-0">
            {kpis.byCategory.slice(0, 6).map((c) => (
              <div key={c.category}>
                <div className="flex items-center justify-between text-body-sm">
                  <span className="text-on-surface">{c.category}</span>
                  <span className="font-mono tabular-nums text-on-surface-variant">
                    {formatCurrency(c.amount, "USD")}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-container-high">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${(c.amount / maxCat) * 100}%` }} />
                </div>
              </div>
            ))}
            {kpis.byCategory.length === 0 && (
              <p className="py-6 text-center text-body-sm text-on-surface-variant">No category data.</p>
            )}
          </div>
        </Card>
      </div>

      {/* Spend trend + forecast */}
      {kpis.byMonth.length >= 2 && (
        <Card className="mt-3 overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Icon name="bar_chart" className="text-[18px] text-secondary" /> Monthly spend trend
            </CardTitle>
          </CardHeader>
          <div className="px-2 pb-2 pt-0">
            <SpendTrendChart byMonth={kpis.byMonth} />
          </div>
          {forecast && (
            <div className="flex flex-wrap items-center gap-x-8 gap-y-1 border-t border-outline-variant px-5 py-3">
              <div className="flex items-center gap-2 text-body-sm font-medium text-on-surface">
                <Icon name="query_stats" className="text-[16px] text-secondary" /> Forecast · {forecast.month}
              </div>
              <div className="text-headline-sm font-semibold tabular-nums text-on-surface">
                {formatCurrency(forecast.value, "USD")}
              </div>
              <div className="text-body-sm text-on-surface-variant">
                range {formatCurrency(forecast.low, "USD")} – {formatCurrency(forecast.high, "USD")} (directional)
              </div>
            </div>
          )}
        </Card>
      )}
      {/* Fallback: show forecast-only row when < 2 months of history exist */}
      {kpis.byMonth.length < 2 && forecast && (
        <Card className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-2 px-5 py-4">
          <div className="flex items-center gap-2 text-body-sm font-medium text-on-surface">
            <Icon name="query_stats" className="text-[18px] text-secondary" /> Forecast · {forecast.month}
          </div>
          <div className="text-headline-md font-semibold tabular-nums text-on-surface">
            {formatCurrency(forecast.value, "USD")}
          </div>
          <div className="text-body-sm text-on-surface-variant">
            range {formatCurrency(forecast.low, "USD")} – {formatCurrency(forecast.high, "USD")} (directional)
          </div>
        </Card>
      )}

      {/* Anomalies — employees see an action-oriented "to fix" list (no risk/confidence/
          reviewer recommendations); manager/finance see the full triage view. */}
      {isEmployee ? (
        <Card className="mt-3 overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Icon name="checklist" className="text-[18px] text-primary" /> Needs your attention
              <span className="ml-1 rounded-full bg-surface-container-high px-2 py-0.5 text-label-md text-on-surface-variant">
                {tasks.length}
              </span>
            </CardTitle>
          </CardHeader>
          {tasks.length === 0 ? (
            <p className="px-4 py-8 text-center text-body-sm text-on-surface-variant">
              You&apos;re all caught up — nothing needs your attention.
            </p>
          ) : (
            <div className="divide-y divide-outline-variant">
              {tasks.map((t: EmployeeTask) => (
                <div key={t.sheetId} className="flex items-center gap-3 px-4 py-3">
                  <span
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                      t.tone === "error" ? "bg-error/10 text-error" : "bg-yellow-500/10 text-yellow-600",
                    )}
                  >
                    <Icon name={t.tone === "error" ? "error" : "warning"} className="text-[18px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <span className="truncate text-body-sm font-medium text-on-surface">{t.title}</span>
                    <p className="line-clamp-1 text-body-sm text-on-surface-variant">{t.reason}</p>
                    <p className="mt-0.5 text-label-sm text-primary">{t.action}</p>
                  </div>
                  {t.href && (
                    <Button asChild size="sm" variant="outline">
                      <Link href={t.href}>Open</Link>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      ) : (
        <Card className="mt-3 overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Icon name="release_alert" className="text-[18px] text-error" /> Risk &amp; anomalies
              <span className="ml-1 rounded-full bg-surface-container-high px-2 py-0.5 text-label-md text-on-surface-variant">
                {anomalies.length}
              </span>
            </CardTitle>
          </CardHeader>
          {anomalies.length === 0 ? (
            <p className="px-4 py-8 text-center text-body-sm text-on-surface-variant">
              No anomalies detected. Nothing needs attention.
            </p>
          ) : (
            <div className="divide-y divide-outline-variant">
              {anomalies.map((a: Anomaly) => (
                <div key={a.sheetId} className="flex items-center gap-3 px-4 py-3">
                  <span className={cn("flex h-10 w-12 shrink-0 flex-col items-center justify-center rounded-lg text-label-sm font-semibold", riskClass(a.risk))}>
                    <span className="text-body-sm tabular-nums">{a.risk}</span>
                    <span className="text-[9px] uppercase">risk</span>
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-body-sm font-medium text-on-surface">{a.title}</span>
                      {a.employeeName && (
                        <span className="shrink-0 text-label-md text-on-surface-variant">· {a.employeeName}</span>
                      )}
                    </div>
                    <p className="line-clamp-1 text-body-sm text-on-surface-variant">{a.reason}</p>
                    <p className="mt-0.5 text-label-sm text-on-surface-variant">
                      Confidence {Math.round(a.confidence * 100)}% · Recommended: {a.action}
                    </p>
                  </div>
                  {a.href && (
                    <Button asChild size="sm" variant="outline">
                      <Link href={a.href}>Review</Link>
                    </Button>
                  )}
                  {assistantHref && (
                    <Button asChild size="sm" variant="ghost">
                      <Link href={askAi(`Explain the risk on expense "${a.title}" and what to do`)}>
                        <Icon name="smart_toy" className="text-[16px]" />
                      </Link>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </PageContainer>
  );
}

function LoadingView() {
  return (
    <PageContainer>
      <PageHeader title="Analytics & Insights" description="AI-assisted spend intelligence — advisory only." size="xl" />
      <Skeleton className="mt-6 h-20 rounded-lg" />
      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Skeleton className="h-56 rounded-lg" />
        <Skeleton className="h-56 rounded-lg" />
      </div>
      <Skeleton className="mt-3 h-40 rounded-lg" />
    </PageContainer>
  );
}

// ── Role-scoped data loaders (each calls only permitted hooks) ──
function EmployeeInsights() {
  const { data: user } = useCurrentUser("employee");
  const { data: sheets, isLoading } = useEmployeeSheets(user?.id ?? "");
  if (isLoading || !user) return <LoadingView />;
  return (
    <InsightsView
      sheets={sheets ?? []}
      role="employee"
      assistantHref={null}
      sheetHref={(s) => `/employee/sheets/${s.id}`}
      csvName="my-expenses"
      pendingHref="/employee/sheets"
      returnedHref="/employee/sheets"
    />
  );
}

function ManagerInsights() {
  const { data: user } = useCurrentUser("manager");
  const { data: sheets, isLoading } = useManagerQueue(user?.agencyId ?? "");
  if (isLoading || !user) return <LoadingView />;
  return (
    <InsightsView
      sheets={sheets ?? []}
      role="manager"
      assistantHref="/manager/assistant"
      sheetHref={() => "/manager"}
      csvName="team-expenses"
      pendingHref="/manager"
    />
  );
}

function FinanceInsights({ role }: { role: Role }) {
  const { data: sheets, isLoading } = useAllSheets();
  const { data: financeKpis } = useFinanceKpis();
  if (isLoading) return <LoadingView />;
  return (
    <InsightsView
      sheets={sheets ?? []}
      role={role}
      assistantHref="/finance/assistant"
      sheetHref={() => "/finance/sheets"}
      csvName="company-expenses"
      financeKpis={financeKpis}
      pendingHref="/finance"
      returnedHref="/finance/sheets"
    />
  );
}

export function InsightsCenter({ role }: { role: Role }) {
  if (role === "employee") return <EmployeeInsights />;
  if (role === "manager") return <ManagerInsights />;
  return <FinanceInsights role={role} />;
}
