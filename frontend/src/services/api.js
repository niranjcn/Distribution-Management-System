// API Configuration
import { clearStoredUser } from '../utils/authStorage';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';
const isDev = import.meta.env.DEV;
const log = isDev ? console.log : () => {};
const logError = isDev ? console.error : () => {};

log('[API] Initialized with base URL:', API_BASE_URL);

const getCookieValue = (name) => {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

const isUnsafeMethod = (method) => !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase());

const buildCsrfHeader = (method) => {
  const csrfToken = getCookieValue('csrftoken');
  return csrfToken && isUnsafeMethod(method) ? { 'X-CSRFToken': csrfToken } : {};
};

const AUTH_FAILURE_STATUSES = new Set([401, 403]);
const AUTH_FAILURE_ALLOWLIST = new Set([
  '/auth/login',
  '/auth/refresh',
  '/auth/complete-forced-update',
]);

const handleAuthFailure = (endpoint, message) => {
  if (AUTH_FAILURE_ALLOWLIST.has(endpoint)) return;

  logError('[API] Auth failure detected, clearing session:', { endpoint, message });
  clearStoredUser();

  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};

// API request helper
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();

  log('[API] Making request:', {
    method: options.method || 'GET',
    endpoint,
    url
  });

  const headers = {
    'Content-Type': 'application/json',
    ...buildCsrfHeader(method),
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    });

    log('[API] Response received:', {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      endpoint
    });

    const raw = await response.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { message: raw || 'API request failed' };
    }

    if (!response.ok) {
      let errorMessage =
        data?.message ||
        data?.detail ||
        (typeof data?.error?.details === 'string' ? data.error.details : null) ||
        'API request failed';

      // FastAPI validation errors are returned as structured details by backend middleware.
      if (
        response.status === 422 &&
        data?.error?.code === 'VALIDATION_ERROR' &&
        Array.isArray(data?.error?.details) &&
        data.error.details.length > 0
      ) {
        const first = data.error.details[0];
        const field = first?.field ? String(first.field).replace('body.', '') : 'field';
        const message = first?.message || 'Invalid value';
        errorMessage = `${field}: ${message}`;
      }

      if (
        response.status === 400 &&
        Array.isArray(data?.error?.details) &&
        data.error.details.length > 0
      ) {
        const first = data.error.details[0];
        errorMessage = first?.message || errorMessage;
      }

      if (AUTH_FAILURE_STATUSES.has(response.status)) {
        handleAuthFailure(endpoint, errorMessage);
      }

      logError('[API] Request failed:', {
        endpoint,
        status: response.status,
        error: errorMessage,
        data
      });
      throw new Error(errorMessage);
    }

    log('[API] Request successful:', endpoint);
    return data;
  } catch (error) {
    logError('[API] Request error:', {
      endpoint,
      error: error.message,
      stack: error.stack
    });
    throw error;
  }
};

