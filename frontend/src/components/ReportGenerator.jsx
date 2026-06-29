import React, { useState } from 'react';
import { FiCpu, FiUser, FiCalendar, FiFileText } from 'react-icons/fi';
import { generateEmployeeSummary } from '../api/client';
import { useToast } from '../context/ToastContext';

export default function ReportGenerator() {
  const { addToast } = useToast();
  
  // Set default dates: start of current month to today
  const today = new Date();
  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  
  const [employeeId, setEmployeeId] = useState('');
  const [startDate, setStartDate] = useState(startOfMonth.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!employeeId.trim()) {
      addToast('Please enter an Employee ID.', 'error');
      return;
    }

    setLoading(true);
    setReport(null);
    try {
      const res = await generateEmployeeSummary(employeeId.trim(), startDate, endDate);
      setReport(res.report);
      addToast('AI Report generated successfully.', 'success');
    } catch (err) {
      console.error(err);
      addToast(err.response?.data?.detail || 'Failed to generate report.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white/5 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-2xl mt-6">
      <div className="flex items-center space-x-3 mb-6">
        <div className="p-3 rounded-full bg-blue-500/20 text-blue-400">
          <FiCpu className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">AI Executive Summary</h2>
          <p className="text-sm text-gray-400">Generate a comprehensive audit narrative for an employee's expenses.</p>
        </div>
      </div>

      <form onSubmit={handleGenerate} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Employee ID */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Employee ID
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FiUser className="text-gray-400" />
              </div>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="e.g. EMP001"
                className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                required
              />
            </div>
          </div>

          {/* Start Date */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Start Date
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FiCalendar className="text-gray-400" />
              </div>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                required
              />
            </div>
          </div>

          {/* End Date */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
              End Date
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FiCalendar className="text-gray-400" />
              </div>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                required
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className={`px-6 py-3 rounded-xl font-bold text-white transition-all duration-300 flex items-center space-x-2 ${
              loading 
                ? 'bg-blue-600/50 cursor-not-allowed' 
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 hover:shadow-[0_0_20px_rgba(79,70,229,0.4)]'
            }`}
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Synthesizing Data...</span>
              </>
            ) : (
              <>
                <FiCpu />
                <span>Generate AI Audit</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Results Section */}
      {report && (
        <div className="mt-8 pt-8 border-t border-white/10 animate-fade-in-up">
          <div className="flex items-center space-x-3 mb-4">
            <FiFileText className="text-indigo-400 w-5 h-5" />
            <h3 className="text-lg font-bold text-white">Generated Report</h3>
          </div>
          <div className="bg-gray-900/50 rounded-xl p-6 border border-white/5">
            <pre className="whitespace-pre-wrap text-gray-300 font-mono text-sm leading-relaxed">
              {report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
