const API_BASE = import.meta.env.VITE_API_URL || '';

async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getStats: () => fetchJSON('/api/dashboard/stats'),
  getClaims: (employeeId) =>
    fetchJSON(employeeId ? `/api/claims?employee_id=${employeeId}` : '/api/claims'),
  getTrips: () => fetchJSON('/api/trips'),
  getEmployees: () => fetchJSON('/api/employees'),
  getPolicy: () => fetchJSON('/api/policy'),
  planBudget: (data) =>
    fetchJSON('/api/budget/plan', { method: 'POST', body: JSON.stringify(data) }),
  checkCompliance: (data) =>
    fetchJSON('/api/policy/check', { method: 'POST', body: JSON.stringify(data) }),
  preApprove: (data) =>
    fetchJSON('/api/trip/pre-approve', { method: 'POST', body: JSON.stringify(data) }),
  generateReport: (approvalToken) =>
    fetchJSON('/api/trip/report', {
      method: 'POST',
      body: JSON.stringify({ approval_token: approvalToken }),
    }),
  classifySpend: (merchant, description = '') =>
    fetchJSON('/api/spend/classify', {
      method: 'POST',
      body: JSON.stringify({ merchant_name: merchant, description }),
    }),
  duplicateCheck: (data) =>
    fetchJSON('/api/claim/duplicate-check', { method: 'POST', body: JSON.stringify(data) }),
  chat: (messages) =>
    fetchJSON('/api/chat', { method: 'POST', body: JSON.stringify({ messages }) }),
  parseReceipt: async (file) => {
    const form = new FormData();
    form.append('file', file);
    // No Content-Type header — the browser sets the multipart boundary.
    const res = await fetch(`${API_BASE}/api/receipts/parse`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
};
