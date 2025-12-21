import { useState, useMemo } from 'react';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import Timeline from '../components/ui/Timeline';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { distributions, returnRequests, defectReports } from '../data/mockData';
import { 
  Check, X, Eye, Filter, Clock, CheckCircle, 
  XCircle, Package, RotateCcw, AlertTriangle 
} from 'lucide-react';

const Approvals = () => {
  const { user, hasRole } = useAuth();
  const { addNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState('all');
  const [selectedItem, setSelectedItem] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');

  // Combine all pending approvals
  const allPendingItems = useMemo(() => {
    const items = [];

    // Pending distributions
    distributions
      .filter(d => d.status === 'pending')
      .forEach(d => {
        items.push({
          ...d,
          type: 'distribution',
          icon: Package,
          title: `Distribution to ${d.toDistributor}`,
          requestedBy: d.fromDistributor,
          requestDate: d.createdAt
        });
      });

    // Pending returns
    returnRequests
      .filter(r => r.status === 'pending')
      .forEach(r => {
        items.push({
          ...r,
          type: 'return',
          icon: RotateCcw,
          title: `Return - ${r.device?.model || 'Unknown Device'}`,
          requestedBy: r.initiatedBy,
          requestDate: r.createdAt
        });
      });

    // Pending defect reports (for review)
    defectReports
      .filter(d => d.status === 'open' || d.status === 'pending')
      .forEach(d => {
        items.push({
          ...d,
          type: 'defect',
          icon: AlertTriangle,
          title: `Defect Report - ${d.device?.model || 'Unknown Device'}`,
          requestedBy: d.reportedBy,
          requestDate: d.reportedAt
        });
      });

    return items.sort((a, b) => new Date(b.requestDate) - new Date(a.requestDate));
  }, []);

  const filteredItems = useMemo(() => {
    if (activeTab === 'all') return allPendingItems;
    return allPendingItems.filter(item => item.type === activeTab);
  }, [activeTab, allPendingItems]);

  const tabs = [
    { id: 'all', label: 'All', count: allPendingItems.length },
    { id: 'distribution', label: 'Distributions', count: allPendingItems.filter(i => i.type === 'distribution').length },
    { id: 'return', label: 'Returns', count: allPendingItems.filter(i => i.type === 'return').length },
    { id: 'defect', label: 'Defects', count: allPendingItems.filter(i => i.type === 'defect').length }
  ];

  const handleApprove = () => {
    addNotification({
      type: 'success',
      title: 'Approved',
      message: `${selectedItem.type} request has been approved successfully.`
    });
    setShowApproveModal(false);
    setSelectedItem(null);
  };

  const handleReject = () => {
    if (!rejectionReason.trim()) {
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Please provide a reason for rejection.'
      });
      return;
    }
    addNotification({
      type: 'info',
      title: 'Rejected',
      message: `${selectedItem.type} request has been rejected.`
    });
    setShowRejectModal(false);
    setRejectionReason('');
    setSelectedItem(null);
  };

  const getTypeColor = (type) => {
    switch (type) {
      case 'distribution': return 'bg-blue-100 text-blue-800';
      case 'return': return 'bg-orange-100 text-orange-800';
      case 'defect': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const columns = [
    {
      key: 'title',
      label: 'Request',
      render: (value, row) => (
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${getTypeColor(row.type)}`}>
            <row.icon className="w-5 h-5" />
          </div>
          <div>
            <p className="font-medium text-gray-800">{value}</p>
            <p className="text-sm text-gray-500">{row.id}</p>
          </div>
        </div>
      )
    },
    {
      key: 'type',
      label: 'Type',
      render: (value) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${getTypeColor(value)}`}>
          {value}
        </span>
      )
    },
    {
      key: 'requestedBy',
      label: 'Requested By',
      render: (value) => <span className="text-gray-700">{value}</span>
    },
    {
      key: 'requestDate',
      label: 'Date',
      render: (value) => <span className="text-gray-500">{value}</span>
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex gap-2">
          <button
            onClick={() => { setSelectedItem(row); setShowDetailModal(true); }}
            className="p-1 hover:bg-gray-100 rounded"
            title="View Details"
          >
            <Eye className="w-4 h-4 text-gray-500" />
          </button>
          {hasRole(['admin', 'manager', 'distributor']) && (
            <>
              <button
                onClick={() => { setSelectedItem(row); setShowApproveModal(true); }}
                className="p-1 hover:bg-green-100 rounded"
                title="Approve"
              >
                <Check className="w-4 h-4 text-green-600" />
              </button>
              <button
                onClick={() => { setSelectedItem(row); setShowRejectModal(true); }}
                className="p-1 hover:bg-red-100 rounded"
                title="Reject"
              >
                <X className="w-4 h-4 text-red-600" />
              </button>
            </>
          )}
        </div>
      )
    }
  ];

  const stats = [
    { label: 'Pending', value: allPendingItems.length, icon: Clock, color: 'yellow' },
    { label: 'Distributions', value: allPendingItems.filter(i => i.type === 'distribution').length, icon: Package, color: 'blue' },
    { label: 'Returns', value: allPendingItems.filter(i => i.type === 'return').length, icon: RotateCcw, color: 'orange' },
    { label: 'Defects', value: allPendingItems.filter(i => i.type === 'defect').length, icon: AlertTriangle, color: 'red' }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Pending Approvals</h1>
        <p className="text-gray-500 mt-1">Review and manage pending requests</p>
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

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {tab.label}
            <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
              activeTab === tab.id
                ? 'bg-white/20'
                : 'bg-gray-200'
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Approvals Table */}
      <Card>
        {filteredItems.length > 0 ? (
          <DataTable
            columns={columns}
            data={filteredItems}
            searchable
            searchPlaceholder="Search approvals..."
          />
        ) : (
          <div className="text-center py-12">
            <CheckCircle className="w-16 h-16 text-green-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-800 mb-2">All Caught Up!</h3>
            <p className="text-gray-500">There are no pending approvals at this time.</p>
          </div>
        )}
      </Card>

      {/* Detail Modal */}
      <Modal
        isOpen={showDetailModal}
        onClose={() => { setShowDetailModal(false); setSelectedItem(null); }}
        title="Request Details"
        size="lg"
      >
        {selectedItem && (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-lg ${getTypeColor(selectedItem.type)}`}>
                <selectedItem.icon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedItem.title}</h3>
                <p className="text-sm text-gray-500">{selectedItem.id}</p>
              </div>
              <StatusBadge status={selectedItem.status} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Type</p>
                <span className={`inline-block mt-1 px-2 py-1 rounded-full text-xs font-medium capitalize ${getTypeColor(selectedItem.type)}`}>
                  {selectedItem.type}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-500">Requested By</p>
                <p className="font-medium text-gray-800">{selectedItem.requestedBy}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Request Date</p>
                <p className="font-medium text-gray-800">{selectedItem.requestDate}</p>
              </div>
              {selectedItem.type === 'distribution' && (
                <>
                  <div>
                    <p className="text-sm text-gray-500">Recipient</p>
                    <p className="font-medium text-gray-800">{selectedItem.recipient}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Device Count</p>
                    <p className="font-medium text-gray-800">{selectedItem.deviceCount} devices</p>
                  </div>
                </>
              )}
              {selectedItem.type === 'return' && (
                <>
                  <div>
                    <p className="text-sm text-gray-500">Device</p>
                    <p className="font-medium text-gray-800">{selectedItem.device}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Reason</p>
                    <p className="font-medium text-gray-800">{selectedItem.reason}</p>
                  </div>
                </>
              )}
              {selectedItem.type === 'defect' && (
                <>
                  <div>
                    <p className="text-sm text-gray-500">Device</p>
                    <p className="font-medium text-gray-800">{selectedItem.device}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Defect Type</p>
                    <p className="font-medium text-gray-800">{selectedItem.defectType}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Severity</p>
                    <StatusBadge status={selectedItem.severity} />
                  </div>
                </>
              )}
            </div>

            {selectedItem.notes && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Notes</p>
                <p className="bg-gray-50 p-3 rounded-lg text-gray-700">{selectedItem.notes}</p>
              </div>
            )}

            {hasRole(['admin', 'manager', 'distributor']) && (
              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button 
                  variant="danger" 
                  onClick={() => { setShowDetailModal(false); setShowRejectModal(true); }}
                >
                  <X className="w-4 h-4 mr-2" />
                  Reject
                </Button>
                <Button 
                  onClick={() => { setShowDetailModal(false); setShowApproveModal(true); }}
                >
                  <Check className="w-4 h-4 mr-2" />
                  Approve
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Approve Modal */}
      <Modal
        isOpen={showApproveModal}
        onClose={() => { setShowApproveModal(false); setSelectedItem(null); }}
        title="Confirm Approval"
        size="sm"
      >
        <div className="text-center py-4">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-6 h-6 text-green-600" />
          </div>
          <p className="text-gray-700 mb-4">
            Are you sure you want to approve this {selectedItem?.type} request?
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={() => setShowApproveModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove}>
              Approve
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reject Modal */}
      <Modal
        isOpen={showRejectModal}
        onClose={() => { setShowRejectModal(false); setSelectedItem(null); setRejectionReason(''); }}
        title="Reject Request"
        size="md"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
            <XCircle className="w-5 h-5 text-red-600" />
            <p className="text-sm text-red-800">
              You are about to reject this {selectedItem?.type} request.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reason for Rejection <span className="text-red-500">*</span>
            </label>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={4}
              placeholder="Please provide a detailed reason for rejection..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setShowRejectModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleReject}>
              Reject Request
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Approvals;
