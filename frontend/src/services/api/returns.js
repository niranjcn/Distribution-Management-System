import { apiRequest } from './client';

export const returnsAPI = {
  getReturns: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/returns?${queryString}`);
    return response;
  },

  getReturn: async (returnId) => {
    const response = await apiRequest(`/returns/${returnId}`);
    return response;
  },

  createReturn: async (returnData) => {
    const response = await apiRequest('/returns', {
      method: 'POST',
      body: JSON.stringify(returnData),
    });
    return response;
  },

  updateReturnStatus: async (returnId, status, notes, extra = {}) => {
    const response = await apiRequest(`/returns/${returnId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes, ...extra }),
    });
    return response;
  },

  cancelReturn: async (returnId) => {
    const response = await apiRequest(`/returns/${returnId}`, {
      method: 'DELETE',
    });
    return response;
  },
};
