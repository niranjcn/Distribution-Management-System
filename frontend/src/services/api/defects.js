import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const defectsAPI = {
  getDefects: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/defects?${queryString}` : '/defects';
    const response = await apiRequest(endpoint);
    return response;
  },

  getDefect: async (defectId) => {
    const response = await apiRequest(`/defects/${defectId}`);
    return response;
  },

  createDefect: async (defectData) => {
    const response = await apiRequest('/defects', {
      method: 'POST',
      body: JSON.stringify(defectData),
    });
    return response;
  },

  updateDefect: async (defectId, defectData) => {
    const response = await apiRequest(`/defects/${defectId}`, {
      method: 'PUT',
      body: JSON.stringify(defectData),
    });
    return response;
  },

  updateDefectStatus: async (defectId, status, notes, extra = {}) => {
    const response = await apiRequest(`/defects/${defectId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes, ...extra }),
    });
    return response;
  },

  uploadPaymentBill: async (defectId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE_URL}/defects/${defectId}/payment-bill`;
    const response = await fetch(url, {
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
      throw new Error(data?.message || data?.detail || 'Failed to upload payment bill');
    }

    return data;
  },

  uploadDefectPhoto: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE_URL}/defects/upload-photo`;
    const response = await fetch(url, {
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
      throw new Error(data?.message || data?.detail || 'Failed to upload defect photo');
    }

    return data;
  },

  confirmPayment: async (defectId, notes = '') => {
    const response = await apiRequest(`/defects/${defectId}/confirm-payment`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
    return response;
  },

  getPendingDueUsers: async () => {
    const response = await apiRequest('/defects/pending-dues/users');
    return response;
  },

  getPendingDuesForUser: async (userId) => {
    const response = await apiRequest(`/defects/pending-dues/users/${encodeURIComponent(userId)}`);
    return response;
  },

  getMyPendingDues: async () => {
    const response = await apiRequest('/defects/pending-dues/me');
    return response;
  },

  fetchPaymentBillBlob: async (billPath) => {
    const apiOrigin = API_BASE_URL.replace(/\/api\/?$/, '');
    const url = /^https?:\/\//i.test(billPath) ? billPath : `${apiOrigin}${billPath}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error('Failed to fetch bill file');
    }
    return {
      blob: await response.blob(),
      contentType: response.headers.get('content-type') || '',
    };
  },

  resolveDefect: async (defectId, resolution) => {
    const response = await apiRequest(`/defects/${defectId}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ resolution }),
    });
    return response;
  },

  replaceDevice: async (defectId, replaceData) => {
    const response = await apiRequest(`/defects/${defectId}/replace`, {
      method: 'POST',
      body: JSON.stringify(replaceData),
    });
    return response;
  },

  enquireReplacement: async (defectId, message) => {
    const response = await apiRequest(`/defects/${defectId}/enquire`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
    return response;
  },

  resendReplacementConfirmation: async (defectId) => {
    const response = await apiRequest(`/defects/${defectId}/resend-confirmation`, {
      method: 'POST',
    });
    return response;
  },

  markReplacementWaiting: async (defectId, notes = '') => {
    const response = await apiRequest(`/defects/${defectId}/mark-waiting`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
    return response;
  },

  forwardToManagement: async (defectId, notes = '') => {
    const response = await apiRequest(`/defects/${defectId}/forward-to-management`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
    return response;
  },

  getReplacements: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/defects/replacements?${queryString}`);
    return response;
  },

  getPendingReplacements: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/defects/replacements/pending?${queryString}`);
    return response;
  },

  confirmReplacementReceipt: async (defectId, notes) => {
    const response = await apiRequest(`/defects/${defectId}/replacement/confirm`, {
      method: 'POST',
      body: JSON.stringify(notes ? { notes } : {}),
    });
    return response;
  },

  deleteDefect: async (defectId) => {
    const response = await apiRequest(`/defects/${defectId}`, {
      method: 'DELETE',
    });
    return response;
  },
};
