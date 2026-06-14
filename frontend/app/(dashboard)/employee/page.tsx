// REFERENCE SCAFFOLD ONLY — see README.md.
// EMPLOYEE dashboard (SCOPING §3.1 / §3.2).
// Shows: the employee's OWN expense sheets and a "submit / resubmit" entry point.
// Permissions: submit/resubmit own sheet ✅, view own sheets ✅. Cannot view others'.

import Link from "next/link";

export default function EmployeeDashboardPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">My Expense Sheets</h1>
        <p className="text-sm text-muted-foreground">
          Create, submit, and track your sheets. A sheet has many line items, each
          with its own attachments (SCOPING §5). Resubmission keeps the same sheet
          ID and increments the version (§5.1).
        </p>
      </header>

      {/* TODO(reference): TanStack Query → GET /sheets?mine=true.
          Render with <SheetGrid /> (AG Grid master-detail: sheet → line items). */}
      <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
        STUB: list of my sheets with status (DRAFT · SUBMITTED · IN_MANAGER_REVIEW ·
        RETURNED_TO_EMPLOYEE · IN_FINANCE_REVIEW · FINANCE_APPROVED/REJECTED ·
        FINANCE_MANUAL_REVIEW · PAID). Built on &lt;SheetGrid /&gt;.
      </div>

      <div className="flex gap-3">
        <button className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground">
          New expense sheet
        </button>
        <Link href="/sheets/example-sheet-id" className="self-center underline">
          → Open a sheet (detail / master-detail preview)
        </Link>
      </div>

      <p className="text-xs text-muted-foreground">
        Form validation mirrors the backend via Zod (lib/schemas.ts); the FastAPI
        Pydantic models are authoritative (SCOPING §9.1).
      </p>
    </section>
  );
}
