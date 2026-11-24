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

/** Send a file as multipart form data, with the same error handling. */
export async function apiUpload(path, file) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(`${BASE_URL}/api${path}`, { method: 'POST', headers, body });
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

  // The account's one organisation (an SME), and its overview.
  getOrganisation: () => apiRequest('/organisation'),
  setUpOrganisation: (data) => apiRequest('/organisation', { method: 'POST', body: data }),
  selectOrganisation: (companyId) =>
    apiRequest('/organisation/select', { method: 'POST', body: { company_id: companyId } }),
  getOverview: () => apiRequest('/organisation/overview'),
  listMembers: () => apiRequest('/organisation/members'),
  listInvitations: () => apiRequest('/organisation/invitations'),
  createInvitation: (data) => apiRequest('/organisation/invitations', { method: 'POST', body: data }),
  revokeInvitation: (id) => apiRequest(`/organisation/invitations/${id}`, { method: 'DELETE' }),
  previewInvitation: (token) =>
    apiRequest(`/organisation/invitations/preview?token=${encodeURIComponent(token)}`),
  acceptInvitation: (token) =>
    apiRequest('/organisation/invitations/accept', { method: 'POST', body: { token } }),
  getAuditLog: () => apiRequest('/organisation/audit-log?limit=100'),
  updateMember: (id, role) =>
    apiRequest(`/organisation/members/${id}`, { method: 'PATCH', body: { role } }),
  removeMember: (id) => apiRequest(`/organisation/members/${id}`, { method: 'DELETE' }),

  getCompany: (id) => apiRequest(`/companies/${id}`),
  updateCompany: (id, data) => apiRequest(`/companies/${id}`, { method: 'PUT', body: data }),

  listPeriods: (companyId) => apiRequest(`/companies/${companyId}/reporting-periods`),
  createPeriod: (companyId, data) =>
    apiRequest(`/companies/${companyId}/reporting-periods`, { method: 'POST', body: data }),
  updatePeriod: (companyId, periodId, data) =>
    apiRequest(`/companies/${companyId}/reporting-periods/${periodId}`, {
      method: 'PUT',
      body: data,
    }),
  // The period must be named, so a wrong id cannot delete the wrong period.
  deletePeriod: (companyId, periodId, label) =>
    apiRequest(
      `/companies/${companyId}/reporting-periods/${periodId}?confirm_label=${encodeURIComponent(label)}`,
      { method: 'DELETE' },
    ),

  listRecords: (companyId) => apiRequest(`/companies/${companyId}/financial-records`),
  createRecord: (companyId, data) =>
    apiRequest(`/companies/${companyId}/financial-records`, { method: 'POST', body: data }),
  updateRecord: (recordId, data) =>
    apiRequest(`/financial-records/${recordId}`, { method: 'PUT', body: data }),

  listAccountCategories: () => apiRequest('/trial-balance/categories'),
  previewTrialBalance: (lines) =>
    apiRequest('/trial-balance/preview', { method: 'POST', body: { lines } }),
  suggestCategories: (companyId, lines) =>
    apiRequest(`/companies/${companyId}/trial-balance/suggest`, {
      method: 'POST',
      body: { lines },
    }),
  submitTrialBalance: (companyId, data) =>
    apiRequest(`/companies/${companyId}/trial-balance`, { method: 'POST', body: data }),
  getTrialBalance: (recordId) => apiRequest(`/financial-records/${recordId}/trial-balance`),
  importTrialBalance: (companyId, file) =>
    apiUpload(`/companies/${companyId}/trial-balance/import`, file),

  getIndicators: (companyId, periodId) =>
    apiRequest(`/companies/${companyId}/indicators/${periodId}`),
  getDashboard: (companyId, periodId) =>
    apiRequest(`/companies/${companyId}/dashboard/${periodId}`),
  listThresholds: () => apiRequest('/thresholds'),
};
