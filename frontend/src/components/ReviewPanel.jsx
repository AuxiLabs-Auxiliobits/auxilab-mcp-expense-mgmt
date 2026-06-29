import { useState, useCallback, useEffect } from 'react';
import {
  FiX, FiCheck, FiXCircle, FiAlertTriangle, FiShield, FiUser,
  FiCalendar, FiTag, FiMapPin, FiDollarSign, FiFileText,
  FiMessageSquare, FiEdit3,
} from 'react-icons/fi';
import { reviewExpense, downloadReceipt } from '../api/client';
import RiskBadge from './RiskBadge';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from './ConfirmModal';

// ── Helper: pull "User Remarks: …" out of system_notes ──────────────────────
function extractUserRemarks(systemNotes) {
  if (!systemNotes) return null;
  const match = systemNotes.match(/User Remarks:\s*([^|]+)/);
  return match ? match[1].trim() : null;
}

// ── Helper: pull reviewer notes (lines that start with "[… Reviewer: …]") ───
function extractReviewerNotes(systemNotes) {
  if (!systemNotes) return [];
  return systemNotes
    .split('|')
    .map((s) => s.trim())
    .filter((s) => /^\[\d{4}-\d{2}-\d{2}.*Reviewer:/.test(s));
}

export default function ReviewPanel({ expense, onClose, onReviewComplete, readOnly = false }) {
  const { addToast } = useToast();
  const { user } = useAuth();
  const [notes, setNotes] = useState('');
  const [editedAmount, setEditedAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [actionResult, setActionResult] = useState(null);
  const [pendingAction, setPendingAction] = useState(null); // {action, label, variant}

  // Initialise editable amount from the expense
  useEffect(() => {
    if (expense) setEditedAmount(String(Number(expense.amount).toFixed(2)));
  }, [expense]);

  const isException = expense?.status === 'EXCEPTION_HOLD';
  const submitterComment = extractUserRemarks(expense?.system_notes);
  const reviewerNotes = extractReviewerNotes(expense?.system_notes);

  // Is the current user the reviewer (not the submitter)?
  const isReviewer = !readOnly && user?.employee_id !== expense?.employee_id;

  const handleAction = useCallback(async (action) => {
    setLoading(true);
    try {
      const amountVal = parseFloat(editedAmount);
      const updatedAmount = !isNaN(amountVal) && amountVal > 0 ? amountVal : null;
      await reviewExpense(expense.id, action, notes, updatedAmount);
      setActionResult({ type: 'success', message: `Claim ${action.toLowerCase()}d successfully.` });
      setTimeout(() => {
        onReviewComplete?.({ ...expense, status: action === 'APPROVE' ? 'APPROVED' : action === 'REJECT' ? 'REJECTED' : 'ESCALATED' });
        onClose?.();
      }, 1500);
    } catch (err) {
      const detail = err.response?.data?.detail || `Failed to ${action.toLowerCase()} claim. Please try again.`;
      setActionResult({ type: 'error', message: detail });
    } finally {
      setLoading(false);
    }
  }, [expense, notes, editedAmount, onClose, onReviewComplete]);

  if (!expense) return null;

  const riskLevel = expense.risk_score <= 35 ? 'low' : expense.risk_score <= 70 ? 'medium' : 'high';
  const riskColors = {
    low: { ring: 'ring-emerald-500/30', text: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    medium: { ring: 'ring-amber-500/30', text: 'text-amber-400', bg: 'bg-amber-500/10' },
    high: { ring: 'ring-rose-500/30', text: 'text-rose-400', bg: 'bg-rose-500/10' },
  };
  const rc = riskColors[riskLevel];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-slate-900 border-l border-slate-700/50 shadow-2xl z-50 animate-slide-in-right overflow-y-auto">

        {/* Header */}
        <div className="sticky top-0 bg-slate-900/95 backdrop-blur-xl border-b border-slate-700/50 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Claim Review</h2>
            <span className="text-sm font-mono text-teal-400/70">{expense.id}</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-all"
          >
            <FiX className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">

          {/* Risk Score Visual */}
          <div className={`flex items-center justify-center py-6 rounded-xl ${rc.bg} ring-1 ${rc.ring}`}>
            <div className="text-center">
              <div className={`text-5xl font-bold font-mono ${rc.text}`}>{expense.risk_score}</div>
              <div className="text-sm text-slate-400 mt-1">Risk Score</div>
              <div className="mt-2"><RiskBadge score={expense.risk_score} /></div>
            </div>
          </div>

          {/* ── Submitter's Comment (only when status = Exception) ──────── */}
          {isException && submitterComment && (
            <div className="rounded-xl bg-amber-500/5 border border-amber-500/25 p-5 space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-400 uppercase tracking-wider">
                <FiMessageSquare className="w-4 h-4" />
                Submitter&apos;s Comment
              </h3>
              <p className="text-sm text-slate-200 leading-relaxed bg-slate-800/50 rounded-lg px-4 py-3 border border-slate-700/40">
                {submitterComment}
              </p>
            </div>
          )}

          {/* Claim Details */}
          <div className="glass-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Claim Details</h3>
            <div className="grid grid-cols-2 gap-4">
              <DetailRow icon={FiUser} label="Employee" value={expense.employee_name} />
              <DetailRow icon={FiTag} label="Category" value={expense.category} />
              <DetailRow icon={FiMapPin} label="Merchant" value={expense.merchant} />
              <DetailRow icon={FiCalendar} label="Date" value={expense.date} />
              <DetailRow icon={FiFileText} label="Department" value={expense.department} />
              {/* Amount — editable for reviewer, read-only for submitter */}
              <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 focus-within:border-teal-500/50 focus-within:bg-slate-800/60 transition-colors">
                <div className="flex items-center gap-2 text-slate-500">
                  <FiDollarSign className="w-3.5 h-3.5" />
                  <span className="text-xs uppercase tracking-wider font-semibold">Amount</span>
                  {isReviewer && (
                    <span className="ml-auto flex items-center gap-1 text-[10px] text-teal-400/70">
                      <FiEdit3 className="w-3 h-3" /> editable
                    </span>
                  )}
                </div>
                {isReviewer ? (
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={editedAmount}
                    onChange={(e) => setEditedAmount(e.target.value)}
                    className="w-full bg-transparent text-sm font-medium focus:outline-none text-slate-200"
                  />
                ) : (
                  <span className="text-sm font-medium text-slate-200">
                    ${Number(expense.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Policy Violations */}
          {expense.policy_violations && expense.policy_violations.length > 0 && (
            <div className="rounded-xl bg-rose-500/5 border border-rose-500/20 p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-rose-400 uppercase tracking-wider mb-3">
                <FiAlertTriangle className="w-4 h-4" />
                Policy Violations ({expense.policy_violations.length})
              </h3>
              <ul className="space-y-2">
                {expense.policy_violations.map((v, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-rose-400 shrink-0" />
                    {v}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AI Summary */}
          {expense.ai_summary && (
            <div className="rounded-xl bg-violet-500/5 border border-violet-500/20 p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-violet-400 uppercase tracking-wider mb-3">
                <FiShield className="w-4 h-4" />
                AI Analysis
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">{expense.ai_summary}</p>
            </div>
          )}

          {/* View Receipt */}
          <div className="flex justify-start">
            {expense.receipt_path ? (
              <button
                onClick={async () => {
                  try {
                    const parts = expense.receipt_path.split('/');
                    const filename = parts[parts.length - 1];
                    const blob = await downloadReceipt(filename);
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                  } catch (err) {
                    addToast('Failed to download receipt.', 'error');
                  }
                }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800/80 border border-slate-700/50 text-sm text-teal-400 hover:bg-slate-700/80 hover:text-teal-300 font-medium transition-colors"
              >
                <FiFileText className="w-4 h-4" />
                View Uploaded Receipt
              </button>
            ) : (
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800/40 border border-slate-700/30 text-sm text-slate-500 font-medium cursor-not-allowed">
                <FiFileText className="w-4 h-4 opacity-50" />
                No Receipt Attached
              </span>
            )}
          </div>

          {/* ── Reviewer Notes visible to the SUBMITTER (read-only) ─────────── */}
          {!isReviewer && reviewerNotes.length > 0 && (
            <div className="rounded-xl bg-teal-500/5 border border-teal-500/20 p-5 space-y-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-teal-400 uppercase tracking-wider">
                <FiMessageSquare className="w-4 h-4" />
                Reviewer Notes
              </h3>
              <ul className="space-y-2">
                {reviewerNotes.map((note, i) => (
                  <li key={i} className="text-sm text-slate-300 leading-relaxed bg-slate-800/50 rounded-lg px-4 py-3 border border-slate-700/40">
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Reviewer Notes input (only for reviewer) */}
          {isReviewer && (
            <div>
              <label className="block text-sm font-semibold text-slate-300 mb-2">
                Reviewer Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add review comments or justification..."
                rows={3}
                className="w-full bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500/50 resize-none transition-all"
              />
            </div>
          )}

          {/* Result Message */}
          {actionResult && (
            <div className={`rounded-xl p-4 text-sm font-medium ${actionResult.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
              }`}>
              {actionResult.message}
            </div>
          )}

          {/* Action Buttons (reviewer only) */}
          {isReviewer && (
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => setPendingAction({ action: 'APPROVE', label: 'Approve', variant: 'info' })}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-emerald-500/15 text-emerald-400 font-semibold text-sm border border-emerald-500/30 hover:bg-emerald-500/25 hover:border-emerald-500/50 disabled:opacity-50 transition-all"
              >
                <FiCheck className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={() => setPendingAction({ action: 'REJECT', label: 'Reject', variant: 'danger' })}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-rose-500/15 text-rose-400 font-semibold text-sm border border-rose-500/30 hover:bg-rose-500/25 hover:border-rose-500/50 disabled:opacity-50 transition-all"
              >
                <FiXCircle className="w-4 h-4" />
                Reject
              </button>
              <button
                onClick={() => setPendingAction({ action: 'ESCALATE', label: 'Escalate', variant: 'warning' })}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-amber-500/15 text-amber-400 font-semibold text-sm border border-amber-500/30 hover:bg-amber-500/25 hover:border-amber-500/50 disabled:opacity-50 transition-all"
              >
                <FiAlertTriangle className="w-4 h-4" />
                Escalate
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Review Action Confirmation Modal */}
      <ConfirmModal
        isOpen={!!pendingAction}
        title={`${pendingAction?.label} Expense Claim`}
        message={`Are you sure you want to ${pendingAction?.label?.toLowerCase()} this expense claim${expense?.employee_name ? ` submitted by ${expense.employee_name}` : ''}? This action will be recorded in the audit log.`}
        confirmText={loading ? 'Processing…' : `Yes, ${pendingAction?.label}`}
        cancelText="Cancel"
        variant={pendingAction?.variant || 'danger'}
        onConfirm={() => { const a = pendingAction?.action; setPendingAction(null); handleAction(a); }}
        onCancel={() => setPendingAction(null)}
      />
    </>
  );
}

function DetailRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
      <div>
        <div className="text-xs text-slate-500">{label}</div>
        <div className="text-sm text-slate-200 font-medium">{value}</div>
      </div>
    </div>
  );
}
