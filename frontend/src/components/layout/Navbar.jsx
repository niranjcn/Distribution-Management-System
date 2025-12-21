import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useNotifications } from '../../context/NotificationContext';
import {
  Menu,
  Bell,
  Search,
  User,
  LogOut,
  Settings,
  ChevronDown,
  Check,
  X,
  AlertTriangle,
  Info
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const Navbar = ({ onMenuClick }) => {
  const { user, logout } = useAuth();
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications();
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const profileRef = useRef(null);
  const notifRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setShowProfile(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/track-device?q=${encodeURIComponent(searchQuery)}`);
      setSearchQuery('');
    }
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'error': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'warning': return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      default: return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        {/* Left side */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu className="w-6 h-6 text-gray-600" />
          </button>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="hidden sm:block">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by MAC address..."
                className="w-64 lg:w-80 pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </form>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Notifications */}
          <div className="relative" ref={notifRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 hover:bg-gray-100 rounded-lg"
            >
              <Bell className="w-6 h-6 text-gray-600" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
                <div className="flex items-center justify-between p-4 border-b border-gray-100">
                  <h3 className="font-semibold text-gray-800">Notifications</h3>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllAsRead}
                      className="text-sm text-blue-600 hover:text-blue-700"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-gray-500">
                      No notifications
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        onClick={() => markAsRead(notif.id)}
                        className={`p-4 border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${
                          !notif.read ? 'bg-blue-50' : ''
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          {getNotificationIcon(notif.type)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800">
                              {notif.title}
                            </p>
                            <p className="text-sm text-gray-600 truncate">
                              {notif.message}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                              {formatDistanceToNow(new Date(notif.timestamp), { addSuffix: true })}
                            </p>
                          </div>
                          {!notif.read && (
                            <div className="w-2 h-2 bg-blue-600 rounded-full" />
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="p-3 border-t border-gray-100">
                  <button
                    onClick={() => {
                      setShowNotifications(false);
                      navigate('/notifications');
                    }}
                    className="w-full text-center text-sm text-blue-600 hover:text-blue-700 font-medium"
                  >
                    View all notifications
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Profile dropdown */}
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setShowProfile(!showProfile)}
              className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg"
            >
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-medium">
                {user?.avatar || user?.name?.charAt(0) || 'U'}
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-sm font-medium text-gray-800">{user?.name}</div>
                <div className="text-xs text-gray-500 capitalize">{user?.role?.replace('-', ' ')}</div>
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
                  <button
                    onClick={() => {
                      setShowProfile(false);
                      navigate('/settings');
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg"
                  >
                    <Settings className="w-4 h-4" />
                    Settings
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
