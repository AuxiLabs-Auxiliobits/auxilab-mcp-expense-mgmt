"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  useApproveSheet,
  useCurrentUser,
  useLineItemAction,
  useManagerBulkApprove,
  useManagerQueue,
} from "@/data/hooks";
import { AGING_CLASS, agingLevel } from "@/lib/aging";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { formatCurrency, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ExpenseSheet, LineItem } from "@/data/types";

type PendingAction = { action: "reject" | "request_info"; item: LineItem } | null;

type SortKey = "oldest" | "newest" | "amount-high" | "amount-low";
type FilterKey = "all" | "aging" | "urgent";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "oldest", label: "Oldest first" },
  { key: "newest", label: "Newest first" },
  { key: "amount-high", label: "Amount: high → low" },
  { key: "amount-low", label: "Amount: low → high" },
];

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All pending" },
  { key: "aging", label: "Aging (2+ days)" },
  { key: "urgent", label: "Urgent (5+ days)" },
];

function QueueStat({
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
    <div className="flex items-center gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-3 shadow-xs">
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-container-high",
          tone,
        )}
      >
        <Icon name={icon} className="text-[18px]" />
      </span>
      <div className="min-w-0">
        <div className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
          {label}
        </div>
        <div className="text-headline-md font-semibold tabular-nums text-on-surface">{value}</div>
      </div>
    </div>
  );
}

