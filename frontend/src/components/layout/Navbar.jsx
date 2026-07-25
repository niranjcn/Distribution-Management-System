import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useNotifications } from '../../context/NotificationContext';
import {
  Menu,
  Bell,
  User,
  LogOut,
  Moon,
  Sun,
  ChevronDown,
  ChevronRight,
  Home
} from 'lucide-react';

const THEME_STORAGE_KEY = 'dms-theme';

const Navbar = ({ onMenuClick }) => {
  const { user, logout } = useAuth();
  const { unreadCount, fetchLatestNotifications } = useNotifications();
  const navigate = useNavigate();
  const location = useLocation();
  const [showProfile, setShowProfile] = useState(false);
  const profileRef = useRef(null);
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') {
      return 'light';
    }
    return localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light';
  });

  // Generate breadcrumbs from path
  const generateBreadcrumbs = () => {
    const paths = location.pathname.split('/').filter(Boolean);
    return paths.map((path, index) => {
      const url = '/' + paths.slice(0, index + 1).join('/');
      const label = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ');
      return { label, url, isLast: index === paths.length - 1 };
    });
  };

  const breadcrumbs = generateBreadcrumbs();

  // Fetch notifications when user is logged in
  useEffect(() => {
    if (user) {
      try {
        fetchLatestNotifications();
      } catch (error) {
        console.error('[Navbar] Error fetching notifications:', error);
      }
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const interval = setInterval(() => {
      fetchLatestNotifications();
    }, 15000);
    return () => clearInterval(interval);
  }, [user?.id]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setShowProfile(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('ops-theme-dark');
    } else {
      root.classList.remove('ops-theme-dark');
    }
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleTheme = () => {
    setTheme((prevTheme) => (prevTheme === 'dark' ? 'light' : 'dark'));
  };

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-gray-200 shadow-sm">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        {/* Left side */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu className="w-6 h-6 text-gray-600" />
          </button>
          
          {/* Breadcrumbs */}
          {breadcrumbs.length > 0 && (
            <>
              <span className="sm:hidden text-sm text-gray-800 font-medium truncate max-w-[160px]">
                {breadcrumbs[breadcrumbs.length - 1].label}
              </span>
              <nav className="hidden sm:flex items-center gap-2 text-sm ml-2">
              <Link to="/" className="text-gray-500 hover:text-gray-700">
                <Home className="w-4 h-4" />
              </Link>
              {breadcrumbs.map((crumb, index) => (
                <div key={crumb.url} className="flex items-center gap-2">
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                  {crumb.isLast ? (
                    <span className="text-gray-800 font-medium">{crumb.label}</span>
                  ) : (
                    <Link to={crumb.url} className="text-gray-500 hover:text-gray-700">
                      {crumb.label}
                    </Link>
                  )}
                </div>
              ))}
            </nav>
          </>
          )}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Notifications */}
          <button
            onClick={() => navigate('/notifications')}
            className="relative p-2 hover:bg-gray-100 rounded-lg"
            title="Open notifications"
            aria-label="Open notifications"
          >
            <Bell className="w-6 h-6 text-gray-600" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          <button
            onClick={toggleTheme}
            className="p-2 hover:bg-gray-100 rounded-lg"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label="Toggle dark mode"
          >
            {theme === 'dark' ? (
              <Sun className="w-6 h-6 text-gray-600" />
            ) : (
              <Moon className="w-6 h-6 text-gray-600" />
            )}
          </button>

          {/* Profile dropdown */}
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setShowProfile(!showProfile)}
              className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg"
            >
              <div className="w-8 h-8 bg-green-700 rounded-full flex items-center justify-center text-white text-sm font-medium shadow-sm">
                {user?.avatar || user?.name?.charAt(0) || 'U'}
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-sm font-medium text-gray-800">{user?.name}</div>
                <div className="text-xs text-gray-500 capitalize">{user?.role?.replace(/[-_]/g, ' ')}</div>
              </div>
              <ChevronDown className="w-4 h-4 text-gray-400 hidden sm:block" />
            </button>

            {showProfile && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-800">{user?.name}</p>
                  <p className="text-sm text-gray-500">{user?.email}</p>
                </div>
                <div className="p-2">
                  <button
                    onClick={() => {
                      setShowProfile(false);
                      navigate('/profile');
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg"
                  >
                    <User className="w-4 h-4" />
                    Profile
                  </button>
                </div>
                <div className="p-2 border-t border-gray-100">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
