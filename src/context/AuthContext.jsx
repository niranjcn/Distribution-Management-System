import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

// Demo users for testing
export const DEMO_USERS = [
  {
    id: '1',
    email: 'admin@dms.com',
    password: 'admin123',
    name: 'Admin User',
    role: 'admin',
    avatar: 'AU'
  },
  {
    id: '2',
    email: 'manager@dms.com',
    password: 'manager123',
    name: 'Manager User',
    role: 'manager',
    avatar: 'MU'
  },
  {
    id: '3',
    email: 'distributor@dms.com',
    password: 'dist123',
    name: 'Main Distributor',
    role: 'distributor',
    avatar: 'MD'
  },
  {
    id: '4',
    email: 'subdist@dms.com',
    password: 'subdist123',
    name: 'Sub Distributor',
    role: 'sub-distributor',
    avatar: 'SD'
  },
  {
    id: '5',
    email: 'operator@dms.com',
    password: 'operator123',
    name: 'Operator User',
    role: 'operator',
    avatar: 'OP'
  }
];

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored user session
    const storedUser = localStorage.getItem('dms_user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500));
    
    const foundUser = DEMO_USERS.find(
      u => u.email === email && u.password === password
    );
    
    if (foundUser) {
      const userWithoutPassword = { ...foundUser };
      delete userWithoutPassword.password;
      setUser(userWithoutPassword);
      localStorage.setItem('dms_user', JSON.stringify(userWithoutPassword));
      return { success: true, user: userWithoutPassword };
    }
    
    return { success: false, error: 'Invalid email or password' };
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('dms_user');
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
