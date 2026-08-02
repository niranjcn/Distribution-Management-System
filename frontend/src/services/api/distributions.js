import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const distributionsAPI = {
  getDistributions: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/distributions?${queryString}`);
    return response;
  },

  getDistribution: async (distributionId) => {
    const response = await apiRequest(`/distributions/${distributionId}`);
    return response;
  },

  getPendingDistributions: async () => {
    const response = await apiRequest('/distributions/pending');
    return response;
  },

  getDistributionDevices: async (distributionId, params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString
      ? `/distributions/${distributionId}/devices?${queryString}`
      : `/distributions/${distributionId}/devices`;
    const response = await apiRequest(endpoint);
    return response;
  },

  createDistribution: async (distributionData) => {
    const response = await apiRequest('/distributions', {
      method: 'POST',
      body: JSON.stringify(distributionData),
    });
    return response;
  },

  bulkUpload: async (file, toUserId, notes = '', dateOfDistribution = '') => {
    if (!file) {
      throw new Error('No file selected for upload');
    }

    const formData = new FormData();

    const fileBuffer = await file.arrayBuffer();
    const fileSnapshot = new Blob([fileBuffer], { type: file.type || 'application/octet-stream' });
    formData.append('file', fileSnapshot, file.name || 'bulk-upload.csv');

    formData.append('to_user_id', toUserId);
    if (notes) {
      formData.append('notes', notes);
    }
    if (dateOfDistribution) {
      formData.append('date_of_distribution', dateOfDistribution);
    }

    const response = await fetch(`${API_BASE_URL}/distributions/bulk-upload`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        ...buildCsrfHeader('POST'),
      },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || data.detail || 'Failed to upload distribution file');
    }

    return data;
  },

  downloadManifest: async (distributionId) => {
    const url = `${API_BASE_URL}/distributions/${distributionId}/manifest`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download distribution manifest';
      try {
        const text = await response.text();
        const parsed = text ? JSON.parse(text) : {};
        errorMessage = parsed?.message || parsed?.detail || errorMessage;
      } catch {
      }
      throw new Error(errorMessage);
    }

    return {
      blob: await response.blob(),
      contentDisposition: response.headers.get('content-disposition') || '',
    };
  },

  downloadMacNuidExport: async (distributionId, format = 'csv') => {
    const url = `${API_BASE_URL}/distributions/${distributionId}/export-mac-nuid?format=${encodeURIComponent(format)}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download MAC/NUID export';
      try {
        const text = await response.text();
        const parsed = text ? JSON.parse(text) : {};
        errorMessage = parsed?.message || parsed?.detail || errorMessage;
      } catch {
      }
      throw new Error(errorMessage);
    }

    return {
      blob: await response.blob(),
      contentDisposition: response.headers.get('content-disposition') || '',
    };
  },

  updateDistributionStatus: async (distributionId, status, notes) => {
    const response = await apiRequest(`/distributions/${distributionId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes }),
    });
    return response;
  },

  cancelDistribution: async (distributionId) => {
    const response = await apiRequest(`/distributions/${distributionId}`, {
      method: 'DELETE',
    });
    return response;
  },

  confirmReceipt: async (distributionId, received, notes = '') => {
    const response = await apiRequest(`/distributions/${distributionId}/receipt`, {
      method: 'POST',
      body: JSON.stringify({ received, notes }),
    });
    return response;
  },

  confirmDisputedReturn: async (distributionId, notes = '') => {
    const response = await apiRequest(`/distributions/${distributionId}/confirm-return`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
    return response;
  },
};