export function ReviewQueue() {
  const { data: user } = useCurrentUser("manager");
  const agencyId = user?.agencyId ?? "";
  const { data: queue, isLoading } = useManagerQueue(agencyId);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const sheets = queue ?? [];
  useEffect(() => {
    if (sheets.length && (!selectedId || !sheets.some((s) => s.id === selectedId))) {
      setSelectedId(sheets[0].id);
    }
  }, [sheets, selectedId]);

  const selected = sheets.find((s) => s.id === selectedId) ?? null;

  const bulkApprove = useManagerBulkApprove();
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<SortKey>("oldest");
  const [filterBy, setFilterBy] = useState<FilterKey>("all");

  const visibleSheets = [...sheets]
    .filter((s) => {
      if (filterBy === "all") return true;
      const level = agingLevel(s.submittedAt).level;
      return filterBy === "urgent" ? level === "escalation" : level !== "ok";
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "newest":
          return agingLevel(a.submittedAt).hours - agingLevel(b.submittedAt).hours;
        case "amount-high":
          return b.total - a.total;
        case "amount-low":
          return a.total - b.total;
        default:
          return agingLevel(b.submittedAt).hours - agingLevel(a.submittedAt).hours;
      }
    });

  // Operational summary (SLA / aging).
  const agingCount = sheets.filter((s) => agingLevel(s.submittedAt).level !== "ok").length;
  const urgentCount = sheets.filter((s) => agingLevel(s.submittedAt).level === "escalation").length;
  const pendingValue = sheets.reduce((sum, s) => sum + s.total, 0);

  function toggleChecked(id: string) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runBulkApprove() {
    const ids = [...checkedIds];
    const actor = user ? { id: user.id, name: user.name } : undefined;
    const results = await bulkApprove.mutateAsync({ ids, actor });
    const routed = results.filter((s) => s.status === "FINANCE_MANUAL_REVIEW").length;
    toast.success(`Approved ${ids.length} sheet${ids.length === 1 ? "" : "s"}`, {
      description: routed
        ? `AI Finance Approver auto-cleared ${ids.length - routed}, routed ${routed} to Finance.`
        : "AI Finance Approver auto-cleared all of them.",
    });
    setCheckedIds(new Set());
  }

  return (
    <div className="flex flex-col gap-6 p-gutter md:p-margin-page lg:h-[calc(100vh-4rem)] lg:overflow-hidden">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-headline-md font-semibold tracking-tight text-on-surface">
            Review Queue
          </h2>
          <div className="mt-1 flex items-center gap-2">
            <span className="rounded border border-outline-variant bg-surface-container-highest px-2 py-0.5 font-mono text-label-md text-on-surface-variant">
              AGENCY: {user?.agencyId.replace("AGY-", "") ?? "—"}
            </span>
            <span className="text-body-sm text-on-surface-variant">
              {sheets.length} sheet{sheets.length === 1 ? "" : "s"} pending approval
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Icon name="filter_list" /> Filter
                {filterBy !== "all" && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Filter</DropdownMenuLabel>
              {FILTERS.map((f) => (
                <DropdownMenuItem key={f.key} onSelect={() => setFilterBy(f.key)}>
                  {f.label}
                  {filterBy === f.key && (
                    <Icon name="check" className="ml-auto text-[16px] text-secondary" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Icon name="sort" /> Sort
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Sort by</DropdownMenuLabel>
              {SORTS.map((s) => (
                <DropdownMenuItem key={s.key} onSelect={() => setSortBy(s.key)}>
                  {s.label}
                  {sortBy === s.key && (
                    <Icon name="check" className="ml-auto text-[16px] text-secondary" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Operational summary — pending volume + aging SLA */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <QueueStat label="Pending Approval" value={String(sheets.length)} icon="pending_actions" tone="text-secondary" />
        <QueueStat label="Aging · 2+ days" value={String(agingCount)} icon="hourglass_bottom" tone="text-yellow-600" />
        <QueueStat label="Urgent · 5+ days" value={String(urgentCount)} icon="priority_high" tone="text-error" />
        <QueueStat label="Total Pending" value={formatCurrency(pendingValue)} icon="payments" tone="text-on-surface-variant" />
      </div>

      {/* Master-detail */}
      <div className="flex flex-1 flex-col gap-6 lg:flex-row lg:overflow-hidden">
        {/* Master list */}
        <div className="flex w-full flex-col overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest lg:h-full lg:w-1/3">
          <div className="flex items-center justify-between border-b border-outline-variant bg-surface-bright p-3">
            <h3 className="text-body-lg font-semibold text-on-surface">Pending Sheets</h3>
            <Badge className="bg-error-container text-error" pill={false}>
              Needs Action
            </Badge>
          </div>
          {checkedIds.size > 0 && (
            <div className="flex items-center justify-between gap-2 border-b border-outline-variant bg-secondary-container/40 px-3 py-2">
              <span className="text-body-sm font-medium text-on-surface">
                {checkedIds.size} selected
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setCheckedIds(new Set())}>
                  Clear
                </Button>
                <Button size="sm" onClick={runBulkApprove} disabled={bulkApprove.isPending}>
                  <Icon name="done_all" /> Approve {checkedIds.size}
                </Button>
              </div>
            </div>
          )}
          <div className="max-h-[55vh] flex-1 space-y-2 overflow-y-auto p-2 lg:max-h-none">
            {isLoading ? (
              [0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded" />)
            ) : visibleSheets.length === 0 ? (
              <EmptyState
                icon={filterBy === "all" ? "task_alt" : "filter_alt_off"}
                title={filterBy === "all" ? "Queue clear" : "No matches"}
                description={
                  filterBy === "all"
                    ? "No sheets awaiting your review."
                    : "No sheets match this filter — try widening it."
                }
              />
            ) : (
              visibleSheets.map((sheet) => (
                <SheetListItem
                  key={sheet.id}
                  sheet={sheet}
                  active={sheet.id === selectedId}
                  checked={checkedIds.has(sheet.id)}
                  onToggle={() => toggleChecked(sheet.id)}
                  onSelect={() => setSelectedId(sheet.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Detail */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest lg:h-full">
          {selected ? (
            <SheetDetail sheet={selected} />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState icon="fact_check" title="Select a sheet" description="Choose a pending sheet to review its line items." />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SheetListItem({
  sheet,
  active,
  checked,
  onToggle,
  onSelect,
}: {
  sheet: ExpenseSheet;
  active: boolean;
  checked: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  const aging = agingLevel(sheet.submittedAt);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      className={cn(
        "relative cursor-pointer overflow-hidden rounded border p-3 transition-all duration-200 ease-smooth",
        active
          ? "border-secondary bg-surface-container-low shadow-sm"
          : "border-outline-variant hover:-translate-y-0.5 hover:border-secondary hover:bg-surface-container-low hover:shadow-elevation-2",
      )}
    >
      {active && <span className="absolute left-0 top-0 h-full w-1 bg-secondary" />}
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={checked}
            onClick={(e) => e.stopPropagation()}
            onChange={onToggle}
            className="h-4 w-4 rounded border-outline-variant text-secondary focus:ring-secondary"
            aria-label={`Select ${sheet.id}`}
          />
          <span className="font-mono text-label-md text-on-surface-variant">{sheet.id}</span>
        </div>
        <span className="text-body-sm font-semibold text-on-surface">
          {formatCurrency(sheet.total, sheet.currency)}
        </span>
      </div>
      <div className="mb-1 text-body-md font-semibold text-on-surface">{sheet.title}</div>
      <div className="flex items-center justify-between text-on-surface-variant">
        <span className="text-body-sm">{sheet.employeeName}</span>
        <span className="text-label-sm">
          {sheet.submittedAt ? formatRelative(sheet.submittedAt) : ""}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between border-t border-outline-variant/30 pt-2">
        <span className="flex items-center gap-2">
          <Icon name="pending_actions" className="text-[14px] text-error" />
          <span className="text-label-sm text-on-surface-variant">{sheet.lineItems.length} Items</span>
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold",
            AGING_CLASS[aging.level],
          )}
          title={`Aging: ${aging.label}`}
        >
          <Icon name={aging.level === "escalation" ? "priority_high" : "schedule"} className="text-[12px]" />
          {aging.label}
        </span>
      </div>
    </div>
  );
}

function SheetDetail({ sheet }: { sheet: ExpenseSheet }) {
  const { data: user } = useCurrentUser("manager");
  const lineItemAction = useLineItemAction();
  const approveSheet = useApproveSheet();
  const [pending, setPending] = useState<PendingAction>(null);
  const [reason, setReason] = useState("");

  const approvedCount = sheet.lineItems.filter((l) => l.managerStatus === "MANAGER_APPROVED").length;
  const total = sheet.lineItems.length;
  const allApproved = total > 0 && approvedCount === total;
  const progress = total ? Math.round((approvedCount / total) * 100) : 0;

  // SoD: a manager cannot action their own line items (SCOPING.md §3.3).
  const isOwnSheet = !!user && sheet.employeeId === user.id;

  const actor = user ? { id: user.id, name: user.name } : undefined;

  async function approve(item: LineItem) {
    await lineItemAction.mutateAsync({ sheetId: sheet.id, lineItemId: item.id, action: "approve", actor });
    toast.success(`Approved · ${item.merchant}`);
  }

  async function confirmPending() {
    if (!pending) return;
    await lineItemAction.mutateAsync({
      sheetId: sheet.id,
      lineItemId: pending.item.id,
      action: pending.action,
      reason,
      actor,
    });
    toast(pending.action === "reject" ? "Line item rejected" : "Information requested", {
      description: `${pending.item.merchant} — returned to employee.`,
    });
    setPending(null);
    setReason("");
  }

  async function approveEntireSheet() {
    const updated = await approveSheet.mutateAsync({ sheetId: sheet.id, actor });
    if (updated.status === "FINANCE_MANUAL_REVIEW") {
      toast.warning(`${sheet.id} routed to Finance for manual review`, {
        description: updated.routeReasonDetail,
      });
    } else if (updated.status === "FINANCE_APPROVED") {
      toast.success(`${sheet.id} auto-approved by the AI Finance Approver`, {
        description: `Confidence ${Math.round((updated.llmConfidence ?? 0) * 100)}%.`,
      });
    } else {
      toast.success(`${sheet.id} sent to Finance`);
    }
  }

  return (
    <>
      {/* Detail header */}
      <div className="border-b border-outline-variant bg-surface-bright p-4">
        <div className="mb-2 flex items-start justify-between">
          <div>
            <h3 className="text-headline-md text-on-surface">{sheet.title}</h3>
            <div className="mt-1 flex items-center gap-3">
              <span className="font-mono text-label-md text-on-surface-variant">{sheet.id}</span>
              <span className="text-outline-variant">|</span>
              <span className="text-body-sm text-on-surface-variant">
                Submitted by {sheet.employeeName}
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-headline-md text-on-surface">
              {formatCurrency(sheet.total, sheet.currency)}
            </div>
            <span className="inline-block rounded-full bg-error-container px-2 py-0.5 text-[11px] font-semibold text-error">
              Pending Review
            </span>
          </div>
        </div>

        {isOwnSheet && (
          <div className="mb-3 flex items-center gap-2 rounded border border-error/20 bg-error-container/50 p-2 text-body-sm text-on-error-container">
            <Icon name="block" className="text-[16px]" />
            Segregation of duties: you can&apos;t action your own line items.
          </div>
        )}

        {/* Progress */}
        <div className="rounded border border-outline-variant bg-surface-container p-3">
          <div className="mb-2 flex items-end justify-between">
            <span className="text-body-sm font-semibold text-on-surface">Review Progress</span>
            <span className="font-mono text-label-md text-on-surface-variant">
              {approvedCount}/{total} Items Approved
            </span>
          </div>
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-variant">
            <div className="h-2 bg-success-green transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>

      {/* Line items */}
      <div className="flex-1 space-y-3 overflow-y-auto bg-background p-4">
        {sheet.lineItems.map((item) => (
          <LineItemReviewCard
            key={item.id}
            item={item}
            disabled={isOwnSheet || lineItemAction.isPending}
            onApprove={() => approve(item)}
            onReject={() => setPending({ action: "reject", item })}
            onRequestInfo={() => setPending({ action: "request_info", item })}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex justify-end gap-3 border-t border-outline-variant bg-surface-bright p-4">
        <Button variant="outline">Return to Queue</Button>
        <Button
          disabled={!allApproved || isOwnSheet || approveSheet.isPending}
          onClick={approveEntireSheet}
          title={allApproved ? undefined : "Complete line item reviews first"}
        >
          <Icon name="done_all" /> Approve Entire Sheet
        </Button>
      </div>

      {/* Reason dialog */}
      <Dialog
        open={!!pending}
        onOpenChange={(open) => {
          if (!open) {
            setPending(null);
            setReason("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pending?.action === "reject" ? "Reject line item" : "Request information"}
            </DialogTitle>
            <DialogDescription>
              {pending?.item.merchant} · {pending && formatCurrency(pending.item.amount)} — this
              returns the whole sheet to the employee and is recorded in the audit log.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            autoFocus
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (recorded with your identity and timestamp)…"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button
              variant={pending?.action === "reject" ? "destructive" : "default"}
              disabled={reason.trim().length < 3 || lineItemAction.isPending}
              onClick={confirmPending}
            >
              {pending?.action === "reject" ? "Reject" : "Request Info"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function LineItemReviewCard({
  item,
  disabled,
  onApprove,
  onReject,
  onRequestInfo,
}: {
  item: LineItem;
  disabled: boolean;
  onApprove: () => void;
  onReject: () => void;
  onRequestInfo: () => void;
}) {
  const status = item.managerStatus;
  const approved = status === "MANAGER_APPROVED";
  const rejected = status === "MANAGER_REJECTED";
  const info = status === "INFO_REQUESTED";
  const actionable = status === "PENDING_MANAGER";

  const stateIcon = approved
    ? { name: "check_circle", cls: "text-success-green bg-success-green/10" }
    : rejected
      ? { name: "cancel", cls: "text-error bg-error-container" }
      : info
        ? { name: "help", cls: "text-yellow-600 bg-yellow-500/10" }
        : { name: "radio_button_unchecked", cls: "text-on-surface-variant bg-surface-container" };

  return (
    <div
      className={cn(
        "relative flex items-start gap-4 overflow-hidden rounded border bg-surface-container-lowest p-3 shadow-sm",
        approved ? "border-success-green/30" : actionable ? "border-secondary" : "border-outline-variant",
      )}
    >
      {actionable && <span className="absolute left-0 top-0 h-full w-1 bg-secondary" />}
      <div className="mt-1">
        <span className={cn("material-symbols-outlined rounded-full p-1", stateIcon.cls)}>
          {stateIcon.name}
        </span>
      </div>
      <div className="flex-1">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-body-md font-semibold text-on-surface">{item.description}</div>
            <div className="mt-0.5 font-mono text-label-md text-on-surface-variant">
              CAT: {item.category}
            </div>
          </div>
          <div className="text-body-md font-semibold text-on-surface">
            {formatCurrency(item.amount, item.currency)}
          </div>
        </div>

        {approved && (
          <div className="mt-2 flex items-center text-body-sm text-success-green">
            <Icon name="done_all" className="mr-1 text-[16px]" /> Approved by manager
          </div>
        )}

        {item.aiFlag && actionable && (
          <div className="mb-3 mt-2 flex items-start gap-2 rounded border border-error/20 bg-error-container p-2">
            <Icon name="warning" className="mt-0.5 text-[16px] text-error" />
            <p className="text-body-sm text-on-surface-variant">
              {item.aiFlag.message}{" "}
              <span className="inline-flex items-center text-secondary">
                <Icon name="link" className="mx-0.5 text-[14px]" />
                {item.aiFlag.clauseRef}
              </span>
              .
            </p>
          </div>
        )}

        {actionable && (
          <div className="mt-3 flex justify-end gap-2 border-t border-outline-variant/30 pt-3">
            <Button variant="outline" size="sm" disabled={disabled} onClick={onRequestInfo}>
              <Icon name="info" /> Request Info
            </Button>
            <Button variant="destructive" size="sm" disabled={disabled} onClick={onReject}>
              <Icon name="close" /> Reject
            </Button>
            <Button variant="secondary" size="sm" disabled={disabled} onClick={onApprove}>
              <Icon name="check" /> Approve
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
