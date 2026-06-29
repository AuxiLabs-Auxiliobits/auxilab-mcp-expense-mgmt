import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('expenseops_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Auth ---
export async function requestOtp(email) {
  const res = await api.post('/auth/request-otp', { email });
  return res.data;
}

export async function signup(data) {
  const res = await api.post('/auth/signup', data);
  return res.data;
}

export async function login(email, password) {
  const res = await api.post('/auth/login', { email, password });
  return res.data;
}

export async function requestPasswordResetOtp(email) {
  const res = await api.post('/auth/forgot-password', { email });
  return res.data;
}

export async function resetPassword(email, otp_code, new_password) {
  const res = await api.post('/auth/reset-password', { email, otp_code, new_password });
  return res.data;
}

export async function fetchMe() {
  const res = await api.get('/auth/me');
  return res.data;
}

export async function fetchManagers() {
  const res = await api.get('/auth/managers');
  return res.data;
}

export async function fetchPendingApprovals() {
  const res = await api.get('/users/pending-approvals');
  return res.data;
}

export async function approveUserAccount(employeeId, action) {
  const res = await api.post(`/users/${employeeId}/approve`, { action });
  return res.data;
}

export async function fetchActiveUsers() {
  const res = await api.get('/users/active');
  return res.data;
}

export async function deleteUser(employeeId) {
  const res = await api.delete(`/users/${employeeId}`);
  return res.data;
}

// --- Dashboard ---
export async function fetchMetrics() {
  const res = await api.get('/dashboard/metrics');
  return res.data;
}

export async function fetchCharts() {
  const res = await api.get('/dashboard/charts');
  return res.data;
}

export async function exportReport() {
  const res = await api.get('/dashboard/export', { responseType: 'blob' });
  return res.data;
}

// --- Expenses ---
export async function fetchExpenses(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      params.append(key, val);
    }
  });
  const res = await api.get(`/expenses/?${params.toString()}`);
  return res.data;
}

export async function fetchExpense(id) {
  const res = await api.get(`/expenses/${id}`);
  return res.data;
}

export async function submitExpense(data) {
  const res = await api.post('/expenses/submit', data);
  return res.data;
}

export async function reviewExpense(id, action, notes = '', amount = null) {
  let status = action === 'APPROVE' ? 'APPROVED' : action === 'REJECT' ? 'REJECTED' : 'ESCALATED';
  const body = { status, system_notes: notes };
  if (amount !== null && amount > 0) body.amount = amount;
  const res = await api.put(`/expenses/${id}/review`, body);
  return res.data;
}

export async function uploadReceipt(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/expenses/upload-receipt', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function bulkImport(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/expenses/bulk-import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function clearAllExpenses() {
  const res = await api.delete('/expenses/clear');
  return res.data;
}

export async function downloadReceipt(filename) {
  const res = await api.get(`/expenses/uploads/${filename}`, {
    responseType: 'blob'
  });
  return res.data;
}

export async function changePassword(data) {
  const res = await api.put('/auth/change-password', data);
  return res.data;
}

export async function generateEmployeeSummary(employeeId, startDate, endDate) {
  const res = await api.get('/expenses/summary', {
    params: { employee_id: employeeId, start_date: startDate, end_date: endDate }
  });
  return res.data;
}

export async function switchEnvironment(environment) {
  const res = await api.post('/auth/environment', { environment });
  return res.data;
}

export default api;
