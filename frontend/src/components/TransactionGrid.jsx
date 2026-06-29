import { useState, useEffect, useCallback, useMemo } from 'react';
import { FiSearch, FiFilter, FiChevronUp, FiChevronDown, FiChevronLeft, FiChevronRight, FiExternalLink } from 'react-icons/fi';
import { fetchExpenses } from '../api/client';
import { mockExpenses } from '../data/mockData';
import RiskBadge from './RiskBadge';

const STATUS_CONFIG = {
  APPROVED: { label: 'Approved', bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  PENDING: { label: 'Pending', bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
  REJECTED: { label: 'Rejected', bg: 'bg-rose-500/15', text: 'text-rose-400', border: 'border-rose-500/30' },
  EXCEPTION_HOLD: { label: 'Exception', bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
  ESCALATED: { label: 'Escalated', bg: 'bg-violet-500/15', text: 'text-violet-400', border: 'border-violet-500/30' },
};

const CATEGORIES = ['All', 'Travel', 'Software', 'Cloud Services', 'Client Entertainment', 'Hardware', 'Office Supplies', 'Training', 'Professional Services', 'Advertising', 'Meals', 'Events', 'Equipment'];
// Each entry: { label: display name, value: DB status value (or 'All') }
const STATUSES = [
  { label: 'All Statuses', value: 'All' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Rejected', value: 'REJECTED' },
  { label: 'Exception', value: 'EXCEPTION_HOLD' },
  { label: 'Escalated', value: 'ESCALATED' },
];
const PAGE_SIZE = 10;

function StatusChip({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.PENDING;
  return (
    <span className={`status-chip ${config.bg} ${config.text} border ${config.border}`}>
      {config.label}
    </span>
  );
}

export default function TransactionGrid({ onSelectExpense, refreshTrigger, employeeId }) {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [sortField, setSortField] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Reset on filter change
  useEffect(() => {
    setPage(1);
    setExpenses([]);
  }, [search, statusFilter, categoryFilter, employeeId, refreshTrigger]);

  useEffect(() => {
    async function load() {
      if (page === 1) setLoading(true);
      else setLoadingMore(true);

      try {
        const filters = { page, size: PAGE_SIZE };
        if (employeeId) filters.employee_id = employeeId;
        // Map display status value → actual DB status for the API
        if (statusFilter !== 'All') filters.status = statusFilter;
        if (categoryFilter !== 'All') filters.category = categoryFilter;

        const data = await fetchExpenses(filters);
        const rawExpenses = data.items || data;
        const totalCount = data.total || rawExpenses.length;

        const normalized = rawExpenses.map(e => ({
          ...e,
          id: e.id || e.claim_id,
          employee_name: e.employee_name || e.employee_id || 'Unknown',
          merchant: e.merchant || e.merchant_name,
          date: e.date || e.transaction_date,
          department: e.department || 'General',
        }));

        setExpenses(prev => page === 1 ? normalized : [...prev, ...normalized]);
        setTotal(totalCount);
        setHasMore(page * PAGE_SIZE < totalCount);
      } catch {
        if (page === 1) setExpenses(mockExpenses);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    }

    // Simple debounce for search
    const timer = setTimeout(() => {
      load();
    }, 300);
    return () => clearTimeout(timer);
  }, [page, search, statusFilter, categoryFilter, employeeId, refreshTrigger]);

  const handleSort = useCallback((field) => {
    setSortDir((prev) => (sortField === field ? (prev === 'asc' ? 'desc' : 'asc') : 'desc'));
    setSortField(field);
  }, [sortField]);

  const sortedExpenses = useMemo(() => {
    let result = [...expenses];

    // Sort
    result.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      if (sortField === 'amount' || sortField === 'risk_score') {
        aVal = Number(aVal) || 0;
        bVal = Number(bVal) || 0;
      } else {
        aVal = String(aVal || '').toLowerCase();
        bVal = String(bVal || '').toLowerCase();
      }
      if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [expenses, sortField, sortDir]);

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <FiChevronDown className="w-3 h-3 opacity-30" />;
    return sortDir === 'asc' ? <FiChevronUp className="w-3 h-3 text-teal-400" /> : <FiChevronDown className="w-3 h-3 text-teal-400" />;
  };

  const columns = [
    { key: 'id', label: 'Claim ID', w: 'w-[120px]' },
    { key: 'employee_id', label: 'Employee ID', w: 'w-[140px]' },
    { key: 'employee_name', label: 'Employee Name', w: 'w-[160px]' },
    { key: 'category', label: 'Category', w: 'w-[140px]' },
    { key: 'merchant', label: 'Merchant', w: 'w-[160px]' },
    { key: 'amount', label: 'Amount', w: 'w-[110px]' },
    { key: 'date', label: 'Date', w: 'w-[100px]' },
    { key: 'status', label: 'Status', w: 'w-[120px]' },
    { key: 'risk_score', label: 'Risk', w: 'w-[120px]' },
  ];

  if (loading) {
    return (
      <div className="glass-card p-6 animate-fade-in-up">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-64 h-10 rounded-lg animate-shimmer" />
          <div className="w-36 h-10 rounded-lg animate-shimmer" />
          <div className="w-36 h-10 rounded-lg animate-shimmer" />
        </div>
        {[...Array(6)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-4 border-b border-slate-700/30">
            <div className="w-24 h-4 rounded animate-shimmer" />
            <div className="w-32 h-4 rounded animate-shimmer" />
            <div className="w-24 h-4 rounded animate-shimmer" />
            <div className="w-32 h-4 rounded animate-shimmer" />
            <div className="w-20 h-4 rounded animate-shimmer" />
            <div className="w-20 h-4 rounded animate-shimmer" />
            <div className="w-20 h-6 rounded-full animate-shimmer" />
            <div className="w-16 h-6 rounded-full animate-shimmer" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      {/* Toolbar */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[240px]">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search employee, merchant, claim ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg pl-10 pr-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500/50 transition-all"
            />
          </div>

          {/* Status Filter */}
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="appearance-none bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 pr-10 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/40 cursor-pointer"
            >
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>

          {/* Category Filter */}
          <div className="relative">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="appearance-none bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 pr-10 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/40 cursor-pointer"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c === 'All' ? 'All Categories' : c}
                </option>
              ))}
            </select>
            <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>

          <div className="ml-auto text-sm text-slate-400">
            {sortedExpenses.length} claim{sortedExpenses.length !== 1 ? 's' : ''}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={`${col.w} px-5 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-slate-200 transition-colors select-none`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <SortIcon field={col.key} />
                  </span>
                </th>
              ))}
              <th className="w-[60px] px-5 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {sortedExpenses.map((expense) => (
              <tr
                key={expense.id}
                onClick={() => onSelectExpense?.(expense)}
                className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
              >
                <td className="px-5 py-4 text-sm font-mono text-teal-400/80">
                  {expense.id?.length > 14 ? expense.id.slice(0, 14) + '…' : expense.id}
                </td>
                <td className="px-5 py-4 text-sm text-slate-200 font-medium">
                  {expense.employee_id}
                </td>
                <td className="px-5 py-4 text-sm text-slate-200 font-medium">
                  {expense.employee_name}
                </td>
                <td className="px-5 py-4 text-sm text-slate-300">
                  {expense.category}
                </td>
                <td className="px-5 py-4 text-sm text-slate-300">
                  {expense.merchant}
                </td>
                <td className="px-5 py-4 text-sm text-slate-200 font-mono font-medium tabular-nums">
                  ${Number(expense.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
                <td className="px-5 py-4 text-sm text-slate-400 tabular-nums">
                  {expense.date}
                </td>
                <td className="px-5 py-4">
                  <StatusChip status={expense.status} />
                </td>
                <td className="px-5 py-4">
                  <RiskBadge score={expense.risk_score} />
                </td>
                <td className="px-5 py-4">
                  <button
                    onClick={(e) => { e.stopPropagation(); onSelectExpense?.(expense); }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-teal-400 transition-all"
                  >
                    <FiExternalLink className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {sortedExpenses.length === 0 && (
              <tr>
                <td colSpan={10} className="px-5 py-16 text-center text-slate-500">
                  <div className="text-4xl mb-3">📋</div>
                  <div className="text-base font-medium">No claims found</div>
                  <div className="text-sm mt-1">Try adjusting your filters</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Load More */}
      {hasMore && (
        <div className="flex items-center justify-center p-5 border-t border-slate-700/50">
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={loadingMore}
            className="px-6 py-2 rounded-full bg-slate-800/50 border border-slate-700 text-slate-300 text-sm font-medium hover:bg-slate-700 hover:text-white transition-all disabled:opacity-50"
          >
            {loadingMore ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  );
}
