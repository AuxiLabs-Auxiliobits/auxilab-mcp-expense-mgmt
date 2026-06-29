import { z } from "zod";
import { CURRENCIES, EXPENSE_CATEGORIES } from "@/data/types";

/**
 * Client-side validation schemas (React Hook Form + Zod). These mirror the
 * authoritative server Pydantic models — defense-in-depth, SCOPING.md §9.1.
 */

export const loginSchema = z.object({
  email: z.string().email("Enter a valid work email"),
  password: z.string().min(1, "Password is required"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const newSheetSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Sheet title is required")
    .min(3, "Give the sheet a descriptive title (min 3 characters)")
    .max(50, "Keep the title under 50 characters"),
  period: z.string().min(1, "Select the expense period"),
});
export type NewSheetValues = z.infer<typeof newSheetSchema>;

const optionalNumber = z.preprocess(
  (v) => (v === "" || v === null || v === undefined ? undefined : v),
  z.coerce.number().positive().optional(),
);

// Tax / VAT — optional, and zero is valid (plenty of receipts carry no tax).
const optionalNonNegative = z.preprocess(
  (v) => (v === "" || v === null || v === undefined ? undefined : v),
  z.coerce.number().nonnegative("Tax can't be negative").optional(),
);

export const lineItemSchema = z
  .object({
    merchant: z.string().min(1, "Merchant is required"),
    description: z.string().min(1, "Description is required"),
    category: z.enum(EXPENSE_CATEGORIES),
    categoryOther: z.string().optional(),
    // Receipt-style amounts: subtotal (pre-tax) is required, tax is optional, and the line
    // TOTAL = subtotal + tax (computed by the form, stored as the claim `amount`).
    subtotal: z.coerce
      .number({ message: "Subtotal is required" })
      .positive("Subtotal must be greater than 0"),
    tax: optionalNonNegative,
    currency: z.enum(CURRENCIES),
    expenseDate: z.string().min(1, "Expense date is required"),
    receiptDatetime: z.string().min(1, "Receipt date & time is required"),
    receiptTotal: optionalNumber,
  })
  // Picking the "Other" catch-all requires specifying what it actually is.
  .superRefine((val, ctx) => {
    if (val.category === "Other" && !val.categoryOther?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["categoryOther"],
        message: 'Specify the expense type for "Other".',
      });
    }
    // The receipt's calendar date must match the expense date (time of day may differ).
    if (val.expenseDate && val.receiptDatetime?.slice(0, 10) !== val.expenseDate) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["receiptDatetime"],
        message: "Receipt date must match the expense date.",
      });
    }
    // If the receipt total is entered, it must equal subtotal + tax (no mismatch).
    if (val.receiptTotal != null && val.subtotal != null) {
      const computed = val.subtotal + (val.tax ?? 0);
      if (Math.abs(val.receiptTotal - computed) > 0.01) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["receiptTotal"],
          message: `Receipt total should equal subtotal + tax (${computed.toFixed(2)}).`,
        });
      }
    }
  });
export type LineItemValues = z.infer<typeof lineItemSchema>;

export const financeOverrideSchema = z.object({
  decision: z.enum(["APPROVED", "REJECTED_WITH_COMMENTS"]),
  reason: z
    .string()
    .min(10, "A mandatory override reason is required for the audit log"),
});
export type FinanceOverrideValues = z.infer<typeof financeOverrideSchema>;

export const roleAssignmentSchema = z.object({
  email: z.string().email("Enter a valid work email"),
  role: z.enum(["employee", "manager", "finance", "admin"]),
});
export type RoleAssignmentValues = z.infer<typeof roleAssignmentSchema>;
