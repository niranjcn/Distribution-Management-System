import { apiRequest, log, logError } from './client';

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
