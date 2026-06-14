// REFERENCE SCAFFOLD ONLY — see README.md.
// Shared domain types for the portal. These MIRROR the backend Pydantic/SQLModel
// models and the status glossary in SCOPING.md §F. The server is authoritative;
// these exist so the UI is typed and self-documenting.

// ---- Roles (SCOPING §3) ----
// Four human roles. The "LLM Approver Agent" is a backend worker, not a human UI role.
export type Role = "employee" | "manager" | "finance" | "admin";

// ---- Sheet status (SCOPING §F / §5.1 state machine) ----
export type SheetStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "IN_MANAGER_REVIEW"
  | "RETURNED_TO_EMPLOYEE"
  | "IN_FINANCE_REVIEW"
  | "FINANCE_APPROVED"
  | "FINANCE_REJECTED"
  | "FINANCE_MANUAL_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "PAID";

// ---- Line-item status (SCOPING §F / §5.1) ----
// Manager stage → Finance (policy) stage.
export type LineItemStatus =
  | "PENDING_MANAGER"
  | "MANAGER_APPROVED"
  | "MANAGER_REJECTED"
  | "INFO_REQUESTED"
  | "POLICY_PASS"
  | "POLICY_FAIL"
  | "POLICY_UNCERTAIN";

// ---- Finance decision emitted by the LLM approver (SCOPING §F / §6.3) ----
export type FinanceDecision =
  | "APPROVED"
  | "REJECTED_WITH_COMMENTS"
  | "ROUTED_TO_HUMAN";

// ---- Expense categories (classifier enum, SCOPING §20.A) ----
export type ExpenseCategory =
  | "Meals & Entertainment"
  | "Travel - Air"
  | "Travel - Hotel"
  | "Travel - Ground"
  | "Office Supplies"
  | "Software / Subscriptions"
  | "Client Entertainment"
  | "Other";

// Allowed attachment extensions (SCOPING §6.1 allow-list).
export type AllowedExtension =
  | ".pdf"
  | ".jpeg"
  | ".jpg"
  | ".heic"
  | ".png"
  | ".docx"
  | ".doc";

export interface Agency {
  id: string;
  name: string;
  status: "active" | "soft-deleted";
}

// Every authenticated user has exactly one role + exactly one agency (SCOPING §3).
export interface SessionUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  agencyId: string;
  agencyName?: string;
}

export interface Attachment {
  id: string;
  lineItemId: string;
  fileName: string;
  fileType: AllowedExtension | string;
  sizeBytes: number;
  blobUri?: string;
  scanStatus: "pending" | "clean" | "infected" | "error";
  ocrStatus: "pending" | "done" | "failed";
}

export interface LineItem {
  id: string;
  sheetId: string;
  category: ExpenseCategory;
  amount: number;
  currency: string; // ISO 4217, e.g. "USD"
  expenseDate: string; // ISO date
  merchant: string;
  description: string;
  receiptDatetime?: string; // ISO datetime — part of the duplicate unique key
  receiptTotal?: number; // parsed total — part of the duplicate unique key
  // Manager (Line 2) verdict
  managerStatus: LineItemStatus;
  managerActorId?: string;
  managerReason?: string;
  // Finance/LLM (Line 3) verdict
  policyStatus?: Extract<
    LineItemStatus,
    "POLICY_PASS" | "POLICY_FAIL" | "POLICY_UNCERTAIN"
  >;
  policyClauseRef?: string; // cited agency policy clause
  attachments: Attachment[];
}

export interface ExpenseSheet {
  id: string; // STABLE across resubmissions (SCOPING §5.1, §19 #4)
  version: number; // increments each resubmission
  employeeId: string;
  agencyId: string;
  status: SheetStatus;
  period: string; // e.g. "2026-06"
  submittedAt?: string;
  financeDecision?: FinanceDecision;
  financeDecidedBy?: string;
  policyVersionUsed?: string; // version pinned at submission time (SCOPING §7)
  lineItems: LineItem[];
}
