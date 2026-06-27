import type { Role } from "@/data/types";

/**
 * RBAC + navigation config. The UI renders only what a role can actually
 * access — anything inaccessible is omitted entirely (never shown disabled).
 * Authoritative checks live in the API (defense-in-depth, SCOPING.md §3.3).
 */

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}

/** A sectioned group of nav items. An untitled group renders as a top "home" block. */
export interface NavGroup {
  title?: string;
  items: NavItem[];
}

export const PORTAL_BASE: Record<Role, string> = {
  employee: "/employee",
  manager: "/manager",
  finance: "/finance",
  admin: "/admin",
};

// Grouped, sectioned navigation (enterprise pattern: Microsoft / Atlassian /
// ServiceNow). The UI renders only what a role can access; nothing is shown
// locked. Authoritative checks live in the API (SCOPING.md §3.3).
const NAV: Record<Role, NavGroup[]> = {
  employee: [
    { items: [{ label: "Dashboard", href: "/employee", icon: "dashboard" }] },
    {
      title: "Expenses",
      items: [
        { label: "My Expense Sheets", href: "/employee/sheets", icon: "description" },
        { label: "My Receipts", href: "/employee/receipts", icon: "receipt_long" },
        { label: "Insights", href: "/employee/insights", icon: "insights" },
      ],
    },
    {
      title: "Account",
      items: [
        { label: "My Activity", href: "/employee/activity", icon: "history" },
        { label: "Settings", href: "/employee/settings", icon: "settings" },
      ],
    },
  ],
  manager: [
    { items: [{ label: "Review Queue", href: "/manager", icon: "fact_check" }] },
    {
      title: "Insights",
      items: [
        { label: "Team Insights", href: "/manager/insights", icon: "insights" },
        { label: "Policy Assistant", href: "/manager/assistant", icon: "smart_toy" },
      ],
    },
    {
      title: "Operations",
      items: [{ label: "My Activity", href: "/manager/audit", icon: "history" }],
    },
  ],
  finance: [
    {
      title: "Policy",
      items: [
        { label: "Policy Console", href: "/finance", icon: "gavel" },
        { label: "Policy Assistant", href: "/finance/assistant", icon: "smart_toy" },
      ],
    },
    {
      title: "Operations",
      items: [
        { label: "Analytics", href: "/finance/insights", icon: "insights" },
        { label: "Expense Sheets", href: "/finance/sheets", icon: "description" },
        { label: "Audit Logs", href: "/finance/audit", icon: "history" },
      ],
    },
  ],
  // Admin is the platform administrator: onboarding & managing users and agencies.
  // No policy or operational reporting (those belong to Finance/Manager).
  admin: [
    {
      title: "Administration",
      items: [{ label: "Users & Agencies", href: "/admin", icon: "group" }],
    },
    {
      title: "Oversight",
      items: [{ label: "Audit Logs", href: "/finance/audit", icon: "history" }],
    },
  ],
};

export function getNav(role: Role): NavGroup[] {
  return NAV[role];
}

/** Which portals each role may switch into (top-nav role switcher). */
export const ROLE_VIEW_ACCESS: Record<Role, Role[]> = {
  employee: ["employee"],
  manager: ["employee", "manager"],
  finance: ["employee", "manager", "finance"],
  admin: ["employee", "manager", "finance", "admin"],
};

/** Capability matrix (SCOPING.md §3.2), used for fine-grained UI gating. */
export type Capability =
  | "submit_sheet"
  | "view_own_sheets"
  | "view_agency_sheets"
  | "view_all_sheets"
  | "manager_action"
  | "finance_decision"
  | "override_llm"
  | "update_policy_document"
  | "manage_agencies"
  | "manage_users"
  | "view_audit_log";

// Submitting an expense sheet is employee-only (per product decision) — managers,
// finance, and admin do not create/submit sheets.
const CAPABILITIES: Record<Role, Capability[]> = {
  employee: ["submit_sheet", "view_own_sheets"],
  manager: ["view_own_sheets", "view_agency_sheets", "manager_action"],
  finance: [
    "view_own_sheets",
    "view_all_sheets",
    "finance_decision",
    "override_llm",
    "update_policy_document",
    "view_audit_log",
  ],
  admin: [
    "view_own_sheets",
    "view_all_sheets",
    "override_llm",
    "update_policy_document",
    "manage_agencies",
    "manage_users",
    "view_audit_log",
  ],
};

export function can(role: Role, capability: Capability): boolean {
  return CAPABILITIES[role].includes(capability);
}

/** Derive the active portal role from the current pathname. */
export function roleFromPath(pathname: string): Role {
  if (pathname.startsWith("/manager")) return "manager";
  if (pathname.startsWith("/finance")) return "finance";
  if (pathname.startsWith("/admin")) return "admin";
  return "employee";
}
