import { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { usersAPI, adminUpdateCredentials, reassignmentRequestsAPI, digitalIdsAPI } from '../services/api';
import { 
  UserPlus, Edit, Trash2, Eye, Shield, Mail, Phone, 
  Building, Calendar, Users as UsersIcon, Loader2, Lock,
  Network, ChevronDown, ChevronRight, Filter, X, EyeOff, Search,
  AlertTriangle, Bell
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { userKeys } from '../hooks';

// Roles each creator can assign
const ALLOWED_ROLES_BY_CREATOR = {
  super_admin:     ['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator', 'sub_distribution_employee'],
  manager:         ['pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator', 'sub_distribution_employee'],
  sub_distributor: ['sub_distribution_manager', 'cluster', 'operator', 'sub_distribution_employee'],
  cluster:         ['operator'],
  sub_distribution_employee: ['cluster', 'operator'],
};

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  md_director: 'MD/Director',
  manager: 'Manager',
  pdic_staff: 'PDIC Staff',
  sub_distribution_manager: 'Sub Distribution MD/Manager',
  sub_distributor: 'Sub Distributor',
  cluster: 'Cluster',
  operator: 'Operator',
  sub_distribution_employee: 'Sub Distribution Employee',
};

const USER_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'name', label: 'Name' },
  { value: 'email', label: 'Email' },
  { value: 'role', label: 'Role' },
  { value: 'status', label: 'Status' },
  { value: 'phone', label: 'Phone' },
  { value: 'designation', label: 'Designation' },
  { value: 'digital_id', label: 'Digital ID' },
  { value: 'broadband_id', label: 'Broadband ID' },
];

const getRoleColor = (role) => {
  switch (role) {
    case 'super_admin':           return 'bg-red-100 text-red-800';
    case 'md_director':           return 'bg-orange-100 text-orange-800';
    case 'manager':         return 'bg-purple-100 text-purple-800';
    case 'pdic_staff':           return 'bg-blue-100 text-blue-800';
    case 'sub_distribution_manager': return 'bg-cyan-100 text-cyan-800';
    case 'sub_distributor': return 'bg-indigo-100 text-indigo-800';
    case 'cluster':         return 'bg-teal-100 text-teal-800';
    case 'operator':        return 'bg-green-100 text-green-800';
    case 'sub_distribution_employee': return 'bg-violet-100 text-violet-800';
    default:                return 'bg-gray-100 text-gray-800';
  }
};

const emptyForm = {
  name: '',
  email: '',
  password: '',
  role: 'operator',
  phone: '',
  designation: '',
  address: '',
  pincode: '',
  networkName: '',
  parentId: '',
  digitalId: '',
  broadbandId: '',
  digitalIdRows: [{ digitalId: '', broadbandId: '' }],
};

const USERS_FETCH_PAGE_SIZE = 1000000;

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;

