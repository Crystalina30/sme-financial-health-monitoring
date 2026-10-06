/**
 * Thin wrapper around fetch.
 *
 * Holds the base URL, attaches the bearer token and turns an error response
 * into a thrown Error, so pages and hooks do not repeat that handling.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'fyp_access_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function describeError(body, status) {
  if (!body) return `Request failed (${status}).`;
  const { detail } = body;
  if (typeof detail === 'string') return detail;
  if (detail?.errors?.length) return detail.errors.join(' ');
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || 'Invalid value').join(' ');
  }
  return `Request failed (${status}).`;
}

export async function apiRequest(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = new Error(describeError(payload, response.status));
    error.status = response.status;
    throw error;
  }
  return payload;
}

export const api = {
  register: (data) => apiRequest('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (data) => apiRequest('/auth/login', { method: 'POST', body: data, auth: false }),
  me: () => apiRequest('/auth/me'),

  listCompanies: () => apiRequest('/companies'),
  createCompany: (data) => apiRequest('/companies', { method: 'POST', body: data }),
  getCompany: (id) => apiRequest(`/companies/${id}`),
  updateCompany: (id, data) => apiRequest(`/companies/${id}`, { method: 'PUT', body: data }),

  listPeriods: (companyId) => apiRequest(`/companies/${companyId}/reporting-periods`),
  createPeriod: (companyId, data) =>
    apiRequest(`/companies/${companyId}/reporting-periods`, { method: 'POST', body: data }),

  listRecords: (companyId) => apiRequest(`/companies/${companyId}/financial-records`),
  createRecord: (companyId, data) =>
    apiRequest(`/companies/${companyId}/financial-records`, { method: 'POST', body: data }),
  updateRecord: (recordId, data) =>
    apiRequest(`/financial-records/${recordId}`, { method: 'PUT', body: data }),

  getIndicators: (companyId, periodId) =>
    apiRequest(`/companies/${companyId}/indicators/${periodId}`),
  getDashboard: (companyId, periodId) =>
    apiRequest(`/companies/${companyId}/dashboard/${periodId}`),
  listThresholds: () => apiRequest('/thresholds'),
};
