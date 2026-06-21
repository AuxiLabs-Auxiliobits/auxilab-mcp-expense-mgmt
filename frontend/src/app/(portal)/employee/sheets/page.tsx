"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useCurrentUser, useEmployeeSheets } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { DataGrid, type Column } from "@/components/shared/data-grid";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { SHEET_STATUS_META, CATEGORY_ICON } from "@/lib/status";
import { formatCurrency, formatDate } from "@/lib/format";
import { downloadCsv } from "@/lib/csv";
import { cn } from "@/lib/utils";
import type { ExpenseSheet, SheetStatus } from "@/data/types";

const FILTERS: { key: string; label: string; match: (s: ExpenseSheet) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "draft", label: "Drafts", match: (s) => s.status === "DRAFT" },
  {
    key: "review",
    label: "In Review",
    match: (s) =>
      (["SUBMITTED", "IN_MANAGER_REVIEW", "IN_FINANCE_REVIEW", "FINANCE_MANUAL_REVIEW"] as SheetStatus[]).includes(s.status),
  },
  { key: "returned", label: "Needs Action", match: (s) => s.status === "RETURNED_TO_EMPLOYEE" },
  {
    key: "approved",
    label: "Approved",
    match: (s) => (["APPROVED", "FINANCE_APPROVED", "PAID"] as SheetStatus[]).includes(s.status),
  },
  {
    key: "rejected",
    label: "Rejected",
    match: (s) => (["REJECTED", "FINANCE_REJECTED", "WITHDRAWN"] as SheetStatus[]).includes(s.status),
  },
];

function Stat({ label, value, icon, tone }: { label: string; value: string; icon: string; tone?: string }) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-surface-container-high", tone)}>
        <Icon name={icon} className="text-[20px]" />
      </span>
      <div>
        <div className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">{label}</div>
        <div className="text-headline-md font-semibold text-on-surface">{value}</div>
      </div>
    </Card>
  );
}

