import React, { useState } from 'react';
import { FiX, FiUser, FiLock, FiLoader, FiCheckCircle } from 'react-icons/fi';
import { changePassword } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function ProfileModal({ onClose }) {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword
      });
      setSuccess('Password updated successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMsg = Array.isArray(detail) ? detail[0].msg : detail;
      setError(errMsg || 'Failed to change password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div 
        className="fixed inset-0 bg-[#020617]/80 backdrop-blur-sm z-50 animate-fade-in"
        onClick={onClose}
      />
      
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-50">
        <div className="glass-card w-full shadow-2xl animate-fade-in-up flex flex-col max-h-[90vh] overflow-hidden">
          
          <div className="flex items-center justify-between p-5 border-b border-slate-700/50">
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <FiUser className="text-teal-400" />
              Profile Settings
            </h2>
            <button 
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
            >
              <FiX className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 overflow-y-auto custom-scrollbar">
            
            <div className="mb-8">
              <h3 className="text-xs uppercase font-semibold text-slate-500 tracking-wider mb-4">Account Details</h3>
              <div className="space-y-4">
                <div>
                  <div className="text-xs text-slate-500">Name</div>
                  <div className="text-sm font-medium text-slate-200">{user?.name}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Role</div>
                  <div className="text-sm font-medium text-slate-200">{user?.role}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Department</div>
                  <div className="text-sm font-medium text-slate-200">{user?.department}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Employee ID</div>
                  <div className="text-sm font-medium text-slate-200">{user?.employee_id}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-xs uppercase font-semibold text-slate-500 tracking-wider mb-4 flex items-center gap-2">
                <FiLock /> Change Password
              </h3>
              
              {error && (
                <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
                  {error}
                </div>
              )}
              {success && (
                <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm flex items-center gap-2">
                  <FiCheckCircle />
                  {success}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Current Password</label>
                  <input
                    type="password"
                    required
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">New Password</label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Confirm New Password</label>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || !currentPassword || !newPassword || !confirmPassword}
                  className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-teal-500/20 text-teal-400 font-semibold text-sm hover:bg-teal-500/30 disabled:opacity-50 transition-colors"
                >
                  {loading ? <FiLoader className="animate-spin" /> : 'Update Password'}
                </button>
              </form>
            </div>

          </div>
        </div>
      </div>
    </>
  );
}
