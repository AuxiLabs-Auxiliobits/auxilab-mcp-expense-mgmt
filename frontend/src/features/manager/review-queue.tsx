"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  useAllSheets,
  useApproveSheet,
  useCurrentUser,
  useLineItemAction,
  useManagerBulkApprove,
  useManagerQueue,
} from "@/data/hooks";
import { AGING_CLASS, agingLevel } from "@/lib/aging";
import { SHEET_STATUS_META } from "@/lib/status";
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
import { ReceiptViewer } from "@/components/shared/receipt-viewer";
import { ReceiptScanDetails } from "@/components/shared/receipt-scan-details";
import { SheetTimeline } from "@/components/shared/sheet-timeline";
import { formatCurrency, formatDate, formatDateTimeIST, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ExpenseSheet, LineItem, SheetStatus } from "@/data/types";

type PendingAction = { action: "reject" | "request_info"; item: LineItem } | null;

type SortKey = "oldest" | "newest" | "amount-high" | "amount-low";
type FilterKey = "all" | "aging" | "urgent";
type QueueView = "pending" | "reviewed";

/** Statuses a sheet lands in *after* the manager has acted on it (SCOPING §6.2). */
const REVIEWED_STATUSES = new Set<SheetStatus>([
  "RETURNED_TO_EMPLOYEE", // manager rejected a line item / requested info → back to employee
  "IN_FINANCE_REVIEW",
  "FINANCE_MANUAL_REVIEW",
  "FINANCE_APPROVED",
  "FINANCE_REJECTED",
  "APPROVED",
  "REJECTED",
  "PAID",
]);

