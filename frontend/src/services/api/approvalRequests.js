import { apiRequest } from './client';

export const approvalRequestsAPI = {
  submit: (data) => apiRequest('/approval-requests', { method: 'POST', body: JSON.stringify(data) }),
  getMy: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/approval-requests/my?${qs}`);
  },
  getPending: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/approval-requests/pending?${qs}`);
  },
  getDetail: (requestId) => apiRequest(`/approval-requests/${requestId}`),
  decide: (requestId, data) => apiRequest(`/approval-requests/${requestId}/decide`, { method: 'POST', body: JSON.stringify(data) }),
  cancel: (requestId) => apiRequest(`/approval-requests/${requestId}/cancel`, { method: 'POST' }),
  stageBulk: (formData) => apiRequest('/approval-requests/stage-bulk', { method: 'POST', body: formData }),
};