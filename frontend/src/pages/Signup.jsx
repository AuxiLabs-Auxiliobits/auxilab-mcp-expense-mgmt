import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { requestOtp, signup, fetchManagers } from '../api/client';
import { FiMail, FiLock, FiUser, FiBriefcase, FiShield, FiLoader, FiCheckCircle } from 'react-icons/fi';

export default function Signup() {
  const [step, setStep] = useState(1); // 1: Details, 2: OTP, 3: Success
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'Software Engineer',
    department: 'Engineering',
    manager_id: '',
    master_key: ''
  });
  const [otp, setOtp] = useState('');
  
  const [managers, setManagers] = useState([]);

  const departmentRoles = {
    'Engineering': ['Software Engineer', 'Manager', 'Director', 'VP'],
    'Sales': ['Analyst', 'Manager', 'Director', 'VP'],
    'Finance': ['Analyst', 'Manager', 'Director', 'VP'],
    'Operations': ['Analyst', 'Manager', 'Director', 'VP'],
    'Executive': ['CEO']
  };

  useEffect(() => {
    if (["Software Engineer", "Analyst"].includes(formData.role)) {
      fetchManagers().then(setManagers).catch(console.error);
    }
  }, [formData.role]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    let updates = { [name]: value };
    
    // Auto-select Executive department for CEO
    if (name === 'role' && value === 'CEO') {
      updates.department = 'Executive';
    }
    
    setFormData(prev => ({ ...prev, ...updates }));
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    if (["Software Engineer", "Analyst"].includes(formData.role) && !formData.manager_id) {
      setError("Please select a manager for approval.");
      return;
    }
    setError('');
    setLoading(true);
    try {
      await requestOtp(formData.email);
      setStep(2);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMsg = Array.isArray(detail) ? detail[0].msg : detail;
      setError(errMsg || "Failed to request OTP.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signup({ ...formData, otp_code: otp });
      setStep(3);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMsg = Array.isArray(detail) ? detail[0].msg : detail;
      setError(errMsg || "Invalid OTP.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError('');
    setLoading(true);
    try {
      await requestOtp(formData.email);
      // Optional: Add a success message here, e.g. using a toast, or set an info message.
      setError("New OTP sent successfully."); // Repurposing error state as info temporarily for simplicity
      setTimeout(() => setError(""), 3000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMsg = Array.isArray(detail) ? detail[0].msg : detail;
      setError(errMsg || "Failed to resend OTP.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center p-4 selection:bg-teal-500/30">
      <div className="glass-card w-full max-w-md p-8 animate-fade-in-up">
        
        <div className="text-center mb-8">
          <div className="h-12 w-12 mx-auto rounded-xl bg-gradient-to-tr from-teal-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-teal-500/20 mb-4">
            <FiShield className="text-2xl text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
            Request Access
          </h1>
          <p className="text-sm text-slate-400">
            {step === 1 ? "Enter your details to begin" : step === 2 ? "Verify your email" : "Account Created"}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm text-center">
            {error}
          </div>
        )}

        {step === 1 && (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Full Name</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <FiUser className="text-slate-500" />
                </div>
                <input required type="text" name="name" value={formData.name} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 pl-10 pr-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50" placeholder="Jane Doe" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Email Address</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <FiMail className="text-slate-500" />
                </div>
                <input required type="email" name="email" value={formData.email} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 pl-10 pr-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50" placeholder="jane@expenseops.com" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <FiLock className="text-slate-500" />
                </div>
                <input required minLength={6} type="password" name="password" value={formData.password} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 pl-10 pr-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50" placeholder="••••••••" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Department</label>
                <select name="department" value={formData.department} onChange={(e) => {
                  const newDept = e.target.value;
                  const validRoles = departmentRoles[newDept];
                  setFormData({ 
                    ...formData, 
                    department: newDept,
                    role: validRoles.includes(formData.role) ? formData.role : validRoles[0]
                  });
                }} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 px-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/50">
                  {Object.keys(departmentRoles).map(dept => (
                    <option key={dept} value={dept}>{dept}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Role</label>
                <select name="role" value={formData.role} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 px-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/50">
                  {departmentRoles[formData.department]?.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>

            {["Software Engineer", "Analyst"].includes(formData.role) && (
              <div className="animate-fade-in-up">
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Select Your Manager</label>
                <select required name="manager_id" value={formData.manager_id} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 px-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/50">
                  <option value="">-- Choose a Manager --</option>
                  {managers.map(m => (
                    <option key={m.employee_id} value={m.employee_id}>{m.name} ({m.role})</option>
                  ))}
                </select>
            <p className="text-[10px] text-slate-500 mt-1">This manager will be assigned as your reporting manager.</p>
              </div>
            )}

            {["CEO", "Director"].includes(formData.role) && (
              <div className="animate-fade-in-up">
                <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">Master Key</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <FiLock className="text-slate-500" />
                  </div>
                  <input required type="password" name="master_key" value={formData.master_key} onChange={handleChange} className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl py-2.5 pl-10 pr-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50" placeholder="Enter executive master key" />
                </div>
                <p className="text-[10px] text-slate-500 mt-1">Required to register an executive account.</p>
              </div>
            )}

            <button type="submit" disabled={loading} className="w-full flex items-center justify-center gap-2 py-3 mt-4 rounded-xl bg-gradient-to-r from-teal-500 to-indigo-500 text-white font-medium shadow-lg shadow-teal-500/20 hover:shadow-teal-500/40 hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-70">
              {loading ? <FiLoader className="animate-spin" /> : "Send OTP"}
            </button>
          </form>
        )}

        {step === 2 && (
          <form onSubmit={handleVerifyOtp} className="space-y-5 animate-fade-in-up">
            <div className="text-center p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
              <p className="text-sm text-slate-300">We've sent a 6-digit OTP to <strong>{formData.email}</strong>.</p>
              <p className="text-xs text-slate-500 mt-2">Please check your inbox and spam folder.</p>
            </div>
            
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider text-center">Enter 6-Digit Code</label>
              <input required type="text" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value)} className="w-full text-center tracking-[0.5em] text-2xl font-mono bg-slate-900/50 border border-slate-700/50 rounded-xl py-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/50" placeholder="••••••" />
            </div>

            <button type="submit" disabled={loading || otp.length !== 6} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-teal-500 to-indigo-500 text-white font-medium shadow-lg shadow-teal-500/20 hover:shadow-teal-500/40 hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-70">
              {loading ? <FiLoader className="animate-spin" /> : "Verify & Register"}
            </button>
            
            <div className="flex items-center justify-between mt-4">
              <button type="button" disabled={loading} onClick={handleResendOtp} className="text-sm text-teal-400 hover:text-teal-300 transition-colors">
                Resend OTP
              </button>
              <button type="button" onClick={() => setStep(1)} className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
                Back to details
              </button>
            </div>
          </form>
        )}

        {step === 3 && (
          <div className="text-center space-y-4 animate-fade-in-up">
            <FiCheckCircle className="w-16 h-16 text-emerald-400 mx-auto" />
            <h2 className="text-xl font-bold text-slate-100">Registration Complete</h2>
            <p className="text-sm text-slate-400">
              Your account has been created and is <strong>fully active</strong>.
            </p>
            <p className="text-xs text-slate-500 p-3 bg-slate-900/50 rounded-lg border border-slate-800">
              You can now log in using your credentials.
            </p>
            <Link to="/login" className="block w-full py-3 rounded-xl bg-slate-800 text-white font-medium hover:bg-slate-700 transition-colors">
              Return to Login
            </Link>
          </div>
        )}

        {step === 1 && (
          <div className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="text-teal-400 hover:text-teal-300 font-medium transition-colors">
              Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
