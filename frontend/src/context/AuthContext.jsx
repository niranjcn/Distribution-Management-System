import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { authAPI } from '../services/api';
import { getStoredUser, saveStoredUser, clearStoredUser, clearLastPath } from '../utils/authStorage';
import { normalizeRole } from '../utils/roles';

const AuthContext = createContext(null);

const INACTIVITY_TIMEOUT = 20 * 60 * 1000; // 20 minutes in milliseconds

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const inactivityTimerRef = useRef(null);
  const isAuthenticatedRef = useRef(false);

  // Inactivity logout handler
  const handleInactivityLogout = useCallback(() => {
    setUser(null);
    clearStoredUser();
    clearLastPath();
    isAuthenticatedRef.current = false;
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
    window.location.href = '/login';
  }, []);

  // Reset inactivity timer on user activity
  const resetInactivityTimer = useCallback(() => {
    if (!isAuthenticatedRef.current) return;
    
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
    }
    inactivityTimerRef.current = setTimeout(handleInactivityLogout, INACTIVITY_TIMEOUT);
  }, [handleInactivityLogout]);

  // Set up activity listeners
  useEffect(() => {
    if (!user) {
      isAuthenticatedRef.current = false;
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
      return;
    }

    isAuthenticatedRef.current = true;
    
    const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
    
    activityEvents.forEach(event => {
      window.addEventListener(event, resetInactivityTimer, { passive: true });
    });

    // Start the initial timer
    resetInactivityTimer();

    return () => {
      activityEvents.forEach(event => {
        window.removeEventListener(event, resetInactivityTimer);
      });
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
      }
    };
  }, [user, resetInactivityTimer]);

  useEffect(() => {
    // Always validate the cookie-backed session with the backend so an active
    // session is detected even when sessionStorage is empty (e.g. a new tab or
    // a browser restart). The refresh cookie persists for days, so a valid
    // login must never be hidden behind a fresh-tab login page.
    const initAuth = async () => {
      try {
        const response = await authAPI.getCurrentUser();
        if (response.success) {
          const validatedUser = response.data;
          validatedUser.role = normalizeRole(validatedUser.role);
          // Add avatar initials
          validatedUser.avatar = validatedUser.name.split(' ').map(n => n[0]).join('').toUpperCase();
          saveStoredUser(validatedUser);
          setUser(validatedUser);
        } else {
          // Invalid token, clear stored session
          clearStoredUser();
        }
      } catch (error) {
        console.error('[AuthContext] Auth validation error:', error);
        // Only clear storage if it's an auth error (401), not a network error
        if (error.message && (error.message.includes('Invalid') || error.message.includes('expired') || error.message.includes('401'))) {
          clearStoredUser();
        } else {
          // Network error or server error - keep the stored session
          const userData = getStoredUser();
          if (userData) {
            userData.avatar = userData.name.split(' ').map(n => n[0]).join('').toUpperCase();
            setUser(userData);
          }
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
        const { user: userData } = response.data;
        userData.role = normalizeRole(userData.role);
        
        // Add avatar initials
        userData.avatar = userData.name.split(' ').map(n => n[0]).join('').toUpperCase();
        
        // Store user metadata only; auth cookies remain httpOnly.
        saveStoredUser(userData);
        setUser(userData);
        
        return { success: true, user: userData };
      }
      
      return { success: false, error: 'Invalid credentials' };
    } catch (error) {
      console.error('[AuthContext] Login error:', error);
      console.error('[AuthContext] Error details:', {
        message: error.message,
        stack: error.stack,
        email
      });
      return { success: false, error: error.message || 'Login failed' };
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('[AuthContext] Logout error:', error);
      console.error('[AuthContext] Error details:', {
        message: error.message,
        stack: error.stack
      });
    } finally {
      setUser(null);
      clearStoredUser();
      clearLastPath();
    }
  };

  const completeForcedCredentialUpdate = async (currentPassword, newEmail, newPhone, newPassword) => {
    const response = await authAPI.completeForcedUpdate(currentPassword, newEmail, newPhone, newPassword);
    if (!response.success) {
      return { success: false, error: 'Forced credential update failed' };
    }

    const { user: updatedUser } = response.data;
    updatedUser.role = normalizeRole(updatedUser.role);
    updatedUser.avatar = updatedUser.name.split(' ').map(n => n[0]).join('').toUpperCase();

    saveStoredUser(updatedUser);
    setUser(updatedUser);
    return { success: true, user: updatedUser };
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
    <AuthContext.Provider value={{ user, setUser, login, logout, loading, hasRole, isAuthenticated, completeForcedCredentialUpdate }}>
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
