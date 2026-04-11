import { useState, useEffect, useMemo } from 'react';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { usersAPI, adminUpdateCredentials } from '../services/api';
import {
  UserPlus, Edit, Trash2, Eye, Shield, Mail, Phone,
  Building, MapPin, Calendar, Users as UsersIcon, Loader2, Lock,
  Network, ChevronDown, ChevronRight, Filter, X, EyeOff
} from 'lucide-react';

// Roles each creator can assign
const ALLOWED_ROLES_BY_CREATOR = {
  super_admin: ['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator'],
  manager: ['pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator'],
  sub_distribution_manager: ['cluster', 'operator'],
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
};

const getRoleColor = (role) => {
  switch (role) {
    case 'super_admin': return 'bg-red-100 text-red-800';
    case 'md_director': return 'bg-orange-100 text-orange-800';
    case 'manager': return 'bg-purple-100 text-purple-800';
    case 'pdic_staff': return 'bg-blue-100 text-blue-800';
    case 'sub_distribution_manager': return 'bg-cyan-100 text-cyan-800';
    case 'sub_distributor': return 'bg-indigo-100 text-indigo-800';
    case 'cluster': return 'bg-teal-100 text-teal-800';
    case 'operator': return 'bg-green-100 text-green-800';
    default: return 'bg-gray-100 text-gray-800';
  }
};

const emptyForm = {
  name: '',
  email: '',
  password: '',
  role: 'operator',
  digitalId: '',
  broadbandId: '',
  phone: '',
  department: '',
  location: '',
  parentId: '',
};

const USERS_FETCH_PAGE_SIZE = 1000000;

