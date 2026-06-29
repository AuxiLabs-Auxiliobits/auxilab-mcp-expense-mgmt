import React, { useState, useEffect, useCallback } from 'react';
import { FiGrid, FiFileText, FiUploadCloud, FiShield, FiCpu, FiTrendingUp, FiRefreshCw, FiDownload, FiTrash2, FiUsers, FiLogOut, FiSettings } from 'react-icons/fi';
import MetricsRibbon from '../components/MetricsRibbon';
import TransactionGrid from '../components/TransactionGrid';
import ReceiptUploader from '../components/ReceiptUploader';
import ReviewPanel from '../components/ReviewPanel';
import ProfileModal from '../components/ProfileModal';
import ReportGenerator from '../components/ReportGenerator';
import ActiveUsersPanel from '../components/ActiveUsersPanel';
import ConfirmModal from '../components/ConfirmModal';

// Chart components
import SpendByCategory from '../components/Charts/SpendByCategory';
import RiskDistribution from '../components/Charts/RiskDistribution';
import MonthlySpendTrend from '../components/Charts/MonthlySpendTrend';
import ApprovalStatusPie from '../components/Charts/ApprovalStatusPie';

// API Client
import { fetchMetrics, fetchCharts, exportReport, clearAllExpenses, fetchPendingApprovals, approveUserAccount, switchEnvironment } from '../api/client';
import { mockMetrics, mockCharts } from '../data/mockData';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const { addToast } = useToast();
  const [metrics, setMetrics] = useState(null);
  const [charts, setCharts] = useState(null);
  const [selectedExpense, setSelectedExpense] = useState(null);
  const [activeTab, setActiveTab] = useState('uploader'); // Default for employees
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // Approvals State
  const [pendingAccounts, setPendingAccounts] = useState([]);

  // Role Checks
  const isEmployee = user?.role === 'Software Engineer' || user?.role === 'Analyst';
  const isManagerPlus = !isEmployee;
  const isExecutive = user?.role === 'Director' || user?.role === 'VP' || user?.role === 'CEO';

  // ── Data Fetching ────────────────────────────────────────────────────────
  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      if (isManagerPlus) {
        const [mRes, cRes, aRes] = await Promise.all([
          fetchMetrics(),
          fetchCharts(),
          fetchPendingApprovals()
        ]);
        setMetrics(mRes);
        setCharts(cRes);
        setPendingAccounts(aRes);
      }
      setIsDemoMode(false);
    } catch (err) {
      console.warn("API server unavailable. Activating premium demo mode with stubs.", err);
      if (isManagerPlus) {
        setMetrics(mockMetrics);
        setCharts(mockCharts);
      }
      setIsDemoMode(true);
    } finally {
      setLoading(false);
    }
  }, [isManagerPlus]);

  useEffect(() => {
    loadDashboardData();
    if (isManagerPlus && activeTab === 'uploader') {
      setActiveTab('overview');
    }
  }, [loadDashboardData, refreshTrigger, isManagerPlus, user?.role]);

  const handleRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleExport = useCallback(async () => {
    try {
      const blob = await exportReport();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `expense_ops_audit_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      console.error("Export failed, simulating download", err);
    }
  }, []);

  const handleReviewComplete = useCallback(() => {
    handleRefresh();
  }, [handleRefresh]);


  const handleApproveAccount = async (empId, action) => {
    try {
      const res = await approveUserAccount(empId, action);
      addToast(res.message || "Action successful", "success");
      handleRefresh(); // Refresh pending accounts list
    } catch (e) {
      console.error("Approval error", e);
      addToast(e.response?.data?.detail || "Failed to process approval", "error");
    }
  };

  const handleSwitchEnv = async (envStr) => {
    try {
      const res = await switchEnvironment(envStr);
      addToast(res.message, "success");
      handleRefresh();
    } catch (e) {
      console.error("Environment switch error", e);
      addToast(e.response?.data?.detail || `Failed to switch to ${envStr}`, "error");
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col antialiased selection:bg-teal-500/30 selection:text-teal-200">

      {/* ── TOP NAV BAR ────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 w-full bg-[#020617]/80 backdrop-blur-md border-b border-slate-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-teal-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-teal-500/10">
            <FiShield className="text-xl text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-teal-400 via-indigo-200 to-indigo-400 bg-clip-text text-transparent">
              ExpenseOps
            </h1>
            <p className="text-[10px] text-slate-400 tracking-wider uppercase font-semibold">
              {user?.name} | {user?.role}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowProfile(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 text-slate-400 font-medium text-sm hover:text-teal-400 transition-all active:scale-95"
            title="Settings"
          >
            <FiSettings />
            Profile
          </button>
          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 text-slate-400 font-medium text-sm hover:text-rose-400 transition-all active:scale-95"
            title="Log Out"
          >
            <FiLogOut />
            Logout
          </button>
        </div>
      </header>

      {/* ── MAIN LAYOUT GRID ────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col gap-6">

        {user?.role === 'CEO' && (
          <div className="bg-slate-800/50 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between mb-2">
            <div>
              <h3 className="text-amber-400 font-bold text-sm">CEO Environment Control</h3>
              <p className="text-xs text-slate-400">Toggle active database. <strong className="text-white">Demo</strong> uses local SQLite. <strong className="text-white">Production</strong> uses persistent Supabase PostgreSQL.</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleSwitchEnv('demo')}
                className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-amber-600 text-xs font-bold transition-all text-white"
              >
                Use Demo
              </button>
              <button
                onClick={() => handleSwitchEnv('production')}
                className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-emerald-600 text-xs font-bold transition-all text-white"
              >
                Use Production
              </button>
            </div>
          </div>
        )}

        {/* Only show metrics ribbon to Managers+ */}
        {isManagerPlus && <MetricsRibbon metrics={metrics} loading={loading} />}

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800/80 gap-6">
          {isManagerPlus && (
            <button
              onClick={() => setActiveTab('overview')}
              className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'overview'
                  ? 'text-teal-400 border-teal-400'
                  : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
            >
              <span className="flex items-center gap-2">
                <FiGrid /> Overview Analytics
              </span>
            </button>
          )}

          {isManagerPlus && (
            <button
              onClick={() => setActiveTab('review_claims')}
              className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'review_claims'
                  ? 'text-teal-400 border-teal-400'
                  : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
            >
              <span className="flex items-center gap-2">
                <FiFileText /> Review Claims
              </span>
            </button>
          )}

          {isManagerPlus && (
            <button
              onClick={() => setActiveTab('ai_reports')}
              className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'ai_reports'
                  ? 'text-teal-400 border-teal-400'
                  : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
            >
              <span className="flex items-center gap-2">
                <FiCpu /> AI Reports
              </span>
            </button>
          )}

          <button
            onClick={() => setActiveTab('uploader')}
            className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'uploader'
                ? 'text-teal-400 border-teal-400'
                : 'text-slate-400 border-transparent hover:text-slate-200'
              }`}
          >
            <span className="flex items-center gap-2">
              <FiUploadCloud /> {isManagerPlus ? 'Interactive Uploader' : 'Submit Expenses'}
            </span>
          </button>

          {isManagerPlus && (
            <button
              onClick={() => setActiveTab('approvals')}
              className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'approvals'
                  ? 'text-teal-400 border-teal-400'
                  : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
            >
              <span className="flex items-center gap-2">
                <FiUsers /> Account Approvals
                {pendingAccounts.length > 0 && (
                  <span className="bg-rose-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{pendingAccounts.length}</span>
                )}
              </span>
            </button>
          )}

          {/* CEO-only: Organisation tab */}
          {user?.role === 'CEO' && (
            <button
              onClick={() => setActiveTab('organisation')}
              className={`pb-3 font-semibold text-sm transition-all border-b-2 ${activeTab === 'organisation'
                  ? 'text-teal-400 border-teal-400'
                  : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
            >
              <span className="flex items-center gap-2">
                <FiUsers /> Organisation
              </span>
            </button>
          )}
        </div>

        {activeTab === 'overview' && isManagerPlus && (
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="glass-card p-5 col-span-1 md:col-span-2">
              <div className="h-64">
                <MonthlySpendTrend data={charts?.monthly_trend} />
              </div>
            </div>
            <div className="glass-card p-5 col-span-1 md:col-span-2">
              <div className="h-64">
                <SpendByCategory data={charts?.spend_by_category} />
              </div>
            </div>
            <div className="glass-card p-5 col-span-1 md:col-span-2">
              <div className="h-64">
                <RiskDistribution data={charts?.risk_distribution} />
              </div>
            </div>
            <div className="glass-card p-5 col-span-1 md:col-span-2">
              <div className="h-64">
                <ApprovalStatusPie data={charts?.approval_status} />
              </div>
            </div>
          </section>
        )}

        {activeTab === 'ai_reports' && isManagerPlus && (
          <section className="animate-fade-in-up">
            <ReportGenerator />
          </section>
        )}

        {activeTab === 'review_claims' && isManagerPlus && (
          <section className="glass-card p-6 flex flex-col gap-4">
            <div>
              <h2 className="text-lg font-bold">Team Claims Ledger</h2>
              <p className="text-sm text-slate-400 mt-1">Review, approve, and audit expenses submitted by your team.</p>
            </div>
            <TransactionGrid
              onSelectExpense={(exp) => setSelectedExpense(exp)}
              refreshTrigger={refreshTrigger}
            />
          </section>
        )}

        {activeTab === 'uploader' && (
          <section className="w-full flex flex-col gap-6">
            <ReceiptUploader onUploadComplete={() => handleRefresh()} />

            {/* Show "My Expenses" for everyone (Managers and Employees) under the Uploader */}
            <div className="glass-card p-6 w-full overflow-hidden">
              <h2 className="text-lg font-bold mb-4">My Submitted Expenses</h2>
              <div className="w-full">
                <TransactionGrid
                  onSelectExpense={(exp) => setSelectedExpense(exp)}
                  refreshTrigger={refreshTrigger}
                  employeeId={user?.employee_id}
                />
              </div>
            </div>
          </section>
        )}

        {activeTab === 'approvals' && isManagerPlus && (
          <section className="glass-card p-6">
            <h2 className="text-lg font-bold mb-4">Pending Account Approvals</h2>
            {pendingAccounts.length === 0 ? (
              <p className="text-sm text-slate-500">No pending accounts await your approval.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-700/50">
                      <th className="p-3 text-xs uppercase text-slate-400 font-semibold">Name</th>
                      <th className="p-3 text-xs uppercase text-slate-400 font-semibold">Role</th>
                      <th className="p-3 text-xs uppercase text-slate-400 font-semibold">Department</th>
                      <th className="p-3 text-xs uppercase text-slate-400 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingAccounts.map((acc) => (
                      <tr key={acc.employee_id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                        <td className="p-3 text-sm text-slate-200 font-medium">{acc.name}</td>
                        <td className="p-3 text-sm text-slate-400">{acc.role}</td>
                        <td className="p-3 text-sm text-slate-400">{acc.department}</td>
                        <td className="p-3 text-right">
                          <button onClick={() => handleApproveAccount(acc.employee_id, 'APPROVE')} className="px-3 py-1 bg-teal-500/20 text-teal-400 rounded-lg text-xs font-medium hover:bg-teal-500/30 transition mr-2">
                            Approve
                          </button>
                          <button onClick={() => handleApproveAccount(acc.employee_id, 'REJECT')} className="px-3 py-1 bg-rose-500/10 text-rose-400 rounded-lg text-xs font-medium hover:bg-rose-500/20 transition">
                            Reject
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* CEO Organisation Tab */}
        {activeTab === 'organisation' && user?.role === 'CEO' && (
          <section className="animate-fade-in-up">
            <ActiveUsersPanel />
          </section>
        )}

      </main>

      {/* ── SLIDE-IN AUDIT DETAIL PANEL ─────────────────────────────────────── */}
      {selectedExpense && (
        <ReviewPanel
          expense={selectedExpense}
          onClose={() => setSelectedExpense(null)}
          onReviewComplete={handleReviewComplete}
          readOnly={!isManagerPlus || selectedExpense.employee_name === user?.name || selectedExpense.employee_id === user?.employee_id}
        />
      )}

      {/* ── PROFILE MODAL ─────────────────────────────────────────────────── */}
      {showProfile && (
        <ProfileModal onClose={() => setShowProfile(false)} />
      )}

      {/* ── LOGOUT CONFIRMATION MODAL ────────────────────────────────────── */}
      <ConfirmModal
        isOpen={showLogoutConfirm}
        title="Sign Out"
        message="Are you sure you want to sign out of ExpenseOps? Any unsaved changes will be lost."
        confirmText="Yes, Sign Out"
        cancelText="Stay"
        variant="warning"
        onConfirm={() => { setShowLogoutConfirm(false); logout(); }}
        onCancel={() => setShowLogoutConfirm(false)}
      />

    </div>
  );
}
