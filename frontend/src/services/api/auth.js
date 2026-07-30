import { apiRequest, log, logError } from './client';

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

  completeForcedUpdate: async (currentPassword, newEmail, newPhone, newPassword) => {
    const response = await apiRequest('/auth/complete-forced-update', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_email: newEmail,
        new_phone: newPhone,
        new_password: newPassword,
      }),
    });
    return response;
  },
};
