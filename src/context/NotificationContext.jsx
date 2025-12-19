import { createContext, useContext, useState, useCallback } from 'react';

const NotificationContext = createContext(null);

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([
    {
      id: '1',
      title: 'New Device Distribution',
      message: '50 devices have been distributed to Sub Distributor A',
      type: 'info',
      read: false,
      timestamp: new Date(Date.now() - 3600000).toISOString()
    },
    {
      id: '2',
      title: 'Pending Approval',
      message: 'You have 5 devices pending approval',
      type: 'warning',
      read: false,
      timestamp: new Date(Date.now() - 7200000).toISOString()
    },
    {
      id: '3',
      title: 'Return Request',
      message: 'New return request from Operator John',
      type: 'error',
      read: true,
      timestamp: new Date(Date.now() - 86400000).toISOString()
    }
  ]);

  const [toasts, setToasts] = useState([]);

  const addNotification = useCallback((notification) => {
    const newNotification = {
      id: Date.now().toString(),
      ...notification,
      read: false,
      timestamp: new Date().toISOString()
    };
    setNotifications(prev => [newNotification, ...prev]);
  }, []);

  const markAsRead = useCallback((id) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <NotificationContext.Provider value={{
      notifications,
      toasts,
      unreadCount,
      addNotification,
      markAsRead,
      markAllAsRead,
      removeNotification,
      showToast
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
