import { useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import { devices } from '../data/mockData';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Plus, Eye, Edit, Trash2, Box, Download, Upload } from 'lucide-react';

const Devices = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const canRegister = ['admin', 'distributor'].includes(user?.role);

  const columns = [
    { key: 'macAddress', label: 'MAC Address' },
    { key: 'serialNumber', label: 'Serial Number' },
    { key: 'model', label: 'Model' },
    { key: 'manufacturer', label: 'Manufacturer' },
    {
      key: 'condition',
      label: 'Condition',
      render: (value) => <StatusBadge status={value} size="sm" />
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    { key: 'currentHolder', label: 'Current Holder' },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedDevice(row);
              setShowModal(true);
            }}
            className="p-1 text-blue-600 hover:bg-blue-50 rounded"
          >
            <Eye className="w-4 h-4" />
          </button>
          {canRegister && (
            <>
              <button className="p-1 text-gray-600 hover:bg-gray-50 rounded">
                <Edit className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedDevice(row);
                  setShowDeleteModal(true);
                }}
                className="p-1 text-red-600 hover:bg-red-50 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      )
    }
  ];

  const handleDelete = () => {
    showToast(`Device ${selectedDevice.macAddress} deleted successfully`, 'success');
    setShowDeleteModal(false);
    setSelectedDevice(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Devices</h1>
          <p className="text-gray-500 mt-1">
            {user?.role === 'operator' ? 'Your assigned devices' : 'Manage all registered devices'}
          </p>
        </div>
        {canRegister && (
          <div className="flex gap-2">
            <Link to="/devices/bulk-import">
              <Button variant="secondary" icon={Upload}>Bulk Import</Button>
            </Link>
            <Link to="/devices/register">
              <Button icon={Plus}>Register Device</Button>
            </Link>
          </div>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Total</p>
          <p className="text-2xl font-bold text-gray-800">{devices.length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Active</p>
          <p className="text-2xl font-bold text-green-600">{devices.filter(d => d.status === 'active').length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">In Use</p>
          <p className="text-2xl font-bold text-blue-600">{devices.filter(d => d.status === 'in-use').length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Stored</p>
          <p className="text-2xl font-bold text-purple-600">{devices.filter(d => d.status === 'stored').length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Defective</p>
          <p className="text-2xl font-bold text-red-600">{devices.filter(d => d.status === 'defective').length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Returned</p>
          <p className="text-2xl font-bold text-orange-600">{devices.filter(d => d.status === 'returned').length}</p>
        </Card>
      </div>

      <DataTable
        columns={columns}
        data={devices}
        selectable={canRegister}
        onRowClick={(row) => {
          setSelectedDevice(row);
          setShowModal(true);
        }}
      />

      {/* View Device Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedDevice(null);
        }}
        title="Device Details"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
            <Link to={`/track-device?mac=${selectedDevice?.macAddress}`}>
              <Button>Track Device</Button>
            </Link>
          </>
        }
      >
        {selectedDevice && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center">
                <Box className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedDevice.model}</h3>
                <p className="text-gray-500">{selectedDevice.manufacturer}</p>
                <div className="flex gap-2 mt-2">
                  <StatusBadge status={selectedDevice.condition} />
                  <StatusBadge status={selectedDevice.status} />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">MAC Address</label>
                <p className="font-medium text-gray-800 font-mono">{selectedDevice.macAddress}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Serial Number</label>
                <p className="font-medium text-gray-800">{selectedDevice.serialNumber}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Hardware Version</label>
                <p className="font-medium text-gray-800">{selectedDevice.hardwareVersion}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Firmware Version</label>
                <p className="font-medium text-gray-800">{selectedDevice.firmwareVersion}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Current Location</label>
                <p className="font-medium text-gray-800 capitalize">{selectedDevice.currentLocation.replace('-', ' ')}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Current Holder</label>
                <p className="font-medium text-gray-800">{selectedDevice.currentHolder}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Registered At</label>
                <p className="font-medium text-gray-800">{selectedDevice.registeredAt}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Registered By</label>
                <p className="font-medium text-gray-800">{selectedDevice.registeredBy}</p>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Device"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete}>Delete</Button>
          </>
        }
      >
        <p className="text-gray-600">
          Are you sure you want to delete device <span className="font-medium">{selectedDevice?.macAddress}</span>? 
          This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
};

export default Devices;
