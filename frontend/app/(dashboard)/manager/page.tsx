// REFERENCE SCAFFOLD ONLY — see README.md.
// MANAGER dashboard (SCOPING §3.1 / §3.2 / §6.2).
// Shows: a PER-LINE-ITEM approval queue for sheets in the manager's OWN AGENCY ONLY.
// Permissions: per-line-item approve / reject / request-info ✅ (agency-scoped).
// SoD: a manager cannot action their OWN line items (SCOPING §3.3) — enforced
// server-side and mirrored in lib/rbac.ts (managerCanActOnItem).

export default function ManagerDashboardPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Manager Approval Queue</h1>
        <p className="text-sm text-muted-foreground">
          Sheets submitted in <strong>your agency only</strong>. Action each line
          item individually. A sheet advances to Finance only when{" "}
          <strong>all</strong> its line items are approved; any rejection or
          info-request returns the whole sheet to the employee (§6.2).
        </p>
      </header>

      {/* TODO(reference): GET /manager/queue (server filters to the manager's agency).
          <SheetGrid /> master-detail: sheet rows → expand to line items with
          approve / reject / request-info actions per item. */}
      <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
        STUB: agency-scoped master-detail queue. Line-item status flow:
        PENDING_MANAGER → MANAGER_APPROVED | MANAGER_REJECTED | INFO_REQUESTED.
      </div>
    </section>
  );
}
