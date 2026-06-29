import React, { useState, useEffect, useCallback } from 'react';
import {
  FiUsers, FiInfo, FiTrash2, FiRefreshCw, FiX,
  FiDollarSign, FiCalendar, FiMail, FiBriefcase,
  FiShield, FiActivity
} from 'react-icons/fi';
import { fetchActiveUsers, deleteUser } from '../api/client';
import { useToast } from '../context/ToastContext';
import ConfirmModal from './ConfirmModal';

/* ─── Role Badge ──────────────────────────────────────────────────────────── */
function RoleBadge({ role }) {
  const colors = {
    CEO: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    Director: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
    VP: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    Manager: 'bg-teal-500/15 text-teal-400 border-teal-500/30',
    'Software Engineer': 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    Analyst: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  };
  const cls = colors[role] || 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  return (
    <span className={`inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
      {role}
    </span>
  );
}

/* ─── Employee Detail Modal ──────────────────────────────────────────────── */
function EmployeeDetailModal({ employee, onClose }) {
  if (!employee) return null;

  const fmt = (iso) => {
    if (!iso) return 'No activity yet';
    return new Date(iso).toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[110]" onClick={onClose} />
      <div className="fixed inset-0 z-[111] flex items-center justify-center p-4" onClick={(e) => e.stopPropagation()}>
        <div className="glass-card w-full max-w-lg p-0 overflow-hidden animate-fade-in-up">
          {/* Header */}
          <div className="relative px-6 pt-6 pb-5 border-b border-slate-700/50"
            style={{ background: 'linear-gradient(135deg, rgba(20,184,166,0.08) 0%, rgba(99,102,241,0.06) 100%)' }}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/60 transition-all"
            >
              <FiX className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-teal-500/30 to-indigo-500/20 border border-teal-500/20 flex items-center justify-center text-xl font-bold text-teal-400">
                {employee.name.charAt(0).toUpperCase()}
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{employee.name}</h3>
                <div className="mt-1"><RoleBadge role={employee.role} /></div>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <InfoRow icon={FiMail} label="Email" value={employee.email} />
            <InfoRow icon={FiBriefcase} label="Department" value={employee.department} />
            <InfoRow icon={FiShield} label="Reporting To" value={employee.manager_name} />
            <InfoRow icon={FiActivity} label="Account Status" value={employee.account_status} />

            {/* Stats */}
            <div className="sm:col-span-2 grid grid-cols-2 gap-3 mt-2 pt-4 border-t border-slate-700/40">
              <StatCard label="Total Expenses Claimed" value={`$${employee.total_expenses.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} icon={FiDollarSign} color="teal" />
              <StatCard label="Number of Claims" value={employee.expense_count} icon={FiActivity} color="violet" />
            </div>

            <div className="sm:col-span-2">
              <InfoRow icon={FiCalendar} label="First Expense Activity" value={fmt(employee.first_activity)} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center shrink-0">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">{label}</p>
        <p className="text-sm text-slate-200 font-medium mt-0.5">{value || '—'}</p>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }) {
  const clr = color === 'teal'
    ? 'from-teal-500/10 to-teal-600/5 border-teal-500/20 text-teal-400'
    : 'from-violet-500/10 to-violet-600/5 border-violet-500/20 text-violet-400';
  return (
    <div className={`rounded-xl bg-gradient-to-br border p-4 ${clr}`}>
      <Icon className="w-4 h-4 mb-2" />
      <p className="text-xs text-slate-400 font-medium">{label}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
    </div>
  );
}

/* ─── Main Panel ─────────────────────────────────────────────────────────── */
export default function ActiveUsersPanel() {
  const { addToast } = useToast();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [detailUser, setDetailUser] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchActiveUsers();
      setUsers(data);
    } catch (err) {
      addToast('Failed to load organisation users.', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteUser(deleteTarget.employee_id);
      addToast(`${deleteTarget.name}'s account has been deleted.`, 'success');
      setDeleteTarget(null);
      load();
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to delete account.', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const filtered = users.filter(u =>
    u.name.toLowerCase().includes(search.toLowerCase()) ||
    u.role.toLowerCase().includes(search.toLowerCase()) ||
    u.department.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-5 animate-fade-in-up">
      {/* Header */}
      <div className="glass-card p-6 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <FiUsers className="w-5 h-5 text-teal-400" /> Organisation Directory
            </h2>
            <p className="text-sm text-slate-400 mt-0.5">
              All active accounts in the organisation — {users.length} member{users.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-300 hover:bg-slate-700/60 hover:text-white transition-all"
          >
            <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search by name, role, or department…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:w-80 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 transition-all"
        />
      </div>

      {/* Table */}
      <div className="glass-card p-0 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <FiRefreshCw className="w-6 h-6 text-teal-400 animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-500">
            <FiUsers className="w-8 h-8 mb-3 opacity-40" />
            <p className="text-sm">No users found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-700/50 bg-slate-800/40">
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Name</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Role</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Department</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Reporting Manager</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold text-right">Total Claimed</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold text-center">Details</th>
                  <th className="px-5 py-3 text-[11px] uppercase tracking-wider text-slate-400 font-semibold text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u, idx) => (
                  <tr
                    key={u.employee_id}
                    className={`border-b border-slate-800/50 transition-colors hover:bg-slate-800/25 ${idx % 2 === 0 ? '' : 'bg-slate-900/20'}`}
                  >
                    {/* Name + Avatar */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-500/30 to-indigo-500/20 border border-teal-500/20 flex items-center justify-center text-xs font-bold text-teal-400 shrink-0">
                          {u.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-200">{u.name}</p>
                          <p className="text-[11px] text-slate-500">{u.email}</p>
                        </div>
                      </div>
                    </td>

                    <td className="px-5 py-3.5"><RoleBadge role={u.role} /></td>

                    <td className="px-5 py-3.5 text-sm text-slate-300">{u.department}</td>

                    {/* Reporting Manager */}
                    <td className="px-5 py-3.5">
                      <span className="text-sm text-slate-300">{u.manager_name}</span>
                    </td>

                    {/* Total */}
                    <td className="px-5 py-3.5 text-right">
                      <span className="text-sm font-mono font-semibold text-teal-400">
                        ${u.total_expenses.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </td>

                    {/* Details "i" */}
                    <td className="px-5 py-3.5 text-center">
                      <button
                        onClick={() => setDetailUser(u)}
                        title="View details"
                        className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/25 text-indigo-400 hover:bg-indigo-500/20 hover:border-indigo-500/40 transition-all text-xs font-bold"
                      >
                        i
                      </button>
                    </td>

                    {/* Delete */}
                    <td className="px-5 py-3.5 text-center">
                      {u.role === 'CEO' ? (
                        <span className="text-[11px] text-slate-600 italic">Protected</span>
                      ) : (
                        <button
                          onClick={() => setDeleteTarget(u)}
                          title="Delete account"
                          className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/25 text-rose-400 hover:bg-rose-500/20 hover:border-rose-500/40 transition-all"
                        >
                          <FiTrash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Employee Detail Modal */}
      {detailUser && (
        <EmployeeDetailModal employee={detailUser} onClose={() => setDetailUser(null)} />
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Delete Account"
        message={`Are you sure you want to permanently delete ${deleteTarget?.name}'s account? All their expense claims and associated data will also be removed. This action cannot be undone.`}
        confirmText={deleting ? 'Deleting…' : 'Yes, Delete'}
        cancelText="Cancel"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
