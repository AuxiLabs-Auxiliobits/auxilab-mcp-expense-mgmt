import { useEffect, useState } from 'react';
import { api } from './api';
import ChatWindow from './components/ChatWindow';
import ClaimsTable from './components/ClaimsTable';
import Dashboard from './components/Dashboard';
import ReportView from './components/ReportView';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', hint: 'Live expense overview' },
  { id: 'chat', label: 'Chat', hint: 'MCP tool conversation' },
  { id: 'claims', label: 'Claims', hint: 'Policy and duplicate review' },
  { id: 'report', label: 'Report', hint: 'Expense summariser' },
];

const REQUIRED_MCP_TOOLS = [
  {
    label: 'Policy Checker',
    aliases: ['expense_policy_checker', 'check_policy_compliance'],
  },
  {
    label: 'Receipt Parser',
    aliases: ['receipt_parser', 'parse_receipt'],
  },
  {
    label: 'Spend Category Classifier',
    aliases: ['spend_category_classifier', 'classify_spend_category'],
  },
  {
    label: 'Duplicate Claim Detector',
    aliases: ['duplicate_claim_detector', 'detect_duplicate_claim'],
  },
  {
    label: 'Expense Report Summariser',
    aliases: ['expense_report_summariser', 'generate_trip_report'],
  },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [claims, setClaims] = useState([]);
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [toolCallCounts, setToolCallCounts] = useState({});

  useEffect(() => {
    async function load() {
      try {
        const [s, c, t] = await Promise.all([api.getStats(), api.getClaims(), api.getTrips()]);
        setStats(s);
        setClaims(c);
        setTrips(t);
        setApiError(null);
      } catch (e) {
        setApiError('Cannot reach API. Start the backend: uvicorn backend.api.main:app --reload --port 8000');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const dataLoading = loading && tab !== 'chat';
  const complianceRate =
    stats?.total_claims > 0 ? Math.round((stats.compliant / stats.total_claims) * 100) : 0;
  const demonstratedToolCount = REQUIRED_MCP_TOOLS.filter((tool) =>
    tool.aliases.some((name) => toolCallCounts[name] > 0)
  ).length;

  function trackToolCalls(toolCalls = []) {
    const names = toolCalls.map((call) => call.name).filter(Boolean);
    if (!names.length) return;

    setToolCallCounts((current) =>
      names.reduce(
        (next, name) => ({
          ...next,
          [name]: (next[name] || 0) + 1,
        }),
        { ...current }
      )
    );
  }

  return (
    <div className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-white/10 bg-[#0b1627] px-5 py-5 lg:block">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400 text-sm font-black text-slate-950">
              TS
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">TripSense</h1>
              <p className="text-xs text-slate-400">Employee Expense MCP</p>
            </div>
          </div>

          <nav className="mt-8 space-y-2">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                  tab === t.id
                    ? 'border-cyan-400/60 bg-cyan-400/10 text-white'
                    : 'border-transparent text-slate-400 hover:border-white/10 hover:bg-white/5 hover:text-slate-100'
                }`}
              >
                <span className="block text-sm font-semibold">{t.label}</span>
                <span className="mt-0.5 block text-xs text-slate-500">{t.hint}</span>
              </button>
            ))}
          </nav>

          <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Live Compliance
            </p>
            <p className="mt-2 font-mono text-3xl font-semibold text-cyan-300">
              {complianceRate}%
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {stats?.compliant ?? 0} clean claims of {stats?.total_claims ?? 0}
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-white/10 bg-[#0b1627]/95 px-4 py-4 backdrop-blur sm:px-6 lg:hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400 text-sm font-black text-slate-950">
                  TS
                </div>
                <div>
                  <h1 className="text-base font-bold">TripSense</h1>
                  <p className="text-xs text-slate-400">Employee Expense MCP</p>
                </div>
              </div>
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 font-mono text-xs text-cyan-200">
                {complianceRate}%
              </span>
            </div>
            <nav className="mt-4 grid grid-cols-4 gap-2">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`rounded-lg px-3 py-2 text-sm font-medium ${
                    tab === t.id ? 'bg-cyan-400 text-slate-950' : 'bg-white/5 text-slate-300'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </header>

          <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 xl:px-8">
            <div className="mx-auto max-w-7xl space-y-6">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-cyan-300">
                    MCP Expense Management
                  </p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">
                    {TABS.find((t) => t.id === tab)?.label}
                  </h2>
                </div>
                <span className="w-fit rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-300">
                  {demonstratedToolCount}/5 MCP tools demonstrated
                </span>
              </div>

              {apiError && tab !== 'chat' && (
                <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                  {apiError}
                </div>
              )}

              {tab === 'chat' && <ChatWindow onToolCalls={trackToolCalls} />}

              {tab === 'dashboard' &&
                (dataLoading ? (
                  <div className="flex items-center justify-center py-20">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-900 border-t-cyan-300" />
                  </div>
                ) : (
                  <Dashboard
                    claims={claims}
                    stats={stats}
                    toolCallCounts={toolCallCounts}
                    tools={REQUIRED_MCP_TOOLS}
                    onViewAllClaims={() => setTab('claims')}
                  />
                ))}

              {tab === 'claims' &&
                (dataLoading ? (
                  <div className="flex items-center justify-center py-20">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-900 border-t-cyan-300" />
                  </div>
                ) : (
                  <ClaimsTable claims={claims} />
                ))}

              {tab === 'report' &&
                (dataLoading ? (
                  <div className="flex items-center justify-center py-20">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-900 border-t-cyan-300" />
                  </div>
                ) : (
                  <ReportView claims={claims} stats={stats} trips={trips} />
                ))}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
