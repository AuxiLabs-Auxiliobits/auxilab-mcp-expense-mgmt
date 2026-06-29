import { DecisionBadge, getDecision } from './ClaimsTable';
import { humanizeCategory, rupees } from '../utils/format';

function StatCard({ label, value, sub, tone = 'cyan' }) {
  const tones = {
    cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200',
    green: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
    amber: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
    red: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
  };
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4 shadow-card">
      <div className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${tones[tone]}`}>
        {label}
      </div>
      <p className="mt-3 font-mono text-2xl font-semibold text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function claimSortValue(claim) {
  return new Date(claim.created_at || claim.claim_date || 0).getTime();
}

function categoryTotals(claims) {
  return claims.reduce((acc, claim) => {
    const key = humanizeCategory(claim.category);
    acc[key] = (acc[key] || 0) + Number(claim.amount || 0);
    return acc;
  }, {});
}

function RecentClaims({ claims, onViewAllClaims }) {
  const recentClaims = [...claims]
    .sort((a, b) => claimSortValue(b) - claimSortValue(a))
    .slice(0, 5);

  return (
    <section className="rounded-card border border-white/10 bg-white/[0.04] p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">
            Recent Claims
          </p>
          <h3 className="mt-1 text-lg font-semibold text-white">Latest expense activity</h3>
        </div>
        <button
          type="button"
          onClick={onViewAllClaims}
          className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200 transition-colors hover:bg-cyan-400/20"
        >
          View all
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {['ID', 'Merchant', 'Category', 'Amount', 'Date', 'Decision'].map((h) => (
                <th
                  key={h}
                  className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {recentClaims.map((claim) => (
              <tr key={claim.id} className="border-b border-white/10 last:border-0">
                <td className="px-3 py-2 font-mono text-xs text-slate-400">{claim.id}</td>
                <td className="px-3 py-2 font-medium text-white">{claim.merchant}</td>
                <td className="px-3 py-2 text-slate-200">{humanizeCategory(claim.category)}</td>
                <td className="px-3 py-2 font-mono text-slate-100">{rupees(claim.amount)}</td>
                <td className="px-3 py-2 font-mono text-xs text-slate-400">{claim.claim_date}</td>
                <td className="px-3 py-2">
                  <DecisionBadge decision={getDecision(claim)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ToolsActive({ tools, toolCallCounts }) {
  return (
    <section className="rounded-card border border-white/10 bg-white/[0.04] p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">MCP Tools Active</p>
      <div className="mt-4 space-y-2">
        {tools.map((tool) => {
          const count = tool.aliases.reduce((sum, name) => sum + (toolCallCounts[name] || 0), 0);

          return (
            <div
              key={tool.label}
              className="flex items-center justify-between gap-3 rounded-lg bg-slate-950/40 px-3 py-2 text-sm"
            >
              <span className="text-slate-300">{tool.label}</span>
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 font-mono text-xs text-cyan-200">
                {count}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SpendByCategory({ claims }) {
  const totals = categoryTotals(claims);
  const totalSpend = claims.reduce((sum, claim) => sum + Number(claim.amount || 0), 0);
  const sortedTotals = Object.entries(totals).sort((a, b) => b[1] - a[1]);

  return (
    <section className="rounded-card border border-white/10 bg-white/[0.04] p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-cyan-300">
        Spend by Category
      </p>
      <div className="mt-4 space-y-3">
        {sortedTotals.map(([category, total]) => {
          const pct = totalSpend ? Math.round((total / totalSpend) * 100) : 0;

          return (
            <div key={category}>
              <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-slate-300">{category}</span>
                <span className="font-mono text-slate-100">{rupees(total)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div className="h-full rounded-full bg-cyan-300" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function Dashboard({
  stats,
  claims = [],
  tools = [],
  toolCallCounts = {},
  onViewAllClaims,
}) {
  if (!stats) return null;

  const complianceRate =
    stats.total_claims > 0 ? Math.round((stats.compliant / stats.total_claims) * 100) : 0;
  const totalAtRisk = Number(stats.total_spend || 0) - Number(stats.compliant_spend || 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Claims" value={stats.total_claims} sub="live SQLite dataset" />
        <StatCard
          label="Compliance Rate"
          value={`${complianceRate}%`}
          sub={`${stats.compliant} clean claims`}
          tone={complianceRate >= 80 ? 'green' : 'amber'}
        />
        <StatCard
          label="Total At Risk"
          value={rupees(totalAtRisk)}
          sub={`${stats.violations} violations, ${stats.missing_receipts} missing receipts`}
          tone="red"
        />
        <StatCard
          label="Duplicate Flags"
          value={stats.duplicates}
          sub="same/similar claims within 3 days"
          tone="amber"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <RecentClaims claims={claims} onViewAllClaims={onViewAllClaims} />
        <div className="space-y-4">
          <ToolsActive tools={tools} toolCallCounts={toolCallCounts} />
          <SpendByCategory claims={claims} />
        </div>
      </div>
    </div>
  );
}
