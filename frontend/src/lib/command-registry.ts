/**
 * RBAC-aware command registry for the global command palette.
 *
 * Commands are derived per-role so a user only ever sees what they can actually do:
 *  - Navigation comes straight from the role's authoritative nav (`getNav`) — real pages only.
 *  - Quick actions / AI are gated by role + capability matrix (`can`).
 * `keywords` carry natural-language synonyms so queries like "create expense" or
 * "finance queue" resolve to the right command (Phase 8).
 */

import type { Role } from "@/data/types";
import { can, getNav } from "@/lib/rbac";

export type CommandKind = "navigation" | "action" | "ai" | "system";

export interface AppCommand {
  id: string;
  label: string;
  group: string;
  icon: string;
  kind: CommandKind;
  href?: string;
  intent?: "toggle-theme" | "sign-out";
  keywords?: string[];
  shortcut?: string;
}

/** Roles that have a Policy Assistant page (employees + admin use widget only). */
function assistantHref(role: Role): string | null {
  if (role === "manager") return "/manager/assistant";
  if (role === "finance") return "/finance/assistant";
  return null;
}

export function buildCommands(role: Role): AppCommand[] {
  const cmds: AppCommand[] = [];

  // ── Navigation (authoritative, role-scoped, real pages only) ──
  for (const group of getNav(role)) {
    for (const item of group.items) {
      cmds.push({
        id: `nav:${item.href}`,
        label: item.label,
        group: "Navigation",
        icon: item.icon,
        kind: "navigation",
        href: item.href,
      });
    }
  }

  // ── Quick actions ──
  if (can(role, "submit_sheet")) {
    cmds.push(
      { id: "act:new-sheet", label: "Create Expense Sheet", group: "Quick Actions", icon: "add", kind: "action", href: "/employee/sheets/new", shortcut: "N", keywords: ["create expense", "new expense", "add expense", "new sheet", "start claim"] },
      { id: "act:upload-receipt", label: "Upload Receipt", group: "Quick Actions", icon: "upload_file", kind: "action", href: "/employee/receipts", keywords: ["upload receipt", "add receipt", "scan receipt"] },
      { id: "act:returned", label: "View Returned Expenses", group: "Quick Actions", icon: "undo", kind: "action", href: "/employee/sheets", keywords: ["returned", "rejected", "needs changes", "resubmit"] },
    );
  }
  if (role === "manager") {
    cmds.push(
      { id: "act:approvals", label: "Review Pending Approvals", group: "Quick Actions", icon: "fact_check", kind: "action", href: "/manager", keywords: ["pending approvals", "review", "approve", "queue", "team expenses"] },
    );
  }
  if (role === "finance") {
    cmds.push(
      { id: "act:finance-queue", label: "Open Finance Queue", group: "Quick Actions", icon: "gavel", kind: "action", href: "/finance", keywords: ["finance queue", "routed", "manual review", "exceptions"] },
      { id: "act:reports", label: "View Reports", group: "Quick Actions", icon: "monitoring", kind: "action", href: "/finance", keywords: ["reports", "analytics", "kpi", "spend", "generate report"] },
      { id: "act:audit", label: "View Audit Logs", group: "Quick Actions", icon: "history", kind: "action", href: "/finance/audit", keywords: ["audit logs", "audit trail", "history"] },
    );
  }
  if (role === "admin") {
    cmds.push(
      { id: "act:add-user", label: "Add User", group: "Quick Actions", icon: "person_add", kind: "action", href: "/admin", keywords: ["add user", "create user", "invite", "new user", "user management"] },
      { id: "act:roles", label: "Manage Roles", group: "Quick Actions", icon: "admin_panel_settings", kind: "action", href: "/admin", keywords: ["manage roles", "permissions", "rbac", "assign role"] },
      { id: "act:audit-admin", label: "View Audit Logs", group: "Quick Actions", icon: "history", kind: "action", href: "/admin/audit", keywords: ["audit logs", "audit trail", "history", "platform log"] },
    );
  }

  // ── AI (only for roles with an assistant page) ──
  const ai = assistantHref(role);
  if (ai) {
    cmds.push({ id: "ai:open", label: "Open AI Assistant", group: "AI", icon: "smart_toy", kind: "ai", href: ai, keywords: ["ai assistant", "chat", "copilot", "ask ai"] });
    cmds.push({ id: "ai:policy", label: "Ask AI about company policy", group: "AI", icon: "quiz", kind: "ai", href: `${ai}?q=${encodeURIComponent("What is our expense policy?")}`, keywords: ["ask policy", "company policy", "rules", "ask question"] });
    if (role === "manager") {
      cmds.push({ id: "ai:approvals", label: "Ask AI to summarize pending approvals", group: "AI", icon: "summarize", kind: "ai", href: `${ai}?q=${encodeURIComponent("Summarize my pending approvals")}`, keywords: ["summarize approvals", "pending", "what needs review"] });
    }
    if (role === "finance") {
      cmds.push({ id: "ai:report", label: "Ask AI to generate a finance report", group: "AI", icon: "summarize", kind: "ai", href: `${ai}?q=${encodeURIComponent("Generate a finance summary for this month")}`, keywords: ["finance report", "generate report", "summary", "month"] });
    }
  }

  // ── System ──
  cmds.push(
    { id: "sys:theme", label: "Toggle theme", group: "System", icon: "contrast", kind: "system", intent: "toggle-theme", keywords: ["dark mode", "light mode", "theme", "appearance"] },
    { id: "sys:signout", label: "Sign out", group: "System", icon: "logout", kind: "system", intent: "sign-out", keywords: ["log out", "logout", "exit"] },
  );

  return cmds;
}

/** Stable order for rendering groups. */
export const GROUP_ORDER = ["Recent", "Navigation", "Quick Actions", "AI", "Results", "System"];
