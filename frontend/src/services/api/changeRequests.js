import { apiRequest } from './client';

export const changeRequestsAPI = {
  submit: (data) => apiRequest('/change-requests', { method: 'POST', body: JSON.stringify(data) }),
  requestReplacementTransferFix: (defectId, notes = '') =>
    apiRequest('/change-requests', {
      method: 'POST',
      body: JSON.stringify({
        request_type: 'replacement_transfer_fix',
        device_id: String(defectId),
        reason: notes || undefined,
      }),
    }),
  submitDeviceDeleteRequest: (deviceIds, reason = '') =>
    apiRequest('/change-requests', {
      method: 'POST',
      body: JSON.stringify({
        request_type: 'device_delete_change',
        device_ids: (deviceIds || []).map(String),
        reason: reason || undefined,
      }),
    }),
  getRequests: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/change-requests?${qs}`);
  },
  review: (requestId, data) => apiRequest(`/change-requests/${requestId}/review`, { method: 'PATCH', body: JSON.stringify(data) }),
};
