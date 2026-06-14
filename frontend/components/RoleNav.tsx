// REFERENCE SCAFFOLD ONLY — see README.md.
// Role-aware sidebar nav. Renders only the links the role is permitted to use,
// mirroring SCOPING §3.2 (defense-in-depth; the server re-checks every request).

import Link from "next/link";
import type { Role } from "@/types";
import { can } from "@/lib/rbac";

interface NavItem {
  href: string;
  label: string;
  show: (role: Role) => boolean;
}

const NAV: NavItem[] = [
  { href: "/employee", label: "My Sheets", show: (r) => r === "employee" },
  {
    href: "/manager",
    label: "Approval Queue",
    show: (r) => can(r, "managerLineItemAction"),
  },
  {
    href: "/finance",
    label: "Finance",
    show: (r) => can(r, "financeDecision") && r === "finance",
  },
  { href: "/admin", label: "Admin", show: (r) => can(r, "manageAgencies") },
];

export function RoleNav({ role }: { role: Role }) {
  const items = NAV.filter((i) => i.show(role));

  return (
    <nav className="w-56 shrink-0 border-r p-4">
      <div className="mb-4 text-xs uppercase tracking-wide text-muted-foreground">
        {role} · agency-scoped
      </div>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="block rounded px-2 py-1 text-sm hover:bg-muted"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
