// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Get auth token from localStorage
const getAuthToken = () => {
  const user = localStorage.getItem('dms_user');
  if (user) {
    const userData = JSON.parse(user);
    return userData.token;
  }
  return null;
};

// API request helper
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getAuthToken();

  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || data.detail || 'API request failed');
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

// Auth API
export const authAPI = {
  login: async (email, password) => {
    const response = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    return response;
  },

  logout: async () => {
    const response = await apiRequest('/auth/logout', {
      method: 'POST',
    });
    return response;
  },

  getCurrentUser: async () => {
    const response = await apiRequest('/auth/me');
    return response;
  },

  changePassword: async (currentPassword, newPassword) => {
    const response = await apiRequest('/auth/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    return response;
  },
};

// Users API
export const usersAPI = {
  getUsers: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/users?${queryString}`);
    return response;
  },

  getUser: async (userId) => {
    const response = await apiRequest(`/users/${userId}`);
    return response;
  },

  createUser: async (userData) => {
    const response = await apiRequest('/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
    return response;
  },

  updateUser: async (userId, userData) => {
    const response = await apiRequest(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
    return response;
  },

  deleteUser: async (userId) => {
    const response = await apiRequest(`/users/${userId}`, {
      method: 'DELETE',
    });
    return response;
  },

  updateUserStatus: async (userId, status) => {
    const response = await apiRequest(`/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    return response;
  },
};

// Devices API
export const devicesAPI = {
  getDevices: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/devices?${queryString}`);
    return response;
  },

  getDevice: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}`);
    return response;
  },

  getAvailableDevices: async () => {
    const response = await apiRequest('/devices/available');
    return response;
  },

  trackDeviceBySerial: async (serialNumber) => {
    const response = await apiRequest(`/devices/track/${serialNumber}`);
    return response;
  },

  getDeviceHistory: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}/history`);
    return response;
  },

  createDevice: async (deviceData) => {
    const response = await apiRequest('/devices', {
      method: 'POST',
      body: JSON.stringify(deviceData),
    });
    return response;
  },

  updateDevice: async (deviceId, deviceData) => {
    const response = await apiRequest(`/devices/${deviceId}`, {
      method: 'PUT',
      body: JSON.stringify(deviceData),
    });
    return response;
  },

  deleteDevice: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}`, {
      method: 'DELETE',
    });
    return response;
  },

  updateDeviceStatus: async (deviceId, status, notes) => {
    const response = await apiRequest(`/devices/${deviceId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes }),
    });
    return response;
  },
};

// Distributions API
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

  createDistribution: async (distributionData) => {
    const response = await apiRequest('/distributions', {
      method: 'POST',
      body: JSON.stringify(distributionData),
    });
    return response;
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
};

// Defects API
export const defectsAPI = {
  getDefects: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/defects?${queryString}`);
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

  updateDefectStatus: async (defectId, status, notes) => {
    const response = await apiRequest(`/defects/${defectId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes }),
    });
    return response;
  },

  resolveDefect: async (defectId, resolution) => {
    const response = await apiRequest(`/defects/${defectId}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ resolution }),
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

// Returns API
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

  updateReturnStatus: async (returnId, status, notes) => {
    const response = await apiRequest(`/returns/${returnId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, notes }),
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

// Approvals API
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
};

// Operators API
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

// Notifications API
export const notificationsAPI = {
  getNotifications: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/notifications?${queryString}`);
    return response;
  },

  getUnreadCount: async () => {
    const response = await apiRequest('/notifications/unread');
    return response;
  },

  markAsRead: async (notificationId) => {
    const response = await apiRequest(`/notifications/${notificationId}/read`, {
      method: 'PATCH',
    });
    return response;
  },

  markAllAsRead: async () => {
    const response = await apiRequest('/notifications/read-all', {
      method: 'PATCH',
    });
    return response;
  },

  deleteNotification: async (notificationId) => {
    const response = await apiRequest(`/notifications/${notificationId}`, {
      method: 'DELETE',
    });
    return response;
  },
};

// Reports API
export const reportsAPI = {
  getInventoryReport: async () => {
    const response = await apiRequest('/reports/inventory');
    return response;
  },

  getDistributionSummary: async () => {
    const response = await apiRequest('/reports/distribution-summary');
    return response;
  },

  getDefectSummary: async () => {
    const response = await apiRequest('/reports/defect-summary');
    return response;
  },

  getReturnSummary: async () => {
    const response = await apiRequest('/reports/return-summary');
    return response;
  },

  getUserActivityReport: async () => {
    const response = await apiRequest('/reports/user-activity');
    return response;
  },

  getDeviceUtilizationReport: async () => {
    const response = await apiRequest('/reports/device-utilization');
    return response;
  },
};

// Dashboard API
export const dashboardAPI = {
  getStats: async () => {
    const response = await apiRequest('/dashboard/stats');
    return response;
  },

  getRecentActivities: async (limit = 10) => {
    const response = await apiRequest(`/dashboard/recent-activities?limit=${limit}`);
    return response;
  },

  getDistributionChartData: async () => {
    const response = await apiRequest('/dashboard/charts/distributions');
    return response;
  },

  getDefectChartData: async () => {
    const response = await apiRequest('/dashboard/charts/defects');
    return response;
  },

  getSystemAlerts: async () => {
    const response = await apiRequest('/dashboard/alerts');
    return response;
  },
};

export default {
  auth: authAPI,
  users: usersAPI,
  devices: devicesAPI,
  distributions: distributionsAPI,
  defects: defectsAPI,
  returns: returnsAPI,
  approvals: approvalsAPI,
  operators: operatorsAPI,
  notifications: notificationsAPI,
  reports: reportsAPI,
  dashboard: dashboardAPI,
};