const Users = () => {
  const { user: currentUser, hasRole } = useAuth();
  const { showToast } = useNotifications();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Role flags — declared here so data loading, memoized views and stats can all use them
  const isSubDist  = currentUser?.role === 'sub_distributor';
  const isCluster  = currentUser?.role === 'cluster';
  const isAdmin    = currentUser?.role === 'super_admin';
  const isMdDirector = currentUser?.role === 'md_director';
  const isManager  = currentUser?.role === 'manager';
  const isAdminOrManager = ['super_admin', 'manager'].includes(currentUser?.role);
  // Roles whose table is server-side paginated (the rest use the client-side full fetch)
  const isTableRole = isAdmin || isMdDirector || isManager;

  const [selectedUser, setSelectedUser] = useState(null);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [detailUser, setDetailUser] = useState(null);
  const [detailForm, setDetailForm] = useState({});
  const [newPassword, setNewPassword] = useState('');
  const [confirmResetPassword, setConfirmResetPassword] = useState('');
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [showConfirmResetPassword, setShowConfirmResetPassword] = useState(false);
  const [savingDetail, setSavingDetail] = useState(false);
  const [detailDigitalIds, setDetailDigitalIds] = useState([]);
  const origDigitalIdIds = useRef(null);

  const [formData, setFormData] = useState(emptyForm);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [showCreateConfirmPassword, setShowCreateConfirmPassword] = useState(false);

  // For admin/manager: parent options when creating cluster or operator
  const [parentOptions, setParentOptions] = useState([]);
  const [subDistributorOptions, setSubDistributorOptions] = useState([]);
  const [loadingParents, setLoadingParents] = useState(false);
  const [selectedOperatorSubDistId, setSelectedOperatorSubDistId] = useState('');
  // How an operator should be placed: directly under a sub distributor, or under a cluster.
  const [operatorPlacement, setOperatorPlacement] = useState('sub_distributor');

  // For admin detail modal: child users (clusters under sub_distributor, operators under cluster)
  const [detailChildren, setDetailChildren] = useState([]);
  const [loadingChildren, setLoadingChildren] = useState(false);

  // For sub_distributor hierarchical view: operators fetched separately
  const [subDistOperators, setSubDistOperators] = useState([]);
  const [loadingOps, setLoadingOps] = useState(false);
  // Which cluster cards are collapsed (by cluster id)
  const [collapsedClusters, setCollapsedClusters] = useState({});
  // Pending reassignment count for super admin
  const [pendingReassignCount, setPendingReassignCount] = useState(0);

  // Manual reassign state
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [reassignTarget, setReassignTarget] = useState(null);
  const [reassignNewParentId, setReassignNewParentId] = useState('');
  const [reassignParentOptions, setReassignParentOptions] = useState([]);
  const [reassigning, setReassigning] = useState(false);

  // Which roles the current user can create
  const creatableRoles = ALLOWED_ROLES_BY_CREATOR[currentUser?.role] || [];
  const canCreateUsers = creatableRoles.length > 0;

  // Cascading filter state (admin/manager table view only)
  const [filters, setFilters] = useState({ role: '', subDistManagerId: '', subDistId: '', clusterId: '', networkName: '' });
  const [tableSearchBy, setTableSearchBy] = useState('all');
  const [tableSearchInput, setTableSearchInput] = useState('');
  const [appliedTableSearch, setAppliedTableSearch] = useState({ by: 'all', query: '' });

  // Server-side pagination state (admin / md_director / manager table)
  const [tableRows, setTableRows] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [tableLoading, setTableLoading] = useState(false);
  const [statsData, setStatsData] = useState(null);
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const tableQueryVersionRef = useRef(0);

  const loadReferenceAndStats = async () => {
    const [sdRes, sdmRes, cRes, statsRes] = await Promise.all([
      usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE }),
      usersAPI.getUsers({ role: 'sub_distribution_manager', page_size: USERS_FETCH_PAGE_SIZE }),
      usersAPI.getUsers({ role: 'cluster', page_size: USERS_FETCH_PAGE_SIZE }),
      usersAPI.getUserStats(),
    ]);
    setUsers([
      ...(sdRes?.data || []),
      ...(sdmRes?.data || []),
      ...(cRes?.data || []),
    ]);
    setStatsData(statsRes?.data || null);
  };

  const fetchUsers = async () => {
    try {
      setLoading(true);
      if (isTableRole) {
        await loadReferenceAndStats();
        return;
      }
      const response = await usersAPI.getUsers({ page_size: USERS_FETCH_PAGE_SIZE });
      setUsers(response.data || []);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      showToast('Failed to load users', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchSubDistOperators = async () => {
    if (currentUser?.role !== 'sub_distributor') return;
    try {
      setLoadingOps(true);
      const response = await usersAPI.getUsers({ role: 'operator', page_size: USERS_FETCH_PAGE_SIZE });
      setSubDistOperators(response.data || []);
    } catch (error) {
      console.error('Failed to fetch operators:', error);
    } finally {
      setLoadingOps(false);
    }
  };

  const getScopeRootId = () => {
    if (filters.clusterId) return filters.clusterId;
    if (filters.subDistId) return filters.subDistId;
    if (filters.subDistManagerId) return filters.subDistManagerId;
    return '';
  };

  const buildTableQueryParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = { page: windowPage, page_size: pageSize };
    if (appliedTableSearch.query) {
      params.search = appliedTableSearch.query;
      if (appliedTableSearch.by && appliedTableSearch.by !== 'all') params.search_by = appliedTableSearch.by;
    }
    if (filters.role) params.role = filters.role;
    if (filters.networkName) params.network_name = filters.networkName;
    const scopeRootId = getScopeRootId();
    if (scopeRootId) params.scope_root_id = scopeRootId;
    return params;
  };

  const loadTableWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (!isTableRole) return;
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = tableQueryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setTableLoading(true);
    try {
      const response = await usersAPI.getUsers(buildTableQueryParams(windowPage));
      if (queryVersion !== tableQueryVersionRef.current) {
        return;
      }
      const rows = Array.isArray(response?.data) ? response.data : [];
      const totalCount = Number(response?.pagination?.total || rows.length);
      setTableRows((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const id = String(row?.id || '');
          if (!id || seen.has(id)) continue;
          seen.add(id);
          unique.push(row);
        }
        return unique;
      });
      setTableTotalCount(totalCount);
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      console.error('Failed to load users:', error);
      showToast('Failed to load users', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setTableLoading(false);
    }
  };

  const resetAndLoadTable = async () => {
    if (!isTableRole) return;
    tableQueryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setTableRows([]);
    setTableTotalCount(0);
    setTablePage(1);
    await loadTableWindow(1, { reset: true, withLoading: true });
  };

  const handleTablePageChange = (nextPage) => {
    setTablePage(nextPage);
    const requiredWindow = Math.ceil(nextPage / TABLE_WINDOW_PAGES);
    const loadedPageCount = Math.max(1, Math.ceil((tableRows.length || 0) / TABLE_PAGE_SIZE));
    const totalPageCount = Math.max(1, Math.ceil((tableTotalCount || 0) / TABLE_PAGE_SIZE));
    const totalWindows = Math.ceil((tableTotalCount || 0) / TABLE_WINDOW_SIZE);

    if (requiredWindow > loadedWindowRef.current) {
      loadTableWindow(requiredWindow, { reset: false, withLoading: false });
    }

    if (nextPage >= loadedPageCount && loadedPageCount < totalPageCount) {
      const nextWindow = loadedWindowRef.current + 1;
      if (nextWindow <= totalWindows && nextWindow > loadedWindowRef.current) {
        loadTableWindow(nextWindow, { reset: false, withLoading: false });
      }
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchSubDistOperators();
    if (currentUser?.role === 'super_admin') {
      reassignmentRequestsAPI.getRequests({ status: 'pending', page_size: 1 })
        .then(res => setPendingReassignCount(res?.pagination?.total || 0))
        .catch(() => setPendingReassignCount(0));
    }
  }, []);

  const queryFingerprint = useMemo(() => JSON.stringify({
    role: isTableRole ? filters.role : '',
    networkName: isTableRole ? filters.networkName : '',
    scopeRootId: isTableRole ? getScopeRootId() : '',
    search: isTableRole ? appliedTableSearch : { by: 'all', query: '' },
  }), [filters, appliedTableSearch, isTableRole]);

  useEffect(() => {
    if (!currentUser?.role) return;
    if (!isTableRole) return;
    resetAndLoadTable();
  }, [currentUser?.role, queryFingerprint]);

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all });
      fetchUsers();
      fetchSubDistOperators();
      if (isTableRole) {
        resetAndLoadTable();
      }
      if (currentUser?.role === 'super_admin') {
        reassignmentRequestsAPI.getRequests({ status: 'pending', page_size: 1 })
          .then(res => setPendingReassignCount(res?.pagination?.total || 0))
          .catch(() => setPendingReassignCount(0));
      }
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  // When add modal opens, default role to first available
  const openAddModal = () => {
    const defaultRole = creatableRoles[0] || 'operator';
    const initialParentId = (
      (currentUser?.role === 'sub_distributor' && (defaultRole === 'cluster' || defaultRole === 'sub_distribution_manager')) ||
      (currentUser?.role === 'cluster' && defaultRole === 'operator')
    ) ? currentUser.id : '';
    setFormData({ ...emptyForm, role: defaultRole, parentId: initialParentId });
    setParentOptions([]);
    setSubDistributorOptions([]);
    setSelectedOperatorSubDistId('');
    setConfirmPassword('');
    setShowCreatePassword(false);
    setShowCreateConfirmPassword(false);
    // For sub_distributor creating cluster, no parent selector needed.
    // For admin/manager, kick off load if default role requires it.
    if (['super_admin', 'manager', 'sub_distribution_manager'].includes(currentUser?.role)) {
      if (defaultRole === 'sub_distribution_manager' || defaultRole === 'cluster' || defaultRole === 'operator' || defaultRole === 'sub_distribution_employee') {
        loadParentOptions(defaultRole);
      }
    }
    setShowAddModal(true);
  };

  // Load parent options for admin/manager when creating cluster or operator
  const loadParentOptions = async (role) => {
    setLoadingParents(true);
    setParentOptions([]);
    setSubDistributorOptions([]);
    try {
      if (role === 'sub_distribution_manager') {
        const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE });
        setParentOptions(res.data || []);
      } else if (role === 'cluster') {
        const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE });
        setParentOptions(res.data || []);
      } else if (role === 'operator') {
        const [subRes, clusterRes] = await Promise.all([
          usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE }),
          usersAPI.getUsers({ role: 'cluster', page_size: USERS_FETCH_PAGE_SIZE }),
        ]);
        setSubDistributorOptions(subRes.data || []);
        setParentOptions(clusterRes.data || []);
      } else if (role === 'sub_distribution_employee') {
        const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE });
        setParentOptions(res.data || []);
      }
    } catch (err) {
      console.error('Failed to load parent options:', err);
    } finally {
      setLoadingParents(false);
    }
  };

  // Handle role change in add form - fetch parent options for admin/manager;
  // for sub_distributor creating operator, populate from local clusters state.
  const handleRoleChange = (newRole) => {
    const isAutoParent = (
      (currentUser?.role === 'sub_distributor' && (newRole === 'cluster' || newRole === 'sub_distribution_manager')) ||
      (currentUser?.role === 'cluster' && newRole === 'operator')
    );
    setFormData(prev => ({ ...prev, role: newRole, parentId: isAutoParent ? currentUser.id : '' }));
    setSelectedOperatorSubDistId('');
    setOperatorPlacement('sub_distributor');
    if (['super_admin', 'manager', 'sub_distribution_manager'].includes(currentUser?.role)) {
      if (newRole === 'sub_distribution_manager' || newRole === 'cluster' || newRole === 'operator' || newRole === 'sub_distribution_employee') {
        loadParentOptions(newRole);
      } else {
        setParentOptions([]);
        setSubDistributorOptions([]);
      }
    } else if (currentUser?.role === 'sub_distributor') {
      if (newRole === 'operator') {
        // Operators can be placed directly under this sub distributor OR under one of its clusters.
        setParentOptions([
          { id: String(currentUser.id), name: currentUser.name, groupLabel: 'Directly under me (Sub Distributor)' },
          ...users.filter((u) => u.role === 'cluster').map(c => ({ ...c, groupLabel: 'Cluster' })),
        ]);
      } else {
        setParentOptions([]);
      }
    } else if (currentUser?.role === 'cluster') {
      setParentOptions([{ id: String(currentUser.id), name: currentUser.name, groupLabel: 'Directly under me (Cluster)' }]);
    } else if (currentUser?.role === 'sub_distribution_employee') {
      if (newRole === 'cluster' || newRole === 'operator') {
        setParentOptions([{ id: String(currentUser.parent_id), name: currentUser.parent_name || 'My Sub Distribution', groupLabel: 'My Sub Distribution' }]);
      } else {
        setParentOptions([]);
      }
    }
  };

  // Fetch children (clusters/operators) when admin opens detail modal for a sub_distributor or cluster
  useEffect(() => {
    if (!detailUser) {
      setDetailChildren([]);
      return;
    }
    if (['sub_distributor', 'cluster'].includes(detailUser.role)) {
      const childRole = detailUser.role === 'sub_distributor' ? 'cluster' : 'operator';
      setLoadingChildren(true);
      usersAPI.getUsers({ role: childRole, parent_id: detailUser.id, page_size: USERS_FETCH_PAGE_SIZE })
        .then(res => setDetailChildren(res.data || []))
        .catch(err => console.error('Failed to fetch children:', err))
        .finally(() => setLoadingChildren(false));
    } else {
      setDetailChildren([]);
    }
  }, [detailUser]);

  const columns = [
    {
      key: 'name',
      label: currentUser?.role === 'sub_distributor' ? 'Cluster' : currentUser?.role === 'cluster' ? 'Operator' : 'User',
      render: (value, row) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
            <span className="font-medium text-gray-600">
              {(value || '').split(' ').filter(Boolean).map(n => n[0]).join('') || '?'}
            </span>
          </div>
          <div>
            <p className="font-medium text-gray-800">{value || '—'}</p>
            <p className="text-sm text-gray-500">{row.email}</p>
          </div>
        </div>
      )
    },
    {
      key: 'role',
      label: 'Role',
      render: (value) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${getRoleColor(value)}`}>
          {ROLE_LABELS[value] || value}
        </span>
      )
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    {
      key: 'phone',
      label: 'Phone',
      render: (value) => value || '-'
    },
    {
      key: 'network_name',
      label: 'Network Name',
      render: (value) => value || '-'
    },
    {
      key: 'created_at',
      label: 'Joined',
      render: (value) => value ? new Date(value).toLocaleDateString() : '-'
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const res = await usersAPI.getUser(row._id || row.id);
                setSelectedUser(res?.data || row);
              } catch {
                setSelectedUser(row);
              }
              setShowViewModal(true);
            }}
            className="p-1 hover:bg-gray-100 rounded"
            title="View"
          >
            <Eye className="w-4 h-4 text-gray-500" />
          </button>
          {canEditUser(row) && (
            <button
              onClick={async () => {
                try {
                  const res = await usersAPI.getUser(row._id || row.id);
                  const full = res?.data || row;
                  setDetailUser(full);
                  setDetailForm({ ...full });
                  const ids = (full.digital_ids || []).map(e => ({ ...e }));
                  setDetailDigitalIds(ids);
                  origDigitalIdIds.current = ids.map(e => e.id).filter(Boolean);
                } catch {
                  setDetailUser(row);
                  setDetailForm({ ...row });
                  setDetailDigitalIds([]);
                  origDigitalIdIds.current = [];
                }
                setNewPassword(''); setConfirmResetPassword(''); setShowResetPassword(false); setShowConfirmResetPassword(false);
              }}
              className="p-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200"
              title="Edit Details"
            >
              <Edit className="w-4 h-4" />
            </button>
          )}
          {canReassignUser(row) && (
            <button
              onClick={() => openReassignModal(row)}
              className="p-1 hover:bg-gray-100 rounded"
              title="Reassign"
            >
              <Network className="w-4 h-4 text-amber-500" />
            </button>
          )}
          {canDeleteUser(row) && (
            <button
              onClick={() => { setSelectedUser(row); setShowDeleteModal(true); }}
              className="p-1 hover:bg-gray-100 rounded"
              title="Delete"
            >
              <Trash2 className="w-4 h-4 text-red-500" />
            </button>
          )}
        </div>
      )
    }
  ];

  const handleAddUser = async (e) => {
    e.preventDefault();
    if (formData.password !== confirmPassword) {
      showToast('Password and confirm password do not match', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        role: formData.role,
      };
      const primaryRow = formData.digitalIdRows?.[0];
      if (primaryRow?.digitalId) payload.digital_id = primaryRow.digitalId;
      if (primaryRow?.broadbandId) payload.broadband_id = primaryRow.broadbandId;
      const extraIds = (formData.digitalIdRows || []).slice(1).map(r => r.digitalId).filter(Boolean);
      if (extraIds.length > 0) payload.additional_digital_ids = extraIds.join('|');
      if (formData.phone)      payload.phone = formData.phone;
      if (formData.designation) payload.designation = formData.designation;
      if (formData.address)    payload.address = formData.address;
      if (formData.pincode)    payload.pincode = formData.pincode;
      if (formData.parentId)   payload.parent_id = formData.parentId;
      if (formData.role === 'operator' && formData.networkName) payload.network_name = formData.networkName;

      await usersAPI.createUser(payload);
      showToast('User created successfully', 'success');
      setShowAddModal(false);
      setFormData(emptyForm);
      setConfirmPassword('');
      setShowCreatePassword(false);
      setShowCreateConfirmPassword(false);
      setParentOptions([]);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to create user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {};
      if (formData.name)        payload.name = formData.name;
      if (formData.phone)       payload.phone = formData.phone;
      if (formData.designation) payload.designation = formData.designation;
      if (formData.role === 'operator') payload.network_name = formData.networkName || null;
      const editPrimaryRow = formData.digitalIdRows?.[0];
      if (editPrimaryRow?.digitalId) payload.digital_id = editPrimaryRow.digitalId;
      if (editPrimaryRow?.broadbandId) payload.broadband_id = editPrimaryRow.broadbandId;

      await usersAPI.updateUser(selectedUser._id || selectedUser.id, payload);
      showToast('User updated successfully', 'success');
      setShowEditModal(false);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to update user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteUser = async () => {
    try {
      const res = await usersAPI.deleteUser(selectedUser._id || selectedUser.id);
      const isReassign = res?.data?.request && (selectedUser?.role === 'sub_distributor' || selectedUser?.role === 'cluster');
      if (isReassign) {
        showToast(`Reassignment request created for ${res.data.children_count} user(s)`, 'success');
      } else {
        showToast('User deleted successfully', 'success');
      }
      setShowDeleteModal(false);
      setSelectedUser(null);
      // Data refetch is handled automatically by appDataMutation event
      // Refresh reassignment count
      if (currentUser?.role === 'super_admin') {
        reassignmentRequestsAPI.getRequests({ status: 'pending', page_size: 1 })
          .then(res2 => setPendingReassignCount(res2?.pagination?.total || 0))
          .catch(() => {});
      }
    } catch (error) {
      showToast(error.message || 'Failed to delete user', 'error');
    }
  };

  const openReassignModal = async (user) => {
    setReassignTarget(user);
    setReassignNewParentId('');

    try {
      if (user.role === 'cluster') {
        const res = await usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE });
        setReassignParentOptions(res.data || []);
      } else if (user.role === 'operator') {
        const [sdRes, clRes] = await Promise.all([
          usersAPI.getUsers({ role: 'sub_distributor', page_size: USERS_FETCH_PAGE_SIZE }),
          usersAPI.getUsers({ role: 'cluster', page_size: USERS_FETCH_PAGE_SIZE }),
        ]);
        setReassignParentOptions([
          ...(sdRes.data || []).map(u => ({ ...u, groupLabel: 'Sub Distributor' })),
          ...(clRes.data || []).map(u => ({ ...u, groupLabel: 'Cluster' })),
        ]);
      }
    } catch (err) {
      showToast('Failed to load parent options', 'error');
    }
    setShowReassignModal(true);
  };

  const handleReassignUser = async () => {
    if (!reassignTarget || !reassignNewParentId) return;
    setReassigning(true);
    try {
      const res = await usersAPI.reassignUser(reassignTarget.id, { new_parent_id: reassignNewParentId });
      showToast(res.message || 'User reassigned successfully', 'success');
      setShowReassignModal(false);
      setReassignTarget(null);
      setReassignNewParentId('');
    } catch (err) {
      showToast(err.message || 'Failed to reassign user', 'error');
    } finally {
      setReassigning(false);
    }
  };

  // Role flags — declared at the top of the component

  const canEditUser = (row) => {
    if (isAdmin) return row.role !== 'super_admin' || String(row.id) === String(currentUser.id);
    if (isManager) return !['super_admin', 'md_director', 'manager'].includes(row.role);
    if (currentUser?.role === 'sub_distribution_employee') return ['cluster', 'operator'].includes(row.role);
    return false;
  };

  const canDeleteUser = (row) => {
    if (isAdmin) return row.role !== 'super_admin' && String(row.id) !== String(currentUser.id);
    if (isManager) return !['super_admin', 'md_director', 'manager'].includes(row.role) && String(row.id) !== String(currentUser.id);
    if (currentUser?.role === 'sub_distribution_employee') return ['cluster', 'operator'].includes(row.role);
    return false;
  };

  const canReassignUser = (row) => {
    if (currentUser?.role === 'sub_distribution_employee') return ['cluster', 'operator'].includes(row.role);
    if (!['super_admin', 'manager'].includes(currentUser?.role)) return false;
    if (row.role !== 'cluster' && row.role !== 'operator') return false;
    if (isManager && ['super_admin', 'md_director', 'manager'].includes(row.role)) return false;
    return true;
  };

  const visibleUsers = useMemo(() => {
    if (isMdDirector) return users.filter((u) => u.role !== 'super_admin');
    if (!isManager) return users;
    // Managers should not see admin user details in the users surface.
    return users.filter((u) => u.role !== 'super_admin');
  }, [users, isManager, isMdDirector]);

  const filteredClusterParentOptions = useMemo(() => {
    if (!isAdminOrManager || formData.role !== 'operator') return parentOptions;
    if (!selectedOperatorSubDistId) return [];
    const managerIdsInSelectedSubDistribution = visibleUsers
      .filter((u) => u.role === 'sub_distribution_manager' && String(u.parent_id) === String(selectedOperatorSubDistId))
      .map((u) => String(u.id));

    return parentOptions.filter((cluster) => (
      String(cluster.parent_id) === String(selectedOperatorSubDistId)
      || managerIdsInSelectedSubDistribution.includes(String(cluster.parent_id))
    ));
  }, [isAdminOrManager, formData.role, parentOptions, selectedOperatorSubDistId, visibleUsers]);

  // Cascading filtered users for admin/manager table
  const filteredUsers = useMemo(() => {
    if (!isAdmin && !isManager) return visibleUsers;
    let result = visibleUsers;
    if (filters.role) {
      result = result.filter(u => u.role === filters.role);
    }
    if (filters.networkName) {
      result = result.filter(u =>
        String(u.network_name || '').toLowerCase().includes(filters.networkName.toLowerCase())
      );
    }
    if (filters.clusterId) {
      result = result.filter(u =>
        String(u.id) === filters.clusterId ||
        String(u.parent_id) === filters.clusterId
      );
    } else if (filters.subDistId) {
      const subDistManagerIds = visibleUsers
        .filter(u => u.role === 'sub_distribution_manager' && String(u.parent_id) === filters.subDistId)
        .map(u => String(u.id));
      const clusterViaSDMIds = visibleUsers
        .filter(u => u.role === 'cluster' && subDistManagerIds.includes(String(u.parent_id)))
        .map(u => String(u.id));
      const clusterDirectIds = visibleUsers
        .filter(u => u.role === 'cluster' && String(u.parent_id) === filters.subDistId)
        .map(u => String(u.id));
      const allClusterIds = [...new Set([...clusterViaSDMIds, ...clusterDirectIds])];

      result = result.filter(u =>
        String(u.id) === filters.subDistId ||
        String(u.parent_id) === filters.subDistId ||
        subDistManagerIds.includes(String(u.id)) ||
        allClusterIds.includes(String(u.id)) ||
        allClusterIds.includes(String(u.parent_id))
      );
    } else if (filters.subDistManagerId) {
      const clusterIds = visibleUsers
        .filter(u => u.role === 'cluster' && String(u.parent_id) === filters.subDistManagerId)
        .map(u => String(u.id));

      result = result.filter(u =>
        String(u.id) === filters.subDistManagerId ||
        clusterIds.includes(String(u.id)) ||
        clusterIds.includes(String(u.parent_id))
      );
    }
    return result;
  }, [visibleUsers, filters, isAdmin, isManager]);

  const searchedFilteredUsers = useMemo(() => {
    const query = String(appliedTableSearch.query || '').trim().toLowerCase();
    if (!query) return filteredUsers;

    const searchableFields = {
      name: (row) => row?.name,
      email: (row) => row?.email,
      role: (row) => row?.role,
      status: (row) => row?.status,
      phone: (row) => row?.phone,
      designation: (row) => row?.designation,
      digital_id: (row) => Array.isArray(row?.digital_ids)
        ? row.digital_ids.map((di) => di?.digital_id || '').join(' ')
        : row?.digital_id,
      broadband_id: (row) => Array.isArray(row?.digital_ids)
        ? row.digital_ids.map((di) => di?.broadband_id || '').join(' ')
        : row?.broadband_id,
    };

    const searchBy = String(appliedTableSearch.by || 'all');
    if (searchBy !== 'all' && searchableFields[searchBy]) {
      return filteredUsers.filter((row) => String(searchableFields[searchBy](row) || '').toLowerCase().includes(query));
    }

    return filteredUsers.filter((row) => {
      return Object.values(searchableFields).some((getter) => String(getter(row) || '').toLowerCase().includes(query));
    });
  }, [filteredUsers, appliedTableSearch]);

  const handleTableSearchSubmit = () => {
    setAppliedTableSearch({ by: tableSearchBy, query: tableSearchInput.trim() });
  };

  const handleTableSearchReset = () => {
    setTableSearchBy('all');
    setTableSearchInput('');
    setAppliedTableSearch({ by: 'all', query: '' });
  };

  // Compute clusterOperators map for sub_distributor hierarchical view
  const clusterOperatorsMap = useMemo(() => {
    const map = {};
    for (const op of subDistOperators) {
      const key = String(op.parent_id);
      if (!map[key]) map[key] = [];
      map[key].push(op);
    }
    return map;
  }, [subDistOperators]);

  const byRole = statsData?.by_role || {};

  const stats = isSubDist
    ? [
        { label: 'Total Clusters',    value: users.filter(u => u.role === 'cluster').length,                                      icon: Network,    color: 'teal'   },
        { label: 'Active Clusters',   value: users.filter(u => u.role === 'cluster' && u.status === 'active').length,             icon: UsersIcon,  color: 'green'  },
        { label: 'Employees',         value: users.filter(u => u.role === 'sub_distribution_employee').length,                    icon: UsersIcon,  color: 'violet' },
        { label: 'Total Operators',   value: subDistOperators.length,                                                              icon: UsersIcon,  color: 'blue'   },
      ]
    : isCluster
    ? [
        { label: 'Total Operators',   value: users.length,                                                            icon: UsersIcon,  color: 'blue'   },
        { label: 'Active Operators',  value: users.filter(u => u.status === 'active').length,                         icon: UsersIcon,  color: 'green'  },
      ]
    : isAdmin
    ? [
        { label: 'Total Users',       value: statsData ? statsData.total : 0,                                          icon: UsersIcon,  color: 'blue'   },
        { label: 'Super Admins',      value: byRole.super_admin || 0,                                                   icon: Shield,     color: 'red'    },
        { label: 'MD/Director',       value: byRole.md_director || 0,                                                   icon: Shield,     color: 'orange' },
        { label: 'Managers',          value: byRole.manager || 0,                                                       icon: Shield,     color: 'purple' },
        { label: 'PDIC Staff',        value: byRole.pdic_staff || 0,                                                    icon: UsersIcon,  color: 'blue'   },
        { label: 'Sub Dist. Manager', value: byRole.sub_distribution_manager || 0,                                      icon: Building,   color: 'cyan'   },
        { label: 'Sub Distributors',  value: byRole.sub_distributor || 0,                                               icon: Building,   color: 'indigo' },
        { label: 'Clusters',          value: byRole.cluster || 0,                                                       icon: Network,    color: 'teal'   },
        { label: 'Operators',         value: byRole.operator || 0,                                                      icon: UsersIcon,  color: 'green'  },
      ]
    : isManager
    ? [
        { label: 'Total Users',       value: statsData ? statsData.total : 0,                                          icon: UsersIcon,  color: 'blue'   },
        { label: 'PDIC Staff',        value: byRole.pdic_staff || 0,                                                    icon: UsersIcon,  color: 'blue'   },
        { label: 'Sub Dist. Manager', value: byRole.sub_distribution_manager || 0,                                     icon: Building,   color: 'cyan'   },
        { label: 'Sub Distributors',  value: byRole.sub_distributor || 0,                                              icon: Building,   color: 'indigo' },
        { label: 'Clusters',          value: byRole.cluster || 0,                                                       icon: Network,    color: 'teal'   },
        { label: 'Operators',         value: byRole.operator || 0,                                                      icon: UsersIcon,  color: 'green'  },
      ]
    : isMdDirector
    ? [
        { label: 'Total Users',       value: statsData ? statsData.total : 0,                                          icon: UsersIcon,  color: 'blue'   },
        { label: 'Operators',         value: byRole.operator || 0,                                                      icon: UsersIcon,  color: 'green'  },
      ]
    : [
        { label: 'Total Users',       value: users.length,                                                            icon: UsersIcon,  color: 'blue'   },
        { label: 'Operators',         value: users.filter(u => u.role === 'operator').length,                         icon: UsersIcon,  color: 'green'  },
      ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">
            {isSubDist ? 'My Users' : isCluster ? 'Operator Management' : isMdDirector ? 'Users (Read Only)' : 'User Management'}
          </h1>
          <p className="text-gray-500 mt-1">
            {isSubDist
              ? 'View clusters and operators under your sub-distribution'
              : isCluster
                ? 'View operators in your cluster'
                : isMdDirector
                  ? 'View all users and their details except Super Admin accounts'
                  : 'Manage system users and their permissions'}
          </p>
        </div>
        {canCreateUsers && (
          <Button icon={UserPlus} onClick={openAddModal}>
            {isSubDist ? 'Add User' : isCluster ? 'Add Operator' : 'Add User'}
          </Button>
        )}
      </div>

      {/* Reassignment request alert for super admin */}
      {isAdmin && pendingReassignCount > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-amber-800">
              <strong>{pendingReassignCount}</strong> reassignment request{pendingReassignCount !== 1 ? 's' : ''} pending.
              <Link to="/reassignment-requests" className="ml-2 text-amber-700 underline hover:text-amber-900 font-medium">
                View and manage
              </Link>
            </p>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className={`grid ${
        isAdmin ? 'grid-cols-2 sm:grid-cols-4 lg:grid-cols-7' :
        isManager ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5' :
        isSubDist ? 'grid-cols-2 sm:grid-cols-4' :
        'grid-cols-2'
      } gap-4`}>
        {stats.map((stat, index) => (
          <Card key={index} className="text-center">
            <div className={`inline-flex p-3 rounded-lg bg-${stat.color}-100 mb-2`}>
              <stat.icon className={`w-6 h-6 text-${stat.color}-600`} />
            </div>
            <p className="text-2xl font-bold text-gray-800">{stat.value}</p>
            <p className="text-sm text-gray-500">{stat.label}</p>
          </Card>
        ))}
      </div>

      {/* Main content: hierarchical view for sub_distributor, table for everyone else */}
      {isSubDist ? (
        <div className="space-y-4">
          {(loading || loadingOps) ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <span className="ml-3 text-gray-500">Loading...</span>
            </div>
          ) : users.length === 0 ? (
            <Card>
              <div className="text-center py-10">
                <Network className="w-14 h-14 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No clusters found under your sub-distribution.</p>
              </div>
            </Card>
          ) : (
            <>
            {users.filter(u => u.role === 'sub_distribution_employee').length > 0 && (
              <Card>
                <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                    <UsersIcon className="w-4 h-4 text-violet-500" /> Sub Distribution Employees
                  </h3>
                </div>
                <div className="space-y-2 p-3">
                  {users
                    .filter(u => u.role === 'sub_distribution_employee')
                    .map(emp => (
                      <div key={emp.id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 bg-violet-100 rounded-full flex items-center justify-center">
                            <span className="text-xs font-medium text-violet-600">
                              {(emp.name || '').split(' ').filter(Boolean).map(n => n[0]).join('') || '?'}
                            </span>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-800">{emp.name}</p>
                            <p className="text-xs text-gray-500">{emp.email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700">Sub Distribution Employee</span>
                          <StatusBadge status={emp.status} size="sm" />
                          <button
                            onClick={() => { setSelectedUser(emp); setShowViewModal(true); }}
                            className="p-1 hover:bg-gray-100 rounded"
                            title="View employee"
                          >
                            <Eye className="w-3.5 h-3.5 text-gray-500" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </Card>
            )}
            {users.filter(u => u.role === 'cluster').map(cluster => {
              const clusterOps = clusterOperatorsMap[String(cluster.id)] || [];
              const isCollapsed = !!collapsedClusters[cluster.id];
              return (
                <Card key={cluster.id} className="overflow-hidden">
                  {/* Cluster header row */}
                  <div
                    className="flex items-center justify-between cursor-pointer select-none"
                    onClick={() => setCollapsedClusters(prev => ({ ...prev, [cluster.id]: !prev[cluster.id] }))}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                        <Network className="w-5 h-5 text-teal-600" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-gray-800">{cluster.name}</p>
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-teal-100 text-teal-700">Cluster</span>
                          <StatusBadge status={cluster.status} size="sm" />
                        </div>
                        <p className="text-xs text-gray-500">{cluster.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-gray-500">{clusterOps.length} operator{clusterOps.length !== 1 ? 's' : ''}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={e => { e.stopPropagation(); setSelectedUser(cluster); setShowViewModal(true); }}
                          className="p-1.5 hover:bg-gray-100 rounded"
                          title="View cluster"
                        >
                          <Eye className="w-4 h-4 text-gray-500" />
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); openReassignModal(cluster); }}
                          className="p-1.5 hover:bg-amber-50 rounded"
                          title="Reassign cluster"
                        >
                          <Network className="w-4 h-4 text-amber-500" />
                        </button>
                        {isCollapsed
                          ? <ChevronRight className="w-4 h-4 text-gray-400" />
                          : <ChevronDown className="w-4 h-4 text-gray-400" />}
                      </div>
                    </div>
                  </div>

                  {/* Operators under this cluster */}
                  {!isCollapsed && (
                    <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                      {clusterOps.length === 0 ? (
                        <p className="text-xs text-gray-400 italic ml-12">No operators in this cluster yet.</p>
                      ) : (
                        clusterOps.map(op => (
                          <div key={op.id} className="flex items-center justify-between ml-10 pl-3 border-l-2 border-gray-100 py-1">
                            <div className="flex items-center gap-2">
                              <div className="w-7 h-7 bg-green-100 rounded-full flex items-center justify-center">
                                <span className="text-xs font-medium text-green-600">
                                  {(op.name || '').split(' ').filter(Boolean).map(n => n[0]).join('') || '?'}
                                </span>
                              </div>
                              <div>
                                <p className="text-sm font-medium text-gray-800">{op.name}</p>
                                <p className="text-xs text-gray-500">{op.email}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <StatusBadge status={op.status} size="sm" />
                              <button
                                onClick={() => { setSelectedUser(op); setShowViewModal(true); }}
                                className="p-1 hover:bg-gray-100 rounded"
                                title="View operator"
                              >
                                <Eye className="w-3.5 h-3.5 text-gray-500" />
                              </button>
                              <button
                                onClick={() => { openReassignModal(op); }}
                                className="p-1 hover:bg-amber-50 rounded"
                                title="Reassign operator"
                              >
                                <Network className="w-3.5 h-3.5 text-amber-500" />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
            </>
          )}
        </div>
      ) : (
        /* Standard table view for all other roles */
        <>
          {/* ── Cascading filter bar (admin / manager only) ── */}
          {(isAdmin || isManager) && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <Filter className="w-4 h-4 text-gray-500" /> Filter Users
                </p>
                {(filters.role || filters.subDistManagerId || filters.subDistId || filters.clusterId || filters.networkName) && (
                  <button
                    onClick={() => setFilters({ role: '', subDistManagerId: '', subDistId: '', clusterId: '', networkName: '' })}
                    className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    Clear all
                  </button>
                )}
              </div>

              <div className="flex flex-wrap gap-3 items-end">
                {/* Role */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-gray-500 font-medium">Role</label>
                  <select
                    value={filters.role}
                    onChange={e => setFilters({
                      role: e.target.value,
                      subDistManagerId: '',
                      subDistId: '',
                      clusterId: '',
                      networkName: (!e.target.value || e.target.value === 'operator') ? filters.networkName : '',
                    })}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 min-w-[150px]"
                  >
                    <option value="">All Roles</option>
                    {Object.entries(ROLE_LABELS).map(([r, l]) => (
                      <option key={r} value={r}>{l}</option>
                    ))}
                  </select>
                </div>

                {/* Sub-Distributor */}
                {(!filters.role || ['sub_distribution_manager', 'cluster', 'operator'].includes(filters.role)) && (
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500 font-medium">Sub-Distributor</label>
                    <select
                      value={filters.subDistId}
                      onChange={e => setFilters(p => ({ ...p, subDistId: e.target.value, subDistManagerId: '', clusterId: '' }))}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 min-w-[180px]"
                    >
                      <option value="">All Sub-Distributors</option>
                      {visibleUsers
                        .filter(u => u.role === 'sub_distributor')
                        .map(sd => (
                          <option key={sd.id} value={String(sd.id)}>{sd.name}</option>
                        ))}
                    </select>
                  </div>
                )}

                {/* Sub Distribution Manager */}
                {(!filters.role || ['cluster', 'operator'].includes(filters.role)) && (
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500 font-medium">Sub Dist. Manager</label>
                    <select
                      value={filters.subDistManagerId}
                      onChange={e => setFilters(p => ({ ...p, subDistManagerId: e.target.value, clusterId: '' }))}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 min-w-[180px]"
                    >
                      <option value="">All Sub Dist. Managers</option>
                      {visibleUsers
                        .filter(u => u.role === 'sub_distribution_manager' && (!filters.subDistId || String(u.parent_id) === filters.subDistId))
                        .map(sdm => (
                        <option key={sdm.id} value={String(sdm.id)}>{sdm.name}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Cluster — visible when role is '' / 'operator'; narrows further if subDistId set */}
                {(!filters.role || filters.role === 'operator') && (
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500 font-medium">Cluster</label>
                    <select
                      value={filters.clusterId}
                      onChange={e => setFilters(p => ({ ...p, clusterId: e.target.value }))}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 min-w-[170px]"
                    >
                      <option value="">All Clusters</option>
                      {visibleUsers
                        .filter(u => {
                          if (u.role !== 'cluster') return false;
                          if (filters.subDistManagerId) return String(u.parent_id) === filters.subDistManagerId;
                          if (filters.subDistId) {
                            if (String(u.parent_id) === filters.subDistId) return true;
                            const parentSdm = visibleUsers.find(sdm => String(sdm.id) === String(u.parent_id));
                            return parentSdm && String(parentSdm.parent_id) === filters.subDistId;
                          }
                          return true;
                        })
                        .map(c => (
                          <option key={c.id} value={String(c.id)}>{c.name}</option>
                        ))}
                    </select>
                  </div>
                )}

                {/* Network Name — operators only */}
                {(!filters.role || filters.role === 'operator') && (
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500 font-medium">Network Name</label>
                    <input
                      type="text"
                      value={filters.networkName}
                      onChange={e => setFilters(p => ({ ...p, networkName: e.target.value }))}
                      placeholder="Filter by network..."
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 min-w-[180px]"
                    />
                  </div>
                )}

                {/* Active filter chips + result count */}
                {(filters.role || filters.subDistManagerId || filters.subDistId || filters.clusterId || filters.networkName) && (
                  <div className="flex items-center gap-2 flex-wrap pb-0.5">
                    {filters.role && (
                      <span className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 ${getRoleColor(filters.role)}`}>
                        {ROLE_LABELS[filters.role]}
                        <button onClick={() => setFilters(p => ({ ...p, role: '' }))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}
                    {filters.subDistManagerId && (
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-100 text-cyan-800 flex items-center gap-1.5">
                        {visibleUsers.find(u => String(u.id) === filters.subDistManagerId)?.name || 'Sub Dist. Manager'}
                        <button onClick={() => setFilters(p => ({ ...p, subDistManagerId: '', subDistId: '', clusterId: '' }))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}

                    {filters.subDistId && (
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 flex items-center gap-1.5">
                        {visibleUsers.find(u => String(u.id) === filters.subDistId)?.name || 'Sub-Dist'}
                        <button onClick={() => setFilters(p => ({ ...p, subDistId: '', clusterId: '' }))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}
                    {filters.clusterId && (
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-teal-100 text-teal-800 flex items-center gap-1.5">
                        {visibleUsers.find(u => String(u.id) === filters.clusterId)?.name || 'Cluster'}
                        <button onClick={() => setFilters(p => ({ ...p, clusterId: '' }))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}
                    {filters.networkName && (
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 flex items-center gap-1.5">
                        Network: {filters.networkName}
                        <button onClick={() => setFilters(p => ({ ...p, networkName: '' }))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {isTableRole ? tableTotalCount : filteredUsers.length} result{isTableRole ? (tableTotalCount !== 1 ? 's' : '') : (filteredUsers.length !== 1 ? 's' : '')}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          <Card className="!p-4">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-800">Search Users</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
              <div className="md:col-span-3">
                <select
                  value={tableSearchBy}
                  onChange={(e) => setTableSearchBy(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  {USER_SEARCH_BY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-6">
                <input
                  type="text"
                  value={tableSearchInput}
                  onChange={(e) => setTableSearchInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleTableSearchSubmit();
                    }
                  }}
                  placeholder="Enter pattern to search..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div className="md:col-span-3 flex gap-2">
                <Button onClick={handleTableSearchSubmit} className="w-full">Search</Button>
                <Button variant="secondary" onClick={handleTableSearchReset}>Reset</Button>
              </div>
            </div>
          </Card>

          <Card>
            {(loading || (isTableRole && tableLoading && tableRows.length === 0)) ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                <span className="ml-3 text-gray-500">Loading users...</span>
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={isTableRole ? tableRows : searchedFilteredUsers}
                searchable={false}
                pageSize={TABLE_PAGE_SIZE}
                totalItems={isTableRole ? tableTotalCount || tableRows.length : undefined}
                currentPage={isTableRole ? tablePage : undefined}
                onPageChange={isTableRole ? handleTablePageChange : undefined}
              />
            )}
          </Card>
        </>
      )}

      {/* View Modal */}
      <Modal
        isOpen={showViewModal}
        onClose={() => { setShowViewModal(false); setSelectedUser(null); }}
        title="User Details"
        size="lg"
      >
        {selectedUser && (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center">
                <span className="text-xl font-medium text-gray-600">
                  {(selectedUser.name || '').split(' ').filter(Boolean).map(n => n[0]).join('') || '?'}
                </span>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedUser.name}</h3>
                <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${getRoleColor(selectedUser.role)}`}>
                  {ROLE_LABELS[selectedUser.role] || selectedUser.role}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* ── Contact ── */}
              <div className="flex items-center gap-3">
                <Mail className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Email</p>
                  <p className="font-medium text-gray-800">{selectedUser.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Phone className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Phone</p>
                  <p className="font-medium text-gray-800">{selectedUser.phone || 'Not provided'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Building className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Designation</p>
                  <p className="font-medium text-gray-800">{selectedUser.designation || 'Not assigned'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Building className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Address</p>
                  <p className="font-medium text-gray-800">{selectedUser.address || 'Not provided'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Building className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Pincode</p>
                  <p className="font-medium text-gray-800">{selectedUser.pincode || 'Not provided'}</p>
                </div>
              </div>

              {/* ── Account ── */}
              <div className="flex items-center gap-3">
                <Shield className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <StatusBadge status={selectedUser.status} />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Joined</p>
                  <p className="font-medium text-gray-800">{selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleDateString() : 'Unknown'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Last Updated</p>
                  <p className="font-medium text-gray-800">{selectedUser.updated_at ? new Date(selectedUser.updated_at).toLocaleDateString() : 'Unknown'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Last Login</p>
                  <p className="font-medium text-gray-800">{selectedUser.last_login ? new Date(selectedUser.last_login).toLocaleString() : 'Never'}</p>
                </div>
              </div>
              {/* ── Digital IDs ── */}
              {selectedUser.digital_ids && selectedUser.digital_ids.length > 0 && (
                <div className="col-span-2 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 font-medium mb-2">Digital IDs</p>
                  <div className="space-y-3">
                    {selectedUser.digital_ids.map((entry, idx) => (
                      <div key={entry.id || idx} className="text-sm border-b border-gray-200 pb-2 last:border-0 last:pb-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Calendar className="w-3.5 h-3.5 text-gray-400" />
                          <span className="text-gray-400 text-xs">{new Date(entry.created_at).toLocaleDateString()}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 ml-5">
                          <div>
                            <span className="text-gray-400 text-xs block">Digital ID</span>
                            <span className="font-medium">{entry.digital_id || '---'}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 text-xs block">Broadband ID</span>
                            <span className="font-medium">{entry.broadband_id || '---'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(!selectedUser.digital_ids || selectedUser.digital_ids.length === 0) && (
                <div className="flex items-center gap-3">
                  <Building className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">Digital IDs</p>
                    <p className="font-medium text-gray-800">None</p>
                  </div>
                </div>
              )}

              {/* ── Created By ── */}
              {selectedUser.created_by && (
                <div className="col-span-2 flex items-center gap-3">
                  <UsersIcon className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">Created By</p>
                    <p className="font-medium text-gray-800">
                      {(() => {
                        if (selectedUser.created_by_name) {
                          return selectedUser.created_by_name;
                        }
                        const creator = users.find(u => String(u.id) === String(selectedUser.created_by));
                        return creator ? creator.name : (selectedUser.created_by ? `User #${selectedUser.created_by}` : 'N/A');
                      })()}
                    </p>
                  </div>
                </div>
              )}

              {/* ── Hierarchy breadcrumb ── */}
              {selectedUser.parent_id && (() => {
                const allAvailable = [...users, ...subDistOperators];
                const parent = allAvailable.find(u => String(u.id) === String(selectedUser.parent_id))
                  || (String(currentUser?.id) === String(selectedUser.parent_id) ? currentUser : null);
                const grandParent = parent?.parent_id
                  ? allAvailable.find(u => String(u.id) === String(parent.parent_id))
                    || (String(currentUser?.id) === String(parent.parent_id) ? currentUser : null)
                  : null;
                if (!parent) return null;
                return (
                  <div className="col-span-2 p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500 font-medium mb-2 flex items-center gap-1">
                      <Network className="w-3.5 h-3.5" /> Hierarchy
                    </p>
                    <div className="flex items-center gap-2 flex-wrap">
                      {grandParent && (
                        <>
                          <span className={`px-2 py-1 rounded-md text-xs font-medium ${getRoleColor(grandParent.role)}`}>
                            {ROLE_LABELS[grandParent.role] || grandParent.role}: <strong>{grandParent.name}</strong>
                          </span>
                          <span className="text-gray-400">→</span>
                        </>
                      )}
                      <span className={`px-2 py-1 rounded-md text-xs font-medium ${getRoleColor(parent.role)}`}>
                        {ROLE_LABELS[parent.role] || parent.role}: <strong>{parent.name}</strong>
                      </span>
                      <span className="text-gray-400">→</span>
                      <span className={`px-2 py-1 rounded-md text-xs font-medium ${getRoleColor(selectedUser.role)}`}>
                        {ROLE_LABELS[selectedUser.role] || selectedUser.role}: <strong>{selectedUser.name}</strong>
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        )}
      </Modal>

      {/* Add User Modal */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false);
          setFormData(emptyForm);
          setParentOptions([]);
          setSubDistributorOptions([]);
          setSelectedOperatorSubDistId('');
        }}
        title={
          isSubDist ? (formData.role === 'operator' ? 'Add New Operator' : 'Add New Cluster')
          : isCluster ? 'Add New Operator'
          : 'Add New User'
        }
        size="md"
      >
        <form onSubmit={handleAddUser} className="space-y-4">
          {/* Required fields */}
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter full name"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="user@example.com"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <span className="flex items-center gap-1"><Lock className="w-3.5 h-3.5" /> Password <span className="text-red-500">*</span></span>
              </label>
              <div className="relative">
                <input
                  type={showCreatePassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Min. 6 characters"
                  minLength={6}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCreatePassword((prev) => !prev)}
                  className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-700"
                  aria-label={showCreatePassword ? 'Hide password' : 'Show password'}
                >
                  {showCreatePassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Confirm Password <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showCreateConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Retype password"
                  minLength={6}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCreateConfirmPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-700"
                  aria-label={showCreateConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                >
                  {showCreateConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {confirmPassword && formData.password !== confirmPassword && (
                <p className="text-xs text-red-600 mt-1">Passwords do not match</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Role <span className="text-red-500">*</span>
              </label>
              <select
                value={formData.role}
                onChange={(e) => handleRoleChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              >
                {creatableRoles.map(r => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
            </div>

            {/* Parent selector — shown when admin/manager creates sub-distributor/cluster/operator,
                OR when sub_distributor creates an operator (must select a parent).
                Cluster creating an operator is NOT shown — the parent is the cluster itself automatically. */}
            {((isAdminOrManager) && (['sub_distribution_manager', 'cluster', 'operator', 'sub_distribution_employee'].includes(formData.role))) ||
             (currentUser?.role === 'sub_distribution_manager' && formData.role === 'sub_distribution_employee') ||
             (currentUser?.role === 'sub_distributor' && formData.role === 'operator') ? (
              <div>
                {isAdminOrManager && formData.role === 'operator' ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Operator Placement</label>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="radio"
                            name="operatorPlacement"
                            checked={operatorPlacement === 'sub_distributor'}
                            onChange={() => {
                              setOperatorPlacement('sub_distributor');
                              setFormData((prev) => ({ ...prev, parentId: '' }));
                              setSelectedOperatorSubDistId('');
                            }}
                            className="accent-blue-600"
                          />
                          Directly under a Sub Distributor
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="radio"
                            name="operatorPlacement"
                            checked={operatorPlacement === 'cluster'}
                            onChange={() => {
                              setOperatorPlacement('cluster');
                              setFormData((prev) => ({ ...prev, parentId: '' }));
                              setSelectedOperatorSubDistId('');
                            }}
                            className="accent-blue-600"
                          />
                          Under a Cluster
                        </label>
                      </div>
                    </div>

                    {operatorPlacement === 'sub_distributor' ? (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Assign to Sub Distributor <span className="text-red-500">*</span>
                        </label>
                        {loadingParents ? (
                          <div className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50">
                            <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                            <span className="text-sm text-gray-500">Loading options...</span>
                          </div>
                        ) : (
                          <select
                            value={formData.parentId}
                            onChange={(e) => setFormData((prev) => ({ ...prev, parentId: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            required
                          >
                            <option value="">Select Sub Distributor...</option>
                            {subDistributorOptions.map((sd) => (
                              <option key={sd.id} value={sd.id}>{sd.name}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    ) : (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Select Sub Distribution <span className="text-red-500">*</span>
                          </label>
                          {loadingParents ? (
                            <div className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50">
                              <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                              <span className="text-sm text-gray-500">Loading options...</span>
                            </div>
                          ) : (
                            <select
                              value={selectedOperatorSubDistId}
                              onChange={(e) => {
                                setSelectedOperatorSubDistId(e.target.value);
                                setFormData((prev) => ({ ...prev, parentId: '' }));
                              }}
                              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              required
                            >
                              <option value="">Select Sub Distribution...</option>
                              {subDistributorOptions.map((sd) => (
                                <option key={sd.id} value={sd.id}>{sd.name}</option>
                              ))}
                            </select>
                          )}
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Assign to Cluster <span className="text-red-500">*</span>
                          </label>
                          <select
                            value={formData.parentId}
                            onChange={(e) => setFormData((prev) => ({ ...prev, parentId: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            required
                            disabled={!selectedOperatorSubDistId}
                          >
                            <option value="">
                              {selectedOperatorSubDistId ? 'Select Cluster...' : 'Select Sub Distribution first...'}
                            </option>
                            {filteredClusterParentOptions.map((cluster) => (
                              <option key={cluster.id} value={cluster.id}>{cluster.name}</option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {formData.role === 'sub_distribution_manager' ? 'Assign to Sub-Distributor' : formData.role === 'cluster' ? 'Assign to Sub Distribution' : formData.role === 'sub_distribution_employee' ? 'Assign to Sub Distributor' : 'Assign to Parent'}
                      <span className="text-red-500"> *</span>
                    </label>
                    {loadingParents ? (
                      <div className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50">
                        <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                        <span className="text-sm text-gray-500">Loading options...</span>
                      </div>
                    ) : (
                      <select
                        value={formData.parentId}
                        onChange={(e) => setFormData(prev => ({ ...prev, parentId: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        required
                      >
                        <option value="">
                          Select {formData.role === 'sub_distribution_manager' ? 'Sub-Distributor' : formData.role === 'cluster' ? 'Sub Distribution' : formData.role === 'sub_distribution_employee' ? 'Sub-Distributor' : 'Parent'}...
                        </option>
                        {parentOptions.map(p => (
                          <option key={p.id} value={p.id}>
                            {p.groupLabel ? `[${p.groupLabel}] ${p.name}` : p.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                )}
              </div>
            ) : null}

            {['sub_distributor', 'cluster', 'operator'].includes(formData.role) && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Digital Identities</label>
                {formData.digitalIdRows.map((row, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={row.digitalId}
                        onChange={(e) => {
                          const copy = [...formData.digitalIdRows];
                          copy[idx] = { ...copy[idx], digitalId: e.target.value };
                          setFormData({ ...formData, digitalIdRows: copy });
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder={idx === 0 ? 'Digital ID (primary)' : `Additional Digital ID ${idx + 1}`}
                      />
                    </div>
                    <div className="flex-1">
                      <input
                        type="text"
                        value={row.broadbandId}
                        onChange={(e) => {
                          const copy = [...formData.digitalIdRows];
                          copy[idx] = { ...copy[idx], broadbandId: e.target.value };
                          setFormData({ ...formData, digitalIdRows: copy });
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder={idx === 0 ? 'Broadband ID (primary)' : 'Broadband ID'}
                      />
                    </div>
                    {idx === 0 ? (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, digitalIdRows: [...formData.digitalIdRows, { digitalId: '', broadbandId: '' }] })}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg shrink-0 mt-1"
                        title="Add another digital identity"
                      >+</button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, digitalIdRows: formData.digitalIdRows.filter((_, i) => i !== idx) })}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg shrink-0 mt-1"
                        title="Remove"
                      >×</button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {formData.role === 'operator' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Network Name</label>
                <input
                  type="text"
                  value={formData.networkName}
                  onChange={(e) => setFormData({ ...formData, networkName: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., Fibrocom"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="+880..."
              />
            </div>
          </div>

          {/* Optional fields */}
          <p className="text-xs text-gray-400 pt-1">Optional — user can fill these in later</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Designation</label>
              <input
                type="text"
                value={formData.designation}
                onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., IT"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
              <input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter address"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Pincode</label>
              <input
                type="text"
                value={formData.pincode}
                onChange={(e) => setFormData({ ...formData, pincode: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter pincode"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowAddModal(false);
                setFormData(emptyForm);
                setConfirmPassword('');
                setShowCreatePassword(false);
                setShowCreateConfirmPassword(false);
                setParentOptions([]);
                setSubDistributorOptions([]);
                setSelectedOperatorSubDistId('');
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating...' : 'Create User'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => { setShowEditModal(false); setSelectedUser(null); }}
        title="Edit User"
        size="md"
      >
        <form onSubmit={handleEditUser} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Designation</label>
              <input
                type="text"
                value={formData.designation}
                onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            {['sub_distributor', 'cluster', 'operator'].includes(selectedUser?.role) && (
              <div className="col-span-2 space-y-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Digital Identities</label>
                {(formData.digitalIdRows || [{ digitalId: '', broadbandId: '' }]).map((row, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={row.digitalId || ''}
                        onChange={(e) => {
                          const copy = [...(formData.digitalIdRows || [{ digitalId: '', broadbandId: '' }])];
                          copy[idx] = { ...copy[idx], digitalId: e.target.value };
                          setFormData({ ...formData, digitalIdRows: copy });
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder={idx === 0 ? 'Digital ID (primary)' : `Additional Digital ID ${idx + 1}`}
                      />
                    </div>
                    <div className="flex-1">
                      <input
                        type="text"
                        value={row.broadbandId || ''}
                        onChange={(e) => {
                          const copy = [...(formData.digitalIdRows || [{ digitalId: '', broadbandId: '' }])];
                          copy[idx] = { ...copy[idx], broadbandId: e.target.value };
                          setFormData({ ...formData, digitalIdRows: copy });
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder={idx === 0 ? 'Broadband ID (primary)' : 'Broadband ID'}
                      />
                    </div>
                    {idx === 0 ? (
                      <button
                        type="button"
                        onClick={() => setFormData({
                          ...formData,
                          digitalIdRows: [...(formData.digitalIdRows || [{ digitalId: '', broadbandId: '' }]), { digitalId: '', broadbandId: '' }]
                        })}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg shrink-0 mt-1"
                      >+</button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setFormData({
                          ...formData,
                          digitalIdRows: (formData.digitalIdRows || []).filter((_, i) => i !== idx)
                        })}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg shrink-0 mt-1"
                      >×</button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => { setShowEditModal(false); setSelectedUser(null); }}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setSelectedUser(null); }}
        title="Delete User"
        size="md"
      >
        <div className="text-center py-4">
          {selectedUser && (selectedUser.role === 'sub_distributor' || selectedUser.role === 'cluster') ? (
            <>
              <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <p className="text-gray-700 mb-2">
                This will create a <strong>Reassignment Request</strong> for{' '}
                <strong>{selectedUser?.name}</strong>.
              </p>
              <p className="text-sm text-gray-500 mb-4">
                Users under this {selectedUser.role === 'sub_distributor' ? 'sub-distributor' : 'cluster'} will need to be reassigned to a new parent before deletion. You can manage this in the Reassignment Requests section.
              </p>
              <div className="flex justify-center gap-3">
                <Button variant="outline" onClick={() => setShowDeleteModal(false)}>
                  Cancel
                </Button>
                <Button variant="danger" onClick={handleDeleteUser}>
                  Request Reassignment
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <p className="text-gray-700 mb-4">
                Are you sure you want to delete <strong>{selectedUser?.name}</strong>?
                This action cannot be undone.
              </p>
              <div className="flex justify-center gap-3">
                <Button variant="outline" onClick={() => setShowDeleteModal(false)}>
                  Cancel
                </Button>
                <Button variant="danger" onClick={handleDeleteUser}>
                  Delete User
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Reassign Modal */}
      <Modal
        isOpen={showReassignModal}
        onClose={() => { setShowReassignModal(false); setReassignTarget(null); setReassignNewParentId(''); }}
        title={`Reassign ${reassignTarget?.role === 'cluster' ? 'Cluster' : 'Operator'}`}
        size="md"
      >
        {reassignTarget && (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-sm text-amber-800">
                Reassigning <strong>{reassignTarget.name}</strong> ({reassignTarget.role === 'cluster' ? 'Cluster' : 'Operator'})
                {reassignTarget.role === 'cluster'
                  ? ' will move all operators under this cluster along with it.'
                  : ' to a different sub distributor or cluster.'}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {reassignTarget.role === 'cluster' ? 'New Sub-Distributor' : 'New Sub-Distributor or Cluster'}
                <span className="text-red-500"> *</span>
              </label>
              <select
                value={reassignNewParentId}
                onChange={(e) => setReassignNewParentId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">
                  Select {reassignTarget.role === 'cluster' ? 'Sub-Distributor' : 'Sub-Distributor / Cluster'}...
                </option>
                {reassignParentOptions
                  .filter(p => String(p.id) !== String(reassignTarget.parent_id))
                  .map(p => (
                    <option key={p.id} value={p.id}>
                      {p.groupLabel ? `[${p.groupLabel}] ${p.name}` : p.name}
                    </option>
                  ))}
              </select>
              {reassignParentOptions.length === 0 && (
                <p className="text-xs text-gray-400 mt-1">Loading options...</p>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => { setShowReassignModal(false); setReassignTarget(null); setReassignNewParentId(''); }}
              >
                Cancel
              </Button>
              <Button onClick={handleReassignUser} disabled={reassigning || !reassignNewParentId}>
                {reassigning ? 'Reassigning...' : 'Reassign'}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Admin User Detail Modal */}
      {detailUser && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-800">User Details</h2>
                <p className="text-sm text-gray-500">{detailUser.email}</p>
              </div>
              <button onClick={() => setDetailUser(null)} className="p-2 hover:bg-gray-100 rounded-lg">✕</button>
            </div>
            <div className="p-6 space-y-4">
              {/* Status toggle */}
              {isAdmin && (
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-800">Account Status</p>
                    <p className={`text-sm ${detailForm.status === 'active' ? 'text-green-600' : 'text-red-600'}`}>
                      {detailForm.status === 'active' ? 'Active' : 'Inactive'}
                    </p>
                  </div>
                  <button
                    onClick={async () => {
                      const newStatus = detailForm.status === 'active' ? 'inactive' : 'active';
                      try {
                        await usersAPI.updateUserStatus(detailUser.id, newStatus);
                        setDetailForm(p => ({ ...p, status: newStatus }));
                        showToast(`User ${newStatus === 'active' ? 'activated' : 'deactivated'}`, 'success');
                      } catch (err) {
                        showToast(err.message || 'Failed to update status', 'error');
                      }
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      detailForm.status === 'active'
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                    }`}
                  >
                    {detailForm.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              )}

              {/* Basic info fields */}
              {[
                { key: 'name', label: 'Full Name' },
                { key: 'email', label: 'Email' },
                { key: 'phone', label: 'Phone' },
                { key: 'designation', label: 'Designation' },
                { key: 'address', label: 'Address' },
                { key: 'pincode', label: 'Pincode' },
                ...(detailUser.role === 'operator' ? [{ key: 'network_name', label: 'Network Name' }] : []),
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                  <input
                    value={detailForm[key] || ''}
                    onChange={e => setDetailForm(p => ({ ...p, [key]: e.target.value }))}
                    disabled={key === 'email' && !isAdmin}
                    className={`w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 ${key === 'email' && !isAdmin ? 'bg-gray-50 text-gray-500 cursor-not-allowed' : ''}`}
                  />
                </div>
              ))}
              {['sub_distributor', 'cluster', 'operator'].includes(detailUser.role) && (
                <div className="p-3 bg-gray-50 rounded-lg">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Digital IDs</label>
                  <div className="space-y-2">
                    {detailDigitalIds.map((entry, idx) => (
                      <div key={entry.id || entry._localId || idx} className="flex items-center gap-2">
                        <input
                          value={entry.digital_id || ''}
                          onChange={e => {
                            const copy = [...detailDigitalIds];
                            copy[idx] = { ...copy[idx], digital_id: e.target.value };
                            setDetailDigitalIds(copy);
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                          placeholder="Digital ID"
                        />
                        <input
                          value={entry.broadband_id || ''}
                          onChange={e => {
                            const copy = [...detailDigitalIds];
                            copy[idx] = { ...copy[idx], broadband_id: e.target.value };
                            setDetailDigitalIds(copy);
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                          placeholder="Broadband ID"
                        />
                        <button
                          type="button"
                          onClick={() => setDetailDigitalIds(prev => prev.filter((_, i) => i !== idx))}
                          className="p-2 text-red-500 hover:bg-red-50 rounded-lg shrink-0"
                          title="Remove"
                        >×</button>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setDetailDigitalIds(prev => [...prev, { _localId: Date.now() + Math.random(), digital_id: '', broadband_id: '' }])}
                    className="mt-2 px-3 py-1.5 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50"
                  >
                    + Add Digital ID
                  </button>
                </div>
              )}
              <div className="text-sm text-gray-500">
                <span className="font-medium">Role:</span> {detailUser.role} &nbsp;|&nbsp;
                <span className="font-medium">Created:</span> {new Date(detailUser.created_at).toLocaleDateString()}
              </div>

              <Button
                disabled={savingDetail}
                onClick={async () => {
                  setSavingDetail(true);
                  try {
                    const updatePayload = {
                      name: detailForm.name,
                      phone: detailForm.phone,
                      designation: detailForm.designation,
                      address: detailForm.address,
                      pincode: detailForm.pincode,
                      network_name: detailUser.role === 'operator' ? detailForm.network_name || null : undefined,
                    };
                    await usersAPI.updateUser(detailUser.id, updatePayload);
                    if (isAdmin && detailForm.email && detailForm.email !== detailUser.email) {
                      await adminUpdateCredentials(detailUser.id, { email: detailForm.email });
                    }
                    // Save digital IDs for sub_distributor, cluster, operator
                    if (['sub_distributor', 'cluster', 'operator'].includes(detailUser.role)) {
                      const origIds = origDigitalIdIds.current || [];
                      const currentIds = detailDigitalIds.map(e => String(e.id)).filter(Boolean);
                      const removedIds = origIds.filter(id => !currentIds.includes(String(id)));
                      for (const id of removedIds) {
                        await digitalIdsAPI.delete(id);
                      }
                      for (const entry of detailDigitalIds) {
                        const dig = (entry.digital_id || '').trim();
                        const bb = (entry.broadband_id || '').trim();
                        if (!dig && !bb) {
                          if (entry.id) {
                            await digitalIdsAPI.delete(entry.id);
                          }
                          continue;
                        }
                        if (entry.id) {
                          await digitalIdsAPI.update(entry.id, {
                            user_id: detailUser.id,
                            digital_id: dig || null,
                            broadband_id: bb || null,
                          });
                        } else {
                          await digitalIdsAPI.create({
                            user_id: detailUser.id,
                            digital_id: dig || null,
                            broadband_id: bb || null,
                          });
                        }
                      }
                    }
                    showToast('User details saved', 'success');
                  } catch (err) {
                    showToast(err.message || 'Failed to save', 'error');
                  } finally {
                    setSavingDetail(false);
                  }
                }}
              >
                {savingDetail ? 'Saving...' : 'Save Details'}
              </Button>

              {/* Password reset */}
              {isAdmin && (
              <div className="border-t pt-4 mt-4">
                <p className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                  <Lock className="w-4 h-4" /> Reset Password
                </p>
                <div className="space-y-3 mb-3">
                  <div className="relative">
                    <input
                      type={showResetPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      placeholder="Enter new password (min 6 chars)"
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowResetPassword(prev => !prev)}
                      className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-700"
                    >
                      {showResetPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={showConfirmResetPassword ? 'text' : 'password'}
                      value={confirmResetPassword}
                      onChange={e => setConfirmResetPassword(e.target.value)}
                      placeholder="Confirm new password"
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmResetPassword(prev => !prev)}
                      className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-700"
                    >
                      {showConfirmResetPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {confirmResetPassword && newPassword !== confirmResetPassword && (
                    <p className="text-xs text-red-600">Passwords do not match</p>
                  )}
                </div>
                <Button
                  variant="outline"
                  onClick={async () => {
                    if (!newPassword || newPassword.length < 6) {
                      showToast('Password must be at least 6 characters', 'error');
                      return;
                    }
                    if (newPassword !== confirmResetPassword) {
                      showToast('Passwords do not match', 'error');
                      return;
                    }
                    try {
                      await adminUpdateCredentials(detailUser.id, { password: newPassword });
                      showToast('Password reset successfully', 'success');
                      setNewPassword('');
                      setConfirmResetPassword('');
                      setShowResetPassword(false);
                      setShowConfirmResetPassword(false);
                    } catch (err) {
                      showToast(err.message || 'Failed to reset password', 'error');
                    }
                  }}
                >
                  Reset Password
                </Button>
              </div>
              )}

              {/* Assigned children: clusters under sub_distributor, operators under cluster */}
              {['sub_distributor', 'cluster'].includes(detailUser.role) && (
                <div className="border-t pt-4 mt-2">
                  <div className="flex items-center justify-between mb-3">
                    <p className="font-medium text-gray-800 flex items-center gap-2">
                      <UsersIcon className="w-4 h-4" />
                      {detailUser.role === 'sub_distributor' ? 'Assigned Clusters' : 'Assigned Operators'}
                    </p>
                    {loadingChildren && <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />}
                  </div>
                  {!loadingChildren && detailChildren.length === 0 ? (
                    <p className="text-sm text-gray-500 italic">
                      No {detailUser.role === 'sub_distributor' ? 'clusters' : 'operators'} assigned yet.
                    </p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {detailChildren.map(child => (
                        <div key={child.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                          <div>
                            <p className="text-sm font-medium text-gray-800">{child.name}</p>
                            <p className="text-xs text-gray-500">{child.email}</p>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getRoleColor(child.role)}`}>
                            {ROLE_LABELS[child.role] || child.role}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Users;