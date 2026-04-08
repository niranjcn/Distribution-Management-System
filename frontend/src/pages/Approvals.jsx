import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import Timeline from '../components/ui/Timeline';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { approvalsAPI, distributionsAPI, returnsAPI, defectsAPI } from '../services/api';
import { 
  Check, X, Eye, Filter, Clock, CheckCircle, 
  XCircle, Package, RotateCcw, AlertTriangle, ShieldAlert, Loader2, Settings
} from 'lucide-react';

const defaultRoutingConfig = {
  distribution: { super_admin: true, manager: true, pdic_staff: true },
  return: { super_admin: true, manager: true, pdic_staff: true },
  defect: { super_admin: true, manager: true, pdic_staff: true },
};

const Approvals = () => {
  const { user, hasRole } = useAuth();
  const navigate = useNavigate();
  const { addNotification, showToast } = useNotifications();
  const [activeTab, setActiveTab] = useState('all');
  const [selectedItem, setSelectedItem] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [allPendingItems, setAllPendingItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [routingConfig, setRoutingConfig] = useState(defaultRoutingConfig);
  const [loadingRoutingConfig, setLoadingRoutingConfig] = useState(true);
  const [savingRoutingConfig, setSavingRoutingConfig] = useState(false);
  const [selectedRoutingRole, setSelectedRoutingRole] = useState('manager');

  // Admin, manager, and staff can access approvals.
  const canAccessApprovals = hasRole(['super_admin', 'manager', 'pdic_staff']);

  if (!canAccessApprovals) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <ShieldAlert className="w-16 h-16 text-red-500 mb-4" />
        <h1 className="text-xl font-bold text-gray-800 text-center">Access Denied</h1>
        <p className="text-gray-500 mt-2 text-center">Only Admins, Managers, and Staff can access approvals.</p>
        <Button className="mt-4" onClick={() => navigate('/')}>
          Back to Dashboard
        </Button>
      </div>
    );
  }

  const currentRoleKey = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role) ? user.role : null;

  const isTypeEnabledForCurrentRole = (type) => {
    if (!currentRoleKey) return true;
    return Boolean(routingConfig?.[type]?.[currentRoleKey]);
  };

  const applyRoleRoutingFilter = (items) => {
    if (!currentRoleKey) return items;
    return items.filter((item) => isTypeEnabledForCurrentRole(item.type));
  };

  const loadRoleRoutingConfig = async () => {
    try {
      setLoadingRoutingConfig(true);
      const response = await approvalsAPI.getRoleRoutingConfig();
      const incoming = response?.data || {};
      setRoutingConfig({
        distribution: {
          super_admin: incoming?.distribution?.super_admin ?? incoming?.distribution?.admin ?? true,
          manager: incoming?.distribution?.manager ?? true,
          pdic_staff: incoming?.distribution?.pdic_staff ?? incoming?.distribution?.staff ?? true,
        },
        return: {
          super_admin: incoming?.return?.super_admin ?? incoming?.return?.admin ?? true,
          manager: incoming?.return?.manager ?? true,
          pdic_staff: incoming?.return?.pdic_staff ?? incoming?.return?.staff ?? true,
        },
        defect: {
          super_admin: incoming?.defect?.super_admin ?? incoming?.defect?.admin ?? true,
          manager: incoming?.defect?.manager ?? true,
          pdic_staff: incoming?.defect?.pdic_staff ?? incoming?.defect?.staff ?? true,
        },
      });
    } catch (error) {
      showToast(error.message || 'Failed to load approval routing config', 'error');
      setRoutingConfig(defaultRoutingConfig);
    } finally {
      setLoadingRoutingConfig(false);
    }
  };

  const toggleRoutingCheckbox = (approvalType) => {
    setRoutingConfig((prev) => ({
      ...prev,
      [approvalType]: {
        ...prev[approvalType],
        [selectedRoutingRole]: !prev[approvalType]?.[selectedRoutingRole],
      },
    }));
  };

  const saveRoutingConfig = async () => {
    try {
      setSavingRoutingConfig(true);
      await approvalsAPI.updateRoleRoutingConfig({
        distribution: {
          super_admin: Boolean(routingConfig?.distribution?.super_admin),
          manager: Boolean(routingConfig?.distribution?.manager),
          pdic_staff: Boolean(routingConfig?.distribution?.pdic_staff),
        },
        return: {
          super_admin: Boolean(routingConfig?.return?.super_admin),
          manager: Boolean(routingConfig?.return?.manager),
          pdic_staff: Boolean(routingConfig?.return?.pdic_staff),
        },
        defect: {
          super_admin: Boolean(routingConfig?.defect?.super_admin),
          manager: Boolean(routingConfig?.defect?.manager),
          pdic_staff: Boolean(routingConfig?.defect?.pdic_staff),
        },
      });
      showToast('Approval routing updated successfully', 'success');
      await loadRoleRoutingConfig();
      await fetchPendingItems();
    } catch (error) {
      showToast(error.message || 'Failed to update approval routing', 'error');
    } finally {
      setSavingRoutingConfig(false);
    }
  };

  const fetchPendingItems = async () => {
    try {
      setLoading(true);
      const items = [];

      try {
        const distResponse = await distributionsAPI.getDistributions({ status: 'pending' });
        (distResponse.data || []).forEach(d => {
          items.push({
            ...d,
            id: d._id || d.id,
            type: 'distribution',
            icon: Package,
            title: `Distribution to ${d.to_user_name || 'Unknown'}`,
            requestedBy: d.from_user_name || 'Unknown',
            requestDate: d.created_at,
            status: d.status
          });
        });
      } catch (e) { console.error('Failed to fetch distributions:', e); }

      try {
        const retResponse = await returnsAPI.getReturns({ status: 'pending' });
        (retResponse.data || []).forEach(r => {
          items.push({
            ...r,
            id: r._id || r.id,
            type: 'return',
            icon: RotateCcw,
            title: `Return - ${r.device_name || r.device_type || 'Unknown Device'}`,
            requestedBy: r.initiated_by_name || 'Unknown',
            requestDate: r.created_at,
            status: r.status
          });
        });
      } catch (e) { console.error('Failed to fetch returns:', e); }

      try {
        const defResponse = await defectsAPI.getDefects({ status: 'reported' });
        (defResponse.data || []).forEach(d => {
          items.push({
            ...d,
            id: d._id || d.id,
            type: 'defect',
            icon: AlertTriangle,
            title: `Defect Report - ${d.device_name || d.device_type || 'Unknown Device'}`,
            requestedBy: d.reported_by_name || 'Unknown',
            requestDate: d.created_at,
            status: d.status
          });
        });
      } catch (e) { console.error('Failed to fetch defects:', e); }

      items.sort((a, b) => new Date(b.requestDate || 0) - new Date(a.requestDate || 0));
      setAllPendingItems(applyRoleRoutingFilter(items));
    } catch (error) {
      console.error('Failed to fetch approvals:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (canAccessApprovals) {
      loadRoleRoutingConfig();
    }
  }, [canAccessApprovals]);

  useEffect(() => {
    if (canAccessApprovals && !loadingRoutingConfig) {
      fetchPendingItems();
    }
  }, [canAccessApprovals, loadingRoutingConfig, routingConfig]);

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

  const handleApprove = async () => {
    try {
      if (!isTypeEnabledForCurrentRole(selectedItem.type)) {
        showToast(`Your role cannot approve ${selectedItem.type} requests`, 'error');
        return;
      }
      if (selectedItem.type === 'distribution') {
        await distributionsAPI.updateDistributionStatus(selectedItem.id, 'approved');
      } else if (selectedItem.type === 'return') {
        await returnsAPI.updateReturnStatus(selectedItem.id, 'approved');
      } else if (selectedItem.type === 'defect') {
        await defectsAPI.updateDefectStatus(selectedItem.id, 'approved');
      }
      showToast(`${selectedItem.type} request approved successfully`, 'success');
      setShowApproveModal(false);
      setSelectedItem(null);
      fetchPendingItems();
    } catch (error) {
      showToast('Failed to approve request', 'error');
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      showToast('Please provide a reason for rejection', 'error');
      return;
    }
    try {
      if (!isTypeEnabledForCurrentRole(selectedItem.type)) {
        showToast(`Your role cannot reject ${selectedItem.type} requests`, 'error');
        return;
      }
      if (selectedItem.type === 'distribution') {
        await distributionsAPI.updateDistributionStatus(selectedItem.id, 'rejected', rejectionReason);
      } else if (selectedItem.type === 'return') {
        await returnsAPI.updateReturnStatus(selectedItem.id, 'rejected', rejectionReason);
      } else if (selectedItem.type === 'defect') {
        await defectsAPI.updateDefectStatus(selectedItem.id, 'rejected', rejectionReason);
      }
      showToast(`${selectedItem.type} request rejected`, 'info');
      setShowRejectModal(false);
      setRejectionReason('');
      setSelectedItem(null);
      fetchPendingItems();
    } catch (error) {
      showToast('Failed to reject request', 'error');
    }
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
      render: (value) => <span className="text-gray-500">{value ? new Date(value).toLocaleDateString() : '-'}</span>
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
          {hasRole(['super_admin', 'manager', 'pdic_staff']) && isTypeEnabledForCurrentRole(row.type) && (
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

      {hasRole(['super_admin']) && (
        <Card title="Role Assignment" subtitle="Assign which request categories are handled by Manager and Admin">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {['manager', 'super_admin', 'pdic_staff'].map((role) => (
                <button
                  key={role}
                  onClick={() => setSelectedRoutingRole(role)}
                  className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    selectedRoutingRole === role
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {role.charAt(0).toUpperCase() + role.slice(1)}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { key: 'distribution', label: 'Distribution Approvals' },
                { key: 'return', label: 'Return Approvals' },
                { key: 'defect', label: 'Defect Reports' },
              ].map((item) => (
                <label
                  key={item.key}
                  className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(routingConfig?.[item.key]?.[selectedRoutingRole])}
                    onChange={() => toggleRoutingCheckbox(item.key)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600"
                  />
                  <span className="text-sm font-medium text-gray-800">{item.label}</span>
                </label>
              ))}
            </div>

            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-500">
                Select a role above, then check the categories that role should handle.
              </p>
              <Button icon={Settings} loading={savingRoutingConfig} onClick={saveRoutingConfig}>
                Save Role Mapping
              </Button>
            </div>
          </div>
        </Card>
      )}

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

            {hasRole(['super_admin', 'manager', 'pdic_staff']) && isTypeEnabledForCurrentRole(selectedItem.type) && (
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

