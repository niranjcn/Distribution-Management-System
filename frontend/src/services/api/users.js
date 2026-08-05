import { apiRequest, buildCsrfHeader, API_BASE_URL } from './client';

export const usersAPI = {
  getUsers: async (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await apiRequest(`/users?${queryString}`);
    return response;
  },

  getUserStats: async () => {
    const response = await apiRequest('/users/stats');
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

  reassignUser: async (userId, data) => {
    const response = await apiRequest(`/users/${userId}/reassign`, {
      method: 'POST',
      body: JSON.stringify(data),
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

  bulkUpload: async (file, role, parentId) => {
    const formData = new FormData();
    const fileBuffer = await file.arrayBuffer();
    const fileSnapshot = new Blob([fileBuffer], { type: file.type || 'application/octet-stream' });
    formData.append('file', fileSnapshot, file.name || 'bulk-upload.csv');
    let url = `${API_BASE_URL}/users/bulk-upload?role=${encodeURIComponent(role)}`;
    if (parentId) url += `&parent_id=${encodeURIComponent(parentId)}`;
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

export const adminUpdateCredentials = (userId, data) =>
  apiRequest(`/users/${userId}/credentials`, { method: 'PATCH', body: JSON.stringify(data) });
