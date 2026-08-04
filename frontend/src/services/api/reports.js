import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const reportsAPI = {
  getInventoryReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/inventory${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getDistributionSummary: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/distribution-summary${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getDefectSummary: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/defect-summary${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getReturnSummary: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/return-summary${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getUserActivityReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/user-activity?${queryString}`);
    return response;
  },

  getSubDistributionReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/sub-distributions${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getClusterReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/clusters${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getOperatorReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/operators${queryString ? `?${queryString}` : ''}`);
    return response;
  },

  getDeviceUtilizationReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/reports/device-utilization?${queryString}`);
    return response;
  },

  downloadDeviceBackup: async (format = 'xlsx') => {
    const url = `${API_BASE_URL}/reports/device-backup?format=${encodeURIComponent(format)}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download device backup';
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

  downloadReturnsDefectsBackup: async (format = 'xlsx') => {
    const url = `${API_BASE_URL}/reports/returns-defects-backup?format=${encodeURIComponent(format)}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download returns/defects backup';
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

  getDbBackupSchedule: async () => {
    const response = await apiRequest('/reports/db-backup-schedule');
    return response;
  },

  updateDbBackupSchedule: async (payload) => {
    const response = await apiRequest('/reports/db-backup-schedule', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return response;
  },

  listBackupDocuments: async () => {
    const response = await apiRequest('/reports/backup-documents');
    return response;
  },

  uploadBackupDocument: async (file) => {
    if (!file) {
      throw new Error('Please select a file to upload');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/reports/backup-documents`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        ...buildCsrfHeader('POST'),
      },
      body: formData,
    });

    const raw = await response.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { message: raw || 'Upload failed' };
    }

    if (!response.ok) {
      throw new Error(data?.message || data?.detail || 'Failed to upload file');
    }

    return data;
  },

  downloadBackupDocument: async (storedName) => {
    const url = `${API_BASE_URL}/reports/backup-documents/${encodeURIComponent(storedName)}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download file';
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
};
