"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useCurrentUser, useFinanceOverride, useSheetDecisions, useSheetReceipts } from "@/data/hooks";
import { financeOverrideSchema, type FinanceOverrideValues } from "@/lib/schemas";
import { CitedClause } from "@/components/shared/ai-citation";
import { PolicyMatchPanel } from "@/components/shared/policy-match-panel";
import { ReceiptViewer, ReceiptsLoading } from "@/components/shared/receipt-viewer";
import { ReceiptScanDetails } from "@/components/shared/receipt-scan-details";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency, formatDateTimeIST, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ExpenseSheet } from "@/data/types";

export function ReviewDetail({
  sheet,
  onClose,
  embedded = false,
}: {
  sheet: ExpenseSheet;
  onClose: () => void;
  /** When true, render bare (no Card chrome / own close) for use inside a Drawer. */
  embedded?: boolean;
}) {
  const { data: user } = useCurrentUser("finance");
  const override = useFinanceOverride();
  const { data: receipts, isLoading: receiptsLoading } = useSheetReceipts(sheet.id);
  const { data: decisions, isLoading: decisionsLoading } = useSheetDecisions(sheet.id);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FinanceOverrideValues>({
    resolver: zodResolver(financeOverrideSchema),
    defaultValues: { decision: "APPROVED", reason: "" },
  });

  const submit = (decision: FinanceOverrideValues["decision"]) =>
    handleSubmit(async (values) => {
      if (!user) return;
      await override.mutateAsync({
        sheetId: sheet.id,
        decision,
        reason: values.reason,
        actor: user,
        sheetStatus: sheet.status,
      });
      toast.success(
        decision === "APPROVED" ? "Sheet approved" : "Sheet rejected",
        { description: `"${sheet.title}" — logged to the immutable audit trail.` },
      );
      onClose();
    });

  // Decision clarity banner — computed once, rendered before the two-column grid.
  const decisionBanner = (() => {
    const by = sheet.financeDecidedBy ? ` · ${sheet.financeDecidedBy}` : "";
    switch (sheet.decisionMethod) {
      case "AI_AUTO_APPROVED":
        return {
          icon: "smart_toy",
          iconCls: "text-primary",
          containerCls: "border-primary/20 bg-primary/5",
          titleCls: "text-primary",
          title: "AI Auto-Approved",
          body: "All policy checks passed — Finance can override below at any time.",
        };
      case "FINANCE_APPROVED":
        return {
          icon: "gavel",
          iconCls: "text-success-green",
          containerCls: "border-success-green/20 bg-success-green/5",
          titleCls: "text-success-green",
          title: `Finance Approved${by}`,
          body: "Manually reviewed and approved after routing to human review.",
        };
      case "FINANCE_OVERRIDE":
        return {
          icon: "gavel",
          iconCls: "text-secondary",
          containerCls: "border-secondary/20 bg-secondary/5",
          titleCls: "text-secondary",
          title: `Finance Overrode AI Decision${by}`,
          body: "Finance reviewed the AI's auto-approval and chose to approve.",
        };
      case "FINANCE_REJECTED":
        return {
          icon: "cancel",
          iconCls: "text-error",
          containerCls: "border-error/20 bg-error-container",
          titleCls: "text-on-error-container",
          title: `Finance Rejected${by}`,
          body: "Sheet was manually reviewed and rejected.",
        };
      case "FINANCE_OVERRIDE_REJECTED":
        return {
          icon: "cancel",
          iconCls: "text-error",
          containerCls: "border-error/20 bg-error-container",
          titleCls: "text-on-error-container",
          title: `Finance Overrode AI (Rejected)${by}`,
          body: "Finance reviewed the AI auto-approval and rejected this sheet instead.",
        };
      default:
        return null;
    }
  })();

  const content = (
    <>
      {!embedded && (
        <div className="mb-6 flex items-start justify-between border-b border-outline-variant pb-4">
          <div>
            <div className="mb-1 flex items-center gap-3">
              <h3 className="text-headline-md font-semibold text-on-surface">Review: {sheet.id}</h3>
              <span className="rounded border border-outline-variant bg-surface-container-highest px-2.5 py-0.5 text-body-sm font-medium text-on-surface-variant">
                {sheet.agencyName}
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              Submitted by {sheet.employeeName} • Total: {formatCurrency(sheet.total, sheet.currency)}
            </p>
          </div>
          <button
            aria-label="Close review"
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <Icon name="close" />
          </button>
        </div>
      )}

      {/* Decision clarity banner — full-width, above the two-column grid */}
      {decisionBanner && (
        <div className={cn("mb-5 flex items-start gap-3 rounded-lg border p-4", decisionBanner.containerCls)}>
          <Icon name={decisionBanner.icon} className={cn("mt-0.5 shrink-0 text-[22px]", decisionBanner.iconCls)} />
          <div>
            <p className={cn("font-semibold text-body-md", decisionBanner.titleCls)}>{decisionBanner.title}</p>
            <p className="mt-0.5 text-body-sm text-on-surface-variant">{decisionBanner.body}</p>
          </div>
        </div>
      )}

      <div className={cn("grid grid-cols-1 gap-6", !embedded && "md:grid-cols-2")}>
        {/* AI Decision Support */}
        <div className="flex flex-col gap-4">
          <h4 className="flex items-center gap-2 text-headline-md font-semibold text-on-surface">
            <Icon name="smart_toy" className="text-primary" /> AI Decision Support
          </h4>

          {/* Routing reason — only for sheets still in (or that came through) manual review */}
          {sheet.status === "FINANCE_MANUAL_REVIEW" && sheet.routeReasonDetail && (
            <div className="rounded border border-error/20 bg-error-container p-4 text-on-error-container">
              <p className="mb-1 font-mono text-label-md font-bold uppercase">Route Reason</p>
              <p className="text-body-sm">{sheet.routeReasonDetail}</p>
            </div>
          )}

          {/* Auto-approval audit trail — only for AI-auto-approved sheets (not Finance-decided) */}
          {sheet.decisionMethod === "AI_AUTO_APPROVED" && sheet.autoApprovalReasons && sheet.autoApprovalReasons.length > 0 && (
            <div className="rounded border border-success-green/20 bg-success-green/5 p-4">
              <p className="mb-2 font-mono text-label-md font-bold uppercase text-success-green">
                Auto-approved — Policy Checks Passed
              </p>
              <ul className="space-y-1">
                {sheet.autoApprovalReasons.map((reason, i) => (
                  <li key={i} className="flex items-start gap-2 text-body-sm text-on-surface">
                    <Icon name="check_circle" className="mt-0.5 shrink-0 text-[14px] text-success-green" />
                    {reason}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-label-sm text-on-surface-variant">
                Finance can override this decision below if the AI assessment is incorrect.
              </p>
            </div>
          )}

          {sheet.citedClause && (
            <CitedClause policyName={sheet.citedClause.policyName} text={sheet.citedClause.text} />
          )}
          {sheet.llmConfidence != null && (
            <p className="font-mono text-label-md text-on-surface-variant">
              LLM confidence: {Math.round(sheet.llmConfidence * 100)}% · policy {sheet.policyVersionUsed}
            </p>
          )}
        </div>

        {/* Override Controls */}
        <div className="flex flex-col gap-4">
          <h4 className="flex items-center gap-2 text-headline-md font-semibold text-on-surface">
            <Icon name="gavel" className="text-secondary" /> Override Decision
          </h4>
          <div className="flex flex-col gap-2">
            <Label htmlFor="override-reason">Mandatory Override Reason</Label>
            <Textarea
              id="override-reason"
              rows={4}
              placeholder="Explain the rationale for this manual decision. This will be recorded in the immutable audit log."
              {...register("reason")}
            />
            {errors.reason && (
              <p className="text-label-md text-error">{errors.reason.message}</p>
            )}
          </div>
          <div className="mt-2 flex gap-4">
            <Button
              type="button"
              variant="outline"
              className="flex-1 bg-surface-container-highest"
              loading={override.isPending}
              onClick={submit("REJECTED_WITH_COMMENTS")}
            >
              <Icon name="close" className="text-error" /> Reject Sheet
            </Button>
            <Button
              type="button"
              className="flex-1"
              loading={override.isPending}
              onClick={submit("APPROVED")}
            >
              <Icon name="check" /> Approve Sheet
            </Button>
          </div>
          <p className="text-center font-mono text-label-sm text-on-surface-variant">
            Actioning this sheet will log your ID and reason.
          </p>
        </div>
      </div>

      {/* Policy match — live RAG evaluation: which policy points this sheet matches/violates. */}
      <div className="mt-6 border-t border-outline-variant pt-5">
        <h4 className="mb-3 flex items-center gap-2 text-headline-md font-semibold text-on-surface">
          <Icon name="rule" className="text-primary" /> Policy Match · Agency Document
        </h4>
        <PolicyMatchPanel sheetId={sheet.id} />
      </div>

      {/* Supporting receipts — full submission visibility for Finance. */}
      <div className="mt-6 border-t border-outline-variant pt-5">
        <h4 className="mb-3 flex items-center gap-2 text-headline-md font-semibold text-on-surface">
          <Icon name="receipt_long" className="text-secondary" /> Supporting Receipts
        </h4>
        {receiptsLoading ? (
          <ReceiptsLoading />
        ) : (
          <ReceiptViewer attachments={receipts ?? []} emptyHint="No receipts were attached to this sheet." />
        )}
      </div>

      {/* Receipt scans — derived values per line item (Document Intelligence), Finance-only. */}
      <div className="mt-6 border-t border-outline-variant pt-5">
        <h4 className="mb-3 flex items-center gap-2 text-headline-md font-semibold text-on-surface">
          <Icon name="document_scanner" className="text-secondary" /> Receipt Scans · Derived Values
        </h4>
        <div className="space-y-3">
          {sheet.lineItems.map((li) => (
            <div
              key={li.id}
              className="rounded-md border border-outline-variant bg-surface-container-lowest p-3"
            >
              <div className="flex items-start justify-between">
                <span className="text-body-md font-medium text-on-surface">
                  {li.description || li.merchant}
                </span>
                <span className="font-mono text-body-sm text-on-surface-variant">
                  {formatCurrency(li.amount, li.currency)}
                </span>
              </div>
              {li.needsHumanReview && (
                <p className="mt-1 flex items-center gap-1.5 text-label-md text-tertiary">
                  <Icon name="flag" className="text-[14px]" />
                  Flagged for review{li.reviewReason ? ` · ${li.reviewReason}` : ""}
                </p>
              )}
              <ReceiptScanDetails sheetId={sheet.id} lineItemId={li.id} currency={li.currency} />
            </div>
          ))}
        </div>
      </div>

      {/* Approval history — manager/finance/LLM actions + remarks, oldest first. */}
      <div className="mt-6 border-t border-outline-variant pt-5">
        <h4 className="mb-3 flex items-center gap-2 text-headline-md font-semibold text-on-surface">
          <Icon name="history" className="text-secondary" /> Approval History
        </h4>
        {decisionsLoading ? (
          <p className="text-body-sm text-on-surface-variant">Loading history…</p>
        ) : (decisions ?? []).length === 0 ? (
          <p className="text-body-sm text-on-surface-variant">No decisions recorded yet.</p>
        ) : (
          <ol className="space-y-2">
            {(decisions ?? []).map((d) => (
              <li
                key={d.id}
                className="flex items-start gap-3 rounded-md border border-outline-variant bg-surface-container-lowest px-3 py-2"
              >
                <Icon name="check_circle" className="mt-0.5 shrink-0 text-[18px] text-secondary" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
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
                  {d.reason && <p className="mt-0.5 text-body-sm text-on-surface-variant">{d.reason}</p>}
                  {d.citedClauses.length > 0 && (
                    <p className="mt-0.5 font-mono text-label-sm text-secondary">
                      Cited: {d.citedClauses.join(", ")}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </>
  );

  return embedded ? content : <Card className="rounded-xl p-6 shadow-sm">{content}</Card>;
}
