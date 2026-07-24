import { apiRequest } from './client';

export const approvalsAPI = {
  getApprovals: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/approvals?${queryString}`);
    return response;
  },

  getApproval: async (approvalId) => {
    const response = await apiRequest(`/approvals/${approvalId}`);
    return response;
  },

  approveRequest: async (approvalId, notes) => {
    const response = await apiRequest(`/approvals/${approvalId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
    return response;
  },

  rejectRequest: async (approvalId, rejectionReason, notes) => {
    const response = await apiRequest(`/approvals/${approvalId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejection_reason: rejectionReason, notes }),
    });
    return response;
  },

  getRoleRoutingConfig: async () => {
    const response = await apiRequest('/approvals/role-routing/config');
    return response;
  },

  updateRoleRoutingConfig: async (payload) => {
    const response = await apiRequest('/approvals/role-routing/config', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return response;
  },
};