export default function EmployeeSheetsPage() {
  const { data: user } = useCurrentUser("employee");
  const { data: sheets, isLoading } = useEmployeeSheets(user?.id ?? "");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState<ExpenseSheet | null>(null);

  const all = useMemo(() => sheets ?? [], [sheets]);
  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.key, all.filter(f.match).length])),
    [all],
  );
  const rows = useMemo(() => {
    const active = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
    const q = query.trim().toLowerCase();
    return all
      .filter(active.match)
      .filter((s) => !q || s.title.toLowerCase().includes(q) || s.id.toLowerCase().includes(q));
  }, [all, filter, query]);

  const reimbursed = all
    .filter((s) => (["APPROVED", "FINANCE_APPROVED", "PAID"] as SheetStatus[]).includes(s.status))
    .reduce((sum, s) => sum + s.total, 0);

  const columns: Column<ExpenseSheet>[] = [
    {
      key: "id",
      header: "Sheet ID",
      width: "140px",
      sortAccessor: (s) => s.id,
      render: (s) => <span className="font-mono text-label-md font-medium text-primary">{s.id}</span>,
    },
    {
      key: "title",
      header: "Title",
      sortAccessor: (s) => s.title.toLowerCase(),
      render: (s) => (
        <div>
          <div className="font-medium text-on-surface">{s.title}</div>
          <div className="font-mono text-label-sm text-on-surface-variant">
            {s.lineItems.length} line item{s.lineItems.length === 1 ? "" : "s"} · v{s.version}
          </div>
        </div>
      ),
    },
    { key: "period", header: "Period", render: (s) => s.period },
    {
      key: "status",
      header: "Status",
      sortAccessor: (s) => s.status,
      render: (s) => <StatusBadge meta={SHEET_STATUS_META[s.status]} className="rounded" />,
    },
    {
      key: "total",
      header: "Total",
      align: "right",
      sortAccessor: (s) => s.total,
      render: (s) => <span className="font-mono font-medium">{formatCurrency(s.total, s.currency)}</span>,
    },
  ];

  return (
    <PageContainer>
      <PageHeader title="My Expense Sheets" description="Every sheet you've created, across all versions." tone="primary">
        <Button asChild>
          <Link href="/employee/sheets/new">
            <Icon name="add" /> New Sheet
          </Link>
        </Button>
      </PageHeader>

      {/* Summary */}
      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Total Sheets" value={String(all.length)} icon="description" tone="text-secondary" />
        <Stat label="In Review" value={String(counts.review ?? 0)} icon="hourglass_empty" tone="text-yellow-600" />
        <Stat label="Needs Action" value={String(counts.returned ?? 0)} icon="error" tone="text-error" />
        <Stat label="Reimbursed" value={formatCurrency(reimbursed)} icon="payments" tone="text-success-green" />
      </div>

      {/* Toolbar */}
      <div className="mt-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-body-sm transition-all duration-200",
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
        <div className="relative lg:w-64">
          <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title or ID…"
            className="pl-9"
            aria-label="Search expense sheets"
          />
        </div>
      </div>

      <Card className="mt-4 overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : (
          <DataGrid
            columns={columns}
            rows={rows}
            getRowId={(s) => s.id}
            pageSize={10}
            columnManagement
            selectable
            bulkActions={(selected, clear) => (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  downloadCsv(
                    "my-expense-sheets.csv",
                    selected.map((s) => ({
                      id: s.id,
                      title: s.title,
                      period: s.period,
                      version: s.version,
                      status: s.status,
                      total: s.total,
                      currency: s.currency,
                    })),
                  );
                  clear();
                }}
              >
                <Icon name="download" /> Export {selected.length}
              </Button>
            )}
            onRowClick={(s) => setPreview(s)}
            emptyMessage={
              query || filter !== "all"
                ? "No sheets match your filters."
                : "No expense sheets yet — create your first one."
            }
          />
        )}
      </Card>

      {/* Split-view preview drawer */}
      <Drawer open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DrawerContent className="max-w-lg">
          {preview && (
            <>
              <DrawerHeader>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-label-md font-medium text-primary">{preview.id}</span>
                  <StatusBadge meta={SHEET_STATUS_META[preview.status]} className="rounded" />
                </div>
                <DrawerTitle className="mt-1">{preview.title}</DrawerTitle>
              </DrawerHeader>
              <DrawerBody className="space-y-5">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="font-mono text-label-md uppercase tracking-wider text-on-surface-variant">
                      Period
                    </div>
                    <div className="mt-0.5 text-body-sm text-on-surface">{preview.period}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-label-md uppercase tracking-wider text-on-surface-variant">
                      Total
                    </div>
                    <div className="mt-0.5 font-mono text-body-md font-semibold text-on-surface">
                      {formatCurrency(preview.total, preview.currency)}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-2 font-mono text-label-md uppercase tracking-wider text-on-surface-variant">
                    {preview.lineItems.length} line item{preview.lineItems.length === 1 ? "" : "s"}
                  </div>
                  <ul className="divide-y divide-outline-variant rounded-lg border border-outline-variant">
                    {preview.lineItems.map((li) => (
                      <li key={li.id} className="flex items-center gap-3 px-3 py-2.5">
                        <Icon
                          name={CATEGORY_ICON[li.category] ?? "category"}
                          className="shrink-0 text-[18px] text-on-surface-variant"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-body-sm font-medium text-on-surface">
                            {li.merchant}
                          </div>
                          <div className="truncate font-mono text-label-sm text-on-surface-variant">
                            {li.category} · {formatDate(li.expenseDate)}
                          </div>
                        </div>
                        {li.attachments.length === 0 && (
                          <Icon name="receipt_long" className="shrink-0 text-[16px] text-error" />
                        )}
                        <span className="shrink-0 font-mono text-body-sm font-medium text-on-surface">
                          {formatCurrency(li.amount, li.currency)}
                        </span>
                      </li>
                    ))}
                    {preview.lineItems.length === 0 && (
                      <li className="px-3 py-4 text-center text-body-sm text-on-surface-variant">
                        No line items yet.
                      </li>
                    )}
                  </ul>
                </div>
              </DrawerBody>
              <DrawerFooter>
                <Button variant="outline" onClick={() => setPreview(null)}>
                  Close
                </Button>
                <Button asChild>
                  <Link href={`/employee/sheets/${preview.id}`}>
                    <Icon name="open_in_new" /> Open full sheet
                  </Link>
                </Button>
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </PageContainer>
  );
}
