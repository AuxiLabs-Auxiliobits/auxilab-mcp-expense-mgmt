"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  useActivityLog,
  useCurrentUser,
  useFinanceKpis,
  useRoutedSheets,
} from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { LiveDot } from "@/components/shared/live-dot";
import { ActivityFeed } from "@/components/shared/activity-feed";
import { SavedViewsMenu } from "@/components/shared/saved-views";
import { DataGrid, type Column } from "@/components/shared/data-grid";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { PolicyDocuments } from "./policy-documents";
import { PolicyUploadDialog } from "./policy-upload-dialog";
import { ReviewDetail } from "./review-detail";
import { ROUTE_REASON_META } from "@/lib/status";
import { AGING_CLASS, agingLevel } from "@/lib/aging";
import { formatCurrency } from "@/lib/format";
import { downloadCsv } from "@/lib/export";
import { cn } from "@/lib/utils";
import type { ExpenseSheet, RouteReason } from "@/data/types";

const REASON_FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "All" },
  { key: "LOW_CONFIDENCE", label: "Low confidence" },
  { key: "AMBIGUOUS_CLAUSE", label: "Ambiguous clause" },
  { key: "MISSING_POLICY", label: "Missing policy" },
  { key: "NUMERIC_DISAGREEMENT", label: "Numeric" },
];

