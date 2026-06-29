import { humanizeCategory, rupees } from '../utils/format';

const STATUS_STYLES = {
  submitted: 'bg-blue-100 text-blue-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  pending: 'bg-amber-100 text-amber-800',
};

const DECISION_STYLES = {
  approve: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
  flag: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  reject: 'border-rose-400/30 bg-rose-400/10 text-rose-300',
};

const DECISION_LABELS = {
  approve: 'Auto-approve',
  flag: 'Flag',
  reject: 'Reject',
};

export function getDecision(claim) {
  if (claim.policy_violation === 1) return 'reject';
  if (claim.duplicate_risk >= 0.5) return 'flag';
  return 'approve';
}

function Badge({ children, variant = 'default' }) {
  const styles = {
    default: 'bg-slate-100 text-slate-700',
    violation: 'bg-red-100 text-red-700',
    duplicate: 'bg-amber-100 text-amber-700',
    missing: 'bg-orange-100 text-orange-700',
    ok: 'bg-green-100 text-green-700',
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles[variant]}`}
    >
      {children}
    </span>
  );
}

export function DecisionBadge({ decision }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${DECISION_STYLES[decision]}`}
    >
      {DECISION_LABELS[decision]}
    </span>
  );
}

export default function ClaimsTable({ claims }) {
  if (!claims?.length) {
    return (
      <p className="rounded-card border border-white/10 bg-white/[0.04] py-8 text-center text-slate-300 shadow-card">
        No claims found. Run seed_claims.py to load demo data.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-white/10 bg-white/[0.04] shadow-card">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-white/10">
            {['ID', 'Employee', 'Merchant', 'Amount', 'Category', 'Date', 'Status', 'Flags'].map(
              (h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => {
            const decision = getDecision(c);

            return (
              <tr
                key={c.id}
                className="border-b border-white/10 odd:bg-slate-950/20 even:bg-slate-950/40 hover:bg-cyan-400/5"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-slate-400">{c.id}</td>
                <td className="px-4 py-2.5 text-slate-100">{c.employee_id}</td>
                <td className="px-4 py-2.5 font-medium text-white">{c.merchant}</td>
                <td className="px-4 py-2.5 font-mono font-semibold text-slate-100">
                  {rupees(c.amount)}
                </td>
                <td className="px-4 py-2.5 text-slate-100">{humanizeCategory(c.category)}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-400">{c.claim_date}</td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_STYLES[c.status] || STATUS_STYLES.pending
                      }`}
                    >
                      {c.status}
                    </span>
                    <DecisionBadge decision={decision} />
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {c.policy_violation ? (
                      <Badge variant="violation">Violation</Badge>
                    ) : (
                      <Badge variant="ok">OK</Badge>
                    )}
                    {c.duplicate_risk >= 0.7 && <Badge variant="duplicate">Duplicate</Badge>}
                    {!c.receipt_id && c.amount > 25 && <Badge variant="missing">No Receipt</Badge>}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
