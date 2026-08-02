import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { returnsAPI } from '../../services/api';
import kvLogo from '../../kv_logo.png';
import {
  LayoutDashboard,
  Box,
  Truck,
  Users,
  FileText,
  Search,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Package,
  ClipboardList,
  BarChart3,
  Warehouse,
  X,
  Network,
  PackageCheck,
  ArrowLeftRight,
  Database,
  DollarSign,
  Eye
} from 'lucide-react';
import { normalizeRole, ROLE_LABELS, ROLES } from '../../utils/roles';

const Sidebar = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const location = useLocation();
  const [expandedMenus, setExpandedMenus] = useState({});
  const [canShowReplacementOptions, setCanShowReplacementOptions] = useState(true);

  useEffect(() => {
    const role = normalizeRole(user?.role);
    const rolesNeedingReceivedReturn = [
      ROLES.SUB_DISTRIBUTION_MANAGER,
      ROLES.SUB_DISTRIBUTOR,
      ROLES.CLUSTER,
      ROLES.OPERATOR,
    ];

    if (!rolesNeedingReceivedReturn.includes(role)) {
      setCanShowReplacementOptions(true);
      return;
    }

    let isMounted = true;
    const checkReceivedAtPdic = async () => {
      try {
        const response = await returnsAPI.getReturns({ status: 'received', page_size: 1 });
        const rows = Array.isArray(response?.data) ? response.data : [];
        const total = Number(response?.pagination?.total ?? rows.length ?? 0);
        if (isMounted) {
          setCanShowReplacementOptions(total > 0);
        }
      } catch {
        if (isMounted) {
          setCanShowReplacementOptions(false);
        }
      }
    };

    checkReceivedAtPdic();
    return () => {
      isMounted = false;
    };
  }, [user?.role, user?.id]);

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
    const role = normalizeRole(user?.role);
    const commonItems = [
      { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { path: '/devices/track', icon: Search, label: 'Track Device' },
    ];

    const defectMenu = {
      key: 'defect',
      icon: AlertTriangle,
      label: 'Defect',
      children: [
        { path: '/defects', label: 'Defect Reports' },
        { path: '/replacements', label: 'Replacements' },
        { path: '/replacements/pending', label: 'Pending Replacements' },
        { path: '/pending-dues', label: 'Pending Dues' },
        { path: '/returns', label: 'Returns' },
        { path: '/approvals', label: 'Approvals' },
      ],
    };

    const reportMenu = {
      key: 'report',
      icon: BarChart3,
      label: 'Report',
      children: [
        { path: '/reports', label: 'Overview' },
        { path: '/reports/sub-distribution', label: 'Sub Distribution' },
        { path: '/reports/cluster', label: 'Cluster' },
        { path: '/reports/operator', label: 'Operator' },
      ],
    };

    const roleMenus = {
      [ROLES.SUPER_ADMIN]: [
        ...commonItems,
        reportMenu,
        { path: '/view-as', icon: Eye, label: 'View User Dashboard' },
        { path: '/activities', icon: FileText, label: 'Activities' },
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'All Users' },
            { path: '/users/hierarchy', label: 'User Hierarchy' },
            { path: '/users/bulk-upload', label: 'Bulk Upload' },
            { path: '/change-requests', label: 'Change Requests' },
            { path: '/reassignment-requests', label: 'Reassignment Requests' },
          ]
        },
        {
          key: 'devices',
          icon: Box,
          label: 'Devices',
          children: [
            { path: '/devices', label: 'All Devices' },
            { path: '/devices/register', label: 'Register Device' },
            { path: '/devices/bulk-import', label: 'Bulk Import' },
            { path: '/devices/edit-requests', label: 'Edit Requests' },
          ]
        },
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        defectMenu,
        { path: '/backup', icon: Database, label: 'Backup' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
      ],
      [ROLES.MD_DIRECTOR]: [
        ...commonItems,
        reportMenu,
        { path: '/view-as', icon: Eye, label: 'View User Dashboard' },
        { path: '/activities', icon: FileText, label: 'Activities' },
        { path: '/users', icon: Users, label: 'Users (Read Only)' },
        { path: '/users/hierarchy', icon: Network, label: 'User Hierarchy' },
        { path: '/devices', icon: Box, label: 'All Devices' },
        { path: '/distributions', icon: Truck, label: 'All Distributions' },
        {
          key: 'defect',
          icon: AlertTriangle,
          label: 'Defect',
          children: [
            { path: '/defects', label: 'Defect Reports' },
            { path: '/replacements', label: 'Replacements' },
            { path: '/replacements/pending', label: 'Pending Replacements' },
            { path: '/pending-dues', label: 'Pending Dues' },
            { path: '/returns', label: 'Returns' },
          ],
        },
        { path: '/backup', icon: Database, label: 'Backup' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
      ],
      [ROLES.MANAGER]: [
        ...commonItems,
        reportMenu,
        { path: '/view-as', icon: Eye, label: 'View User Dashboard' },
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'Assign Users' },
            { path: '/users/hierarchy', label: 'User Hierarchy' },
            { path: '/users/bulk-upload', label: 'Bulk Upload' },
            { path: '/change-requests', label: 'Change Requests' },
          ]
        },
        {
          key: 'devices',
          icon: Box,
          label: 'Devices',
          children: [
            { path: '/devices', label: 'All Devices' },
            { path: '/devices/register', label: 'Register Device' },
            { path: '/devices/bulk-import', label: 'Bulk Import' },
            { path: '/devices/edit-requests', label: 'Edit Requests' },
          ]
        },
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        defectMenu,
        { path: '/backup', icon: Database, label: 'Backup' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
      ],
      [ROLES.PDIC_STAFF]: [
        ...commonItems,
        reportMenu,
        {
          key: 'devices',
          icon: Box,
          label: 'Devices',
          children: [
            { path: '/devices', label: 'All Devices' },
            { path: '/devices/register', label: 'Register Device' },
            { path: '/devices/bulk-import', label: 'Bulk Import' },
          ]
        },
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'All Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        defectMenu,
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
      ],
      [ROLES.SUB_DISTRIBUTION_MANAGER]: [
        ...commonItems,
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'Scoped Users' },
            { path: '/users/hierarchy', label: 'User Hierarchy' },
            { path: '/users/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/devices', icon: Box, label: 'My Devices' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
        { path: '/distributions', icon: Truck, label: 'Scoped Distributions' },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        ...(canShowReplacementOptions ? [
          { path: '/replacements', icon: ArrowLeftRight, label: 'Replacements' },
          { path: '/replacements/pending', icon: AlertTriangle, label: 'Pending Replacements' },
        ] : []),
        { path: '/pending-dues', icon: DollarSign, label: 'Pending Payments' },
      ],
      [ROLES.SUB_DISTRIBUTOR]: [
        ...commonItems,
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'My Users' },
            { path: '/users/hierarchy', label: 'User Hierarchy' },
            { path: '/users/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/devices', icon: Box, label: 'My Devices' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
        { path: '/delivery-confirmations', icon: PackageCheck, label: 'Delivery Confirmations' },
        ...(canShowReplacementOptions ? [{ path: '/replacement-confirmation', icon: PackageCheck, label: 'Replacement Confirmation' }] : []),
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'My Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        ...(canShowReplacementOptions ? [
          { path: '/replacements', icon: ArrowLeftRight, label: 'Replacements' },
          { path: '/replacements/pending', icon: AlertTriangle, label: 'Pending Replacements' },
        ] : []),
        { path: '/pending-dues', icon: DollarSign, label: 'Pending Payments' },
        { path: '/returns', icon: RotateCcw, label: 'Return Requests' },
      ],
      [ROLES.CLUSTER]: [
        ...commonItems,
        {
          key: 'users',
          icon: Users,
          label: 'User Management',
          children: [
            { path: '/users', label: 'My Users' },
            { path: '/users/hierarchy', label: 'User Hierarchy' },
            { path: '/users/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/devices', icon: Box, label: 'My Devices' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
        { path: '/delivery-confirmations', icon: PackageCheck, label: 'Delivery Confirmations' },
        ...(canShowReplacementOptions ? [{ path: '/replacement-confirmation', icon: PackageCheck, label: 'Replacement Confirmation' }] : []),
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'My Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/defects', icon: AlertTriangle, label: 'Defect Reports' },
        ...(canShowReplacementOptions ? [
          { path: '/replacements', icon: ArrowLeftRight, label: 'Replacements' },
          { path: '/replacements/pending', icon: AlertTriangle, label: 'Pending Replacements' },
        ] : []),
        { path: '/pending-dues', icon: DollarSign, label: 'Pending Payments' },
        { path: '/returns', icon: RotateCcw, label: 'Return Requests' },
      ],
      [ROLES.OPERATOR]: [
        ...commonItems,
        { path: '/devices', icon: Box, label: 'My Devices' },
        { path: '/external-inventory', icon: Warehouse, label: 'External Inventory' },
        { path: '/delivery-confirmations', icon: PackageCheck, label: 'Delivery Confirmations' },
        ...(canShowReplacementOptions ? [{ path: '/replacement-confirmation', icon: PackageCheck, label: 'Replacement Confirmation' }] : []),
        {
          key: 'distribution',
          icon: Truck,
          label: 'Distribution',
          children: [
            { path: '/distributions', label: 'My Distributions' },
            { path: '/distributions/create', label: 'Create Distribution' },
            { path: '/distributions/bulk-upload', label: 'Bulk Upload' },
          ]
        },
        { path: '/defects/create', icon: AlertTriangle, label: 'Report Defect' },
        { path: '/defects', icon: ClipboardList, label: 'My Defect Reports' },
        ...(canShowReplacementOptions ? [
          { path: '/replacements', icon: ArrowLeftRight, label: 'Replacements' },
          { path: '/replacements/pending', icon: AlertTriangle, label: 'Pending Replacements' },
        ] : []),
        { path: '/pending-dues', icon: DollarSign, label: 'Pending Payments' },
        { path: '/returns', icon: RotateCcw, label: 'My Returns' },
      ],
    };

    return roleMenus[role] || commonItems;
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
            className={`w-full flex items-center justify-between px-4 py-3 text-sm font-medium rounded-lg transition-colors ${hasActiveChild
              ? 'bg-green-50 text-green-700'
              : 'text-gray-600 hover:bg-gray-100'
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
                  className={`block px-3 py-2 text-sm rounded-lg transition-colors ${isActive(child.path)
                    ? 'bg-green-700 text-white'
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
        className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors ${isActive(item.path)
          ? 'bg-green-50 text-green-700'
          : 'text-gray-600 hover:bg-gray-100'
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
        className={`fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-200 shadow-sm z-50 transform transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full'
          } lg:translate-x-0`}
      >
        <div className="flex flex-col h-full">

          {/* Logo block — matches KannurVision image */}
          <div className="flex items-start justify-between px-2 pt-2 pb-2 border-b border-gray-200">
            <Link to="/" className="flex flex-col items-center w-full gap-1">
              {/* KannurVision logo image — bigger, no gap */}
              <img
                src={kvLogo}
                alt="KannurVision"
                className="w-40 h-auto object-contain"
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
              {/* PDIC text — flush below logo */}
              <span className="text-base font-bold text-gray-800 tracking-widest leading-tight">PDIC</span>
              {/* NETWORK MANAGER subtitle */}
              <span className="text-[10px] font-medium text-gray-400 tracking-widest uppercase">Network Manager</span>
            </Link>
            <button
              onClick={onClose}
              className="lg:hidden p-1 hover:bg-gray-100 rounded-lg mt-1 flex-shrink-0"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>

          {/* Navigation section label */}
          <div className="px-4 pt-4 pb-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Navigation</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-0.5">
            {menuItems.map(renderMenuItem)}
          </nav>

        </div>
      </aside>
    </>
  );
};

export default Sidebar;
