// REFERENCE SCAFFOLD ONLY — see README.md.
// Zod schemas for client-side form validation (React Hook Form). These MIRROR the
// server Pydantic v2 models (SCOPING §9.1 "defense-in-depth: Zod client + Pydantic
// server, authoritative"). The server re-validates; client validation is UX only.

import { z } from "zod";

export const EXPENSE_CATEGORIES = [
  "Meals & Entertainment",
  "Travel - Air",
  "Travel - Hotel",
  "Travel - Ground",
  "Office Supplies",
  "Software / Subscriptions",
  "Client Entertainment",
  "Other",
] as const;

export const ALLOWED_EXTENSIONS = [
  ".pdf",
  ".jpeg",
  ".jpg",
  ".heic",
  ".png",
  ".docx",
  ".doc",
] as const;

// Baseline thresholds (SCOPING §20.B) — illustrative; real values come from the
// agency's baseline policy JSON served by the backend.
export const MAX_FILE_MB = 25;

// ---- Line item ----
export const lineItemSchema = z.object({
  category: z.enum(EXPENSE_CATEGORIES),
  amount: z.number().positive("Amount must be greater than 0"), // amount ≤ 0 rejected (§6.1)
  currency: z
    .string()
    .length(3, "Use a 3-letter ISO currency code")
    .toUpperCase(),
  expenseDate: z.string().refine((d) => !Number.isNaN(Date.parse(d)), {
    message: "Invalid date",
  }),
  merchant: z.string().min(1, "Merchant is required"),
  description: z.string().min(1, "Description is required"),
  // Receipt fields participate in the duplicate unique key
  // (employee, receipt_datetime, receipt_total) — SCOPING §6.1.
  receiptDatetime: z.string().optional(),
  receiptTotal: z.number().nonnegative().optional(),
});

export type LineItemInput = z.infer<typeof lineItemSchema>;

// ---- Expense sheet ----
// TODO(reference): the server additionally enforces — month-end submission cutoff
// (§19 #6), receipt-required threshold (§6.1), reconciliation, and duplicate checks.
// Those are AUTHORITATIVE on the backend and intentionally NOT fully replicated here.
export const expenseSheetSchema = z.object({
  period: z
    .string()
    .regex(/^\d{4}-\d{2}$/, "Period must be YYYY-MM"),
  lineItems: z
    .array(lineItemSchema)
    .min(1, "A sheet must have at least one line item"), // no empty sheets (§8)
});

export type ExpenseSheetInput = z.infer<typeof expenseSheetSchema>;

// ---- Manager per-line-item action (Line 2, §6.2) ----
export const managerActionSchema = z.object({
  lineItemId: z.string(),
  action: z.enum(["approve", "reject", "request-info"]),
  reason: z.string().optional(),
});

export type ManagerActionInput = z.infer<typeof managerActionSchema>;

// ---- Finance override (§6.3) ----
export const financeOverrideSchema = z.object({
  sheetId: z.string(),
  decision: z.enum(["APPROVED", "REJECTED"]),
  reason: z.string().min(1, "An override reason is required"), // override must be logged
});

export type FinanceOverrideInput = z.infer<typeof financeOverrideSchema>;
