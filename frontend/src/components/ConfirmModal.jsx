import React from 'react';
import { FiAlertTriangle, FiX } from 'react-icons/fi';

/**
 * ConfirmModal – lightweight reusable confirmation dialog.
 *
 * Props:
 *   isOpen      {bool}     – controls visibility
 *   title       {string}   – modal headline
 *   message     {string}   – body text / description
 *   confirmText {string}   – confirm button label (default "Confirm")
 *   cancelText  {string}   – cancel button label (default "Cancel")
 *   variant     {string}   – "danger" | "warning" | "info"  (default "danger")
 *   onConfirm   {function} – called when user clicks confirm
 *   onCancel    {function} – called when user clicks cancel / backdrop
 */
export default function ConfirmModal({
  isOpen,
  title = 'Are you sure?',
  message = 'This action cannot be undone.',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}) {
  if (!isOpen) return null;

  const colors = {
    danger: { ring: 'ring-rose-500/30', icon: 'text-rose-400', btn: 'bg-rose-500/15 text-rose-400 border-rose-500/30 hover:bg-rose-500/25' },
    warning: { ring: 'ring-amber-500/30', icon: 'text-amber-400', btn: 'bg-amber-500/15 text-amber-400 border-amber-500/30 hover:bg-amber-500/25' },
    info: { ring: 'ring-teal-500/30', icon: 'text-teal-400', btn: 'bg-teal-500/15 text-teal-400 border-teal-500/30 hover:bg-teal-500/25' },
  }[variant] || {};

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-0 z-[101] flex items-center justify-center p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="glass-card w-full max-w-sm p-6 animate-fade-in-up">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div className={`flex items-center gap-2.5 ${colors.icon}`}>
              <FiAlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-base font-semibold">{title}</h3>
            </div>
            <button
              onClick={onCancel}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-all"
            >
              <FiX className="w-4 h-4" />
            </button>
          </div>

          {/* Message */}
          <p className="text-sm text-slate-300 leading-relaxed mb-6">{message}</p>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-800/60 text-slate-300 border border-slate-700/50 hover:bg-slate-700/60 transition-all"
            >
              {cancelText}
            </button>
            <button
              onClick={onConfirm}
              className={`flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold border transition-all ${colors.btn}`}
            >
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
