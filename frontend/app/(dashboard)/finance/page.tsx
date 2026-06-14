// REFERENCE SCAFFOLD ONLY — see README.md.
// FINANCE dashboard (SCOPING §3.1 / §3.2 / §6.3 / §7).
// Shows: the manual-review queue (sheets the LLM ROUTED_TO_HUMAN), the ability to
// OVERRIDE LLM decisions (with logged reason), agency policy DOCUMENT management,
// org-wide reporting/analytics, and the audit log.
// Permissions: finance decision ✅ (manual + handles routed), override LLM ✅,
// update agency policy doc ✅, view audit log ✅, view all sheets ✅.
// SoD: finance cannot override a decision on THEIR OWN sheet (lib/rbac.ts).

import { KpiTiles } from "@/components/KpiTiles";
import { SpendChart } from "@/components/SpendChart";

export default function FinanceDashboardPage() {
  return (
    <section className="space-y-8">
      <header>
        <h1 className="text-xl font-semibold">Finance</h1>
        <p className="text-sm text-muted-foreground">
          Handle sheets the LLM approver routed for manual intervention, override
          LLM decisions with a logged reason, maintain agency policy documents, and
          view org-wide reporting + the immutable audit log.
        </p>
      </header>

      {/* Analytics — Tremor KPI tiles + ECharts spend chart (SCOPING §10). */}
      <KpiTiles />
      <SpendChart />

      {/* Manual-review queue (Finance decision: APPROVED · REJECTED_WITH_COMMENTS
          · ROUTED_TO_HUMAN; finance resolves ROUTED → APPROVED | REJECTED). */}
      <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
        STUB: routed / manual-review queue (FINANCE_MANUAL_REVIEW). Each row shows
        the LLM&apos;s per-line-item verdicts, cited policy clause, confidence, and
        model + policy version (replayable audit, §6.3). Override with a reason.
      </div>

      {/* Policy document management (content owned by Finance, §7). */}
      <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
        STUB: agency policy documents — upload / publish / version (maker-checker,
        re-index on publish). Version-pinned per agency (§7).
      </div>

      {/* Audit log (viewable by Finance & Admin). */}
      <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
        STUB: immutable audit log viewer (actor, role, agency, action, before/after,
        timestamp; LLM runs include model + policy version + cited clauses).
      </div>
    </section>
  );
}
