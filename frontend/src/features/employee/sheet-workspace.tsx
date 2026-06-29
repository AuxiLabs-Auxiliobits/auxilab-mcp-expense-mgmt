"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  useDiscardDraft,
  useRemoveLineItem,
  useResubmitSheet,
  useSheet,
  useSheetDecisions,
  useSubmitSheet,
  useUpdateSheet,
  useWithdrawSheet,
} from "@/data/hooks";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { DecisionEntry, ExpenseSheet, LineItem, SheetStatus } from "@/data/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AiCitation, CitedClause } from "@/components/shared/ai-citation";
import { StatusBadge } from "@/components/shared/status-badge";
import { Reveal } from "@/components/shared/reveal";
import { Counter } from "@/components/shared/counter";
import { LiveDot } from "@/components/shared/live-dot";
import { SheetTimeline } from "@/components/shared/sheet-timeline";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CATEGORY_ICON,
  LINE_ITEM_STATUS_META,
  ROUTE_REASON_META,
  SHEET_STATUS_META,
} from "@/lib/status";
import { formatCurrency, formatDate, formatDateTimeIST, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ReceiptPreview } from "@/components/shared/receipt-preview";
import { LineItemDialog } from "./line-item-form";

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

const EDITABLE: SheetStatus[] = [
  "DRAFT",
  "RETURNED_TO_EMPLOYEE",
  "FINANCE_REJECTED",
  "REJECTED",
];
const NEEDS_FEEDBACK: SheetStatus[] = [
  "RETURNED_TO_EMPLOYEE",
  "FINANCE_REJECTED",
  "REJECTED",
];
const IN_FLIGHT: SheetStatus[] = [
  "SUBMITTED",
  "IN_MANAGER_REVIEW",
  "IN_FINANCE_REVIEW",
  "FINANCE_MANUAL_REVIEW",
];
// Withdraw is only allowed before the manager approves it (queued / in manager review).
// Once it advances to finance, it can't be recalled.
const WITHDRAWABLE: SheetStatus[] = ["SUBMITTED", "IN_MANAGER_REVIEW"];


