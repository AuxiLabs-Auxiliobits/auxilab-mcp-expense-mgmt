import { endOfMonth, isAfter, parseISO } from "date-fns";
import type {
  BaselinePolicy,
  Currency,
  ExpenseCategory,
  LineItem,
} from "@/data/types";

/**
 * Client-side intake checks (Line 1 — deterministic, SCOPING.md §6.1 + §20.B).
 * Mirrors the server's authoritative checks for fast feedback as the employee
 * fills the form (defense-in-depth, §9.1).
 */
export interface IntakeIssue {
  level: "error" | "warning";
  message: string;
  clauseRef: string;
}

export interface LineItemDraft {
  merchant: string;
  description: string;
  category: ExpenseCategory;
  categoryOther?: string;
  amount: number;
  currency: Currency;
  expenseDate: string; // yyyy-mm-dd
  receiptDatetime?: string;
  receiptTotal?: number;
  tax?: number;
  attachments: { fileName: string; fileType: string; sizeBytes: number }[];
}

/** File allow-list / size / empty checks — run on upload (§6.1 File). */
export function fileIssue(file: File, policy: BaselinePolicy): string | null {
  const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
  if (!policy.allowed_extensions.includes(ext)) {
    return `Unsupported file type "${ext}". Allowed: ${policy.allowed_extensions.join(" ")}`;
  }
  if (file.size === 0) return "File is empty (0 bytes).";
  if (file.size > policy.max_file_mb * 1024 * 1024) {
    return `File exceeds the ${policy.max_file_mb} MB limit.`;
  }
  return null;
}

/** Non-blocking advisory for a file (HEIC conversion, etc.). */
export function fileNote(fileName: string): string | null {
  const ext = "." + (fileName.split(".").pop() ?? "").toLowerCase();
  if (ext === ".heic") return "HEIC will be converted to JPEG on upload.";
  if (ext === ".pdf") return null; // encrypted/password-protected PDFs are rejected server-side
  return null;
}

/** Data + duplicate checks for a single line item (§6.1 Data / Duplicate). */
export function validateLineItem(
  draft: LineItemDraft,
  policy: BaselinePolicy,
  siblings: LineItem[] = [],
  now: Date = new Date(),
): IntakeIssue[] {
  const issues: IntakeIssue[] = [];

  if (!(draft.amount > 0)) {
    issues.push({ level: "error", message: "Amount must be greater than 0.", clauseRef: "BASE-AMT" });
  }

  if (policy.prohibited_categories.includes(draft.category)) {
    // "Other" is the catch-all: allowed once the user specifies what it is;
    // unspecified, it stays prohibited. Any other prohibited category is hard-blocked.
    if (draft.category === "Other") {
      if (!draft.categoryOther?.trim()) {
        issues.push({
          level: "error",
          message: 'Specify the expense type for "Other".',
          clauseRef: "BASE-PROHIBITED",
        });
      }
    } else {
      issues.push({
        level: "error",
        message: `"${draft.category}" is a prohibited category.`,
        clauseRef: "BASE-PROHIBITED",
      });
    }
  }

  if (draft.expenseDate) {
    const exp = parseISO(draft.expenseDate);
    if (isAfter(exp, now)) {
      issues.push({ level: "error", message: "Expense date is in the future.", clauseRef: "BASE-DATE" });
    } else if (isAfter(now, endOfMonth(exp))) {
      issues.push({
        level: "warning",
        message: "Past the month-end submission cutoff for the incurred month.",
        clauseRef: "BASE-CUTOFF",
      });
    }
  }

  if (draft.amount > policy.receipt_required_threshold && draft.attachments.length === 0) {
    issues.push({
      level: "error",
      message: `A receipt is required for amounts over $${policy.receipt_required_threshold}.`,
      clauseRef: "BASE-RECEIPT",
    });
  }

  if (draft.category === "Meals & Entertainment" && draft.amount > policy.per_meal_limit) {
    issues.push({
      level: "warning",
      message: `Exceeds the per-meal limit ($${policy.per_meal_limit}).`,
      clauseRef: "BASE-MEAL",
    });
  }

  if (
    draft.category === "Travel - Hotel" &&
    draft.amount > policy.per_hotel_night_limit
  ) {
    issues.push({
      level: "warning",
      message: `Exceeds the per-hotel-night limit ($${policy.per_hotel_night_limit}) — verify nights.`,
      clauseRef: "BASE-HOTEL",
    });
  }

  if (draft.tax != null) {
    if (draft.tax < 0) {
      issues.push({ level: "error", message: "Tax cannot be negative.", clauseRef: "BASE-TAX" });
    } else if (draft.tax > draft.amount) {
      issues.push({
        level: "error",
        message: "Tax cannot exceed the expense amount.",
        clauseRef: "BASE-TAX",
      });
    }
  }

  if (draft.receiptTotal != null && Math.abs(draft.receiptTotal - draft.amount) > 0.01) {
    issues.push({
      level: "warning",
      message: `Entered amount doesn't reconcile with the receipt total ($${draft.receiptTotal.toFixed(2)}).`,
      clauseRef: "BASE-RECON",
    });
  }

  const duplicate = siblings.some(
    (s) =>
      s.receiptDatetime &&
      draft.receiptDatetime &&
      s.receiptDatetime === draft.receiptDatetime &&
      Math.abs((s.receiptTotal ?? s.amount) - draft.amount) < 0.01,
  );
  if (duplicate) {
    issues.push({
      level: "warning",
      message: "Possible duplicate of another line item (same receipt date & total).",
      clauseRef: "DUP-01",
    });
  }

  return issues;
}

/** Reduce issues to the single inline flag shown on a line-item row. */
export function toAiFlag(issues: IntakeIssue[]): LineItem["aiFlag"] {
  const chosen = issues.find((i) => i.level === "error") ?? issues[0];
  if (!chosen) return undefined;
  return {
    message: chosen.message,
    clauseRef: chosen.clauseRef,
    severity: chosen.level === "error" ? "error" : "warning",
  };
}
