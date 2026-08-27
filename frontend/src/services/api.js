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

/* ── Reference data (public, no admin auth needed) ── */
export const referenceAPI = {
  datingOptions: () => v1.get('/reference/dating-options'),
  locations:     (params) => v1.get('/reference/locations', { params }),
};

/* ── Admin (LinkUp) ── */
export const adminAPI = {
  stats:          () => v1.get('/admin/stats'),

  accounts:       (params) => v1.get('/admin/accounts', { params }),
  accountCreate:  (data) => v1.post('/admin/accounts', data),
  accountShow:    (id) => v1.get(`/admin/accounts/${id}`),
  accountStatus:  (id, data) => v1.put(`/admin/accounts/${id}/status`, data),
  accountPremium: (id, data) => v1.put(`/admin/accounts/${id}/premium`, data),

  reports:        (params) => v1.get('/admin/reports', { params }),
  reportResolve:  (id, data) => v1.put(`/admin/reports/${id}/resolve`, data),

  hubs:           (params) => v1.get('/admin/hubs', { params }),
  events:         (params) => v1.get('/admin/events', { params }),

  // Listings importer — discovery, claims, verification (see
  // PROFILE_CLAIM_IMPORTER_PLAN.md). Read-only on discovery/sources for now;
  // there is no crawl-trigger endpoint yet (Phase 12) and no adapter to run
  // regardless — both configured sources are 'unavailable'.
  listingSources:        () => v1.get('/admin/listings/sources'),
  listingsDiscovered:    (params) => v1.get('/admin/listings/discovered', { params }),
  listingClaims:         (params) => v1.get('/admin/listings/claims', { params }),
  listingReviewLiveness: (claimId, data) => v1.post(`/admin/listings/claims/${claimId}/review-liveness`, data),
  listingTransitionClaim: (claimId, data) => v1.post(`/admin/listings/claims/${claimId}/transition`, data),
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
