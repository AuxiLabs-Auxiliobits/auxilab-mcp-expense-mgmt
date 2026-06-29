"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  useAllSheets,
  useFinanceKpis,
  useProcessPendingApprover,
  useRoutedSheets,
} from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
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
import { ReviewDetail } from "./review-detail";
import { ROUTE_REASON_META } from "@/lib/status";
import { AGING_CLASS, agingLevel } from "@/lib/aging";
import { formatCurrency, formatDateTimeIST, formatRelative } from "@/lib/format";
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

/** Action-oriented triage tile — clickable variants filter the queue. */
function TriageTile({
  label,
  value,
  sub,
  tone,
  active,
  onClick,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const className = cn(
    "flex flex-col items-start px-5 py-3.5 text-left transition-colors",
    onClick && "cursor-pointer hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary",
    active && "bg-primary-fixed/50",
  );
  const inner = (
    <>
      <span className="text-label-md font-medium text-on-surface-variant">{label}</span>
      <span className={cn("mt-0.5 text-headline-md font-semibold tabular-nums text-on-surface", tone)}>
        {value}
      </span>
      {onClick ? (
        <span className="mt-0.5 flex items-center gap-0.5 text-label-sm font-medium text-secondary">
          {active ? "Filtering" : "Filter queue"}
          <Icon name="arrow_downward" className="text-[12px]" />
        </span>
      ) : (
        sub && <span className="mt-0.5 text-label-sm text-on-surface-variant">{sub}</span>
      )}
    </>
  );
  return onClick ? (
    <button type="button" onClick={onClick} aria-pressed={active} className={className}>
      {inner}
    </button>
  ) : (
    <div className={className}>{inner}</div>
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
  const { data: routed, isLoading, refetch, isFetching } = useRoutedSheets();
  const { data: allSheets } = useAllSheets();
  const { data: kpis } = useFinanceKpis();
  const processPending = useProcessPendingApprover();

  function runPending() {
    processPending.mutate(undefined, {
      onSuccess: (r) =>
        toast.success(
          r.processed
            ? `Processed ${r.processed} pending — ${r.approved} auto-approved, ${r.routed} routed for review`
            : "No sheets are waiting in finance review.",
        ),
    });
  }

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reason, setReason] = useState("all");
  const [query, setQuery] = useState("");
  // Aging filter driven by the triage tiles: escalation = SLA breaches, warning = approaching SLA.
  const [aging, setAging] = useState<"all" | "escalation" | "warning">("all");

  const all = useMemo(() => routed ?? [], [routed]);

  // AI auto-approved sheets — available for Finance to audit and optionally override.
  const autoApproved = useMemo(
    () => (allSheets ?? []).filter((s) => s.status === "FINANCE_APPROVED"),
    [allSheets],
  );

  // Fully approved and rejected sheets — Finance can still override at any point.
  const approved = useMemo(
    () => (allSheets ?? []).filter((s) => s.status === "APPROVED"),
    [allSheets],
  );
  const rejected = useMemo(
    () => (allSheets ?? []).filter((s) => s.status === "FINANCE_REJECTED" || s.status === "REJECTED"),
    [allSheets],
  );

  // Triage signals.
  const breaches = all.filter((s) => agingLevel(s.submittedAt).level === "escalation").length;
  const warnings = all.filter((s) => agingLevel(s.submittedAt).level === "warning").length;
  const oldestHours = all.reduce((m, s) => Math.max(m, agingLevel(s.submittedAt).hours), 0);
  const oldestLabel = oldestHours >= 24 ? `${Math.floor(oldestHours / 24)}d` : `${oldestHours}h`;

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
      .filter((s) => aging === "all" || agingLevel(s.submittedAt).level === aging)
      .filter(
        (s) =>
          !q ||
          s.id.toLowerCase().includes(q) ||
          s.agencyName.toLowerCase().includes(q) ||
          s.employeeName.toLowerCase().includes(q),
      );
  }, [all, reason, query, aging]);

  const selected =
    all.find((s) => s.id === selectedId) ??
    autoApproved.find((s) => s.id === selectedId) ??
    approved.find((s) => s.id === selectedId) ??
    rejected.find((s) => s.id === selectedId) ??
    null;
  const hasFilters = reason !== "all" || !!query || aging !== "all";

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
      key: "submitted",
      header: "Submitted (IST)",
      sortAccessor: (s) => s.submittedAt ?? "",
      render: (s) =>
        s.submittedAt ? (
          <span
            className="font-mono text-label-md text-on-surface-variant"
            title={formatRelative(s.submittedAt)}
          >
            {formatDateTimeIST(s.submittedAt)}
          </span>
        ) : (
          <span className="text-on-surface-variant">—</span>
        ),
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
        <Button
          variant="outline"
          onClick={() => refetch()}
          loading={isFetching}
          title="Pull in newly routed sheets without reloading"
        >
          <Icon name="refresh" /> Refresh
        </Button>
        <Button
          variant="outline"
          onClick={runPending}
          loading={processPending.isPending}
          title="Run the AI approver on sheets stuck in finance review"
        >
          <Icon name="smart_toy" /> Process pending
        </Button>
        <Button variant="outline" onClick={() => exportSheets(rows)} disabled={!rows.length}>
          <Icon name="download" /> Export
        </Button>
      </PageHeader>

      {/* Triage strip — action-first metrics. The first two filter the queue. */}
      <Card className="mt-6 grid grid-cols-2 divide-x divide-y divide-outline-variant sm:grid-cols-4 sm:divide-y-0">
        <TriageTile
          label="Pending review"
          value={String(all.length)}
          tone="text-on-surface"
          active={!hasFilters}
          onClick={() => {
            setReason("all");
            setQuery("");
            setAging("all");
            focusQueue();
          }}
        />
        <TriageTile
          label="SLA breaches"
          value={String(breaches)}
          tone={breaches ? "text-error" : undefined}
          active={aging === "escalation"}
          onClick={() => {
            setAging((v) => (v === "escalation" ? "all" : "escalation"));
            focusQueue();
          }}
        />
        <TriageTile
          label="Approaching SLA"
          value={String(warnings)}
          tone={warnings ? "text-yellow-600" : undefined}
          active={aging === "warning"}
          onClick={() => {
            setAging((v) => (v === "warning" ? "all" : "warning"));
            focusQueue();
          }}
        />
        <TriageTile label="Oldest in queue" value={all.length ? oldestLabel : "—"} sub="time waiting" />
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
              {/* <SavedViewsMenu
                storageKey="finance-console-views-v2"
                current={{ reason, query, aging }}
                onApply={(v) => {
                  setReason(v.reason ?? "all");
                  setQuery(v.query ?? "");
                  setAging(v.aging ?? "all");
                }}
              /> */}
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
              {aging !== "all" && (
                <button
                  onClick={() => setAging("all")}
                  className={cn(
                    "flex h-7 items-center gap-1 rounded-md px-2.5 text-label-md font-medium",
                    aging === "escalation"
                      ? "bg-error-container text-error"
                      : "bg-yellow-500/10 text-yellow-600",
                  )}
                >
                  <Icon
                    name={aging === "escalation" ? "priority_high" : "schedule"}
                    className="text-[13px]"
                  />
                  {aging === "escalation" ? "SLA breaches" : "Approaching SLA"}
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

      {/* AI Auto-approved audit — Finance can review and override any auto-approved sheet */}
      <Card className="mt-3 overflow-hidden">
        <CardHeader className="flex-col items-stretch gap-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="flex items-center gap-2">
                <Icon name="check_circle" className="text-success-green" />
                AI Auto-approved
              </CardTitle>
              <Badge className="bg-success-green/10 text-success-green" pill={false}>
                {autoApproved.length}
              </Badge>
            </div>
            <p className="text-label-sm text-on-surface-variant">
              These sheets passed policy checks automatically. Finance may override any decision.
            </p>
          </div>
        </CardHeader>
        <DataGrid
          columns={[
              {
                key: "id",
                header: "Sheet ID",
                sortAccessor: (s) => s.id,
                render: (s) => (
                  <span className="font-mono text-label-md font-medium text-primary">{s.id}</span>
                ),
              },
              {
                key: "agency",
                header: "Agency",
                sortAccessor: (s) => s.agencyName,
                render: (s) => s.agencyName,
              },
              {
                key: "employee",
                header: "Employee",
                sortAccessor: (s) => s.employeeName,
                render: (s) => (
                  <span className="text-on-surface-variant">{s.employeeName}</span>
                ),
              },
              {
                key: "amount",
                header: "Amount",
                align: "right" as const,
                sortAccessor: (s) => s.total,
                render: (s) => (
                  <span className="font-mono font-medium">
                    {formatCurrency(s.total, s.currency)}
                  </span>
                ),
              },
              {
                key: "confidence",
                header: "AI Confidence",
                sortAccessor: (s) => s.llmConfidence ?? 0,
                render: (s) => <ConfidenceBar value={s.llmConfidence} />,
              },
              {
                key: "policy",
                header: "Top Policy Reason",
                render: (s) =>
                  s.autoApprovalReasons && s.autoApprovalReasons.length > 0 ? (
                    <span
                      className="inline-block max-w-xs truncate text-body-sm text-on-surface-variant"
                      title={s.autoApprovalReasons.join(" · ")}
                    >
                      <Icon
                        name="check_circle"
                        className="mr-1 inline text-[13px] text-success-green"
                      />
                      {s.autoApprovalReasons[0]}
                      {s.autoApprovalReasons.length > 1 && (
                        <span className="ml-1 text-label-sm text-secondary">
                          +{s.autoApprovalReasons.length - 1} more
                        </span>
                      )}
                    </span>
                  ) : (
                    <span className="text-on-surface-variant">—</span>
                  ),
              },
              {
                key: "action",
                header: "",
                align: "right" as const,
                render: () => (
                  <Icon name="chevron_right" className="text-[18px] text-on-surface-variant" />
                ),
              },
            ]}
            rows={autoApproved}
            getRowId={(s) => s.id}
            pageSize={10}
            onRowClick={(s) => setSelectedId(s.id)}
            emptyMessage="No auto-approved sheets."
          />
        </Card>

      {/* Approved sheets — fully cleared, Finance can still audit/override */}
      <Card className="mt-3 overflow-hidden">
        <CardHeader className="flex-col items-stretch gap-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="flex items-center gap-2">
                <Icon name="task_alt" className="text-success-green" />
                Approved
              </CardTitle>
              <Badge className="bg-success-green/10 text-success-green" pill={false}>
                {approved.length}
              </Badge>
            </div>
            <p className="text-label-sm text-on-surface-variant">
              Fully approved sheets. Finance may still override.
            </p>
          </div>
        </CardHeader>
        <DataGrid
          columns={[
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
              key: "amount",
              header: "Amount",
              align: "right" as const,
              sortAccessor: (s) => s.total,
              render: (s) => <span className="font-mono font-medium">{formatCurrency(s.total, s.currency)}</span>,
            },
            {
              key: "decided_by",
              header: "Decided By",
              render: (s) => <span className="text-on-surface-variant">{s.financeDecidedBy ?? "—"}</span>,
            },
            {
              key: "action",
              header: "",
              align: "right" as const,
              render: () => <Icon name="chevron_right" className="text-[18px] text-on-surface-variant" />,
            },
          ]}
          rows={approved}
          getRowId={(s) => s.id}
          pageSize={10}
          onRowClick={(s) => setSelectedId(s.id)}
          emptyMessage="No approved sheets."
        />
      </Card>

      {/* Rejected sheets — Finance can reverse at any time */}
      <Card className="mt-3 overflow-hidden">
        <CardHeader className="flex-col items-stretch gap-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="flex items-center gap-2">
                <Icon name="cancel" className="text-error" />
                Rejected
              </CardTitle>
              <Badge className="bg-error-container text-error" pill={false}>
                {rejected.length}
              </Badge>
            </div>
            <p className="text-label-sm text-on-surface-variant">
              Rejected sheets. Finance may reverse the decision.
            </p>
          </div>
        </CardHeader>
        <DataGrid
          columns={[
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
              key: "amount",
              header: "Amount",
              align: "right" as const,
              sortAccessor: (s) => s.total,
              render: (s) => <span className="font-mono font-medium">{formatCurrency(s.total, s.currency)}</span>,
            },
            {
              key: "decided_by",
              header: "Decided By",
              render: (s) => <span className="text-on-surface-variant">{s.financeDecidedBy ?? "—"}</span>,
            },
            {
              key: "action",
              header: "",
              align: "right" as const,
              render: () => <Icon name="chevron_right" className="text-[18px] text-on-surface-variant" />,
            },
          ]}
          rows={rejected}
          getRowId={(s) => s.id}
          pageSize={10}
          onRowClick={(s) => setSelectedId(s.id)}
          emptyMessage="No rejected sheets."
        />
      </Card>

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
                <DrawerTitle className="mt-1">
                  {selected.status === "FINANCE_APPROVED"
                    ? "AI auto-approved — audit"
                    : selected.status === "APPROVED"
                    ? "Approved — override if needed"
                    : selected.status === "FINANCE_REJECTED" || selected.status === "REJECTED"
                    ? "Rejected — reverse if needed"
                    : "Manual review"}
                </DrawerTitle>
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
