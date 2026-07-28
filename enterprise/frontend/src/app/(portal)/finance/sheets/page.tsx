"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAllSheets } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { DataGrid, type Column } from "@/components/shared/data-grid";
import { SavedViewsMenu } from "@/components/shared/saved-views";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FINANCE_DECISION_META, SHEET_STATUS_META } from "@/lib/status";
import { formatCurrency } from "@/lib/format";
import { downloadCsv } from "@/lib/csv";
import { cn } from "@/lib/utils";
import type { ExpenseSheet, SheetStatus } from "@/data/types";

const REVIEW_STATUSES: SheetStatus[] = [
  "SUBMITTED",
  "IN_MANAGER_REVIEW",
  "IN_FINANCE_REVIEW",
  "FINANCE_MANUAL_REVIEW",
];
const APPROVED_STATUSES: SheetStatus[] = ["APPROVED", "FINANCE_APPROVED", "PAID"];
const REJECTED_STATUSES: SheetStatus[] = ["REJECTED", "FINANCE_REJECTED", "WITHDRAWN"];

const FILTERS: { key: string; label: string; match: (s: ExpenseSheet) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "finance", label: "In Finance Review", match: (s) => s.status === "IN_FINANCE_REVIEW" },
  { key: "manual", label: "Manual Review", match: (s) => s.status === "FINANCE_MANUAL_REVIEW" },
  { key: "review", label: "In Review", match: (s) => REVIEW_STATUSES.includes(s.status) },
  { key: "approved", label: "Approved", match: (s) => APPROVED_STATUSES.includes(s.status) },
  { key: "rejected", label: "Rejected", match: (s) => REJECTED_STATUSES.includes(s.status) },
];

function Stat({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: string;
  icon: string;
  tone?: string;
}) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-surface-container-high", tone)}>
        <Icon name={icon} className="text-[20px]" />
      </span>
      <div className="min-w-0">
        <div className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">{label}</div>
        <div className="text-headline-md font-semibold text-on-surface">{value}</div>
      </div>
    </Card>
  );
}

