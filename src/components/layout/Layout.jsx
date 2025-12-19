import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import Toast from '../ui/Toast';
import { useNotifications } from '../../context/NotificationContext';
import { ChevronRight, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { toasts } = useNotifications();
  const location = useLocation();

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

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      <div className="lg:ml-64 min-h-screen flex flex-col">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />
        
        {/* Breadcrumbs */}
        {breadcrumbs.length > 0 && (
          <div className="bg-white border-b border-gray-200 px-4 lg:px-6 py-3">
            <nav className="flex items-center gap-2 text-sm">
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
          </div>
        )}

        {/* Main content */}
        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 px-4 lg:px-6 py-4">
          <div className="text-center text-sm text-gray-500">
            © 2024 Distribution Management System. All rights reserved.
          </div>
        </footer>
      </div>

      {/* Toast notifications */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <Toast key={toast.id} {...toast} />
        ))}
      </div>
    </div>
  );
};

export default Layout;
