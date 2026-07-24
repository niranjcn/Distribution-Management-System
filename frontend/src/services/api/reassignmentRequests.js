import { apiRequest } from './client';

export const reassignmentRequestsAPI = {
  getRequests: async (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/reassignment-requests?${qs}`);
  },
  getRequest: async (id) => {
    return apiRequest(`/reassignment-requests/${id}`);
  },
  reassign: async (id, data) => {
    return apiRequest(`/reassignment-requests/${id}/reassign`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  reject: async (id) => {
    return apiRequest(`/reassignment-requests/${id}/reject`, {
      method: 'POST',
    });
  },
};