function focusQueue() {
  document.getElementById("review-queue")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Read-only AI performance metric (demoted from the action tiles). */
function PerfStat({
  label,
  value,
  delta,
  deltaTone,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: string;
}) {
  return (
    <div className="px-4 py-3">
      <div className="text-label-sm font-medium text-on-surface-variant">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-body-lg font-semibold tabular-nums text-on-surface">{value}</span>
        {delta && <span className={cn("text-label-sm font-medium", deltaTone)}>{delta}</span>}
      </div>
    </div>
  );
}

function ConfidenceBar({ value }: { value?: number }) {
  if (value == null) return <span className="text-on-surface-variant">—</span>;
  const pct = Math.round(value * 100);
  const tone = pct >= 75 ? "bg-success-green" : pct >= 60 ? "bg-yellow-500" : "bg-error";
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-container-high">
        <span className={cn("block h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono text-label-md tabular-nums text-on-surface-variant">{pct}%</span>
    </span>
  );
}

export function FinanceConsole() {
  const { data: routed, isLoading } = useRoutedSheets();
  const { data: kpis } = useFinanceKpis();
  const { data: financeUser } = useCurrentUser("finance");
  const { data: activity } = useActivityLog("finance", financeUser?.id ?? "");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reason, setReason] = useState("all");
  const [query, setQuery] = useState("");
  const [slaOnly, setSlaOnly] = useState(false);

  const all = useMemo(() => routed ?? [], [routed]);

  const counts = useMemo(
    () =>
      Object.fromEntries(
        REASON_FILTERS.map((f) => [
          f.key,
          f.key === "all" ? all.length : all.filter((s) => s.routeReason === f.key).length,
        ]),
      ),
    [all],
  );

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all
      .filter((s) => reason === "all" || s.routeReason === reason)
      .filter((s) => !slaOnly || agingLevel(s.submittedAt).level === "escalation")
      .filter(
        (s) =>
          !q ||
          s.id.toLowerCase().includes(q) ||
          s.agencyName.toLowerCase().includes(q) ||
          s.employeeName.toLowerCase().includes(q),
      );
  }, [all, reason, query, slaOnly]);

  const selected = all.find((s) => s.id === selectedId) ?? null;
  const hasFilters = reason !== "all" || !!query || slaOnly;

  function exportSheets(list: ExpenseSheet[]) {
    downloadCsv(
      `routed-queue-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Sheet ID", "Agency", "Employee", "Amount", "Currency", "Flag reason", "AI confidence", "Age (h)", "Status"],
      list.map((s) => [
        s.id,
        s.agencyName,
        s.employeeName,
        s.total,
        s.currency,
        s.routeReason ?? "",
        s.llmConfidence != null ? Math.round(s.llmConfidence * 100) / 100 : "",
        agingLevel(s.submittedAt).hours,
        s.status,
      ]),
    );
  }

  const columns: Column<ExpenseSheet>[] = [
    {
      key: "id",
      header: "Sheet ID",
      sortAccessor: (s) => s.id,
      render: (s) => <span className="font-mono text-label-md font-medium text-primary">{s.id}</span>,
    },
    { key: "agency", header: "Agency", sortAccessor: (s) => s.agencyName, render: (s) => s.agencyName },
    {
      key: "employee",
      header: "Employee",
      sortAccessor: (s) => s.employeeName,
      render: (s) => <span className="text-on-surface-variant">{s.employeeName}</span>,
    },
    {
      key: "items",
      header: "Items",
      align: "right",
      sortAccessor: (s) => s.lineItems.length,
      render: (s) => <span className="tabular-nums text-on-surface-variant">{s.lineItems.length}</span>,
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      sortAccessor: (s) => s.total,
      render: (s) => <span className="font-mono font-medium">{formatCurrency(s.total, s.currency)}</span>,
    },
    {
      key: "reason",
      header: "Flag Reason",
      render: (s) =>
        s.routeReason ? (
          <Badge className={ROUTE_REASON_META[s.routeReason as RouteReason].badgeClass} pill={false}>
            <Icon name={ROUTE_REASON_META[s.routeReason as RouteReason].icon} className="text-[14px]" />
            {ROUTE_REASON_META[s.routeReason as RouteReason].label}
          </Badge>
        ) : (
          <span className="text-on-surface-variant">—</span>
        ),
    },
    {
      key: "confidence",
      header: "AI Confidence",
      sortAccessor: (s) => s.llmConfidence ?? 0,
      render: (s) => <ConfidenceBar value={s.llmConfidence} />,
    },
    {
      key: "age",
      header: "Age (SLA)",
      sortAccessor: (s) => agingLevel(s.submittedAt).hours,
      render: (s) => {
        const aging = agingLevel(s.submittedAt);
        return (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-label-sm font-semibold",
              AGING_CLASS[aging.level],
            )}
          >
            <Icon
              name={aging.level === "escalation" ? "priority_high" : "schedule"}
              className="text-[12px]"
            />
            {aging.label}
          </span>
        );
      },
    },
    {
      key: "action",
      header: "",
      align: "right",
      render: () => <Icon name="chevron_right" className="text-[18px] text-on-surface-variant" />,
    },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="Policy & AI Approver Console"
        description="Resolve AI-flagged exceptions, monitor approver performance, and govern agency policy."
        size="xl"
      >
        <span className="flex items-center gap-2 rounded-md border border-outline-variant bg-surface-container-highest px-3 py-1.5 font-mono text-label-md uppercase text-on-surface">
          <LiveDot /> AI engine active
        </span>
        <Button variant="outline" onClick={() => exportSheets(rows)} disabled={!rows.length}>
          <Icon name="download" /> Export
        </Button>
        <PolicyUploadDialog
          trigger={
            <Button variant="outline">
              <Icon name="upload_file" /> Update policy
            </Button>
          }
        />
      </PageHeader>

      {/* AI Approver performance — read-only analytics (demoted) */}
      <Card className="mt-6 overflow-hidden">
        <div className="flex items-center justify-between border-b border-outline-variant px-4 py-2">
          <h2 className="flex items-center gap-1.5 text-label-md font-semibold uppercase tracking-wider text-on-surface-variant">
            <Icon name="smart_toy" className="text-[16px] text-secondary" /> AI Approver performance · 30 days
          </h2>
          {kpis && (
            <span className="hidden font-mono text-label-sm text-on-surface-variant sm:inline">
              {kpis.manualInterventions} manual interventions · RAG synced {kpis.ragSyncedAgo}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 divide-x divide-y divide-outline-variant sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
          <PerfStat
            label="Auto-approval"
            value={kpis ? `${kpis.autoApprovalRate}%` : "—"}
            delta={kpis ? `▲ ${kpis.autoApprovalDelta}%` : undefined}
            deltaTone="text-success-green"
          />
          <PerfStat label="Escalation rate" value={kpis ? `${kpis.escalationRate}%` : "—"} />
          <PerfStat label="Approval accuracy" value={kpis ? `${kpis.approvalAccuracy}%` : "—"} />
          <PerfStat label="False-positive" value={kpis ? `${kpis.falsePositiveRate}%` : "—"} />
          <PerfStat label="SLA compliance" value={kpis ? `${kpis.slaCompliance}%` : "—"} />
          <PerfStat label="Avg resolution" value={kpis ? `${kpis.avgResolutionHours}h` : "—"} />
        </div>
      </Card>

      {/* Interactive funnel — counts + the Routed stage focuses the queue */}
      <Card className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2 px-5 py-3 text-body-sm">
        <span className="flex items-center gap-1.5 text-on-surface-variant">
          <Icon name="outbox" className="text-[18px]" /> Submitted
        </span>
        <Icon name="chevron_right" className="text-[16px] text-outline" />
        <span className="flex items-center gap-1.5 font-medium text-on-surface">
          <Icon name="smart_toy" className="text-[18px] text-secondary" /> AI Approver
        </span>
        <Icon name="chevron_right" className="text-[16px] text-outline" />
        <span className="flex items-center gap-1.5 text-success-green">
          <Icon name="check_circle" className="text-[18px]" /> Auto-cleared {kpis ? `${kpis.autoApprovalRate}%` : ""}
        </span>
        <span className="text-outline">·</span>
        <button
          type="button"
          onClick={focusQueue}
          className="flex items-center gap-1.5 rounded-md border border-error/30 bg-error-container px-2 py-0.5 font-medium text-error transition-colors hover:bg-error/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
        >
          <Icon name="hub" className="text-[18px]" /> Routed {all.length}
          <Icon name="arrow_downward" className="text-[13px]" />
        </button>
        <Icon name="chevron_right" className="text-[16px] text-outline" />
        <span className="flex items-center gap-1.5 text-on-surface-variant">
          <Icon name="gavel" className="text-[18px]" /> Finance decision
        </span>
        <Icon name="chevron_right" className="text-[16px] text-outline" />
        <span className="flex items-center gap-1.5 text-on-surface-variant">
          <Icon name="paid" className="text-[18px]" /> Paid
        </span>
      </Card>

      {/* Hero — exception queue workspace */}
      <Card id="review-queue" className="mt-3 scroll-mt-4 overflow-hidden">
        <CardHeader className="flex-col items-stretch gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle>Routed for Manual Review</CardTitle>
              <Badge className="bg-error-container text-error" pill={false}>
                {rows.length} of {all.length}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <SavedViewsMenu
                storageKey="finance-console-views"
                current={{ reason, query, slaOnly }}
                onApply={(v) => {
                  setReason(v.reason ?? "all");
                  setQuery(v.query ?? "");
                  setSlaOnly(!!v.slaOnly);
                }}
              />
              <Button size="sm" variant="outline" onClick={() => exportSheets(rows)} disabled={!rows.length}>
                <Icon name="download" className="text-[16px]" /> Export
              </Button>
            </div>
          </div>
          {/* Consolidated toolbar: search + filter chips */}
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative lg:w-72">
              <Icon
                name="search"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant"
              />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search sheet, agency, employee…"
                className="pl-9"
                aria-label="Search routed sheets"
              />
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {REASON_FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setReason(f.key)}
                  aria-pressed={reason === f.key}
                  className={cn(
                    "flex h-7 items-center gap-1.5 rounded-md px-2.5 text-label-md font-medium transition-colors",
                    reason === f.key
                      ? "bg-primary text-on-primary"
                      : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
                  )}
                >
                  {f.label}
                  <span
                    className={cn(
                      "rounded px-1 tabular-nums",
                      reason === f.key ? "bg-on-primary/20" : "bg-surface-container-high",
                    )}
                  >
                    {counts[f.key] ?? 0}
                  </span>
                </button>
              ))}
              {slaOnly && (
                <button
                  onClick={() => setSlaOnly(false)}
                  className="flex h-7 items-center gap-1 rounded-md bg-error-container px-2.5 text-label-md font-medium text-error"
                >
                  <Icon name="priority_high" className="text-[13px]" /> SLA breaches
                  <Icon name="close" className="text-[13px]" />
                </button>
              )}
            </div>
          </div>
        </CardHeader>
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <DataGrid
            columns={columns}
            rows={rows}
            getRowId={(s) => s.id}
            pageSize={15}
            selectable
            columnManagement
            bulkActions={(sel) => (
              <Button size="sm" variant="outline" onClick={() => exportSheets(sel)}>
                <Icon name="download" className="text-[16px]" /> Export selected
              </Button>
            )}
            onRowClick={(s) => setSelectedId(s.id)}
            emptyMessage={
              hasFilters
                ? "No routed sheets match your filters."
                : "Queue clear — no sheets routed for manual review."
            }
          />
        )}
      </Card>

      {/* Secondary — policy governance + activity */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <PolicyDocuments />
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <Link
              href="/finance/audit"
              className="font-mono text-label-md text-secondary hover:underline"
            >
              Audit log
            </Link>
          </CardHeader>
          <ActivityFeed entries={activity ?? []} />
        </Card>
      </div>

      {/* Review drawer */}
      <Drawer open={!!selected} onOpenChange={(o) => !o && setSelectedId(null)}>
        <DrawerContent className="max-w-2xl">
          {selected && (
            <>
              <DrawerHeader>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-label-md font-medium text-primary">{selected.id}</span>
                  <span className="rounded border border-outline-variant bg-surface-container-highest px-2 py-0.5 font-mono text-label-sm text-on-surface-variant">
                    {selected.agencyName}
                  </span>
                </div>
                <DrawerTitle className="mt-1">Manual review</DrawerTitle>
                <DrawerDescription>
                  {selected.employeeName} · {formatCurrency(selected.total, selected.currency)}
                </DrawerDescription>
              </DrawerHeader>
              <DrawerBody>
                <ReviewDetail sheet={selected} embedded onClose={() => setSelectedId(null)} />
              </DrawerBody>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </PageContainer>
  );
}
