/**
 * Domain model — mirrors the backend data model (SCOPING.md §12.1) and the
 * status glossary (§F). These TypeScript types are the contract the mock API
 * implements today and the real FastAPI/Pydantic backend will implement later.
 */

export type Role = "employee" | "manager" | "finance" | "admin";

export const ROLE_LABELS: Record<Role, string> = {
  employee: "Employee",
  manager: "Manager",
  finance: "Finance",
  admin: "Admin",
};

// ── Status machines ──────────────────────────────────────────────────────────

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
  | "PAID"
  | "WITHDRAWN";

export type LineItemStatus =
  | "PENDING_MANAGER"
  | "MANAGER_APPROVED"
  | "MANAGER_REJECTED"
  | "INFO_REQUESTED"
  | "POLICY_PASS"
  | "POLICY_FAIL"
  | "POLICY_UNCERTAIN";

export type FinanceDecision =
  | "APPROVED"
  | "REJECTED_WITH_COMMENTS"
  | "ROUTED_TO_HUMAN";

/** Why the LLM Finance Approver routed a sheet to a human (SCOPING.md §6.3). */
export type RouteReason =
  | "LOW_CONFIDENCE"
  | "AMBIGUOUS_CLAUSE"
  | "MISSING_POLICY"
  | "NUMERIC_DISAGREEMENT";

// ── Categories (classifier output enum, SCOPING.md §20.A) ────────────────────

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

export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number];

export const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "INR"] as const;
export type Currency = (typeof CURRENCIES)[number];

// ── Entities ─────────────────────────────────────────────────────────────────

export type AgencyStatus = "active" | "suspended" | "soft_deleted";
export type AgencyTier = "Enterprise" | "Pro" | "Basic";

export interface Agency {
  id: string;
  name: string;
  status: AgencyStatus;
  tier: AgencyTier;
  userCount: number;
  createdBy: string;
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  agencyId: string;
  avatarUrl?: string;
}

export interface AgencyPolicyDocument {
  id: string;
  agencyId: string;
  name: string;
  version: string;
  effectiveDate: string;
  indexedAt: string;
  status: "active" | "draft" | "archived";
  createdBy: string;
  publishedBy?: string;
}

export type ScanStatus = "pending" | "clean" | "infected" | "failed";
export type OcrStatus = "pending" | "done" | "failed";

export interface Attachment {
  id: string;
  lineItemId: string;
  fileName: string;
  fileType: string;
  sizeBytes: number;
  scanStatus: ScanStatus;
  ocrStatus: OcrStatus;
}

/** Deterministic intake-tier check results (SCOPING.md §6.1). */
export interface ClaimChecks {
  policyResult: "pass" | "fail" | "warning";
  categoryConfidence: number;
  duplicateRisk: number;
  reconciles: boolean;
  failedChecks: string[];
}

export interface LineItem {
  id: string;
  sheetId: string;
  merchant: string;
  description: string;
  category: ExpenseCategory;
  /** Free-text specification when category is "Other". */
  categoryOther?: string;
  amount: number;
  currency: Currency;
  expenseDate: string;
  receiptDatetime?: string;
  receiptTotal?: number;
  tax?: number;
  managerStatus: LineItemStatus;
  managerReason?: string;
  policyStatus?: LineItemStatus;
  policyClauseRef?: string;
  /** AI-surfaced intake/finance flag shown inline in the grids. */
  aiFlag?: {
    message: string;
    clauseRef: string;
    severity: "warning" | "error";
  };
  attachments: Attachment[];
  checks?: ClaimChecks;
}

export interface SheetDecision {
  id: string;
  sheetId: string;
  actorId: string;
  actorName: string;
  actorRole: Role | "llm_approver";
  action: string;
  reason?: string;
  llmModelVersion?: string;
  policyVersion?: string;
  timestamp: string;
}

export interface ExpenseSheet {
  id: string;
  title: string;
  employeeId: string;
  employeeName: string;
  agencyId: string;
  agencyName: string;
  version: number;
  status: SheetStatus;
  period: string;
  total: number;
  currency: Currency;
  submittedAt?: string;
  updatedAt: string;
  financeDecision?: FinanceDecision;
  financeDecidedBy?: string;
  policyVersionUsed?: string;
  routeReason?: RouteReason;
  routeReasonDetail?: string;
  llmConfidence?: number;
  citedClause?: { policyName: string; text: string };
  lineItems: LineItem[];
}

export interface AuditLogEntry {
  id: string;
  actorId: string;
  actorName: string;
  /** Role that performed the action — drives per-user activity scoping.
   *  `llm_approver` is the AI Finance Approver; `system` is the platform. */
  actorRole: Role | "llm_approver" | "system";
  action: string;
  entity: string;
  summary: string;
  reference?: string;
  hash?: string;
  timestamp: string;
  severity: "info" | "success" | "warning" | "error";
}

// ── Baseline policy (intake tier, structured JSON, SCOPING.md §20.B) ──────────

export interface BaselinePolicy {
  per_meal_limit: number;
  per_hotel_night_limit: number;
  prohibited_categories: string[];
  receipt_required_threshold: number;
  submission_cutoff: string;
  max_file_mb: number;
  allowed_extensions: string[];
  duplicate_near_match_days: number;
  cap_boundary: "inclusive" | "exclusive";
  llm_confidence_routing_threshold: number;
  currency: Currency;
}

// ── Dashboard aggregates ─────────────────────────────────────────────────────

export interface EmployeeKpis {
  reimbursedThisMonth: number;
  pendingApprovalValue: number;
  pendingApprovalCount: number;
  draftsValue: number;
}

export interface FinanceKpis {
  autoApprovalRate: number;
  autoApprovalDelta: number;
  manualInterventions: number;
  manualInterventionsDelta: number;
  policyCitations: number;
  topClause: string;
  ragSyncedAgo: string;
  // ── AI Approver performance (enterprise analytics, SCOPING.md §6.5) ──
  /** % of AI decisions upheld when sampled on audit. */
  approvalAccuracy: number;
  /** % of sheets the AI routed to a human instead of auto-deciding. */
  escalationRate: number;
  /** % of routed sheets a human approved unchanged (AI was over-cautious). */
  falsePositiveRate: number;
  /** % of routed sheets resolved within the SLA window. */
  slaCompliance: number;
  /** Mean hours from route → finance decision. */
  avgResolutionHours: number;
  /** % of paid sheets fully policy-compliant. */
  policyComplianceRate: number;
}

export interface SpendByCategory {
  category: ExpenseCategory;
  amount: number;
}

// ── Notifications ────────────────────────────────────────────────────────────

export type NotificationKind = "success" | "warning" | "error" | "info";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  icon: string;
  title: string;
  body: string;
  href?: string;
  timestamp: string;
  read: boolean;
  /** Who should see it (omit = all roles). */
  roles?: Role[];
}
