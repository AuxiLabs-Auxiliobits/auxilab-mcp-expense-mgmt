// REFERENCE SCAFFOLD ONLY — see README.md.
// ADMIN dashboard (SCOPING §3.1 / §3.2 / §7).
// Shows: agency lifecycle (onboard / delete — soft-delete + referential integrity),
// user & role management, and baseline policy CONFIG (the structured JSON tier, §20.B).
// Permissions: create policy / onboard / delete agency ✅, manage users & roles ✅,
// view audit log ✅. (Agency policy DOCUMENT content is owned by Finance, §7.)

export default function AdminDashboardPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Manage agencies, users &amp; roles, and the baseline policy configuration.
          Agency lifecycle is maker-checker and soft-delete only (blocked while open
          sheets reference an agency, §8).
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
          STUB: Agencies — onboard / soft-delete (Crispin, SKDK, JetFuel, …).
        </div>
        <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
          STUB: Users &amp; roles — every user has exactly one role + one agency (§3).
        </div>
        <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
          STUB: Baseline policy config (JSON) — receipt threshold, submission cutoff,
          allowed extensions, max file MB, duplicate window, LLM routing threshold
          (§20.B).
        </div>
      </div>
    </section>
  );
}
