"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useCurrentUser, useFinanceOverride } from "@/data/hooks";
import { financeOverrideSchema, type FinanceOverrideValues } from "@/lib/schemas";
import { CitedClause } from "@/components/shared/ai-citation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency } from "@/lib/format";
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
      });
      toast.success(
        decision === "APPROVED" ? "Sheet approved" : "Sheet rejected",
        { description: `${sheet.id} — logged to the immutable audit trail.` },
      );
      onClose();
    });

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

      <div className={cn("grid grid-cols-1 gap-6", !embedded && "md:grid-cols-2")}>
        {/* AI Decision Support */}
        <div className="flex flex-col gap-4">
          <h4 className="flex items-center gap-2 text-headline-md font-semibold text-on-surface">
            <Icon name="smart_toy" className="text-primary" /> AI Decision Support
          </h4>
          {sheet.routeReasonDetail && (
            <div className="rounded border border-error/20 bg-error-container p-4 text-on-error-container">
              <p className="mb-1 font-mono text-label-md font-bold uppercase">Uncertainty Reason</p>
              <p className="text-body-sm">{sheet.routeReasonDetail}</p>
            </div>
          )}
          {sheet.citedClause && (
            <CitedClause policyName={sheet.citedClause.policyName} text={sheet.citedClause.text} />
          )}
          {sheet.llmConfidence != null && (
            <p className="font-mono text-label-md text-on-surface-variant">
              LLM confidence: {sheet.llmConfidence} · policy {sheet.policyVersionUsed}
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
    </>
  );

  return embedded ? content : <Card className="rounded-xl p-6 shadow-sm">{content}</Card>;
}
