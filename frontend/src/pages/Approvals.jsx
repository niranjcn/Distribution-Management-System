import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { approvalsAPI, distributionsAPI, returnsAPI, defectsAPI } from '../services/api';
import {
  Check,
  X,
  Eye,
  Clock,
  CheckCircle,
  XCircle,
  Package,
  PackageCheck,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;

const TYPE_ICONS = {
  distribution: Package,
  return_confirmation: PackageCheck,
  defect: AlertTriangle,
};

const Approvals = () => {
  const { hasRole, user } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();

  const [activeTab, setActiveTab] = useState('all');
  const [selectedItem, setSelectedItem] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rows, setRows] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [counts, setCounts] = useState({ all: 0, distribution: 0, return_confirmation: 0, defect: 0 });
  const [loading, setLoading] = useState(true);
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

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

  const buildParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = { page: windowPage, page_size: pageSize };
    if (activeTab !== 'all') {
      params.item_type = activeTab;
    }
    return params;
  };

  const loadWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoading(true);

    try {
      const response = await approvalsAPI.getPendingApprovals(buildParams(windowPage));
      if (queryVersion !== queryVersionRef.current) return;

      const pageRows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || pageRows.length);

      const decorated = pageRows.map((row) => ({
        ...row,
        icon: TYPE_ICONS[row.type] || Clock,
      }));

      setRows((prev) => {
        const merged = reset ? decorated : [...prev, ...decorated];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = `${row.type}:${row.id}`;
          if (seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setTableTotalCount(total);
      setCounts({
        all: Number(response?.counts?.all ?? total),
        distribution: Number(response?.counts?.distribution ?? 0),
        return_confirmation: Number(response?.counts?.return_confirmation ?? 0),
        defect: Number(response?.counts?.defect ?? 0),
      });
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load pending actions', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoading(false);
    }
  };

  const resetAndLoad = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setRows([]);
    setTableTotalCount(0);
    setTablePage(1);
    await loadWindow(1, { reset: true, withLoading: true });
  };

  const handleTablePageChange = async (nextPage) => {
    setTablePage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(rows.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && rows.length < tableTotalCount;
    if (needsNextWindow) {
      await loadWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  useEffect(() => {
    if (user?.role) {
      resetAndLoad();
    }
  }, [user?.role, activeTab]);

  useEffect(() => {
    const handler = () => {
      resetAndLoad();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, [activeTab]);

  const handleApprove = async () => {
    try {
      if (selectedItem.type === 'distribution') {
        await distributionsAPI.updateDistributionStatus(selectedItem.id, 'approved');
        showToast('Distribution request approved successfully', 'success');
      } else if (selectedItem.type === 'defect') {
        await defectsAPI.updateDefectStatus(selectedItem.id, 'approved');
        showToast('Defect report approved successfully', 'success');
      } else if (selectedItem.type === 'return_confirmation') {
        await returnsAPI.updateReturnStatus(selectedItem.id, 'received');
        showToast('Return receipt confirmed successfully', 'success');
      }

      setShowApproveModal(false);
      setSelectedItem(null);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast('Failed to process request', 'error');
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      showToast('Please provide a reason for rejection', 'error');
      return;
    }

    try {
      if (selectedItem.type === 'distribution') {
        await distributionsAPI.updateDistributionStatus(selectedItem.id, 'rejected', rejectionReason);
        showToast('Distribution request rejected', 'info');
      } else if (selectedItem.type === 'defect') {
        await defectsAPI.updateDefectStatus(selectedItem.id, 'rejected', rejectionReason);
        showToast('Defect report rejected', 'info');
      }

      setShowRejectModal(false);
      setRejectionReason('');
      setSelectedItem(null);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast('Failed to reject request', 'error');
    }
  };

  const getTypeColor = (type) => {
    switch (type) {
      case 'distribution':
        return 'bg-blue-100 text-blue-800';
      case 'return_confirmation':
        return 'bg-purple-100 text-purple-800';
      case 'defect':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
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
      ),
    },
    {
      key: 'type',
      label: 'Type',
      render: (value) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${getTypeColor(value)}`}>
          {value === 'return_confirmation' ? 'return confirmation' : value}
        </span>
      ),
    },
    {
      key: 'requestedBy',
      label: 'Requested By',
      render: (value) => <span className="text-gray-700">{value}</span>,
    },
    {
      key: 'requestDate',
      label: 'Date',
      render: (value) => <span className="text-gray-500">{value ? new Date(value).toLocaleDateString() : '-'}</span>,
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />,
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex gap-2">
          <button
            onClick={() => {
              setSelectedItem(row);
              setShowDetailModal(true);
            }}
            className="p-1 hover:bg-gray-100 rounded"
            title="View Details"
          >
            <Eye className="w-4 h-4 text-gray-500" />
          </button>

          {row.type === 'return_confirmation' ? (
            <button
              onClick={() => {
                setSelectedItem(row);
                setShowApproveModal(true);
              }}
              className="p-1 hover:bg-purple-100 rounded"
              title="Confirm Return Receipt"
            >
              <PackageCheck className="w-4 h-4 text-purple-700" />
            </button>
          ) : (
            <>
              <button
                onClick={() => {
                  setSelectedItem(row);
                  setShowApproveModal(true);
                }}
                className="p-1 hover:bg-green-100 rounded"
                title="Approve"
              >
                <Check className="w-4 h-4 text-green-600" />
              </button>
              <button
                onClick={() => {
                  setSelectedItem(row);
                  setShowRejectModal(true);
                }}
                className="p-1 hover:bg-red-100 rounded"
                title="Reject"
              >
                <X className="w-4 h-4 text-red-600" />
              </button>
            </>
          )}
        </div>
      ),
    },
  ];

  const tabs = [
    { id: 'all', label: 'All', count: counts.all },
    { id: 'distribution', label: 'Distributions', count: counts.distribution },
    { id: 'return_confirmation', label: 'Return Confirmations', count: counts.return_confirmation },
    { id: 'defect', label: 'Defects', count: counts.defect },
  ];

  const stats = [
    { label: 'Pending', value: counts.all, icon: Clock, color: 'yellow' },
    { label: 'Distributions', value: counts.distribution, icon: Package, color: 'blue' },
    { label: 'Return Confirmations', value: counts.return_confirmation, icon: PackageCheck, color: 'purple' },
    { label: 'Defects', value: counts.defect, icon: AlertTriangle, color: 'red' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Pending Actions</h1>
        <p className="text-gray-500 mt-1">Review approvals and confirm returned devices reached PDIC</p>
      </div>

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

      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {tab.label}
            <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${activeTab === tab.id ? 'bg-white/20' : 'bg-gray-200'}`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      <Card>
        {loading && rows.length === 0 ? (
          <div className="text-center py-12 text-gray-500">Loading pending actions...</div>
        ) : rows.length > 0 ? (
          <DataTable
            columns={columns}
            data={rows}
            searchable={false}
            pageSize={TABLE_PAGE_SIZE}
            totalItems={tableTotalCount || rows.length}
            currentPage={tablePage}
            onPageChange={handleTablePageChange}
          />
        ) : (
          <div className="text-center py-12">
            <CheckCircle className="w-16 h-16 text-green-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-800 mb-2">All Caught Up!</h3>
            <p className="text-gray-500">There are no pending actions at this time.</p>
          </div>
        )}
      </Card>

      <Modal
        isOpen={showDetailModal}
        onClose={() => {
          setShowDetailModal(false);
          setSelectedItem(null);
        }}
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
                  {selectedItem.type === 'return_confirmation' ? 'return confirmation' : selectedItem.type}
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

              {selectedItem.type === 'return_confirmation' && (
                <>
                  <div>
                    <p className="text-sm text-gray-500">Device</p>
                    <p className="font-medium text-gray-800">{selectedItem.device}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Reason</p>
                    <p className="font-medium text-gray-800 capitalize">{selectedItem.reason}</p>
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
                  {selectedItem.description && (
                    <div className="col-span-2">
                      <p className="text-sm text-gray-500">Notes</p>
                      <p className="text-gray-800 mt-1 p-3 bg-gray-50 rounded-lg">{selectedItem.description}</p>
                    </div>
                  )}
                  {selectedItem.images && selectedItem.images.length > 0 && (
                    <div className="col-span-2">
                      <p className="text-sm text-gray-500 mb-2">Photos</p>
                      <div className="grid grid-cols-3 gap-2">
                        {selectedItem.images.map((photoUrl, index) => (
                          <a
                            key={index}
                            href={/^https?:\/\//i.test(photoUrl) ? photoUrl : `${import.meta.env.VITE_API_URL?.replace(/\/api\/?$/, '') || 'http://localhost:8080'}${photoUrl}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200 block hover:opacity-90 transition-opacity"
                          >
                            <img
                              src={/^https?:\/\//i.test(photoUrl) ? photoUrl : `${import.meta.env.VITE_API_URL?.replace(/\/api\/?$/, '') || 'http://localhost:8080'}${photoUrl}`}
                              alt={`Defect photo ${index + 1}`}
                              className="w-full h-full object-cover"
                            />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t">
              {selectedItem.type !== 'return_confirmation' && (
                <Button
                  variant="danger"
                  onClick={() => {
                    setShowDetailModal(false);
                    setShowRejectModal(true);
                  }}
                >
                  <X className="w-4 h-4 mr-2" />
                  Reject
                </Button>
              )}
              <Button
                onClick={() => {
                  setShowDetailModal(false);
                  setShowApproveModal(true);
                }}
              >
                {selectedItem.type === 'return_confirmation' ? (
                  <>
                    <PackageCheck className="w-4 h-4 mr-2" />
                    Confirm Receipt
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Approve
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={showApproveModal}
        onClose={() => {
          setShowApproveModal(false);
          setSelectedItem(null);
        }}
        title={selectedItem?.type === 'return_confirmation' ? 'Confirm Return Receipt' : 'Confirm Approval'}
        size="sm"
      >
        <div className="text-center py-4">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-6 h-6 text-green-600" />
          </div>
          <p className="text-gray-700 mb-4">
            {selectedItem?.type === 'return_confirmation'
              ? 'Are you sure you want to confirm this returned device reached PDIC?'
              : `Are you sure you want to approve this ${selectedItem?.type} request?`}
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={() => setShowApproveModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove}>{selectedItem?.type === 'return_confirmation' ? 'Confirm' : 'Approve'}</Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showRejectModal}
        onClose={() => {
          setShowRejectModal(false);
          setSelectedItem(null);
          setRejectionReason('');
        }}
        title="Reject Request"
        size="md"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
            <XCircle className="w-5 h-5 text-red-600" />
            <p className="text-sm text-red-800">You are about to reject this {selectedItem?.type} request.</p>
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