export default function FinanceSheetsPage() {
  const router = useRouter();
  const { data: sheets, isLoading } = useAllSheets();

  const [filter, setFilter] = useState("all");
  const [agency, setAgency] = useState("all");
  const [query, setQuery] = useState("");

  const all = useMemo(() => sheets ?? [], [sheets]);

  const agencies = useMemo(
    () => Array.from(new Set(all.map((s) => s.agencyName))).sort((a, b) => a.localeCompare(b)),
    [all],
  );

  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.key, all.filter(f.match).length])),
    [all],
  );

  const rows = useMemo(() => {
    const active = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
    const q = query.trim().toLowerCase();
    return all
      .filter(active.match)
      .filter((s) => agency === "all" || s.agencyName === agency)
      .filter(
        (s) =>
          !q ||
          s.title.toLowerCase().includes(q) ||
          s.employeeName.toLowerCase().includes(q) ||
          s.id.toLowerCase().includes(q),
      );
  }, [all, filter, agency, query]);

  const manualReview = useMemo(
    () => all.filter((s) => s.status === "FINANCE_MANUAL_REVIEW").length,
    [all],
  );
  const approvedValue = useMemo(
    () =>
      all
        .filter((s) => APPROVED_STATUSES.includes(s.status))
        .reduce((sum, s) => sum + s.total, 0),
    [all],
  );
  const totalValue = useMemo(() => all.reduce((sum, s) => sum + s.total, 0), [all]);

  const columns: Column<ExpenseSheet>[] = [
    {
      key: "id",
      header: "Sheet ID",
      width: "130px",
      sortAccessor: (s) => s.id,
      render: (s) => <span className="font-mono text-label-md font-medium text-primary">{s.id}</span>,
    },
    {
      key: "employee",
      header: "Employee",
      sortAccessor: (s) => s.employeeName.toLowerCase(),
      render: (s) => (
        <div className="min-w-0">
          <div className="truncate font-medium text-on-surface">{s.employeeName}</div>
          <div className="truncate font-mono text-label-sm text-on-surface-variant">{s.title}</div>
        </div>
      ),
    },
    {
      key: "agency",
      header: "Agency",
      sortAccessor: (s) => s.agencyName.toLowerCase(),
      render: (s) => <span className="text-on-surface-variant">{s.agencyName}</span>,
    },
    {
      key: "status",
      header: "Status",
      sortAccessor: (s) => s.status,
      render: (s) => <StatusBadge meta={SHEET_STATUS_META[s.status]} className="rounded" />,
    },
    {
      key: "decision",
      header: "Finance Decision",
      render: (s) =>
        s.financeDecision ? (
          <StatusBadge meta={FINANCE_DECISION_META[s.financeDecision]} className="rounded" />
        ) : (
          <span className="text-on-surface-variant">—</span>
        ),
    },
    {
      key: "total",
      header: "Total",
      align: "right",
      sortAccessor: (s) => s.total,
      render: (s) => <span className="font-mono font-medium">{formatCurrency(s.total, s.currency)}</span>,
    },
  ];

  function toCsv(list: ExpenseSheet[]) {
    downloadCsv(
      "expense-sheets.csv",
      list.map((s) => ({
        id: s.id,
        title: s.title,
        employee: s.employeeName,
        agency: s.agencyName,
        period: s.period,
        version: s.version,
        status: s.status,
        finance_decision: s.financeDecision ?? "",
        total: s.total,
        currency: s.currency,
      })),
    );
  }
  const exportCsv = () => toCsv(rows);

  return (
    <PageContainer>
      <PageHeader
        title="Expense Sheets"
        description="Org-wide view of every sheet across agencies."
        tone="primary"
        size="xl"
      >
        <Button variant="outline" onClick={exportCsv} disabled={rows.length === 0}>
          <Icon name="download" /> Export CSV
          {rows.length > 0 && rows.length !== all.length ? (
            <span className="ml-1 font-mono text-label-sm text-on-surface-variant">({rows.length})</span>
          ) : null}
        </Button>
      </PageHeader>

      {/* Summary */}
      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Total Sheets" value={String(all.length)} icon="description" tone="text-secondary" />
        <Stat label="Manual Review" value={String(manualReview)} icon="gavel" tone="text-yellow-600" />
        <Stat label="Approved Value" value={formatCurrency(approvedValue)} icon="payments" tone="text-success-green" />
        <Stat label="Total Value" value={formatCurrency(totalValue)} icon="account_balance" tone="text-secondary" />
      </div>

      {/* Toolbar */}
      <div className="mt-6 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              aria-pressed={filter === f.key}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-body-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
                filter === f.key
                  ? "border-primary bg-primary text-on-primary shadow-xs"
                  : "border-outline-variant text-on-surface-variant hover:border-secondary hover:text-secondary",
              )}
            >
              {f.label}
              <span
                className={cn(
                  "rounded-full px-1.5 font-mono text-label-sm",
                  filter === f.key ? "bg-on-primary/20" : "bg-surface-container-high",
                )}
              >
                {counts[f.key] ?? 0}
              </span>
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="sm:w-56">
            <Select value={agency} onValueChange={setAgency}>
              <SelectTrigger aria-label="Filter by agency">
                <span className="flex items-center gap-2 truncate">
                  <Icon name="apartment" className="text-[18px] text-on-surface-variant" />
                  <SelectValue placeholder="All agencies" />
                </span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All agencies</SelectItem>
                {agencies.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="relative sm:ml-auto sm:w-72">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search title, employee, or ID…"
              className="pl-9"
              aria-label="Search expense sheets"
            />
          </div>
          <SavedViewsMenu
            storageKey="finance-sheets-views"
            current={{ filter, agency, query }}
            onApply={(v) => {
              setFilter(v.filter);
              setAgency(v.agency);
              setQuery(v.query);
            }}
          />
        </div>
      </div>

      <Card className="mt-4 overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : (
          <DataGrid
            columns={columns}
            rows={rows}
            getRowId={(s) => s.id}
            pageSize={12}
            columnManagement
            selectable
            bulkActions={(selected, clear) => (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  toCsv(selected);
                  clear();
                }}
              >
                <Icon name="download" /> Export {selected.length}
              </Button>
            )}
            onRowClick={(s) => router.push(`/employee/sheets/${s.id}`)}
            emptyMessage={
              query || filter !== "all" || agency !== "all"
                ? "No sheets match your filters."
                : "No expense sheets."
            }
          />
        )}
      </Card>
    </PageContainer>
  );
}
