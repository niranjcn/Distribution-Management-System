import { apiRequest } from './client';

export const operatorsAPI = {
  getOperators: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/operators?${queryString}`);
    return response;
  },

  getOperator: async (operatorId) => {
    const response = await apiRequest(`/operators/${operatorId}`);
    return response;
  },

  getOperatorDevices: async (operatorId) => {
    const response = await apiRequest(`/operators/${operatorId}/devices`);
    return response;
  },

  createOperator: async (operatorData) => {
    const response = await apiRequest('/operators', {
      method: 'POST',
      body: JSON.stringify(operatorData),
    });
    return response;
  },

  updateOperator: async (operatorId, operatorData) => {
    const response = await apiRequest(`/operators/${operatorId}`, {
      method: 'PUT',
      body: JSON.stringify(operatorData),
    });
    return response;
  },

  deleteOperator: async (operatorId) => {
    const response = await apiRequest(`/operators/${operatorId}`, {
      method: 'DELETE',
    });
    return response;
  },
};
