// REFERENCE SCAFFOLD ONLY — see README.md.
// Landing page → redirect each authenticated user to their role dashboard.
// In a real app this reads the NextAuth session (lib/auth.ts) and redirects by role.

import { redirect } from "next/navigation";
import Link from "next/link";
import { defaultDashboardPath } from "@/lib/rbac";
import type { Role } from "@/types";

export default async function HomePage() {
  // STUB: real implementation —
  //   const session = await auth();
  //   if (!session) redirect("/login");
  //   redirect(defaultDashboardPath(session.user.role));
  const session: { user: { role: Role } } | null = null;

  if (session) {
    redirect(defaultDashboardPath((session as { user: { role: Role } }).user.role));
  }

  // Reference landing — shows the role entry points (no auth wired in the stub).
  const roles: Role[] = ["employee", "manager", "finance", "admin"];

  return (
    <main className="mx-auto max-w-3xl p-10">
      <h1 className="text-2xl font-semibold">Expense Management Portal</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        REFERENCE SCAFFOLD. After sign-in via Entra External ID, users are
        redirected to their role dashboard (SCOPING §3).
      </p>

      <div className="mt-6 flex flex-col gap-2">
        <Link className="underline" href="/login">
          → Sign in
        </Link>
        {roles.map((role) => (
          <Link key={role} className="underline" href={defaultDashboardPath(role)}>
            → {role} dashboard (preview)
          </Link>
        ))}
      </div>
    </main>
  );
}
