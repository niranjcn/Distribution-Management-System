import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const externalInventoryAPI = {
  getDashboard: async () => {
    const response = await apiRequest('/external-inventory/dashboard');
    return response;
  },

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

  updateItem: async (inventoryId, payload) => {
    const response = await apiRequest(`/external-inventory/items/${inventoryId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return response;
  },

  deleteItem: async (inventoryId) => {
    const response = await apiRequest(`/external-inventory/items/${inventoryId}`, {
      method: 'DELETE',
    });
    return response;
  },

  uploadItemImage: async (inventoryId, file) => {
    const formData = new FormData();
    formData.append('image', file);

    const response = await fetch(`${API_BASE_URL}/external-inventory/items/${inventoryId}/image`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...buildCsrfHeader('POST') },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.message || data?.detail || 'Failed to upload item image');
    }
    return data;
  },

  createAdjustment: async (payload) => {
    const response = await apiRequest('/external-inventory/adjustments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  getPurchaseOrders: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/external-inventory/purchase-orders?${queryString}`);
    return response;
  },

  createPurchaseOrder: async (payload) => {
    const response = await apiRequest('/external-inventory/purchase-orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  receivePurchaseOrder: async (poId, payload) => {
    const response = await apiRequest(`/external-inventory/purchase-orders/${poId}/receive`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  getReceipts: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/external-inventory/receipts?${queryString}`);
    return response;
  },

  getMovements: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/external-inventory/movements?${queryString}`);
    return response;
  },
};
