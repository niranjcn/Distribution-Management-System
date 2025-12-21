import { useState } from 'react';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { users as mockUsers, subDistributors, operators } from '../data/mockData';
import { 
  UserPlus, Edit, Trash2, Eye, Shield, Mail, Phone, 
  Building, MapPin, Calendar, Users as UsersIcon 
} from 'lucide-react';

const Users = () => {
  const { user: currentUser, hasRole } = useAuth();
  const [users] = useState([...mockUsers, ...subDistributors.map(sd => ({
    id: sd.id,
    name: sd.name,
    email: `${sd.id}@dms.com`,
    role: 'sub-distributor',
    status: 'active',
    region: sd.region,
    deviceCount: sd.deviceCount,
    createdAt: '2024-01-15'
  })), ...operators.map(op => ({
    id: op.id,
    name: op.name,
    email: `${op.id}@dms.com`,
    role: 'operator',
    status: op.status,
    assignedBy: op.assignedBy,
    assignedDate: op.assignedDate
  }))]);
  
  const [selectedUser, setSelectedUser] = useState(null);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'operator',
    region: '',
    status: 'active'
  });

  const getRoleColor = (role) => {
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-800';
      case 'manager': return 'bg-purple-100 text-purple-800';
      case 'distributor': return 'bg-blue-100 text-blue-800';
      case 'sub-distributor': return 'bg-indigo-100 text-indigo-800';
      case 'operator': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const columns = [
    {
      key: 'name',
      label: 'User',
      render: (value, row) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
            <span className="font-medium text-gray-600">
              {value.split(' ').map(n => n[0]).join('')}
            </span>
          </div>
          <div>
            <p className="font-medium text-gray-800">{value}</p>
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
          {value.replace('-', ' ')}
        </span>
      )
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    {
      key: 'region',
      label: 'Region',
      render: (value) => value || '-'
    },
    {
      key: 'createdAt',
      label: 'Joined',
      render: (value, row) => value || row.assignedDate || '-'
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
          {hasRole(['admin', 'manager']) && (
            <>
              <button
                onClick={() => { 
                  setSelectedUser(row); 
                  setFormData({
                    name: row.name,
                    email: row.email,
                    phone: row.phone || '',
                    role: row.role,
                    region: row.region || '',
                    status: row.status
                  });
                  setShowEditModal(true); 
                }}
                className="p-1 hover:bg-gray-100 rounded"
                title="Edit"
              >
                <Edit className="w-4 h-4 text-blue-500" />
              </button>
              {row.id !== currentUser.id && (
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

  const handleAddUser = (e) => {
    e.preventDefault();
    // In a real app, this would call an API
    console.log('Adding user:', formData);
    setShowAddModal(false);
    setFormData({
      name: '',
      email: '',
      phone: '',
      role: 'operator',
      region: '',
      status: 'active'
    });
  };

  const handleEditUser = (e) => {
    e.preventDefault();
    // In a real app, this would call an API
    console.log('Editing user:', selectedUser.id, formData);
    setShowEditModal(false);
  };

  const handleDeleteUser = () => {
    // In a real app, this would call an API
    console.log('Deleting user:', selectedUser.id);
    setShowDeleteModal(false);
    setSelectedUser(null);
  };

  const stats = [
    { label: 'Total Users', value: users.length, icon: UsersIcon, color: 'blue' },
    { label: 'Administrators', value: users.filter(u => u.role === 'admin').length, icon: Shield, color: 'red' },
    { label: 'Distributors', value: users.filter(u => u.role === 'distributor' || u.role === 'sub-distributor').length, icon: Building, color: 'indigo' },
    { label: 'Operators', value: users.filter(u => u.role === 'operator').length, icon: UsersIcon, color: 'green' }
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">User Management</h1>
          <p className="text-gray-500 mt-1">Manage system users and their permissions</p>
        </div>
        {hasRole(['admin', 'manager']) && (
          <Button 
            icon={UserPlus}
            onClick={() => setShowAddModal(true)}
          >
            Add User
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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

      {/* Users Table */}
      <Card>
        <DataTable
          columns={columns}
          data={users}
          searchable
          searchPlaceholder="Search users..."
        />
      </Card>

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
                  {selectedUser.name.split(' ').map(n => n[0]).join('')}
                </span>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedUser.name}</h3>
                <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${getRoleColor(selectedUser.role)}`}>
                  {selectedUser.role.replace('-', ' ')}
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
                <MapPin className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Region</p>
                  <p className="font-medium text-gray-800">{selectedUser.region || 'Not assigned'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-500">Joined</p>
                  <p className="font-medium text-gray-800">{selectedUser.createdAt || selectedUser.assignedDate || 'Unknown'}</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <StatusBadge status={selectedUser.status} />
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Add/Edit Modal */}
      {(showAddModal || showEditModal) && (
        <Modal
          isOpen={showAddModal || showEditModal}
          onClose={() => { 
            setShowAddModal(false); 
            setShowEditModal(false); 
            setSelectedUser(null);
            setFormData({
              name: '',
              email: '',
              phone: '',
              role: 'operator',
              region: '',
              status: 'active'
            });
          }}
          title={showAddModal ? 'Add New User' : 'Edit User'}
          size="md"
        >
          <form onSubmit={showAddModal ? handleAddUser : handleEditUser} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Role <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  {hasRole(['admin']) && <option value="admin">Admin</option>}
                  {hasRole(['admin']) && <option value="manager">Manager</option>}
                  <option value="distributor">Distributor</option>
                  <option value="sub-distributor">Sub-Distributor</option>
                  <option value="operator">Operator</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
              <input
                type="text"
                value={formData.region}
                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                placeholder="e.g., North Region"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button 
                type="button" 
                variant="outline"
                onClick={() => { 
                  setShowAddModal(false); 
                  setShowEditModal(false); 
                }}
              >
                Cancel
              </Button>
              <Button type="submit">
                {showAddModal ? 'Add User' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </Modal>
      )}

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
    </div>
  );
};

export default Users;
