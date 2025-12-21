import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored user session and validate with backend
    const initAuth = async () => {
      const storedUser = localStorage.getItem('dms_user');
      if (storedUser) {
        try {
          const userData = JSON.parse(storedUser);
          // Validate token with backend
          const response = await authAPI.getCurrentUser();
          if (response.success) {
            const user = response.data;
            // Add avatar initials
            user.avatar = user.name.split(' ').map(n => n[0]).join('').toUpperCase();
            setUser(user);
          } else {
            // Invalid token, clear storage
            localStorage.removeItem('dms_user');
          }
        } catch (error) {
          console.error('Auth validation error:', error);
          localStorage.removeItem('dms_user');
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email, password) => {
    try {
      const response = await authAPI.login(email, password);
      
      if (response.success) {
        const { user: userData, access_token } = response.data;
        
        // Add avatar initials
        userData.avatar = userData.name.split(' ').map(n => n[0]).join('').toUpperCase();
        userData.token = access_token;
        
        // Store user with token
        localStorage.setItem('dms_user', JSON.stringify(userData));
        setUser(userData);
        
        return { success: true, user: userData };
      }
      
      return { success: false, error: 'Invalid credentials' };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: error.message || 'Login failed' };
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      localStorage.removeItem('dms_user');
    }
  };

  const hasRole = (roles) => {
    if (!user) return false;
    if (Array.isArray(roles)) {
      return roles.includes(user.role);
    }
    return user.role === roles;
  };

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, hasRole, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
