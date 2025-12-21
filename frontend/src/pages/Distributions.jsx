import { useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import { distributions, devices } from '../data/mockData';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Plus, Eye, Truck, CheckCircle, XCircle, Clock } from 'lucide-react';

const Distributions = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [selectedDist, setSelectedDist] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approvalComment, setApprovalComment] = useState('');

  const canCreate = ['admin', 'distributor', 'sub-distributor'].includes(user?.role);
  const canApprove = ['sub-distributor', 'operator'].includes(user?.role);

  const columns = [
    { key: 'batchId', label: 'Batch ID' },
    { key: 'fromDistributor', label: 'From' },
    { key: 'toDistributor', label: 'To' },
    { key: 'deviceCount', label: 'Devices' },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    { key: 'createdAt', label: 'Created' },
    {
      key: 'approvedBy',
      label: 'Approved By',
      render: (value) => value || '-'
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedDist(row);
              setShowModal(true);
            }}
            className="p-1 text-blue-600 hover:bg-blue-50 rounded"
          >
            <Eye className="w-4 h-4" />
          </button>
          {canApprove && row.status === 'pending' && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedDist(row);
                  setShowApproveModal(true);
                }}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
              >
                <CheckCircle className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  showToast('Distribution rejected', 'warning');
                }}
                className="p-1 text-red-600 hover:bg-red-50 rounded"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      )
    }
  ];

  const handleApprove = () => {
    showToast(`Distribution ${selectedDist.batchId} approved successfully`, 'success');
    setShowApproveModal(false);
    setSelectedDist(null);
    setApprovalComment('');
  };

  const getDistributionDevices = (deviceIds) => {
    return devices.filter(d => deviceIds.includes(d.id));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Distributions</h1>
          <p className="text-gray-500 mt-1">Manage device distributions across the chain</p>
        </div>
        {canCreate && (
          <Link to="/distributions/create">
            <Button icon={Plus}>Create Distribution</Button>
          </Link>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-xl font-bold text-gray-800">{distributions.length}</p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Clock className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Pending</p>
              <p className="text-xl font-bold text-yellow-600">
                {distributions.filter(d => d.status === 'pending').length}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Approved</p>
              <p className="text-xl font-bold text-green-600">
                {distributions.filter(d => d.status === 'approved').length}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">In Transit</p>
              <p className="text-xl font-bold text-indigo-600">
                {distributions.filter(d => d.status === 'in-transit').length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <DataTable
        columns={columns}
        data={distributions}
        onRowClick={(row) => {
          setSelectedDist(row);
          setShowModal(true);
        }}
      />

      {/* View Distribution Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedDist(null);
        }}
        title="Distribution Details"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
            {canApprove && selectedDist?.status === 'pending' && (
              <Button onClick={() => {
                setShowModal(false);
                setShowApproveModal(true);
              }}>
                Approve Distribution
              </Button>
            )}
          </>
        }
      >
        {selectedDist && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center">
                <Truck className="w-8 h-8 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-800">{selectedDist.batchId}</h3>
                <p className="text-gray-500">{selectedDist.fromDistributor} → {selectedDist.toDistributor}</p>
                <StatusBadge status={selectedDist.status} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Created At</label>
                <p className="font-medium text-gray-800">{selectedDist.createdAt}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device Count</label>
                <p className="font-medium text-gray-800">{selectedDist.deviceCount}</p>
              </div>
              {selectedDist.approvedAt && (
                <>
                  <div>
                    <label className="text-xs text-gray-500 uppercase tracking-wider">Approved At</label>
                    <p className="font-medium text-gray-800">{selectedDist.approvedAt}</p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase tracking-wider">Approved By</label>
                    <p className="font-medium text-gray-800">{selectedDist.approvedBy}</p>
                  </div>
                </>
              )}
            </div>

            {selectedDist.notes && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Notes</label>
                <p className="text-gray-800 mt-1">{selectedDist.notes}</p>
              </div>
            )}

            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Devices in this Distribution</label>
              <div className="space-y-2">
                {getDistributionDevices(selectedDist.devices).map(device => (
                  <div key={device.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-800">{device.model}</p>
                      <p className="text-sm text-gray-500">{device.macAddress}</p>
                    </div>
                    <StatusBadge status={device.status} size="sm" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Approval Modal */}
      <Modal
        isOpen={showApproveModal}
        onClose={() => {
          setShowApproveModal(false);
          setApprovalComment('');
        }}
        title="Approve Distribution"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowApproveModal(false)}>Cancel</Button>
            <Button variant="danger" onClick={() => {
              showToast('Distribution rejected', 'warning');
              setShowApproveModal(false);
            }}>
              Reject
            </Button>
            <Button onClick={handleApprove}>Approve</Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            You are about to approve distribution <span className="font-medium">{selectedDist?.batchId}</span> with {selectedDist?.deviceCount} devices.
          </p>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Comments (Optional)
            </label>
            <textarea
              value={approvalComment}
              onChange={(e) => setApprovalComment(e.target.value)}
              rows={3}
              placeholder="Add any comments or notes..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <p className="text-sm text-yellow-800">
              By approving, you confirm that you have received all {selectedDist?.deviceCount} devices in good condition.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Distributions;
