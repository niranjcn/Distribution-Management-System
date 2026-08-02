import { apiRequest, buildCsrfHeader, API_BASE_URL, log, logError } from './client';

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

  bulkDeleteDevices: async (deviceIds) => {
    const response = await apiRequest('/devices/bulk-delete', {
      method: 'POST',
      body: JSON.stringify({ device_ids: deviceIds }),
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

  getDevicesForReplacement: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/devices/for-replacement?${queryString}` : '/devices/for-replacement';
    const response = await apiRequest(endpoint);
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
