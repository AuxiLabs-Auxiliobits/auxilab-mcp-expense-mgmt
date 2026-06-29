"use client";

import type { ExpenseSheet } from "@/data/types";
import { formatDateTimeIST } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import { LiveDot } from "@/components/shared/live-dot";

// ── Types ────────────────────────────────────────────────────────────────────

export type StepState = "done" | "active" | "error" | "upcoming";

export interface TimelineStep {
  key: string;
  label: string;
  icon: string;
  state: StepState;
  detail?: string;
}

// ── Tone map (state → Tailwind classes) ──────────────────────────────────────

export const STEP_TONE: Record<StepState, { ring: string; bg: string; text: string; bar: string }> = {
  done: {
    ring: "border-success-green/40",
    bg: "bg-success-green/10 text-success-green",
    text: "text-on-surface",
    bar: "bg-success-green/40",
  },
  active: {
    ring: "border-primary/50",
    bg: "bg-primary/10 text-primary",
    text: "text-on-surface",
    bar: "bg-outline-variant",
  },
  error: {
    ring: "border-error/40",
    bg: "bg-error-container text-on-error-container",
    text: "text-on-surface",
    bar: "bg-outline-variant",
  },
  upcoming: {
    ring: "border-outline-variant",
    bg: "bg-surface-container-high text-on-surface-variant",
    text: "text-on-surface-variant",
    bar: "bg-outline-variant",
  },
};

// ── Builder — maps any SheetStatus to the four-step rail ─────────────────────

export function buildTimeline(sheet: ExpenseSheet): TimelineStep[] {
  const s = sheet.status;
  const submitted = s !== "DRAFT" && s !== "WITHDRAWN";

  const draftDone = s !== "DRAFT";
  const managerReturned = s === "RETURNED_TO_EMPLOYEE" || s === "REJECTED";
  const managerDone = [
    "IN_FINANCE_REVIEW", "FINANCE_APPROVED", "FINANCE_REJECTED",
    "FINANCE_MANUAL_REVIEW", "APPROVED", "PAID",
  ].includes(s);

  const routed = s === "FINANCE_MANUAL_REVIEW";
  const aiRejected = s === "FINANCE_REJECTED";
  const aiDone = ["FINANCE_APPROVED", "APPROVED", "PAID"].includes(s) || routed;

  const paidDone = s === "PAID";
  const finalApproved = ["FINANCE_APPROVED", "APPROVED", "PAID"].includes(s);

  const submitState: StepState = s === "DRAFT" ? "active" : "done";

  let managerState: StepState = "upcoming";
  if (managerReturned) managerState = "error";
  else if (managerDone) managerState = "done";
  else if (submitted) managerState = "active";

  let aiState: StepState = "upcoming";
  if (aiRejected) aiState = "error";
  else if (aiDone) aiState = "done";
  else if (s === "IN_FINANCE_REVIEW") aiState = "active";

  let financeState: StepState = "upcoming";
  if (finalApproved) financeState = "done";
  else if (routed) financeState = "active";
  else if (s === "FINANCE_REJECTED") financeState = "error";

  void draftDone;
  void managerDone;

  return [
    {
      key: "submitted",
      label: "Submitted",
      icon: "send",
      state: submitState,
      detail: sheet.submittedAt ? formatDateTimeIST(sheet.submittedAt) : "Not yet submitted",
    },
    {
      key: "manager",
      label: "Manager Review",
      icon: "supervisor_account",
      state: managerState,
      detail:
        managerState === "error"
          ? "Returned for changes"
          : managerState === "done"
            ? "Approved per line item"
            : managerState === "active"
              ? "In review"
              : "Pending",
    },
    {
      key: "ai",
      label: "AI Finance Approver",
      icon: "smart_toy",
      state: aiState,
      detail:
        aiState === "error"
          ? "Auto-rejected"
          : routed
            ? "Routed to a human"
            : aiState === "done"
              ? "Auto-approved"
              : aiState === "active"
                ? "Evaluating policy"
                : "Pending",
    },
    {
      key: "finance",
      label: paidDone ? "Paid" : "Finance Decision",
      icon: paidDone ? "paid" : "account_balance",
      state: paidDone ? "done" : financeState,
      detail:
        paidDone
          ? "Reimbursed"
          : finalApproved
            ? "Approved"
            : financeState === "error"
              ? "Rejected"
              : financeState === "active"
                ? "Manual review"
                : "Pending",
    },
  ];
}

// ── Render ────────────────────────────────────────────────────────────────────

export function SheetTimeline({ sheet }: { sheet: ExpenseSheet }) {
  const steps = buildTimeline(sheet);
  return (
    <div
      className="border-t border-outline-variant bg-surface-container-low px-4 py-4 md:px-6"
      aria-label="Sheet status timeline"
    >
      <ol className="flex flex-col gap-4 sm:flex-row sm:items-stretch sm:gap-0">
        {steps.map((step, i) => {
          const tone = STEP_TONE[step.state];
          const last = i === steps.length - 1;
          return (
            <li
              key={step.key}
              className="flex flex-1 items-start gap-3 sm:flex-col sm:items-stretch sm:gap-2"
            >
              <div className="flex items-center gap-3 sm:gap-2">
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                    tone.ring,
                    tone.bg,
                  )}
                  aria-hidden
                >
                  <Icon
                    name={
                      step.state === "done"
                        ? "check"
                        : step.state === "error"
                          ? "priority_high"
                          : step.icon
                    }
                    className="text-[18px]"
                  />
                </span>
                {!last && (
                  <span className={cn("hidden h-0.5 flex-1 rounded sm:block", tone.bar)} aria-hidden />
                )}
              </div>
              <div className="min-w-0 sm:pr-4">
                <div className={cn("flex items-center gap-1.5 text-body-sm font-medium", tone.text)}>
                  {step.label}
                  {step.state === "active" && <LiveDot tone="primary" />}
                </div>
                <div className="font-mono text-label-sm text-on-surface-variant">{step.detail}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
