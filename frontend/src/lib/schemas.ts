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
    .min(3, "Give the sheet a descriptive title (min 3 characters)")
    .max(50, "Keep the title under 50 characters"),
  period: z.string().min(1, "Select the expense period"),
});
export type NewSheetValues = z.infer<typeof newSheetSchema>;

const optionalNumber = z.preprocess(
  (v) => (v === "" || v === null || v === undefined ? undefined : v),
  z.coerce.number().positive().optional(),
);

export const lineItemSchema = z
  .object({
    merchant: z.string().min(1, "Merchant is required"),
    description: z.string().min(1, "Description is required"),
    category: z.enum(EXPENSE_CATEGORIES),
    categoryOther: z.string().optional(),
    amount: z.coerce
      .number({ message: "Amount is required" })
      .positive("Amount must be greater than 0"),
    currency: z.enum(CURRENCIES),
    expenseDate: z.string().min(1, "Expense date is required"),
    receiptDatetime: z.string().min(1, "Receipt date & time is required"),
    receiptTotal: optionalNumber,
    tax: optionalNumber,
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
