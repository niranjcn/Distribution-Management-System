import { createContext, useContext, useState, useCallback } from 'react';
import { notificationsAPI } from '../services/api';

const NotificationContext = createContext(null);

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const refreshUnreadCount = useCallback(async () => {
    try {
      const response = await notificationsAPI.getUnreadCount();
      const count = response?.data?.count ?? 0;
      setUnreadCount(Number.isFinite(count) ? count : 0);
    } catch (error) {
      console.error('[NotificationContext] Failed to refresh unread count:', error);
    }
  }, []);

  const fetchLatestNotifications = async () => {
    setLoading(true);
    try {
      console.log('[NotificationContext] Fetching latest notifications...');
      const response = await notificationsAPI.getLatestNotifications(5);
      console.log('[NotificationContext] Response:', response);
      
      if (response.success) {
        const formattedNotifications = response.data.map(notif => ({
          id: notif.id,
          title: notif.title,
          message: notif.message,
          type: notif.type,
          read: notif.is_read,
          timestamp: notif.created_at,
          link: notif.link,
          category: notif.category
        }));
        setNotifications(formattedNotifications);
        await refreshUnreadCount();
        console.log('[NotificationContext] Successfully loaded', formattedNotifications.length, 'notifications');
      }
    } catch (error) {
      console.error('[NotificationContext] Failed to fetch notifications:', error);
      console.error('[NotificationContext] Error details:', {
        message: error.message,
        stack: error.stack
      });
      // Don't show error toast on initial load, just use empty array
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  };

  const addNotification = useCallback((notification) => {
    const newNotification = {
      id: Date.now().toString(),
      ...notification,
      read: false,
      timestamp: new Date().toISOString()
    };
    setNotifications(prev => [newNotification, ...prev].slice(0, 5)); // Keep only latest 5
    setUnreadCount(prev => prev + 1);
  }, []);

  const markAsRead = useCallback(async (id) => {
    try {
      console.log('[NotificationContext] Marking notification as read:', id);
      await notificationsAPI.markAsRead(id);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
      console.log('[NotificationContext] Successfully marked notification as read');
    } catch (error) {
      console.error('[NotificationContext] Failed to mark notification as read:', error);
      console.error('[NotificationContext] Error details:', {
        message: error.message,
        notificationId: id
      });
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    try {
      console.log('[NotificationContext] Marking all notifications as read');
      await notificationsAPI.markAllAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
      console.log('[NotificationContext] Successfully marked all notifications as read');
    } catch (error) {
      console.error('[NotificationContext] Failed to mark all notifications as read:', error);
      console.error('[NotificationContext] Error details:', {
        message: error.message,
        stack: error.stack
      });
    }
  }, []);

  const removeNotification = useCallback(async (id) => {
    try {
      console.log('[NotificationContext] Removing notification:', id);
      await notificationsAPI.deleteNotification(id);
      setNotifications(prev => prev.filter(n => n.id !== id));
      console.log('[NotificationContext] Successfully removed notification');
    } catch (error) {
      console.error('[NotificationContext] Failed to remove notification:', error);
      console.error('[NotificationContext] Error details:', {
        message: error.message,
        notificationId: id
      });
    }
  }, []);

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  

  return (
    <NotificationContext.Provider value={{
      notifications,
      toasts,
      unreadCount,
      loading,
      addNotification,
      markAsRead,
      markAllAsRead,
      removeNotification,
      showToast,
      fetchLatestNotifications,
      refreshUnreadCount
    }}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
