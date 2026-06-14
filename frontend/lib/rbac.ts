// REFERENCE SCAFFOLD ONLY — see README.md.
//
// ⚠️ CLIENT-SIDE PERMISSION HELPERS — NOT A SECURITY BOUNDARY.
// These mirror the permission matrix in SCOPING.md §3.2 purely for UI affordances
// (render only the actions a user is allowed to attempt). The FastAPI backend is
// AUTHORITATIVE: it re-enforces RBAC + agency scope at the route, data-query, and
// RAG-retrieval layers (SCOPING §3.3). Never trust this code for access control.

import type { Role } from "@/types";

// Capability keys mirror the rows of the §3.2 matrix.
export type Capability =
  | "submitOwnSheet"
  | "viewOwnSheets"
  | "viewSheets" // scope handled separately (own-agency vs all)
  | "managerLineItemAction" // approve / reject / request-info per line item
  | "financeDecision" // approve / reject / route (manual + handles routed)
  | "overrideLlmDecision"
  | "updateAgencyPolicyDoc"
  | "manageAgencies" // create policy / onboard / delete agency
  | "manageUsers"
  | "viewAuditLog";

// Direct transcription of SCOPING §3.2. LLM Approver omitted — it is a backend agent.
const MATRIX: Record<Capability, Role[]> = {
  submitOwnSheet: ["employee", "manager", "finance", "admin"],
  viewOwnSheets: ["employee", "manager", "finance", "admin"],
  viewSheets: ["manager", "finance", "admin"], // manager = own agency only (see sheetViewScope)
  managerLineItemAction: ["manager"],
  financeDecision: ["finance", "admin"],
  overrideLlmDecision: ["finance", "admin"],
  updateAgencyPolicyDoc: ["finance", "admin"],
  manageAgencies: ["admin"],
  manageUsers: ["admin"],
  viewAuditLog: ["finance", "admin"],
};

export function can(role: Role, capability: Capability): boolean {
  return MATRIX[capability]?.includes(role) ?? false;
}

// Scope of "view sheets": managers are agency-scoped (SCOPING §3.2, §3.3, §19 #1).
export type ViewScope = "none" | "own-agency" | "all";

export function sheetViewScope(role: Role): ViewScope {
  switch (role) {
    case "manager":
      return "own-agency";
    case "finance":
    case "admin":
      return "all";
    case "employee":
    default:
      return "none"; // employees see only their OWN sheets, handled by viewOwnSheets
  }
}

// Segregation of duties helpers (SCOPING §3.3) — also re-enforced server-side.
// A manager cannot approve their OWN line items.
export function managerCanActOnItem(
  role: Role,
  managerUserId: string,
  itemSubmitterId: string,
): boolean {
  return can(role, "managerLineItemAction") && managerUserId !== itemSubmitterId;
}

// A finance user cannot override a decision on THEIR OWN sheet.
export function financeCanOverride(
  role: Role,
  financeUserId: string,
  sheetEmployeeId: string,
): boolean {
  return can(role, "overrideLlmDecision") && financeUserId !== sheetEmployeeId;
}

// The default landing route for each role (used by app/page.tsx redirect).
export function defaultDashboardPath(role: Role): string {
  return `/${role}`;
}