// Auth API
export const authAPI = {
  login: async (email, password) => {
    log('[authAPI] Login attempt for:', email);
    try {
      const response = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      log('[authAPI] Login successful');
      return response;
    } catch (error) {
      logError('[authAPI] Login failed:', error.message);
      throw error;
    }
  },

  logout: async () => {
    log('[authAPI] Logging out');
    try {
      const response = await apiRequest('/auth/logout', {
        method: 'POST',
      });
      log('[authAPI] Logout successful');
      return response;
    } catch (error) {
      logError('[authAPI] Logout failed:', error.message);
      throw error;
    }
  },

  getCurrentUser: async () => {
    log('[authAPI] Fetching current user');
    try {
      const response = await apiRequest('/auth/me');
      log('[authAPI] Current user fetched successfully');
      return response;
    } catch (error) {
      logError('[authAPI] Failed to fetch current user:', error.message);
      throw error;
    }
  },

  changePassword: async (currentPassword, newPassword) => {
    log('[authAPI] Changing password');
    try {
      const response = await apiRequest('/auth/password', {
        method: 'PUT',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      log('[authAPI] Password changed successfully');
      return response;
    } catch (error) {
      logError('[authAPI] Failed to change password:', error.message);
      throw error;
    }
  },

  completeForcedUpdate: async (currentPassword, newEmail, newPassword) => {
    const response = await apiRequest('/auth/complete-forced-update', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_email: newEmail,
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

  bulkUpload: async (file) => {
    const formData = new FormData();
    const fileBuffer = await file.arrayBuffer();
    const fileSnapshot = new Blob([fileBuffer], { type: file.type || 'application/octet-stream' });
    formData.append('file', fileSnapshot, file.name || 'bulk-upload.csv');
    const url = `${API_BASE_URL}/users/bulk-upload`;
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: { ...buildCsrfHeader('POST') },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.detail || 'Upload failed');
    return data;
  },
};

// Devices API
export const devicesAPI = {
  getDevices: async (params = {}) => {
    log('[devicesAPI] Getting devices with params:', params);
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await apiRequest(`/devices?${queryString}`);
      log('[devicesAPI] Successfully fetched', response.data?.length || 0, 'devices');
      return response;
    } catch (error) {
      logError('[devicesAPI] Failed to get devices:', error.message);
      throw error;
    }
  },

  getDevice: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}`);
    return response;
  },

  getAvailableDevices: async () => {
    const response = await apiRequest('/devices/available');
    return response;
  },

  getMyOverview: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/devices/my-overview?${queryString}` : '/devices/my-overview';
    const response = await apiRequest(endpoint);
    return response;
  },

  getManagementHolderInsights: async () => {
    const response = await apiRequest('/devices/management-holder-insights');
    return response;
  },

  trackDeviceBySerial: async (serialNumber) => {
    log('[devicesAPI] Tracking device by serial:', serialNumber);
    try {
      const response = await apiRequest(`/devices/track/${serialNumber}`);
      log('[devicesAPI] Device tracking data retrieved');
      return response;
    } catch (error) {
      logError('[devicesAPI] Failed to track device:', error.message);
      throw error;
    }
  },

  getDeviceHistory: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}/history`);
    return response;
  },

  createDevice: async (deviceData) => {
    log('[devicesAPI] Creating device:', deviceData);
    try {
      const response = await apiRequest('/devices', {
        method: 'POST',
        body: JSON.stringify(deviceData),
      });
      log('[devicesAPI] Device created successfully:', response.data);
      return response;
    } catch (error) {
      logError('[devicesAPI] Failed to create device:', error.message);
      throw error;
    }
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

  repairDeviceHolder: async (deviceId) => {
    const response = await apiRequest(`/devices/${deviceId}/repair-holder`, {
      method: 'POST',
    });
    return response;
  },

  bulkUpload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE_URL}/devices/bulk-upload`;
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        ...buildCsrfHeader('POST'),
      },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.detail || 'Upload failed');
    return data;
  },

  getDevicesForReplacement: async (excludeDeviceId = null) => {
    const params = excludeDeviceId ? `?exclude_device_id=${excludeDeviceId}` : '';
    const response = await apiRequest(`/devices/for-replacement${params}`);
    return response;
  },

  requestDeviceEdit: async (deviceId, changes) => {
    const response = await apiRequest(`/devices/${deviceId}/request-edit`, {
      method: 'POST',
      body: JSON.stringify(changes),
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

  bulkUpload: async (file, toUserId, notes = '', dateOfDistribution = '') => {
    if (!file) {
      throw new Error('No file selected for upload');
    }

    const formData = new FormData();

    // Create an in-memory snapshot to avoid browser disk-change upload errors.
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
        // Keep default message when response is not JSON.
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
        // Keep default message when response is not JSON.
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

// Defects API
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

  confirmReplacementReceipt: async (defectId, notes = '') => {
    const response = await apiRequest(`/defects/${defectId}/replacement/confirm`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
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

  getRoleRoutingConfig: async () => {
    const response = await apiRequest('/approvals/role-routing/config');
    return response;
  },

  updateRoleRoutingConfig: async (payload) => {
    const response = await apiRequest('/approvals/role-routing/config', {
      method: 'PUT',
      body: JSON.stringify(payload),
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
    log('[notificationsAPI] Getting notifications with params:', params);
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await apiRequest(`/notifications?${queryString}`);
      log('[notificationsAPI] Successfully fetched notifications');
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to get notifications:', error.message);
      throw error;
    }
  },

  getUnreadCount: async () => {
    log('[notificationsAPI] Getting unread count');
    try {
      const response = await apiRequest('/notifications/unread');
      log('[notificationsAPI] Unread count:', response.data?.count ?? 0);
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to get unread count:', error.message);
      throw error;
    }
  },

  getLatestNotifications: async (limit = 5) => {
    log('[notificationsAPI] Getting latest notifications, limit:', limit);
    try {
      const response = await apiRequest(`/notifications/latest?limit=${limit}`);
      log('[notificationsAPI] Successfully fetched', response.data?.length || 0, 'notifications');
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to get latest notifications:', error.message);
      throw error;
    }
  },

  markAsRead: async (notificationId) => {
    log('[notificationsAPI] Marking notification as read:', notificationId);
    try {
      const response = await apiRequest(`/notifications/${notificationId}/read`, {
        method: 'PATCH',
      });
      log('[notificationsAPI] Notification marked as read');
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to mark notification as read:', error.message);
      throw error;
    }
  },

  markAllAsRead: async () => {
    log('[notificationsAPI] Marking all notifications as read');
    try {
      const response = await apiRequest('/notifications/read-all', {
        method: 'PATCH',
      });
      log('[notificationsAPI] All notifications marked as read');
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to mark all notifications as read:', error.message);
      throw error;
    }
  },

  deleteNotification: async (notificationId) => {
    log('[notificationsAPI] Deleting notification:', notificationId);
    try {
      const response = await apiRequest(`/notifications/${notificationId}`, {
        method: 'DELETE',
      });
      log('[notificationsAPI] Notification deleted');
      return response;
    } catch (error) {
      logError('[notificationsAPI] Failed to delete notification:', error.message);
      throw error;
    }
  },
};

// External Inventory API
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
        // Keep default message when response is not JSON.
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
        // Keep default message when response is not JSON.
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
        // Keep default message when response is not JSON.
      }
      throw new Error(errorMessage);
    }

    return {
      blob: await response.blob(),
      contentDisposition: response.headers.get('content-disposition') || '',
    };
  },
};

// Dashboard API
export const dashboardAPI = {
  getStats: async () => {
    const response = await apiRequest('/dashboard/stats');
    return response;
  },

  getAdvancedMetrics: async () => {
    const response = await apiRequest('/dashboard/advanced-metrics');
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

  getScopeUsers: async () => {
    const response = await apiRequest('/dashboard/scope-users');
    return response;
  },

  getUserKpi: async (userId) => {
    const response = await apiRequest(`/dashboard/user-kpi/${userId}`);
    return response;
  },
};

// Change Requests API
export const changeRequestsAPI = {
  submit: (data) => apiRequest('/change-requests', { method: 'POST', body: JSON.stringify(data) }),
  requestReplacementTransferFix: (defectId, notes = '') =>
    apiRequest('/change-requests', {
      method: 'POST',
      body: JSON.stringify({
        request_type: 'replacement_transfer_fix',
        device_id: String(defectId),
        reason: notes || undefined,
      }),
    }),
  getRequests: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/change-requests?${qs}`);
  },
  review: (requestId, data) => apiRequest(`/change-requests/${requestId}/review`, { method: 'PATCH', body: JSON.stringify(data) }),
};

// Admin user credentials update
export const adminUpdateCredentials = (userId, data) =>
  apiRequest(`/users/${userId}/credentials`, { method: 'PATCH', body: JSON.stringify(data) });

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
  externalInventory: externalInventoryAPI,
  reports: reportsAPI,
  dashboard: dashboardAPI,
};