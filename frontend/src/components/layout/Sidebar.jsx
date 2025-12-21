import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Box,
  Truck,
  Users,
  FileText,
  Settings,
  Search,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Package,
  ClipboardList,
  UserCog,
  BarChart3,
  Bell,
  X
} from 'lucide-react';

const Sidebar = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const location = useLocation();
  const [expandedMenus, setExpandedMenus] = useState({});

  const toggleMenu = (menuKey) => {
    setExpandedMenus(prev => ({
      ...prev,
      [menuKey]: !prev[menuKey]
    }));
  };

  const isActive = (path) => location.pathname === path;
  const isParentActive = (children) => children.some(child => location.pathname === child.path);

  // Define menu items based on user role
  const getMenuItems = () => {
    const commonItems = [
      { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { path: '/devices/track', icon: Search, label: 'Track Device' },
    ];

    const roleMenus = {
      admin: [
        ...commonItems,
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'All Users' },
          ]
        },
        {
          key: 'devices',
          icon: Box,
          label: 'Devices',
          children: [
            { path: '/devices', label: 'All Devices' },
            { path: '/devices/register', label: 'Register Device' },
          ]
        },
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
          ]
        },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        { path: '/returns', icon: RotateCcw, label: 'Returns' },
        { path: '/approvals', icon: CheckSquare, label: 'Approvals' },
        { path: '/reports', icon: BarChart3, label: 'Reports' },
        { path: '/settings', icon: Settings, label: 'Settings' },
      ],
      manager: [
        ...commonItems,
        { path: '/users', icon: Users, label: 'Users' },
        { path: '/devices', icon: Box, label: 'Devices' },
        { path: '/distributions', icon: Truck, label: 'Distributions' },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        { path: '/returns', icon: RotateCcw, label: 'Returns' },
        { path: '/approvals', icon: CheckSquare, label: 'Approvals' },
        { path: '/reports', icon: BarChart3, label: 'Reports' },
      ],
      distributor: [
        ...commonItems,
        {
          key: 'devices',
          icon: Box,
          label: 'Device Management',
          children: [
            { path: '/devices', label: 'All Devices' },
            { path: '/devices/register', label: 'Register Device' },
          ]
        },
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
          ]
        },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        { path: '/returns', icon: RotateCcw, label: 'Return Requests' },
        { path: '/approvals', icon: CheckSquare, label: 'Approvals' },
        { path: '/reports', icon: BarChart3, label: 'Reports' },
      ],
      'sub-distributor': [
        ...commonItems,
        { path: '/devices', icon: Box, label: 'My Devices' },
        {
          key: 'distribution',
          icon: Package,
          label: 'Distributions',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Assign to Operator' },
          ]
        },
        { path: '/approvals', icon: CheckSquare, label: 'Pending Approvals' },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        { path: '/returns', icon: RotateCcw, label: 'Return Requests' },
      ],
      operator: [
        ...commonItems,
        { path: '/devices', icon: Box, label: 'My Devices' },
        { path: '/defects/create', icon: AlertTriangle, label: 'Report Defect' },
        { path: '/defects', icon: ClipboardList, label: 'My Defect Reports' },
        { path: '/returns/create', icon: RotateCcw, label: 'Initiate Return' },
        { path: '/returns', icon: RotateCcw, label: 'My Returns' },
      ],
    };

    return roleMenus[user?.role] || commonItems;
  };

  const menuItems = getMenuItems();

  const renderMenuItem = (item, index) => {
    if (item.children) {
      const isExpanded = expandedMenus[item.key];
      const hasActiveChild = isParentActive(item.children);
      
      return (
        <div key={item.key}>
          <button
            onClick={() => toggleMenu(item.key)}
            className={`w-full flex items-center justify-between px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
              hasActiveChild
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <div className="flex items-center gap-3">
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </div>
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
          
          {isExpanded && (
            <div className="ml-4 mt-1 space-y-1 border-l-2 border-gray-200 pl-4">
              {item.children.map((child) => (
                <Link
                  key={child.path}
                  to={child.path}
                  onClick={onClose}
                  className={`block px-3 py-2 text-sm rounded-lg transition-colors ${
                    isActive(child.path)
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {child.label}
                </Link>
              ))}
            </div>
          )}
        </div>
      );
    }

    return (
      <Link
        key={item.path}
        to={item.path}
        onClick={onClose}
        className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
          isActive(item.path)
            ? 'bg-blue-600 text-white'
            : 'text-gray-700 hover:bg-gray-100'
        }`}
      >
        <item.icon className="w-5 h-5" />
        <span>{item.label}</span>
      </Link>
    );
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-200 z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <Truck className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-800">DMS</span>
            </Link>
            <button
              onClick={onClose}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-1">
            {menuItems.map(renderMenuItem)}
          </nav>

          {/* User role badge */}
          <div className="p-4 border-t border-gray-200">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase tracking-wider">Logged in as</div>
              <div className="text-sm font-medium text-gray-800 capitalize mt-1">
                {user?.role?.replace('-', ' ')}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
