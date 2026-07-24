import { apiRequest, API_BASE_URL } from './client';

export const dashboardAPI = {
  getStats: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/stats?${queryString}`);
    return response;
  },

  getAdvancedMetrics: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/advanced-metrics?${queryString}`);
    return response;
  },

  getRecentActivities: async (limit = 10) => {
    const response = await apiRequest(`/dashboard/recent-activities?limit=${limit}`);
    return response;
  },

  getActivities: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/activities?${queryString}`);
    return response;
  },

  trackActivity: async (payload) => {
    const response = await apiRequest('/dashboard/activities/track', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response;
  },

  getDistributionChartData: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/charts/distributions?${queryString}`);
    return response;
  },

  getDefectChartData: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/charts/defects?${queryString}`);
    return response;
  },

  getSystemAlerts: async () => {
    const response = await apiRequest('/dashboard/alerts');
    return response;
  },

  getScopeUsers: async () => {
    const response = await apiRequest('/dashboard/scope-users');
    return response;
  },

  getUserKpi: async (userId, params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/user-kpi/${userId}?${queryString}`);
    return response;
  },

  getDistributionDeviceAnalytics: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/distribution-device-analytics?${queryString}`);
    return response;
  },

  getViewAsDashboard: async (userId, params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/dashboard/view-as/${userId}?${queryString}`);
    return response;
  },

  downloadReport: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const url = `${API_BASE_URL}/reports/download?${queryString}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = 'Failed to download report';
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
