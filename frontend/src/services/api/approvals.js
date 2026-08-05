import { apiRequest } from './client';

export const approvalsAPI = {
  getPendingApprovals: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/approvals/pending?${queryString}` : '/approvals/pending';
    const response = await apiRequest(endpoint);
    return response;
  },
};
