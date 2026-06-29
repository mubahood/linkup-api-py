import axios from 'axios';

// All admin endpoints live under /v1/admin/* (LinkUp API).
const v1 = axios.create({
  baseURL: '/v1',
  headers: { 'Content-Type': 'application/json' },
});

v1.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

v1.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

/* ── Auth ── */
export const authAPI = {
  // POST /v1/admin/login — accepts phone, email, or handle + password
  login: ({ email, password }) => v1.post('/admin/login', { identifier: email, password }),
};

/* ── Admin (LinkUp) ── */
export const adminAPI = {
  stats:          () => v1.get('/admin/stats'),

  accounts:       (params) => v1.get('/admin/accounts', { params }),
  accountShow:    (id) => v1.get(`/admin/accounts/${id}`),
  accountStatus:  (id, data) => v1.put(`/admin/accounts/${id}/status`, data),
  accountPremium: (id, data) => v1.put(`/admin/accounts/${id}/premium`, data),

  reports:        (params) => v1.get('/admin/reports', { params }),
  reportResolve:  (id, data) => v1.put(`/admin/reports/${id}/resolve`, data),

  hubs:           (params) => v1.get('/admin/hubs', { params }),
  events:         (params) => v1.get('/admin/events', { params }),
};

// Unwrap helpers for the API envelope: { code, message, data: ... }
export const dataOf = (res) => res?.data?.data;
// Paginated envelope: data = { current_page, data: [...], per_page, total, last_page }
export const pageOf = (res) => {
  const d = res?.data?.data || {};
  return {
    items: d.data || [],
    total: d.total || 0,
    page: d.current_page || 1,
    perPage: d.per_page || 20,
    lastPage: d.last_page || 1,
  };
};

export default v1;
