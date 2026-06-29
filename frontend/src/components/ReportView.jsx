import { humanizeCategory, rupees } from '../utils/format';

function categoryTotals(claims) {
  return claims.reduce((acc, claim) => {
    const key = humanizeCategory(claim.category || 'other');
    acc[key] = (acc[key] || 0) + Number(claim.amount || 0);
    return acc;
  }, {});
}

export default function ReportView({ claims = [], stats, trips = [] }) {
  const totals = categoryTotals(claims);
  const totalClaims = stats?.total_claims ?? claims.length;
  const cleanClaims = stats?.compliant ?? 0;
  const complianceRate = totalClaims > 0 ? Math.round((cleanClaims / totalClaims) * 100) : 0;
  const violationCount = stats?.violations ?? claims.filter((c) => c.policy_violation).length;
  const duplicateFlags =
    stats?.duplicates ?? claims.filter((c) => Number(c.duplicate_risk || 0) >= 0.7).length;
  const missingReceipts =
    stats?.missing_receipts ?? claims.filter((c) => !c.receipt_id && Number(c.amount) > 25).length;
  const totalAtRisk = claims.reduce((sum, claim) => {
    const risky =
      claim.policy_violation ||
      Number(claim.duplicate_risk || 0) >= 0.7 ||
      (!claim.receipt_id && Number(claim.amount) > 25);
    return risky ? sum + Number(claim.amount || 0) : sum;
  }, 0);
  const totalSpend = stats?.total_spend ?? claims.reduce((sum, claim) => sum + Number(claim.amount || 0), 0);
  const topCategory = Object.entries(totals).sort((a, b) => b[1] - a[1])[0];

  const narrative = `Expense report summariser reviewed ${totalClaims} claims across ${
    trips.length || 'the active'
  } trip(s). Total spend is ${rupees(totalSpend)}, with ${violationCount} policy violation(s), ${duplicateFlags} duplicate flag(s), and ${missingReceipts} missing receipt issue(s). Compliance is ${complianceRate}%, so ${
    complianceRate >= 85
      ? 'the report is broadly compliant and ready for light manager review.'
      : complianceRate >= 65
        ? 'the report should be reviewed before approval.'
        : 'the report requires manager attention before reimbursement.'
  }`;

  return (
    <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5 shadow-card">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">
              Expense Report Summariser
            </p>
            <h3 className="mt-1 text-xl font-semibold text-white">Manager-ready summary</h3>
          </div>
          <div className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-3 text-right">
            <p className="text-xs text-cyan-100">Compliance</p>
            <p className="font-mono text-2xl font-semibold text-cyan-200">{complianceRate}%</p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-slate-950/40 p-4">
            <p className="text-xs text-slate-400">Total Spend</p>
            <p className="mt-1 font-mono text-lg font-semibold text-white">{rupees(totalSpend)}</p>
          </div>
          <div className="rounded-lg bg-slate-950/40 p-4">
            <p className="text-xs text-slate-400">Violations</p>
            <p className="mt-1 font-mono text-lg font-semibold text-rose-300">{violationCount}</p>
          </div>
          <div className="rounded-lg bg-slate-950/40 p-4">
            <p className="text-xs text-slate-400">Total At Risk</p>
            <p className="mt-1 font-mono text-lg font-semibold text-amber-300">{rupees(totalAtRisk)}</p>
          </div>
          <div className="rounded-lg bg-slate-950/40 p-4">
            <p className="text-xs text-slate-400">Top Category</p>
            <p className="mt-1 truncate text-sm font-semibold text-white">{topCategory?.[0] || 'None'}</p>
          </div>
        </div>

        <div className="mt-5">
          <p className="mb-3 text-sm font-semibold text-slate-200">Totals by category</p>
          <div className="space-y-3">
            {Object.entries(totals)
              .sort((a, b) => b[1] - a[1])
              .map(([category, total]) => {
                const pct = totalSpend ? Math.round((total / totalSpend) * 100) : 0;
                return (
                  <div key={category}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-300">{category}</span>
                      <span className="font-mono text-slate-100">{rupees(total)}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full rounded-full bg-cyan-300" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5 shadow-card">
          <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">Narrative</p>
          <p className="mt-3 text-sm leading-6 text-slate-200">{narrative}</p>
        </section>

        <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5 shadow-card">
          <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">
            MCP Tool Coverage
          </p>
          <div className="mt-4 space-y-2 text-sm">
            {[
              'Expense Policy Checker',
              'Receipt Parser',
              'Spend Category Classifier',
              'Duplicate Claim Detector',
              'Expense Report Summariser',
            ].map((tool) => (
              <div key={tool} className="flex items-center justify-between rounded-lg bg-slate-950/40 px-3 py-2">
                <span className="text-slate-300">{tool}</span>
                <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-xs text-emerald-300">
                  visualized
                </span>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
