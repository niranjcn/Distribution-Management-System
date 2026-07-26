import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { usersAPI } from '../services/api';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import StatusBadge from '../components/ui/StatusBadge';
import {
  Users,
  Network,
  User,
  ChevronDown,
  ChevronRight,
  UserPlus,
  Loader2,
  Lock,
  Search,
  X,
  Building2,
  Shield,
} from 'lucide-react';

// ─── colour palette per role ─────────────────────────────────────────────────
const ROLE_STYLES = {
  super_admin: { ring: 'ring-red-400', bg: 'bg-red-50', text: 'text-red-700', badge: 'bg-red-100 text-red-800' },
  md_director: { ring: 'ring-orange-400', bg: 'bg-orange-50', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-800' },
  manager: { ring: 'ring-purple-400', bg: 'bg-purple-50', text: 'text-purple-700', badge: 'bg-purple-100 text-purple-800' },
  pdic_staff: { ring: 'ring-sky-400', bg: 'bg-sky-50', text: 'text-sky-700', badge: 'bg-sky-100 text-sky-800' },
  sub_distribution_manager: { ring: 'ring-cyan-400', bg: 'bg-cyan-50', text: 'text-cyan-700', badge: 'bg-cyan-100 text-cyan-800' },
  sub_distributor: { ring: 'ring-indigo-400', bg: 'bg-indigo-50', text: 'text-indigo-700', badge: 'bg-indigo-100 text-indigo-800' },
  cluster: { ring: 'ring-teal-400', bg: 'bg-teal-50', text: 'text-teal-700', badge: 'bg-teal-100 text-teal-800' },
  operator: { ring: 'ring-green-400', bg: 'bg-green-50', text: 'text-green-700', badge: 'bg-green-100 text-green-800' },
};

const ROLE_LABELS = {
  super_admin: 'Super Admin', md_director: 'MD/Director', manager: 'Manager', pdic_staff: 'PDIC Staff',
  sub_distribution_manager: 'Sub Distribution Manager',
  sub_distributor: 'Sub Distributor', cluster: 'Cluster', operator: 'Operator',
};

const ROLE_ICON = {
  super_admin: Shield, md_director: Shield, manager: Shield, pdic_staff: User, sub_distribution_manager: Building2,
  sub_distributor: Building2, cluster: Network, operator: User,
};

const ALLOWED_ROLES_BY_CREATOR = {
  super_admin: ['super_admin', 'md_director', 'manager', 'pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator'],
  manager: ['pdic_staff', 'sub_distribution_manager', 'sub_distributor', 'cluster', 'operator'],
  sub_distributor: [],
  cluster: ['operator'],
};

const emptyForm = { name: '', email: '', password: '', role: 'cluster', phone: '', department: '', location: '', parentId: '', digitalId: '', broadbandId: '', clusterId: '', operatorId: '' };

// ─── avatar initials helper ────────────────────────────────────────────────────
const initials = (name) =>
  (name || '').split(' ').filter(Boolean).map(n => n[0].toUpperCase()).join('').slice(0, 2) || '?';

// ─── Individual node card ──────────────────────────────────────────────────────
const UserNode = ({ user, depth = 0, children, defaultOpen = false, onSelect }) => {
  const [open, setOpen] = useState(defaultOpen || depth < 2);
  const style = ROLE_STYLES[user.role] || ROLE_STYLES.operator;
  const Icon = ROLE_ICON[user.role] || User;
  const hasChildren = children && children.length > 0;

  return (
    <div className={`relative ${depth > 0 ? 'ml-6 sm:ml-10 mt-2' : 'mt-3'}`}>
      {/* vertical connector line */}
      {depth > 0 && (
        <span className="absolute -left-5 top-5 w-4 h-px bg-gray-300" />
      )}

      <div
        className={`flex items-center gap-3 p-3 rounded-xl border-2 ${style.ring} ${style.bg} cursor-pointer select-none shadow-sm hover:shadow-md transition-shadow`}
        onClick={() => { onSelect && onSelect(user); }}
      >
        {/* expand toggle */}
        {hasChildren ? (
          <button
            className="shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-white/60 hover:bg-white text-gray-500"
            onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
          >
            {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
        ) : (
          <span className="shrink-0 w-6 h-6" />
        )}

        {/* avatar */}
        <div className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center ring-2 ${style.ring} bg-white`}>
          <span className={`text-xs font-bold ${style.text}`}>{initials(user.name)}</span>
        </div>

        {/* info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-gray-800 truncate">{user.name}</p>
            <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${style.badge}`}>
              {ROLE_LABELS[user.role] || user.role}
            </span>
            <StatusBadge status={user.status} size="sm" />
          </div>
          <p className="text-xs text-gray-500 truncate">{user.email}</p>
          {user.phone && <p className="text-xs text-gray-400">{user.phone}</p>}
        </div>

        {hasChildren && (
          <span className="shrink-0 text-xs text-gray-400 bg-white/70 px-2 py-0.5 rounded-full">
            {children.length}
          </span>
        )}
      </div>

      {/* children */}
      {open && hasChildren && (
        <div className="relative pl-5 border-l-2 border-gray-200 ml-3 mt-1 space-y-1">
          {children}
        </div>
      )}
    </div>
  );
};

// ─── Main page ─────────────────────────────────────────────────────────────────
const HIERARCHY_PAGE_SIZE = 1000000;

const UserHierarchy = () => {
  const { user: currentUser } = useAuth();
  const { showToast } = useNotifications();
  const navigate = useNavigate();

  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);

  // ─ Add user modal ─
  const [showAdd, setShowAdd] = useState(false);
  const [formData, setFormData] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [parentOptions, setParentOptions] = useState([]);
  const [loadingParents, setLoadingParents] = useState(false);

  const creatableRoles = ALLOWED_ROLES_BY_CREATOR[currentUser?.role] || [];
  const isManager = currentUser?.role === 'manager';
  const isMdDirector = currentUser?.role === 'md_director';

  const visibleUsers = useMemo(() => {
    if (isMdDirector) return allUsers.filter((u) => u.role !== 'super_admin');
    if (!isManager) return allUsers;
    return allUsers.filter((u) => u.role !== 'super_admin');
  }, [allUsers, isManager, isMdDirector]);

  const visibleRoleEntries = useMemo(() => {
    if (isMdDirector) return Object.entries(ROLE_LABELS).filter(([role]) => role !== 'super_admin');
    if (!isManager) return Object.entries(ROLE_LABELS);
    return Object.entries(ROLE_LABELS).filter(([role]) => role !== 'super_admin');
  }, [isManager, isMdDirector]);

  // ─── fetch all users visible to the current user ───────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      if (currentUser?.role === 'sub_distributor') {
        // clusters directly under me
        const [clusterRes, opRes] = await Promise.all([
          usersAPI.getUsers({ page_size: HIERARCHY_PAGE_SIZE }),
          usersAPI.getUsers({ role: 'operator', page_size: HIERARCHY_PAGE_SIZE }),
        ]);
        const clusters = (clusterRes.data || []);
        const operators = (opRes.data || []);
        setAllUsers([...clusters, ...operators]);
      } else {
        const res = await usersAPI.getUsers({ page_size: HIERARCHY_PAGE_SIZE });
        setAllUsers(res.data || []);
      }
    } catch (err) {
      console.error(err);
      showToast('Failed to load users', 'error');
    } finally {
      setLoading(false);
    }
  }, [currentUser?.role]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ─── build tree from flat list ─────────────────────────────────────────────
  const buildTree = useCallback(() => {
    const query = search.toLowerCase();
    const list = query
      ? visibleUsers.filter(u =>
        u.name?.toLowerCase().includes(query) ||
        u.email?.toLowerCase().includes(query) ||
        (ROLE_LABELS[u.role] || u.role).toLowerCase().includes(query) ||
        u.digital_id?.toLowerCase().includes(query) ||
        u.broadband_id?.toLowerCase().includes(query) ||
        u.cluster_id?.toLowerCase().includes(query) ||
        u.operator_id?.toLowerCase().includes(query),
      )
      : visibleUsers;

    // index by id for quick lookup
    const byId = {};
    for (const u of visibleUsers) byId[String(u.id)] = u;

    // collect matched ids + all their ancestors (so matched nodes always have context)
    const visibleIds = new Set(list.map(u => String(u.id)));
    if (query) {
      for (const u of list) {
        let pid = String(u.parent_id);
        while (pid && pid !== 'null' && pid !== 'undefined' && byId[pid]) {
          visibleIds.add(pid);
          pid = String(byId[pid].parent_id);
        }
      }
    }

    const visible = query ? visibleUsers.filter(u => visibleIds.has(String(u.id))) : visibleUsers;

    // group children by parent_id
    const childrenOf = {};
    for (const u of visible) {
      const pid = String(u.parent_id);
      if (!childrenOf[pid]) childrenOf[pid] = [];
      childrenOf[pid].push(u);
    }

    // determine roots
    let roots;
    if (currentUser?.role === 'sub_distributor') {
      roots = childrenOf[String(currentUser.id)] || [];
    } else if (currentUser?.role === 'cluster') {
      roots = childrenOf[String(currentUser.id)] || [];
    } else {
      // admin / manager: top-level users whose parent is not in the visible set,
      // but only show sub_distributor and above as roots (skip operators/clusters at root)
      roots = visible.filter(u => {
        const pid = String(u.parent_id);
        return !pid || pid === 'null' || pid === 'undefined' || !byId[pid];
      });
    }

    // Recursive renderer
    const renderUser = (u, depth) => (
      <UserNode
        key={u.id}
        user={u}
        depth={depth}
        defaultOpen={!!query || depth < 1}
        onSelect={setSelectedUser}
        children={(childrenOf[String(u.id)] || []).map(child => renderUser(child, depth + 1))}
      />
    );

    return roots.map(r => renderUser(r, 0));
  }, [visibleUsers, search, currentUser]);

  // ─── parent options when creating cluster / operator ──────────────────────
  const loadParentOptions = useCallback(async (role) => {
    setLoadingParents(true);
    setParentOptions([]);
    try {
      if (role === 'sub_distribution_manager') {
        const r = await usersAPI.getUsers({ role: 'sub_distributor', page_size: HIERARCHY_PAGE_SIZE });
        setParentOptions((r.data || []).map(u => ({ ...u, groupLabel: 'Sub Distributor' })));
      } else if (role === 'cluster') {
        if (currentUser?.role === 'sub_distribution_manager') {
          setParentOptions([{ id: String(currentUser.id), name: currentUser.name, groupLabel: 'You (Sub Distribution Manager)' }]);
        } else {
          const r = await usersAPI.getUsers({ role: 'sub_distribution_manager', page_size: HIERARCHY_PAGE_SIZE });
          setParentOptions((r.data || []).map(u => ({ ...u, groupLabel: 'Sub Distribution Manager' })));
        }
      } else if (role === 'operator') {
        if (currentUser?.role === 'cluster') {
          setParentOptions([{ id: String(currentUser.id), name: currentUser.name, groupLabel: 'You (Cluster)' }]);
        } else if (currentUser?.role === 'sub_distributor') {
          // operators must go under one of this sub_dist's clusters
          setParentOptions(visibleUsers.filter(u => u.role === 'cluster').map(u => ({ ...u, groupLabel: 'Cluster' })));
        } else {
          // admin / manager: show all clusters
          const r = await usersAPI.getUsers({ role: 'cluster', page_size: HIERARCHY_PAGE_SIZE });
          setParentOptions((r.data || []).map(u => ({ ...u, groupLabel: 'Cluster' })));
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingParents(false);
    }
  }, [currentUser, visibleUsers]);

  const handleRoleChange = (role) => {
    setFormData(prev => ({ ...prev, role, parentId: '' }));
    if (role === 'sub_distribution_manager' || role === 'cluster' || role === 'operator') loadParentOptions(role);
    else setParentOptions([]);
  };

  const openAdd = () => {
    const defaultRole = creatableRoles[0] || 'cluster';
    setFormData({ ...emptyForm, role: defaultRole });
    setParentOptions([]);
    if (defaultRole === 'sub_distribution_manager' || defaultRole === 'cluster' || defaultRole === 'operator') loadParentOptions(defaultRole);
    setShowAdd(true);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        role: formData.role,
      };
      if (formData.phone) payload.phone = formData.phone;
      if (formData.department) payload.department = formData.department;
      if (formData.location) payload.location = formData.location;
      if (formData.parentId) payload.parent_id = formData.parentId;
      if (formData.role === 'sub_distributor') {
        payload.digital_id = formData.digitalId || null;
        payload.broadband_id = formData.broadbandId || null;
      }
      if (formData.role === 'cluster') {
        payload.cluster_id = formData.clusterId || null;
      }
      if (formData.role === 'operator') {
        payload.operator_id = formData.operatorId || null;
      }
      await usersAPI.createUser(payload);
      showToast('User created successfully', 'success');
      setShowAdd(false);
      setFormData(emptyForm);
      fetchAll();
    } catch (err) {
      showToast(err.message || 'Failed to create user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const treeNodes = buildTree();

  // ─── page title per role ───────────────────────────────────────────────────
  const pageTitle =
    currentUser?.role === 'sub_distributor' ? 'My User Hierarchy' :
      currentUser?.role === 'cluster' ? 'My Operators' :
        'User Hierarchy';

  const pageDesc =
    currentUser?.role === 'sub_distributor' ? 'Clusters and operators under your sub-distribution' :
      currentUser?.role === 'cluster' ? 'Operators in your cluster' :
        'Visual tree of every user — Sub Distributors → Clusters → Operators';

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">{pageTitle}</h1>
          <p className="text-gray-500 mt-1 text-sm">{pageDesc}</p>
        </div>
        {creatableRoles.length > 0 && (
          <Button icon={UserPlus} onClick={openAdd}>Add User</Button>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {visibleRoleEntries.map(([role, label]) => {
          const s = ROLE_STYLES[role];
          return (
            <span key={role} className={`px-3 py-1 rounded-full text-xs font-medium ${s.badge}`}>
              {label}
            </span>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search users…"
          className="w-full pl-9 pr-9 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {search && (
          <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
            <X className="w-4 h-4 text-gray-400 hover:text-gray-600" />
          </button>
        )}
      </div>

      {/* Tree */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 sm:p-6 overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-3 text-gray-500">Building hierarchy…</span>
          </div>
        ) : treeNodes.length === 0 ? (
          <div className="text-center py-20">
            <Users className="w-16 h-16 text-gray-200 mx-auto mb-4" />
            <p className="text-gray-400">
              {search ? 'No users match your search.' : 'No users found.'}
            </p>
          </div>
        ) : (
          <div className="min-w-[340px]">
            {/* Current user as root for sub_dist / cluster */}
            {['sub_distributor', 'cluster'].includes(currentUser?.role) && (
              <div className="flex items-center gap-3 p-3 rounded-xl border-2 border-blue-400 bg-blue-50 mb-2 shadow-sm">
                <div className="w-9 h-9 rounded-full flex items-center justify-center ring-2 ring-blue-400 bg-white">
                  <span className="text-xs font-bold text-blue-700">{initials(currentUser.name)}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-800">{currentUser.name}</p>
                    <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-blue-100 text-blue-800">
                      {ROLE_LABELS[currentUser.role]} (You)
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">{currentUser.email}</p>
                </div>
              </div>
            )}
            <div className={['sub_distributor', 'cluster'].includes(currentUser?.role) ? 'pl-5 border-l-2 border-blue-200 ml-3' : ''}>
              {treeNodes}
            </div>
          </div>
        )}
      </div>

      {/* Selected user detail side-sheet */}
      {selectedUser && (
        <div
          className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center sm:justify-end p-0 sm:p-4"
          onClick={() => setSelectedUser(null)}
        >
          <div
            className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:w-80 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            {/* header */}
            <div className={`p-5 ${(ROLE_STYLES[selectedUser.role] || ROLE_STYLES.operator).bg} rounded-t-2xl`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center ring-2 ${(ROLE_STYLES[selectedUser.role] || ROLE_STYLES.operator).ring} bg-white`}>
                    <span className={`text-sm font-bold ${(ROLE_STYLES[selectedUser.role] || ROLE_STYLES.operator).text}`}>
                      {initials(selectedUser.name)}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-800">{selectedUser.name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${(ROLE_STYLES[selectedUser.role] || ROLE_STYLES.operator).badge}`}>
                      {ROLE_LABELS[selectedUser.role] || selectedUser.role}
                    </span>
                  </div>
                </div>
                <button onClick={() => setSelectedUser(null)} className="p-1.5 hover:bg-white/60 rounded-lg">
                  <X className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            </div>

            {/* body */}
            <div className="p-5 space-y-3 text-sm">
              <Row label="Email" value={selectedUser.email} />
              <Row label="Phone" value={selectedUser.phone} />
              <Row label="Department" value={selectedUser.department} />
              <Row label="Location" value={selectedUser.location} />
              <Row label="Status" value={<StatusBadge status={selectedUser.status} size="sm" />} />
              <Row label="Joined" value={selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleDateString() : '—'} />
              {selectedUser.digital_id && <Row label="Digital ID" value={selectedUser.digital_id} />}
              {selectedUser.broadband_id && <Row label="Broadband ID" value={selectedUser.broadband_id} />}
              {selectedUser.cluster_id && <Row label="Cluster ID" value={selectedUser.cluster_id} />}
              {selectedUser.operator_id && <Row label="Operator ID" value={selectedUser.operator_id} />}
              {selectedUser.parent_id && (
                <Row
                  label="Parent"
                  value={visibleUsers.find(u => String(u.id) === String(selectedUser.parent_id))?.name || `ID ${selectedUser.parent_id}`}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add user modal */}
      <Modal
        isOpen={showAdd}
        onClose={() => { setShowAdd(false); setFormData(emptyForm); setParentOptions([]); }}
        title="Add New User"
        size="md"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {/* Name */}
            <Field label="Full Name" required>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter full name"
                required
              />
            </Field>

            {/* Email */}
            <Field label="Email" required>
              <input
                type="email"
                value={formData.email}
                onChange={e => setFormData(p => ({ ...p, email: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="user@example.com"
                required
              />
            </Field>

            {/* Password */}
            <Field label={<span className="flex items-center gap-1"><Lock className="w-3.5 h-3.5" /> Password</span>} required>
              <input
                type="password"
                value={formData.password}
                onChange={e => setFormData(p => ({ ...p, password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Min. 6 characters"
                minLength={6}
                required
              />
            </Field>

            {/* Role */}
            <Field label="Role" required>
              <select
                value={formData.role}
                onChange={e => handleRoleChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              >
                {creatableRoles.map(r => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
            </Field>

            {/* Parent assignment */}
            {(formData.role === 'sub_distribution_manager' || formData.role === 'cluster' || formData.role === 'operator') && (
              <Field
                label={formData.role === 'sub_distribution_manager' ? 'Assign to Sub-Distributor' : formData.role === 'cluster' ? 'Assign to Sub Dist. Manager' : 'Assign to Cluster'}
                required
              >
                {loadingParents ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-300 rounded-lg">
                    <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    <span className="text-sm text-gray-500">Loading…</span>
                  </div>
                ) : (
                  <select
                    value={formData.parentId}
                    onChange={e => setFormData(p => ({ ...p, parentId: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  >
                    <option value="">Select {formData.role === 'sub_distribution_manager' ? 'Sub-Distributor' : formData.role === 'cluster' ? 'Sub Dist. Manager' : 'Cluster'}…</option>
                    {parentOptions.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.groupLabel ? `[${p.groupLabel}] ${p.name}` : p.name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            )}
          </div>

          <p className="text-xs text-gray-400">Optional — user can fill in later</p>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Phone">
              <input
                type="tel"
                value={formData.phone}
                onChange={e => setFormData(p => ({ ...p, phone: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="+880…"
              />
            </Field>
            <Field label="Department">
              <input
                type="text"
                value={formData.department}
                onChange={e => setFormData(p => ({ ...p, department: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. IT"
              />
            </Field>
            <div className="col-span-2">
              <Field label="Location">
                <input
                  type="text"
                  value={formData.location}
                  onChange={e => setFormData(p => ({ ...p, location: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g. Dhaka"
                />
              </Field>
            </div>
          </div>

          {formData.role === 'sub_distributor' && (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Digital ID">
                <input
                  type="text"
                  value={formData.digitalId}
                  onChange={e => setFormData(p => ({ ...p, digitalId: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter digital ID"
                />
              </Field>
              <Field label="Broadband ID">
                <input
                  type="text"
                  value={formData.broadbandId}
                  onChange={e => setFormData(p => ({ ...p, broadbandId: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter broadband ID"
                />
              </Field>
            </div>
          )}

          {formData.role === 'cluster' && (
            <Field label="Cluster ID">
              <input
                type="text"
                value={formData.clusterId}
                onChange={e => setFormData(p => ({ ...p, clusterId: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter cluster ID"
              />
            </Field>
          )}

          {formData.role === 'operator' && (
            <Field label="Operator ID">
              <input
                type="text"
                value={formData.operatorId}
                onChange={e => setFormData(p => ({ ...p, operatorId: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter operator ID"
              />
            </Field>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => { setShowAdd(false); setFormData(emptyForm); setParentOptions([]); }}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create User'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

// ─── tiny helpers ─────────────────────────────────────────────────────────────
const Row = ({ label, value }) => (
  <div className="flex justify-between items-start gap-2">
    <span className="text-gray-500 shrink-0">{label}</span>
    <span className="text-gray-800 text-right">{value || '—'}</span>
  </div>
);

const Field = ({ label, children, required }) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
  </div>
);

export default UserHierarchy;