const Users = () => {
  const { user: currentUser, hasRole } = useAuth();
  const { showToast } = useNotifications();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [selectedUser, setSelectedUser] = useState(null);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [detailUser, setDetailUser] = useState(null);
  const [detailForm, setDetailForm] = useState({});
  const [newPassword, setNewPassword] = useState('');
  const [savingDetail, setSavingDetail] = useState(false);

  const [formData, setFormData] = useState(emptyForm);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [showCreateConfirmPassword, setShowCreateConfirmPassword] = useState(false);

  // For admin/manager: parent options when creating cluster or operator
  const [parentOptions, setParentOptions] = useState([]);
  const [subDistributorOptions, setSubDistributorOptions] = useState([]);
  const [loadingParents, setLoadingParents] = useState(false);
  const [selectedOperatorSubDistId, setSelectedOperatorSubDistId] = useState('');

  // For admin detail modal: child users (clusters under sub_distributor, operators under cluster)
  const [detailChildren, setDetailChildren] = useState([]);
  const [loadingChildren, setLoadingChildren] = useState(false);

  // For sub_distributor hierarchical view: operators fetched separately
  const [subDistOperators, setSubDistOperators] = useState([]);
  const [loadingOps, setLoadingOps] = useState(false);
  // Which cluster cards are collapsed (by cluster id)
  const [collapsedClusters, setCollapsedClusters] = useState({});

  // Which roles the current user can create
  const creatableRoles = ALLOWED_ROLES_BY_CREATOR[currentUser?.role] || [];
  const canCreateUsers = creatableRoles.length > 0;

  // Cascading filter state (admin/manager table view only)
  const [filters, setFilters] = useState({ role: '', subDistManagerId: '', subDistId: '', clusterId: '' });

  const fetchUsers = async () => {
    try {
      setLoading(true);
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

  useEffect(() => {
    fetchUsers();
    fetchSubDistOperators();
  }, []);

  // When add modal opens, default role to first available
  const openAddModal = () => {
    const defaultRole = creatableRoles[0] || 'operator';
    setFormData({ ...emptyForm, role: defaultRole, parentId: '' });
    setParentOptions([]);
    setSubDistributorOptions([]);
    setSelectedOperatorSubDistId('');
    setConfirmPassword('');
    setShowCreatePassword(false);
    setShowCreateConfirmPassword(false);
    // For sub_distributor creating cluster, no parent selector needed.
    // For admin/manager, kick off load if default role requires it.
    if (['super_admin', 'manager'].includes(currentUser?.role)) {
      if (defaultRole === 'sub_distribution_manager' || defaultRole === 'cluster' || defaultRole === 'operator') {
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
    setFormData(prev => ({ ...prev, role: newRole, parentId: '' }));
    setSelectedOperatorSubDistId('');
    if (['super_admin', 'manager'].includes(currentUser?.role)) {
      if (newRole === 'sub_distribution_manager' || newRole === 'cluster' || newRole === 'operator') {
        loadParentOptions(newRole);
      } else {
        setParentOptions([]);
        setSubDistributorOptions([]);
      }
    } else if (currentUser?.role === 'sub_distributor') {
      if (newRole === 'operator') {
        // Clusters are already in `users` state
        setParentOptions(users.map(c => ({ ...c, groupLabel: 'Cluster' })));
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
            onClick={() => { setSelectedUser(row); setShowViewModal(true); }}
            className="p-1 hover:bg-gray-100 rounded"
            title="View"
          >
            <Eye className="w-4 h-4 text-gray-500" />
          </button>
          {['super_admin', 'sub_distribution_manager'].includes(currentUser?.role) && (
            <button
              onClick={() => { setDetailUser(row); setDetailForm({ ...row }); setNewPassword(''); }}
              className="p-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200"
              title="Edit Details"
            >
              <Edit className="w-4 h-4" />
            </button>
          )}
          {['super_admin', 'sub_distribution_manager'].includes(currentUser?.role) && (
            <>
              {String(row.id) !== String(currentUser.id) && (
                <button
                  onClick={() => { setSelectedUser(row); setShowDeleteModal(true); }}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4 text-red-500" />
                </button>
              )}
            </>
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
      if (formData.role === 'sub_distributor') {
        payload.digital_id = formData.digitalId || null;
        payload.broadband_id = formData.broadbandId || null;
      }
      if (formData.phone) payload.phone = formData.phone;
      if (formData.department) payload.department = formData.department;
      if (formData.location) payload.location = formData.location;
      if (formData.parentId) payload.parent_id = formData.parentId;

      await usersAPI.createUser(payload);
      showToast('User created successfully', 'success');
      setShowAddModal(false);
      setFormData(emptyForm);
      setConfirmPassword('');
      setShowCreatePassword(false);
      setShowCreateConfirmPassword(false);
      setParentOptions([]);
      fetchUsers();
      fetchSubDistOperators();
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
      if (formData.name) payload.name = formData.name;
      if (formData.phone) payload.phone = formData.phone;
      if (formData.department) payload.department = formData.department;
      if (formData.location) payload.location = formData.location;

      await usersAPI.updateUser(selectedUser._id || selectedUser.id, payload);
      showToast('User updated successfully', 'success');
      setShowEditModal(false);
      fetchUsers();
    } catch (error) {
      showToast(error.message || 'Failed to update user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteUser = async () => {
    try {
      await usersAPI.deleteUser(selectedUser._id || selectedUser.id);
      showToast('User deleted successfully', 'success');
      setShowDeleteModal(false);
      setSelectedUser(null);
      fetchUsers();
      fetchSubDistOperators();
    } catch (error) {
      showToast(error.message || 'Failed to delete user', 'error');
    }
  };

  // Role flags — declared here so filteredUsers memo and stats can both use them
  const isSubDist = currentUser?.role === 'sub_distributor';
  const isCluster = currentUser?.role === 'cluster';
  const isAdmin = currentUser?.role === 'super_admin';
  const isMdDirector = currentUser?.role === 'md_director';
  const isManager = currentUser?.role === 'manager';
  const isAdminOrManager = ['super_admin', 'manager'].includes(currentUser?.role);

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
    if (filters.clusterId) {
      result = result.filter(u =>
        String(u.id) === filters.clusterId ||
        String(u.parent_id) === filters.clusterId
      );
    } else if (filters.subDistId) {
      const subDistManagerIds = visibleUsers
        .filter(u => u.role === 'sub_distribution_manager' && String(u.parent_id) === filters.subDistId)
        .map(u => String(u.id));
      const clusterIds = visibleUsers
        .filter(u => u.role === 'cluster' && subDistManagerIds.includes(String(u.parent_id)))
        .map(u => String(u.id));

      result = result.filter(u =>
        String(u.id) === filters.subDistId ||
        String(u.parent_id) === filters.subDistId ||
        subDistManagerIds.includes(String(u.id)) ||
        clusterIds.includes(String(u.parent_id))
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

  const stats = isSubDist
    ? [
      { label: 'Total Clusters', value: users.length, icon: Network, color: 'teal' },
      { label: 'Active Clusters', value: users.filter(u => u.status === 'active').length, icon: UsersIcon, color: 'green' },
      { label: 'Total Operators', value: subDistOperators.length, icon: UsersIcon, color: 'blue' },
      { label: 'Active Operators', value: subDistOperators.filter(u => u.status === 'active').length, icon: UsersIcon, color: 'indigo' },
    ]
    : isCluster
      ? [
        { label: 'Total Operators', value: users.length, icon: UsersIcon, color: 'blue' },
        { label: 'Active Operators', value: users.filter(u => u.status === 'active').length, icon: UsersIcon, color: 'green' },
      ]
      : isAdmin
        ? [
          { label: 'Total Users', value: users.length, icon: UsersIcon, color: 'blue' },
          { label: 'Super Admins', value: users.filter(u => u.role === 'super_admin').length, icon: Shield, color: 'red' },
          { label: 'MD/Director', value: users.filter(u => u.role === 'md_director').length, icon: Shield, color: 'orange' },
          { label: 'Managers', value: users.filter(u => u.role === 'manager').length, icon: Shield, color: 'purple' },
          { label: 'PDIC Staff', value: users.filter(u => u.role === 'pdic_staff').length, icon: UsersIcon, color: 'blue' },
          { label: 'Sub Dist. Manager', value: users.filter(u => u.role === 'sub_distribution_manager').length, icon: Building, color: 'cyan' },
          { label: 'Sub Distributors', value: users.filter(u => u.role === 'sub_distributor').length, icon: Building, color: 'indigo' },
          { label: 'Clusters', value: users.filter(u => u.role === 'cluster').length, icon: Network, color: 'teal' },
          { label: 'Operators', value: users.filter(u => u.role === 'operator').length, icon: UsersIcon, color: 'green' },
        ]
        : isManager
          ? [
            { label: 'Total Users', value: visibleUsers.length, icon: UsersIcon, color: 'blue' },
            { label: 'PDIC Staff', value: visibleUsers.filter(u => u.role === 'pdic_staff').length, icon: UsersIcon, color: 'blue' },
            { label: 'Sub Dist. Manager', value: visibleUsers.filter(u => u.role === 'sub_distribution_manager').length, icon: Building, color: 'cyan' },
            { label: 'Sub Distributors', value: visibleUsers.filter(u => u.role === 'sub_distributor').length, icon: Building, color: 'indigo' },
            { label: 'Clusters', value: visibleUsers.filter(u => u.role === 'cluster').length, icon: Network, color: 'teal' },
            { label: 'Operators', value: visibleUsers.filter(u => u.role === 'operator').length, icon: UsersIcon, color: 'green' },
          ]
          : [
            { label: 'Total Users', value: users.length, icon: UsersIcon, color: 'blue' },
            { label: 'Operators', value: users.filter(u => u.role === 'operator').length, icon: UsersIcon, color: 'green' },
          ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">
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

      {/* Stats */}
      <div className={`grid ${isAdmin ? 'grid-cols-2 sm:grid-cols-4 lg:grid-cols-7' :
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

      {/* Main content: hierarchical view for sub_distributor and sub_distribution_manager, table for everyone else */}
      {(isSubDist || isSdm) ? (
        <div className="space-y-4">
          {(loading || (isSubDist && loadingOps) || (isSdm && loadingSdmOps)) ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <span className="ml-3 text-gray-500">Loading...</span>
            </div>
          ) : users.length === 0 ? (
            <Card>
              <div className="text-center py-10">
                <Network className="w-14 h-14 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">
                  {isSdm ? 'No clusters found under your assigned sub-distribution.' : 'No clusters found under your sub-distribution.'}
                </p>
              </div>
            </Card>
          ) : (
            <>
              {/* SDM only: show assigned sub-distributor details as root anchor */}
              {isSdm && sdmParentSubDist && (
                <Card className="border-indigo-200 bg-gradient-to-r from-indigo-50 to-blue-50">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                      <Building className="w-6 h-6 text-indigo-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-base font-bold text-indigo-900">{sdmParentSubDist.name}</p>
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">Sub Distributor</span>
                        <StatusBadge status={sdmParentSubDist.status} size="sm" />
                        <span className="ml-auto text-xs text-indigo-500 font-medium">Your Assigned Sub-Distribution</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
                        {sdmParentSubDist.email && (<span className="text-xs text-gray-500">{sdmParentSubDist.email}</span>)}
                        {sdmParentSubDist.phone && (<span className="text-xs text-gray-500">{sdmParentSubDist.phone}</span>)}
                        {sdmParentSubDist.location && (<span className="text-xs text-gray-500">{sdmParentSubDist.location}</span>)}
                        {sdmParentSubDist.digital_id && (<span className="text-xs text-gray-500">Digital ID: {sdmParentSubDist.digital_id}</span>)}
                        {sdmParentSubDist.broadband_id && (<span className="text-xs text-gray-500">Broadband ID: {sdmParentSubDist.broadband_id}</span>)}
                      </div>
                    </div>
                    <button
                      onClick={() => { setSelectedUser(sdmParentSubDist); setShowViewModal(true); }}
                      className="p-1.5 hover:bg-indigo-100 rounded ml-2 flex-shrink-0"
                      title="View sub-distributor details"
                    >
                      <Eye className="w-4 h-4 text-indigo-500" />
                    </button>
                  </div>
                  <div className="mt-3 ml-6 border-l-2 border-indigo-200 pl-4 pt-1">
                    <p className="text-xs text-indigo-400 font-medium">{users.length} cluster{users.length !== 1 ? 's' : ''} under this sub-distribution</p>
                  </div>
                </Card>
              )}

              {users.map(cluster => {
                const clusterOps = isSdm
                  ? (sdmClusterOperatorsMap[String(cluster.id)] || [])
                  : (clusterOperatorsMap[String(cluster.id)] || []);
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
                {(filters.role || filters.subDistManagerId || filters.subDistId || filters.clusterId) && (
                  <button
                    onClick={() => setFilters({ role: '', subDistManagerId: '', subDistId: '', clusterId: '' })}
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
                    onChange={e => setFilters({ role: e.target.value, subDistManagerId: '', subDistId: '', clusterId: '' })}
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

                {/* Active filter chips + result count */}
                {(filters.role || filters.subDistManagerId || filters.subDistId || filters.clusterId) && (
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
                    <span className="text-xs text-gray-400">
                      {filteredUsers.length} result{filteredUsers.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          <Card>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                <span className="ml-3 text-gray-500">Loading users...</span>
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={filteredUsers}
                searchable
                searchPlaceholder="Search users..."
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
        size="md"
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
                  <p className="text-sm text-gray-500">Department</p>
                  <p className="font-medium text-gray-800">{selectedUser.department || 'Not assigned'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <MapPin className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Location</p>
                  <p className="font-medium text-gray-800">{selectedUser.location || 'Not assigned'}</p>
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
                <Shield className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <StatusBadge status={selectedUser.status} />
                </div>
              </div>

              {selectedUser.role === 'sub_distributor' && (
                <>
                  <div className="flex items-center gap-3">
                    <Building className="w-5 h-5 text-gray-400" />
                    <div>
                      <p className="text-sm text-gray-500">Digital ID</p>
                      <p className="font-medium text-gray-800">{selectedUser.digital_id || 'Not provided'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Building className="w-5 h-5 text-gray-400" />
                    <div>
                      <p className="text-sm text-gray-500">Broadband ID</p>
                      <p className="font-medium text-gray-800">{selectedUser.broadband_id || 'Not provided'}</p>
                    </div>
                  </div>
                </>
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
                OR when sub_distributor creates an operator (must select a cluster) */}
            {((isAdminOrManager) && (formData.role === 'sub_distribution_manager' || formData.role === 'cluster' || formData.role === 'operator')) ||
              (currentUser?.role === 'sub_distributor' && formData.role === 'operator') ? (
              <div>
                {isAdminOrManager && formData.role === 'operator' ? (
                  <div className="space-y-3">
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
                  </div>
                ) : (
                  <>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {formData.role === 'sub_distribution_manager' ? 'Assign to Sub-Distributor' : formData.role === 'cluster' ? 'Assign to Sub Distribution' : 'Assign to Cluster'}
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
                          Select {formData.role === 'sub_distribution_manager' ? 'Sub-Distributor' : formData.role === 'cluster' ? 'Sub Distribution' : 'Cluster'}...
                        </option>
                        {(currentUser?.role === 'sub_distributor' ? users : parentOptions).map(p => (
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

            {formData.role === 'sub_distributor' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Digital ID (Optional)</label>
                  <input
                    type="text"
                    value={formData.digitalId}
                    onChange={(e) => setFormData({ ...formData, digitalId: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Enter digital ID"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Broadband ID (Optional)</label>
                  <input
                    type="text"
                    value={formData.broadbandId}
                    onChange={(e) => setFormData({ ...formData, broadbandId: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Enter broadband ID"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Optional fields */}
          <p className="text-xs text-gray-400 pt-1">Optional — user can fill these in later</p>
          <div className="grid grid-cols-2 gap-4">
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
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., IT"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., Dhaka"
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
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
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
        size="sm"
      >
        <div className="text-center py-4">
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
        </div>
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
                      fetchUsers();
                    } catch (err) {
                      showToast(err.message || 'Failed to update status', 'error');
                    }
                  }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${detailForm.status === 'active'
                      ? 'bg-red-100 text-red-700 hover:bg-red-200'
                      : 'bg-green-100 text-green-700 hover:bg-green-200'
                    }`}
                >
                  {detailForm.status === 'active' ? 'Deactivate' : 'Activate'}
                </button>
              </div>

              {/* Basic info fields */}
              {[
                { key: 'name', label: 'Full Name' },
                { key: 'email', label: 'Email' },
                { key: 'phone', label: 'Phone' },
                { key: 'department', label: 'Department' },
                { key: 'location', label: 'Location' },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                  <input
                    value={detailForm[key] || ''}
                    onChange={e => setDetailForm(p => ({ ...p, [key]: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
              <div className="text-sm text-gray-500">
                <span className="font-medium">Role:</span> {detailUser.role} &nbsp;|&nbsp;
                <span className="font-medium">Created:</span> {new Date(detailUser.created_at).toLocaleDateString()}
              </div>

              <Button
                disabled={savingDetail}
                onClick={async () => {
                  setSavingDetail(true);
                  try {
                    // Update basic fields
                    await usersAPI.updateUser(detailUser.id, {
                      name: detailForm.name,
                      phone: detailForm.phone,
                      department: detailForm.department,
                      location: detailForm.location,
                    });
                    // Update email separately if changed
                    if (detailForm.email && detailForm.email !== detailUser.email) {
                      await adminUpdateCredentials(detailUser.id, { email: detailForm.email });
                    }
                    showToast('User details saved', 'success');
                    fetchUsers();
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
              <div className="border-t pt-4 mt-4">
                <p className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                  <Lock className="w-4 h-4" /> Reset Password
                </p>
                <input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 6 chars)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 mb-3"
                />
                <Button
                  variant="outline"
                  onClick={async () => {
                    if (!newPassword || newPassword.length < 6) {
                      showToast('Password must be at least 6 characters', 'error');
                      return;
                    }
                    try {
                      await adminUpdateCredentials(detailUser.id, { password: newPassword });
                      showToast('Password reset successfully', 'success');
                      setNewPassword('');
                    } catch (err) {
                      showToast(err.message || 'Failed to reset password', 'error');
                    }
                  }}
                >
                  Reset Password
                </Button>
              </div>

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

