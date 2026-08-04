import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const externalInventoryAPI = {
  getItems: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/external-inventory/items?${queryString}`);
    return response;
  },

  createItem: async (payload) => {
    const response = await apiRequest('/external-inventory/items', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  bulkUploadItems: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/external-inventory/items/bulk-upload`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...buildCsrfHeader('POST') },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.message || data?.detail || 'Import failed');
    }
    return data;
  },

  updateItem: async (itemId, payload) => {
    const response = await apiRequest(`/external-inventory/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return response;
  },

  deleteItem: async (itemId) => {
    const response = await apiRequest(`/external-inventory/items/${itemId}`, {
      method: 'DELETE',
    });
    return response;
  },

  distributeItem: async (payload) => {
    const response = await apiRequest('/external-inventory/distributions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  bulkDistributeItems: async (payload) => {
    const response = await apiRequest('/external-inventory/distributions/bulk', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  bulkUploadDistribution: async (file, toUserId, notes) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('to_user_id', String(toUserId));
    if (notes) {
      formData.append('notes', notes);
    }

    const response = await fetch(`${API_BASE_URL}/external-inventory/distributions/bulk-upload`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...buildCsrfHeader('POST') },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.message || data?.detail || 'Bulk distribution failed');
    }
    return data;
  },

  getDistributions: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/external-inventory/distributions?${queryString}`);
    return response;
  },
};