/** The manager's own outcome on a reviewed sheet: returned = rejected/info, else approved. */
function managerOutcome(status: SheetStatus): { label: string; tone: string; icon: string } {
  return status === "RETURNED_TO_EMPLOYEE"
    ? { label: "Returned", tone: "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20", icon: "undo" }
    : { label: "Approved", tone: "bg-success-green/10 text-success-green border border-success-green/20", icon: "check_circle" };
}

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
  const { data: queue, isLoading, refetch, isFetching } = useManagerQueue(agencyId);
  const [view, setView] = useState<QueueView>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // True after the user explicitly returns to the queue, so the auto-select effect
  // below doesn't immediately re-open the first sheet (that defeated "Return to Queue").
  const [manualClear, setManualClear] = useState(false);

  const sheets = useMemo(() => queue ?? [], [queue]);

  const bulkApprove = useManagerBulkApprove();
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<SortKey>("oldest");
  const [filterBy, setFilterBy] = useState<FilterKey>("all");

  const isReviewed = view === "reviewed";

  // "Reviewed" history = sheets *I personally* decided. `managerDecidedBy` is stamped
  // server-side the moment a sheet leaves manager review (advanced to finance or returned to
  // the employee), so this is exact even when several managers share an agency — and unbounded
  // (no audit-window limit). The agency sheet list is agency-scoped server-side; fetched only
  // when the tab is open.
  const { data: allSheets, refetch: refetchReviewed, isFetching: reviewedFetching } =
    useAllSheets(isReviewed);
  const reviewedSheets = useMemo(
    () =>
      [...(allSheets ?? [])]
        .filter(
          (s) =>
            s.agencyId === agencyId &&
            REVIEWED_STATUSES.has(s.status) &&
            !!user &&
            s.managerDecidedBy === user.id,
        )
        .sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt)),
    [allSheets, agencyId, user],
  );

  const reviewedLoading = reviewedFetching && reviewedSheets.length === 0;

  const selectSheet = (id: string) => {
    setManualClear(false);
    setSelectedId(id);
  };
  const returnToQueue = () => {
    setManualClear(true);
    setSelectedId(null);
  };
  const switchView = (next: QueueView) => {
    setView(next);
    setManualClear(true); // don't auto-open the first sheet after a tab switch
    setSelectedId(null);
    setCheckedIds(new Set());
  };

  // Auto-select the first pending sheet (only in the live queue, never in history).
  useEffect(() => {
    if (manualClear || isReviewed) return;
    if (sheets.length && (!selectedId || !sheets.some((s) => s.id === selectedId))) {
      setSelectedId(sheets[0].id);
    }
  }, [sheets, selectedId, manualClear, isReviewed]);

  const activeList = isReviewed ? reviewedSheets : sheets;
  const selected = activeList.find((s) => s.id === selectedId) ?? null;

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
    const { approved, failed } = await bulkApprove.mutateAsync({ ids, actor });
    const routed = approved.filter((s) => s.status === "FINANCE_MANUAL_REVIEW").length;
    const cleared = approved.length - routed;
    const detail = routed
      ? `AI Finance Approver auto-cleared ${cleared}, routed ${routed} to Finance.`
      : "AI Finance Approver auto-cleared all of them.";

    if (failed.length) {
      // Some sheets went through, some didn't — report both rather than failing the lot.
      // Drop the approved ones from the selection so a retry only re-runs the failures.
      setCheckedIds(new Set(failed));
      if (approved.length) {
        toast.warning(
          `Approved ${approved.length} of ${ids.length} sheets — ${failed.length} failed.`,
          { description: `${detail} The failed sheet${failed.length === 1 ? " is" : "s are"} still selected — try again.` },
        );
      } else {
        toast.error(`Couldn't approve ${failed.length} sheet${failed.length === 1 ? "" : "s"}. Please try again.`);
      }
      return;
    }

    toast.success(`Approved ${approved.length} sheet${approved.length === 1 ? "" : "s"}`, {
      description: detail,
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
              AGENCY: {user?.agencyName || user?.agencyId?.replace("AGY-", "") || "—"}
            </span>
            <span className="text-body-sm text-on-surface-variant">
              {isReviewed
                ? `${reviewedSheets.length} sheet${reviewedSheets.length === 1 ? "" : "s"} you've reviewed`
                : `${sheets.length} sheet${sheets.length === 1 ? "" : "s"} pending approval`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Pending ↔ Reviewed history toggle */}
          <div className="flex rounded-md border border-outline-variant bg-surface-container-low p-0.5">
            {(["pending", "reviewed"] as const).map((v) => (
              <button
                key={v}
                onClick={() => switchView(v)}
                className={cn(
                  "rounded px-3 py-1 text-label-md font-medium capitalize transition-colors",
                  view === v
                    ? "bg-surface-bright text-on-surface shadow-xs"
                    : "text-on-surface-variant hover:text-on-surface",
                )}
              >
                {v}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => (isReviewed ? refetchReviewed() : refetch())}
            loading={isReviewed ? reviewedFetching : isFetching}
            title={
              isReviewed
                ? "Refresh your review history"
                : "Pull in newly submitted sheets without reloading"
            }
          >
            <Icon name="refresh" /> Refresh
          </Button>
          {!isReviewed && (
          <>
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
          </>
          )}
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
            <h3 className="text-body-lg font-semibold text-on-surface">
              {isReviewed ? "Reviewed Sheets" : "Pending Sheets"}
            </h3>
            <Badge
              className={isReviewed ? "bg-surface-container-highest text-on-surface-variant" : "bg-error-container text-error"}
              pill={false}
            >
              {isReviewed ? "History" : "Needs Action"}
            </Badge>
          </div>
          {!isReviewed && checkedIds.size > 0 && (
            <div className="flex items-center justify-between gap-2 border-b border-outline-variant bg-secondary-container/40 px-3 py-2">
              <span className="text-body-sm font-medium text-on-surface">
                {checkedIds.size} selected
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setCheckedIds(new Set())}>
                  Clear
                </Button>
                <Button size="sm" onClick={runBulkApprove} loading={bulkApprove.isPending}>
                  <Icon name="done_all" /> Approve {checkedIds.size}
                </Button>
              </div>
            </div>
          )}
          <div className="max-h-[55vh] flex-1 space-y-2 overflow-y-auto p-2 lg:max-h-none">
            {isReviewed ? (
              reviewedLoading ? (
                [0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded" />)
              ) : reviewedSheets.length === 0 ? (
                <EmptyState
                  icon="history"
                  title="No reviewed sheets yet"
                  description="Sheets you approve or return to the employee will appear here."
                />
              ) : (
                reviewedSheets.map((sheet) => (
                  <SheetListItem
                    key={sheet.id}
                    sheet={sheet}
                    active={sheet.id === selectedId}
                    onSelect={() => selectSheet(sheet.id)}
                    decision={managerOutcome(sheet.status)}
                  />
                ))
              )
            ) : isLoading ? (
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
                  onSelect={() => selectSheet(sheet.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Detail */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest lg:h-full">
          {selected ? (
            <SheetDetail sheet={selected} onReturn={returnToQueue} readOnly={isReviewed} />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                icon="fact_check"
                title="Select a sheet"
                description={
                  isReviewed
                    ? "Choose a reviewed sheet to see its line items and your decision."
                    : "Choose a pending sheet to review its line items."
                }
              />
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
  decision,
}: {
  sheet: ExpenseSheet;
  active: boolean;
  checked?: boolean;
  onToggle?: () => void;
  onSelect: () => void;
  /** When set (history view), shows the manager's outcome instead of the selection checkbox + SLA. */
  decision?: { label: string; tone: string; icon: string };
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
          {onToggle && (
            <input
              type="checkbox"
              checked={!!checked}
              onClick={(e) => e.stopPropagation()}
              onChange={onToggle}
              className="h-4 w-4 rounded border-outline-variant text-secondary focus:ring-secondary"
              aria-label={`Select ${sheet.title}`}
            />
          )}
          <span className="font-mono text-label-md text-on-surface-variant">{sheet.period}</span>
        </div>
        <span className="text-body-sm font-semibold text-on-surface">
          {formatCurrency(sheet.total, sheet.currency)}
        </span>
      </div>
      <div className="mb-1 text-body-md font-semibold text-on-surface">{sheet.title}</div>
      <div className="flex items-center justify-between text-on-surface-variant">
        <span className="text-body-sm">{sheet.employeeName}</span>
        <span
          className="text-label-sm"
          title={sheet.submittedAt ? formatRelative(sheet.submittedAt) : ""}
        >
          {sheet.submittedAt ? formatDateTimeIST(sheet.submittedAt) : ""}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between border-t border-outline-variant/30 pt-2">
        <span className="flex items-center gap-2">
          <Icon
            name={decision ? "fact_check" : "pending_actions"}
            className={cn("text-[14px]", decision ? "text-on-surface-variant" : "text-error")}
          />
          <span className="text-label-sm text-on-surface-variant">{sheet.lineItems.length} Items</span>
        </span>
        {decision ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold",
              decision.tone,
            )}
            title={`You ${decision.label.toLowerCase()} this sheet`}
          >
            <Icon name={decision.icon} className="text-[12px]" />
            {decision.label}
          </span>
        ) : (
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
        )}
      </div>
    </div>
  );
}

function SheetDetail({
  sheet,
  onReturn,
  readOnly = false,
}: {
  sheet: ExpenseSheet;
  onReturn: () => void;
  /** History view: render the sheet without any review actions. */
  readOnly?: boolean;
}) {
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
      toast.warning(`“${sheet.title}” routed to Finance for manual review`, {
        description: updated.routeReasonDetail,
      });
    } else if (updated.status === "FINANCE_APPROVED") {
      toast.success(`“${sheet.title}” auto-approved by the AI Finance Approver`, {
        description: `Confidence ${Math.round((updated.llmConfidence ?? 0) * 100)}%.`,
      });
    } else {
      toast.success(`“${sheet.title}” sent to Finance`);
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
              <span className="font-mono text-label-md text-on-surface-variant">{sheet.period}</span>
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
            {readOnly ? (
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  SHEET_STATUS_META[sheet.status].badgeClass,
                )}
              >
                <Icon name={SHEET_STATUS_META[sheet.status].icon} className="text-[13px]" />
                {SHEET_STATUS_META[sheet.status].label}
              </span>
            ) : (
              <span className="inline-block rounded-full bg-error-container px-2 py-0.5 text-[11px] font-semibold text-error">
                Pending Review
              </span>
            )}
          </div>
        </div>

        {isOwnSheet && (
          <div className="mb-3 flex items-center gap-2 rounded border border-error/20 bg-error-container/50 p-2 text-body-sm text-on-error-container">
            <Icon name="block" className="text-[16px]" />
            Segregation of duties: you can&apos;t action your own line items.
          </div>
        )}

        {/* Sheet status timeline — same rail the employee sees */}
        <SheetTimeline sheet={sheet} />

        {/* Manager-level review progress */}
        <div className="mt-3 rounded border border-outline-variant bg-surface-container p-3">
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
        {/* Employee note — shown when the employee left a note before resubmitting */}
        {sheet.employeeNote && (
          <div className="flex items-start gap-3 rounded-lg border border-secondary/30 bg-secondary/5 p-3">
            <Icon name="comment" className="mt-0.5 shrink-0 text-[18px] text-secondary" />
            <div className="min-w-0">
              <p className="mb-0.5 font-mono text-label-sm font-semibold uppercase tracking-wider text-secondary">
                Employee note
              </p>
              <p className="text-body-sm text-on-surface">{sheet.employeeNote}</p>
            </div>
          </div>
        )}
        {sheet.lineItems.map((item) => (
          <LineItemReviewCard
            key={item.id}
            item={item}
            sheetId={sheet.id}
            disabled={readOnly || isOwnSheet || lineItemAction.isPending}
            approving={
              lineItemAction.isPending && lineItemAction.variables?.lineItemId === item.id
            }
            onApprove={() => approve(item)}
            onReject={() => setPending({ action: "reject", item })}
            onRequestInfo={() => setPending({ action: "request_info", item })}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex justify-end gap-3 border-t border-outline-variant bg-surface-bright p-4">
        <Button variant="outline" onClick={onReturn}>
          <Icon name="arrow_back" /> {readOnly ? "Back" : "Return to Queue"}
        </Button>
        {!readOnly && (
          <Button
            disabled={!allApproved || isOwnSheet}
            loading={approveSheet.isPending}
            onClick={approveEntireSheet}
            title={allApproved ? undefined : "Complete line item reviews first"}
          >
            <Icon name="done_all" /> Approve Entire Sheet
          </Button>
        )}
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
              disabled={reason.trim().length < 3}
              loading={lineItemAction.isPending}
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
  sheetId,
  disabled,
  approving = false,
  onApprove,
  onReject,
  onRequestInfo,
}: {
  item: LineItem;
  sheetId: string;
  disabled: boolean;
  approving?: boolean;
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
              {item.categoryOther ? ` — ${item.categoryOther}` : ""}
            </div>
          </div>
          <div className="text-body-md font-semibold text-on-surface">
            {formatCurrency(item.amount, item.currency)}
          </div>
        </div>

        {/* Employee-filled detail fields */}
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
          {item.merchant && (
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">Merchant</dt>
              <dd className="text-body-sm text-on-surface">{item.merchant}</dd>
            </div>
          )}
          {item.expenseDate && (
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">Date</dt>
              <dd className="text-body-sm text-on-surface">{formatDate(item.expenseDate)}</dd>
            </div>
          )}
          {item.receiptTotal != null && (
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">Receipt Total</dt>
              <dd className="text-body-sm text-on-surface">{formatCurrency(item.receiptTotal, item.currency)}</dd>
            </div>
          )}
          {item.receiptDatetime && (
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">Receipt Date</dt>
              <dd className="text-body-sm text-on-surface">{formatDate(item.receiptDatetime)}</dd>
            </div>
          )}
        </dl>

        {/* Intake flag — shown when the system detected a soft issue (policy, reconciliation,
            duplicate risk). Not an auto-return; the manager reviews and decides. */}
        {item.policyStatus === "POLICY_UNCERTAIN" && item.reviewReason && (
          <div className="mt-2 flex items-start gap-2 rounded border border-yellow-500/30 bg-yellow-500/8 p-2">
            <Icon name="flag" className="mt-0.5 shrink-0 text-[16px] text-yellow-600" />
            <div>
              <p className="text-label-sm font-semibold text-yellow-700">Flagged at intake</p>
              <p className="text-body-sm text-on-surface-variant">{item.reviewReason}</p>
            </div>
          </div>
        )}

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

        {/* Manager-only: scan-derived values from the receipt (not shown to the employee). */}
        <ReceiptScanDetails
          sheetId={sheetId}
          lineItemId={item.id}
          currency={item.currency}
          expenseDate={item.expenseDate}
        />

        {/* Per-line-item receipt(s) — preview/download directly under the item that owns them. */}
        {(item.attachments?.length ?? 0) > 0 && (
          <div className="mt-2 rounded-md border border-outline-variant/50 bg-surface-container-lowest p-2">
            <p className="mb-1.5 flex items-center gap-1 font-mono text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
              <Icon name="receipt_long" className="text-[13px]" />
              Receipt{item.attachments.length > 1 ? "s" : ""}
            </p>
            <ReceiptViewer attachments={item.attachments} />
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
            <Button variant="secondary" size="sm" disabled={disabled} loading={approving} onClick={onApprove}>
              <Icon name="check" /> Approve
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