export function SheetWorkspace({ sheetId }: { sheetId: string }) {
  const router = useRouter();
  const { data: sheet, isLoading } = useSheet(sheetId);
  const removeLineItem = useRemoveLineItem();
  const submitSheet = useSubmitSheet();
  const resubmitSheet = useResubmitSheet();
  const withdrawSheet = useWithdrawSheet();
  const discardDraft = useDiscardDraft();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<LineItem | undefined>();
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [note, setNote] = useState(sheet?.employeeNote ?? "");
  const updateSheet = useUpdateSheet();

  if (isLoading || !sheet) {
    return (
      <>
        <Skeleton className="h-5 w-28" />
        <Skeleton className="mt-4 h-36 rounded-lg" />
        <Skeleton className="mt-4 h-20 rounded-lg" />
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-72 rounded-lg lg:col-span-2" />
          <Skeleton className="h-72 rounded-lg" />
        </div>
      </>
    );
  }

  const editable = EDITABLE.includes(sheet.status);
  const isDraft = sheet.status === "DRAFT";
  const isResubmit = NEEDS_FEEDBACK.includes(sheet.status);
  const inFlight = IN_FLIGHT.includes(sheet.status);
  const withdrawable = WITHDRAWABLE.includes(sheet.status);
  const errorCount = sheet.lineItems.filter(
    (li) => li.aiFlag?.severity === "error" || li.policyStatus === "POLICY_FAIL",
  ).length;
  const warningCount = sheet.lineItems.filter((li) => li.aiFlag?.severity === "warning").length;
  const missingReceipts = sheet.lineItems.filter((li) => li.attachments.length === 0).length;
  const empty = sheet.lineItems.length === 0;
  const currencies = [...new Set(sheet.lineItems.map((li) => li.currency))];
  const mixedCurrency = currencies.length > 1;
  const rejectionReasons = sheet.lineItems.filter(
    (li) =>
      (li.managerStatus === "MANAGER_REJECTED" || li.managerStatus === "INFO_REQUESTED") &&
      li.managerReason,
  );

  function openAdd() {
    setEditing(undefined);
    setDialogOpen(true);
  }
  function openEdit(item: LineItem) {
    setEditing(item);
    setDialogOpen(true);
  }
  async function remove(item: LineItem) {
    await removeLineItem.mutateAsync({ sheetId, lineItemId: item.id });
    toast("Line item removed", { description: item.merchant });
  }
  async function submit() {
    await submitSheet.mutateAsync(sheetId);
    toast.success(`"${sheet!.title}" submitted for manager review`);
    router.push("/employee");
  }
  async function resubmit() {
    try {
      const result = await resubmitSheet.mutateAsync(sheetId);
      if (result.status === "RETURNED_TO_EMPLOYEE") {
        toast.error("Sheet returned by intake check", {
          description:
            "One or more items failed validation (policy violation or duplicate). Fix the flagged items and resubmit.",
        });
      } else {
        toast.success(`"${result.title}" resubmitted (v${result.version})`, {
          description: "Restarted from manager review.",
        });
        router.push("/employee");
      }
    } catch {
      // 422 (missing receipts) — global mutationCache.onError already shows the toast
    }
  }
  async function withdraw() {
    await withdrawSheet.mutateAsync(sheetId);
    toast("Sheet withdrawn", { description: `"${sheet!.title}" pulled back to draft.` });
    router.push("/employee");
  }
  async function discard() {
    const title = sheet!.title;
    try {
      await discardDraft.mutateAsync({ sheetId, employeeId: sheet!.employeeId });
      setConfirmDiscard(false);
      toast("Draft discarded", { description: `"${title}" was permanently deleted.` });
      router.push("/employee/sheets");
    } catch (e) {
      toast.error("Couldn't discard the draft", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  const blocked = empty || errorCount > 0 || missingReceipts > 0;
  const primaryPending = isResubmit ? resubmitSheet.isPending : submitSheet.isPending;

  return (
    <>
      <Link
        href="/employee/sheets"
        className="inline-flex items-center gap-1 rounded text-body-sm text-on-surface-variant transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <Icon name="arrow_back" className="text-[18px]" /> Back to sheets
      </Link>

      {/* ── Sticky header ──────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 mt-3">
        <Card className="overflow-hidden border-outline-variant/70 shadow-elevation-1 backdrop-blur supports-[backdrop-filter]:bg-surface-container-lowest/90">
          <div className="flex flex-col gap-5 p-5 md:p-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <EditableTitle sheet={sheet} editable={editable} />
                <StatusBadge meta={SHEET_STATUS_META[sheet.status]} className="rounded-md" />
                {inFlight && (
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-outline-variant px-2 py-0.5 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                    <LiveDot tone="primary" /> Live
                  </span>
                )}
              </div>
              <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-label-md text-on-surface-variant">
                <span className="inline-flex items-center gap-1">
                  <Icon name="apartment" className="text-[14px]" />
                  {sheet.agencyName}
                </span>
                <span aria-hidden className="text-outline-variant">/</span>
                <span className="inline-flex items-center gap-1">
                  <Icon name="event" className="text-[14px]" />
                  {sheet.period}
                </span>
                <span aria-hidden className="text-outline-variant">/</span>
                <span className="inline-flex items-center gap-1">
                  <Icon name="person" className="text-[14px]" />
                  {sheet.employeeName}
                </span>
              </div>
            </div>

            {/* Total + primary contextual action */}
            <div className="flex shrink-0 flex-col items-start gap-3 border-t border-outline-variant pt-4 lg:items-end lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
              <div className="lg:text-right">
                <div className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                  Sheet total
                </div>
                <div className="text-headline-xl font-semibold tabular-nums text-on-surface">
                  <Counter
                    value={sheet.total}
                    format={(n) => formatCurrency(n, sheet.currency)}
                  />
                </div>
                <div className="font-mono text-label-sm text-on-surface-variant">
                  {sheet.lineItems.length} item{sheet.lineItems.length === 1 ? "" : "s"} ·
                  updated {formatDateTimeIST(sheet.updatedAt)}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {isDraft && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmDiscard(true)}
                    className="border-error/40 text-error hover:bg-error-container hover:text-on-error-container"
                    title="Permanently delete this draft"
                  >
                    <Icon name="delete" /> Discard Draft
                  </Button>
                )}
                {inFlight && (
                  <Button
                    variant="outline"
                    size="sm"
                    loading={withdrawSheet.isPending}
                    disabled={!withdrawable}
                    onClick={withdraw}
                    title={
                      withdrawable
                        ? "Withdraw this sheet back to draft"
                        : "Can't withdraw — the manager has already approved it"
                    }
                  >
                    <Icon name="cancel_presentation" /> Withdraw
                  </Button>
                )}
                {editable && (
                  isResubmit ? (
                    <Button
                      onClick={resubmit}
                      loading={primaryPending}
                      disabled={blocked}
                      aria-label="Resubmit sheet for review"
                    >
                      <Icon name="restart_alt" /> Resubmit Sheet
                    </Button>
                  ) : (
                    <Button
                      onClick={submit}
                      loading={primaryPending}
                      disabled={blocked}
                      aria-label="Submit sheet for review"
                    >
                      <Icon name="send" /> Submit for Review
                    </Button>
                  )
                )}
              </div>
              {editable && blocked && (
                <p className="flex items-center gap-1 font-mono text-label-sm text-error lg:justify-end">
                  <Icon name="error" className="text-[14px]" />
                  {empty
                    ? "Add a line item to submit"
                    : missingReceipts > 0
                      ? `${missingReceipts} item${missingReceipts === 1 ? "" : "s"} missing receipts`
                      : `${errorCount} item${errorCount === 1 ? "" : "s"} need fixing`}
                </p>
              )}
            </div>
          </div>

          {/* Decision timeline rail */}
          <SheetTimeline sheet={sheet} />
        </Card>
      </header>

      {/* ── Notices ────────────────────────────────────────────────────── */}
      {mixedCurrency && (
        <Reveal>
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-tertiary/30 bg-tertiary/5 px-4 py-3 text-body-sm text-on-surface">
            <Icon name="currency_exchange" className="text-[18px] text-tertiary" />
            Mixed-currency sheet ({currencies.join(", ")}). FX is applied at the reimbursement
            decision; totals shown are nominal.
          </div>
        </Reveal>
      )}

      {isResubmit && (
        <Reveal>
          <Card className="mt-4 border-error/30 bg-error-container/30 shadow-sm">
            <div className="p-5">
              <div className="mb-2 flex items-center gap-2 text-on-error-container">
                <Icon name="report" />
                <h2 className="text-body-lg font-semibold">
                  This sheet was{" "}
                  {sheet.status === "RETURNED_TO_EMPLOYEE"
                    ? "returned by your manager"
                    : "rejected at the finance gate"}
                </h2>
              </div>
              <p className="text-body-sm text-on-surface-variant">
                Address the feedback below, then resubmit. Resubmitting sends your sheet back
                to your manager for review.
              </p>

              {sheet.citedClause && (
                <div className="mt-3">
                  <CitedClause policyName={sheet.citedClause.policyName} text={sheet.citedClause.text} />
                </div>
              )}
              {sheet.routeReasonDetail && (
                <p className="mt-3 rounded border border-outline-variant bg-surface p-3 text-body-sm text-on-surface">
                  {sheet.routeReasonDetail}
                </p>
              )}
              {rejectionReasons.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {rejectionReasons.map((li) => (
                    <li key={li.id} className="rounded border border-outline-variant bg-surface p-3 text-body-sm">
                      <span className="font-medium text-on-surface">{li.merchant}:</span>{" "}
                      <span className="text-on-surface-variant">{li.managerReason}</span>
                    </li>
                  ))}
                </ul>
              )}

              {/* Employee note — visible to the manager when they review the resubmission */}
              <div className="mt-4 border-t border-outline-variant/40 pt-4">
                <label className="mb-1.5 block font-mono text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
                  Add a note for the reviewer <span className="ml-1 font-normal normal-case text-on-surface-variant/60">(optional)</span>
                </label>
                <Textarea
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  onBlur={() => {
                    if (note !== (sheet?.employeeNote ?? "")) {
                      updateSheet.mutate({ sheetId: sheetId, note });
                    }
                  }}
                  placeholder="Explain what you changed or why expenses were necessary — the manager sees this when reviewing."
                  className="resize-none"
                />
              </div>
            </div>
          </Card>
        </Reveal>
      )}

      {/* ── Body: line items (main) + decision sidebar ─────────────────── */}
      <div className="mt-4 grid items-start gap-4 lg:grid-cols-3">
        {/* Line items */}
        <Card className="shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between gap-3 border-b border-outline-variant px-5 py-4">
            <div className="flex items-center gap-2">
              <h2 className="text-body-lg font-semibold text-on-surface">Line Items</h2>
              <span className="rounded-full bg-surface-container-high px-2 py-0.5 font-mono text-label-sm text-on-surface-variant">
                {sheet.lineItems.length}
              </span>
            </div>
            {editable && (
              <Button size="sm" onClick={openAdd}>
                <Icon name="add" /> Add Line Item
              </Button>
            )}
          </div>

          {isResubmit && (
            <div className="flex items-start gap-2 border-b border-outline-variant bg-surface-bright px-5 py-2.5 text-body-sm text-on-surface-variant">
              <Icon name="edit_note" className="mt-0.5 text-[18px] text-secondary" />
              <span>
                Edit the flagged items below to address the feedback — change details or
                replace attachments — then resubmit. You can also add or remove items.
              </span>
            </div>
          )}

          {empty ? (
            <div className="flex flex-col items-center gap-3 px-5 py-14 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-container-high text-on-surface-variant">
                <Icon name="receipt_long" className="text-[24px]" />
              </span>
              <p className="text-body-sm text-on-surface-variant">No line items yet.</p>
              {editable && (
                <Button size="sm" variant="outline" onClick={openAdd}>
                  <Icon name="add" /> Add your first one
                </Button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-outline-variant">
              {sheet.lineItems.map((item, i) => (
                <Reveal key={item.id} delay={i * 50}>
                  <LineItemRow
                    item={item}
                    editable={editable}
                    onEdit={() => openEdit(item)}
                    onRemove={() => remove(item)}
                    removing={
                      removeLineItem.isPending &&
                      removeLineItem.variables?.lineItemId === item.id
                    }
                  />
                </Reveal>
              ))}
            </ul>
          )}

          {editable && (
            <div className="flex flex-col gap-3 border-t border-outline-variant bg-surface-container-low px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="font-mono text-label-md text-on-surface-variant">
                {errorCount > 0 ? (
                  <span className="flex items-center gap-1 text-error">
                    <Icon name="error" className="text-[16px]" />
                    {errorCount} item{errorCount === 1 ? "" : "s"} need fixing before submission
                  </span>
                ) : isResubmit ? (
                  "You can resubmit with or without changes."
                ) : (
                  "Add all your expenses, then submit for review."
                )}
              </div>
              {isResubmit ? (
                <Button onClick={resubmit} disabled={blocked} loading={resubmitSheet.isPending}>
                  <Icon name="restart_alt" /> Resubmit Sheet
                </Button>
              ) : (
                <Button onClick={submit} disabled={blocked} loading={submitSheet.isPending}>
                  <Icon name="send" /> Submit for Review
                </Button>
              )}
            </div>
          )}
        </Card>

        {/* Decision / summary sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-44">
          <DecisionPanel sheet={sheet} />

          <Card className="shadow-sm">
            <div className="border-b border-outline-variant px-5 py-3">
              <h2 className="text-body-lg font-semibold text-on-surface">Summary</h2>
            </div>
            <dl className="divide-y divide-outline-variant text-body-sm">
              <SummaryRow label="Line items" value={String(sheet.lineItems.length)} />
              <SummaryRow
                label="Sheet total"
                value={formatCurrency(sheet.total, sheet.currency)}
                emphasis
              />
              <SummaryRow
                label="Missing receipts"
                value={String(missingReceipts)}
                tone={missingReceipts > 0 ? "error" : "muted"}
              />
              <SummaryRow
                label="Policy flags"
                value={`${errorCount} error${errorCount === 1 ? "" : "s"} · ${warningCount} warning${warningCount === 1 ? "" : "s"}`}
                tone={errorCount > 0 ? "error" : warningCount > 0 ? "warning" : "muted"}
              />
            </dl>
          </Card>

          {isResubmit && (
            <p className="flex items-start gap-1.5 px-1 text-body-sm text-on-surface-variant">
              <Icon name="info" className="mt-0.5 text-[16px]" />
              Anti-gaming: an unchanged resubmit of a policy-rejected sheet will be rejected
              again deterministically.
            </p>
          )}
        </aside>
      </div>

      <LineItemDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        sheetId={sheet.id}
        period={sheet.period}
        item={editing}
        siblings={sheet.lineItems.filter((l) => l.id !== editing?.id)}
      />

      <Dialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Discard this draft?</DialogTitle>
            <DialogDescription>
              <span className="font-medium text-on-surface">{sheet.title}</span> and its{" "}
              {sheet.lineItems.length} line item{sheet.lineItems.length === 1 ? "" : "s"} will
              be permanently deleted. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDiscard(false)}
              disabled={discardDraft.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={discard}
              loading={discardDraft.isPending}
              className="bg-error text-on-error hover:bg-error/90"
            >
              <Icon name="delete" /> Discard Draft
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Inline sheet-title editor (rename a draft in place) ──────────────────────
function EditableTitle({ sheet, editable }: { sheet: ExpenseSheet; editable: boolean }) {
  const updateSheet = useUpdateSheet();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sheet.title);

  useEffect(() => {
    setDraft(sheet.title);
  }, [sheet.title]);

  const h1 = "text-headline-lg font-semibold tracking-tight text-on-surface";

  if (!editable) {
    return <h1 className={h1}>{sheet.title}</h1>;
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-1.5">
        <h1 className={h1}>{sheet.title}</h1>
        <button
          type="button"
          onClick={() => {
            setDraft(sheet.title);
            setEditing(true);
          }}
          aria-label="Rename sheet"
          className="rounded p-1 text-on-surface-variant transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="edit" className="text-[18px]" />
        </button>
      </div>
    );
  }

  const trimmed = draft.trim();
  const valid = trimmed.length >= 3 && trimmed.length <= 50;

  async function save() {
    if (!valid) return;
    if (trimmed !== sheet.title) {
      try {
        await updateSheet.mutateAsync({ sheetId: sheet.id, title: trimmed });
        toast.success("Sheet renamed");
      } catch (e) {
        toast.error("Couldn't rename the sheet", {
          description: e instanceof Error ? e.message : undefined,
        });
        return;
      }
    }
    setEditing(false);
  }

  return (
    <div className="flex items-center gap-2">
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        maxLength={50}
        autoFocus
        aria-label="Sheet title"
        className="h-9 w-64 text-body-lg font-semibold"
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void save();
          } else if (e.key === "Escape") {
            setEditing(false);
          }
        }}
      />
      <Button size="sm" onClick={save} disabled={!valid} loading={updateSheet.isPending}>
        <Icon name="check" /> Save
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
        Cancel
      </Button>
    </div>
  );
}

// ── Decision panel (AI / finance outcome detail) ─────────────────────────────
function DecisionPanel({ sheet }: { sheet: ExpenseSheet }) {
  const decided = sheet.financeDecision != null;
  const routed = sheet.status === "FINANCE_MANUAL_REVIEW";
  // Full chronological trail (manager → AI → finance actions). Skipped for drafts — a
  // sheet that hasn't been submitted has no decisions yet.
  const { data: decisions, isLoading: decisionsLoading } = useSheetDecisions(
    sheet.status === "DRAFT" ? undefined : sheet.id,
  );
  const trail = decisions ?? [];

  return (
    <Card className="shadow-sm">
      <div className="flex items-center gap-2 border-b border-outline-variant px-5 py-3">
        <Icon name="smart_toy" className="text-[18px] text-secondary" />
        <h2 className="text-body-lg font-semibold text-on-surface">Decision Trail</h2>
      </div>
      <div className="space-y-3 p-5">
        {!decided && !routed && (
          <p className="text-body-sm text-on-surface-variant">
            {sheet.status === "DRAFT"
              ? "Not submitted yet. Add your expenses and submit for manager review."
              : "Awaiting decisions. Verdicts from your manager and the AI Finance Approver will appear here."}
          </p>
        )}

        {sheet.financeDecidedBy && (
          <div className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2">
            <div className="flex items-center gap-2 text-body-sm text-on-surface">
              <Icon name="badge" className="text-[16px] text-on-surface-variant" />
              Decided by
            </div>
            <span className="font-mono text-label-md text-on-surface-variant">
              {sheet.financeDecidedBy}
            </span>
          </div>
        )}

        {sheet.routeReason && (
          <div className="space-y-2 rounded-lg border border-outline-variant bg-surface-container-low p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                Route reason
              </span>
              <StatusBadge meta={ROUTE_REASON_META[sheet.routeReason]} className="rounded-md" />
            </div>
            {/* Model confidence is intentionally hidden from employees (visible to
                manager/finance only). */}
            {sheet.routeReasonDetail && (
              <p className="text-body-sm text-on-surface">{sheet.routeReasonDetail}</p>
            )}
          </div>
        )}

        {sheet.citedClause && (
          <CitedClause policyName={sheet.citedClause.policyName} text={sheet.citedClause.text} />
        )}

        {/* Full chronological history — manager / AI / finance actions, oldest first. */}
        {sheet.status !== "DRAFT" && (
          <div className="border-t border-outline-variant pt-3">
            <h3 className="mb-2 flex items-center gap-1.5 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
              <Icon name="history" className="text-[14px]" /> History
            </h3>
            {decisionsLoading ? (
              <p className="text-body-sm text-on-surface-variant">Loading history…</p>
            ) : trail.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant">No decisions recorded yet.</p>
            ) : (
              <ol className="space-y-2">
                {trail.map((d) => (
                  <DecisionTrailItem key={d.id} decision={d} />
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

// One entry in the employee's decision trail (manager/AI/finance action + remark + citations).
function DecisionTrailItem({ decision: d }: { decision: DecisionEntry }) {
  // Employees don't see model confidence — strip any "confidence=0.96" token the AI approver
  // records in the reason. (Manager/finance views keep it.)
  const reason = d.reason?.replace(/\s*confidence\s*=\s*[\d.]+/gi, "").trim();
  return (
    <li className="flex items-start gap-2.5 rounded-md border border-outline-variant bg-surface-container-lowest px-3 py-2">
      <Icon name="check_circle" className="mt-0.5 shrink-0 text-[16px] text-secondary" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-body-sm font-medium text-on-surface">{d.action}</span>
          <span className="rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-label-sm uppercase text-on-surface-variant">
            {d.actorRole}
          </span>
          <span
            className="font-mono text-label-sm text-on-surface-variant"
            title={formatRelative(d.timestamp)}
          >
            {formatDateTimeIST(d.timestamp)}
          </span>
        </div>
        {reason && <p className="mt-0.5 text-body-sm text-on-surface-variant">{reason}</p>}
        {d.citedClauses.length > 0 && (
          <p className="mt-0.5 font-mono text-label-sm text-secondary">
            Cited: {d.citedClauses.join(", ")}
          </p>
        )}
      </div>
    </li>
  );
}

function SummaryRow({
  label,
  value,
  emphasis,
  tone = "default",
}: {
  label: string;
  value: string;
  emphasis?: boolean;
  tone?: "default" | "muted" | "error" | "warning";
}) {
  const toneClass =
    tone === "error"
      ? "text-error"
      : tone === "warning"
        ? "text-yellow-600"
        : tone === "muted"
          ? "text-on-surface-variant"
          : "text-on-surface";
  return (
    <div className="flex items-center justify-between px-5 py-2.5">
      <dt className="text-on-surface-variant">{label}</dt>
      <dd
        className={cn(
          "font-mono tabular-nums",
          emphasis ? "text-body-md font-semibold text-on-surface" : "text-label-md",
          !emphasis && toneClass,
        )}
      >
        {value}
      </dd>
    </div>
  );
}

// ── Line item row ────────────────────────────────────────────────────────────
function LineItemRow({
  item,
  editable,
  onEdit,
  onRemove,
  removing = false,
}: {
  item: LineItem;
  editable: boolean;
  onEdit: () => void;
  onRemove: () => void;
  removing?: boolean;
}) {
  const needsFix =
    editable &&
    (item.managerStatus === "MANAGER_REJECTED" ||
      item.managerStatus === "INFO_REQUESTED" ||
      item.aiFlag?.severity === "error" ||
      item.policyStatus === "POLICY_FAIL");
  const hasReceipt = item.attachments.length > 0;

  return (
    <li
      className={cn(
        "relative flex items-start gap-4 px-5 py-4 transition-colors",
        needsFix ? "bg-error-container/20" : "hover:bg-surface-container-low",
      )}
    >
      {needsFix && <span className="absolute left-0 top-0 h-full w-1 bg-error" aria-hidden />}
      <div
        className={cn(
          "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
          needsFix
            ? "bg-error-container text-on-error-container"
            : "bg-surface-container-high text-on-surface-variant",
        )}
      >
        <Icon name={CATEGORY_ICON[item.category] ?? "category"} className="text-[20px]" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="truncate text-body-md font-medium text-on-surface">{item.merchant}</div>
            <div className="font-mono text-label-md text-on-surface-variant">
              {item.category} · {formatDate(item.expenseDate)}
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <div className="font-mono text-body-md font-semibold tabular-nums text-on-surface">
              {formatCurrency(item.amount, item.currency)}
            </div>
            {editable && (
              <div className="flex items-center gap-1">
                <Button size="sm" variant={needsFix ? "default" : "outline"} onClick={onEdit}>
                  <Icon name="edit" /> {needsFix ? "Edit to fix" : "Edit"}
                </Button>
                <button
                  onClick={onRemove}
                  disabled={removing}
                  aria-busy={removing || undefined}
                  className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-error-container hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error disabled:opacity-50"
                  aria-label={`Remove ${item.merchant}`}
                >
                  <Icon name={removing ? "progress_activity" : "delete"} className={cn("text-[18px]", removing && "animate-spin")} />
                </button>
              </div>
            )}
          </div>
        </div>

        {item.description && item.description !== item.merchant && (
          <p className="mt-1 text-body-sm text-on-surface-variant">{item.description}</p>
        )}

        {item.managerReason && (
          <div className="mt-2 flex items-start gap-2 rounded border border-error/20 bg-error-container/40 p-2 text-body-sm text-on-surface">
            <Icon name="comment" className="mt-0.5 text-[16px] text-error" />
            <span>
              <span className="font-medium">Manager feedback:</span> {item.managerReason}
            </span>
          </div>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-2">
          {!editable && (
            <StatusBadge meta={LINE_ITEM_STATUS_META[item.managerStatus]} className="rounded-md" />
          )}
          {item.policyStatus && (editable ? item.policyStatus === "POLICY_FAIL" : true) && (
            <StatusBadge meta={LINE_ITEM_STATUS_META[item.policyStatus]} className="rounded-md" />
          )}
          {!editable && item.needsHumanReview && (
            <span
              title={item.reviewReason ?? "Receipt scan flagged for review"}
              className="inline-flex items-center gap-1 rounded border border-tertiary/40 bg-tertiary/10 px-2 py-0.5 font-mono text-label-sm text-tertiary"
            >
              <Icon name="flag" className="text-[12px]" /> Needs finance review
            </span>
          )}
          {hasReceipt ? (
            item.attachments.map((a) => (
              <span
                key={a.id}
                className="inline-flex items-center gap-1.5 rounded border border-outline-variant p-1 pr-2 font-mono text-label-sm text-on-surface-variant"
              >
                <ReceiptPreview
                  downloadUrl={a.downloadUrl}
                  fileName={a.fileName}
                  fileType={a.fileType}
                />
                <span className="max-w-[14rem] truncate">{a.fileName}</span>
                {a.sizeBytes > 0 && <span className="text-on-surface-variant/70">{fmtBytes(a.sizeBytes)}</span>}
              </span>
            ))
          ) : (
            <span className="inline-flex items-center gap-1 rounded border border-error/30 bg-error-container/30 px-2 py-0.5 font-mono text-label-sm text-error">
              <Icon name="receipt_long" className="text-[12px]" /> No receipt
            </span>
          )}
        </div>

        {item.aiFlag && (
          <div className="mt-2">
            <AiCitation
              message={item.aiFlag.message}
              clauseRef={item.aiFlag.clauseRef}
              severity={item.aiFlag.severity}
            />
          </div>
        )}
      </div>
    </li>
  );
}
