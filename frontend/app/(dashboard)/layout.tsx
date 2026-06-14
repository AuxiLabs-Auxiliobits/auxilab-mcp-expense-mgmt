// REFERENCE SCAFFOLD ONLY — see README.md.
// Shared chrome for all role dashboards. In a real app this reads the session and
// passes the role to RoleNav so only permitted nav links render (defense-in-depth,
// SCOPING §3.3 — the server still re-checks every request).

import type { ReactNode } from "react";
import { RoleNav } from "@/components/RoleNav";
import type { Role } from "@/types";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  // STUB: const session = await auth(); const role = session.user.role;
  const role: Role = "employee";

  return (
    <div className="flex min-h-screen">
      <RoleNav role={role} />
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
