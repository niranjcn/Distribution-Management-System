import { useState, useEffect, useRef } from 'react';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import Timeline from '../components/ui/Timeline';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { returnsAPI, approvalRequestsAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { useQueryClient } from '@tanstack/react-query';
import { returnKeys } from '../hooks';
import { Eye, RotateCcw, Loader2, PackageCheck, AlertTriangle, Search } from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const TABLE_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'return_id', label: 'Return ID' },
  { value: 'device_serial', label: 'Device Serial' },
  { value: 'device_nuid', label: 'NUID' },
  { value: 'requested_by_name', label: 'Initiated By' },
  { value: 'digital_id', label: 'Digital ID' },
  { value: 'broadband_id', label: 'Broadband ID' },
  { value: 'reason', label: 'Reason' },
  { value: 'status', label: 'Status' },
];

const RETURN_STATUS_CARD_CONFIG = ['pending', 'under-review', 'approved', 'rejected'];

const Returns = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [returnRequests, setReturnRequests] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [statusCounts, setStatusCounts] = useState({
    pending: 0,
    'under-review': 0,
    approved: 0,
    rejected: 0,
  });
  const [tablePage, setTablePage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedReturn, setSelectedReturn] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [actionComment, setActionComment] = useState('');
  const [tableSearchBy, setTableSearchBy] = useState('all');
  const [tableSearchInput, setTableSearchInput] = useState('');
  const [appliedTableSearch, setAppliedTableSearch] = useState({ by: 'all', query: '' });
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

  const buildReturnParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      page: windowPage,
      page_size: pageSize,
    };
    if (appliedTableSearch.query) {
      params.search = appliedTableSearch.query;
      if (appliedTableSearch.by && appliedTableSearch.by !== 'all') {
        params.search_by = appliedTableSearch.by;
      }
    }
    return params;
  };

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await returnsAPI.getReturns(buildReturnParams(page, EXPORT_PAGE_SIZE));
      const rows = Array.isArray(response?.data) ? response.data : [];
      total = Number(response?.pagination?.total || rows.length);
      collected = collected.concat(rows);

      if (!rows.length || collected.length >= total) {
        break;
      }

      page += 1;
    }

    return collected;
  };

  const buildReturnCountParams = (status) => {
    const params = {
      page: 1,
      page_size: 1,
      status,
    };
    if (appliedTableSearch.query) {
      params.search = appliedTableSearch.query;
      if (appliedTableSearch.by && appliedTableSearch.by !== 'all') {
        params.search_by = appliedTableSearch.by;
      }
    }
    return params;
  };

  const loadReturnStatusCounts = async () => {
    const queryVersion = queryVersionRef.current;
    try {
      const responses = await Promise.all(
        RETURN_STATUS_CARD_CONFIG.map((status) => returnsAPI.getReturns(buildReturnCountParams(status)))
      );
      if (queryVersion !== queryVersionRef.current) return;

      const nextCounts = RETURN_STATUS_CARD_CONFIG.reduce((acc, status, index) => {
        const total = Number(responses[index]?.pagination?.total || 0);
        acc[status] = Number.isFinite(total) ? total : 0;
        return acc;
      }, {});

      setStatusCounts(nextCounts);
    } catch (error) {
      console.error('Failed to load return status counts:', error);
    }
  };

  const loadReturnWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoading(true);

    try {
      const response = await returnsAPI.getReturns(buildReturnParams(windowPage));
      if (queryVersion !== queryVersionRef.current) return;

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setReturnRequests((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.id || row?._id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setTableTotalCount(total);
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      console.error('Failed to fetch returns:', error);
      showToast('Failed to load return requests', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoading(false);
    }
  };

  const resetAndLoadReturns = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setReturnRequests([]);
    setTableTotalCount(0);
    setStatusCounts({ pending: 0, 'under-review': 0, approved: 0, rejected: 0 });
    setTablePage(1);
    await Promise.all([
      loadReturnWindow(1, { reset: true, withLoading: true }),
      loadReturnStatusCounts(),
    ]);
  };

  const handleSearchSubmit = () => {
    const nextQuery = tableSearchInput.trim();
    setAppliedTableSearch({ by: tableSearchBy, query: nextQuery });
  };

  const handleSearchReset = () => {
    setTableSearchBy('all');
    setTableSearchInput('');
    setAppliedTableSearch({ by: 'all', query: '' });
  };

  const handleTablePageChange = async (nextPage) => {
    setTablePage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(returnRequests.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && returnRequests.length < tableTotalCount;
    if (needsNextWindow) {
      await loadReturnWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  useEffect(() => {
    resetAndLoadReturns();
  }, [appliedTableSearch]);

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: returnKeys.all });
      resetAndLoadReturns();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  const canConfirmReceipt = ['super_admin', 'manager', 'pdic_staff', 'sub_distribution_employee'].includes(user?.role);
  const pendingReceiptCount = statusCounts.pending + statusCounts.approved;

  const columns = [
    {
      key: 'device_name',
      label: 'Device',
      render: (value, row) => (
        <DeviceIdentity
          device={{
            ...row,
            model: row.model || row.device_model || value,
            serial_number: row.serial_number || row.device_serial,
          }}
        />
      )
    },
    { key: 'reason', label: 'Reason' },
    {
      key: 'requested_by_name',
      label: 'Initiated By',
      render: (value, row) => value || row.initiated_by_name || 'N/A'
    },
    { key: 'created_at', label: 'Date', render: (value) => value ? new Date(value).toLocaleDateString() : '-' },
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
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedReturn(row);
              setShowModal(true);
            }}
            className="p-1 text-blue-600 hover:bg-blue-50 rounded"
          >
            <Eye className="w-4 h-4" />
          </button>
          {canConfirmReceipt && ['pending', 'approved'].includes(row.status) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedReturn(row);
                setActionComment('');
                setShowReceiptModal(true);
              }}
              className="p-1 text-purple-600 hover:bg-purple-50 rounded"
              title="Confirm device reached PDIC"
            >
              <PackageCheck className="w-4 h-4" />
            </button>
          )}
        </div>
      )
    }
  ];

  const handleConfirmReceipt = async () => {
    try {
      if (user?.role === 'sub_distribution_employee') {
        await approvalRequestsAPI.submit({
          request_type: 'return_status',
          summary: `Confirm received return ${selectedReturn.return_id || selectedReturn._id}`,
          payload: {
            return_id: String(selectedReturn._id || selectedReturn.id),
            status: 'received',
            notes: actionComment || undefined,
          },
        });
        showToast('Return confirmation submitted for approval', 'success');
        setShowReceiptModal(false);
        setActionComment('');
        return;
      }
      await returnsAPI.updateReturnStatus(
        selectedReturn._id || selectedReturn.id,
        'received',
        actionComment
      );
      showToast('Device receipt confirmed — ownership transferred back to PDIC', 'success');
      setShowReceiptModal(false);
      setActionComment('');
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to confirm receipt', 'error');
    }
  };

  const getTimelineItems = (returnReq) => {
    const items = [
      {
        title: 'Return Initiated',
        description: `By ${returnReq.initiated_by_name || 'Unknown'}`,
        timestamp: returnReq.created_at ? new Date(returnReq.created_at).toLocaleDateString() : '',
        status: 'completed'
      }
    ];

    if (returnReq.approval_chain) {
      returnReq.approval_chain.forEach((approval) => {
        items.push({
          title: `${(approval.role || '').replace('-', ' ')} Review`,
          description: approval.status === 'approved' 
            ? `Approved by ${approval.by || 'Unknown'}`
            : approval.status === 'pending' 
              ? 'Awaiting review'
              : 'Under review',
          timestamp: approval.at || '',
          user: approval.by,
          status: approval.status === 'approved' ? 'completed' : 
                  approval.status === 'pending' ? 'current' : 'pending'
        });
      });
    }

    if (returnReq.completed_at) {
      items.push({
        title: 'Return Completed',
        timestamp: new Date(returnReq.completed_at).toLocaleDateString(),
        status: 'completed'
      });
    }

    return items;
  };

  return (
    <div className="space-y-6">
      {canConfirmReceipt && pendingReceiptCount > 0 && (
        <div className="space-y-3">
          {pendingReceiptCount > 0 && (
            <div className="p-4 rounded-xl border border-amber-300 bg-amber-50">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                <p className="font-semibold text-amber-900">PDIC Receipt Confirmation Pending</p>
              </div>
              <p className="text-sm text-amber-800">
                {pendingReceiptCount} return requests are waiting for device reached confirmation at PDIC.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Return Requests</h1>
          <p className="text-gray-500 mt-1">Manage device return requests and approvals</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Total</p>
          <p className="text-2xl font-bold text-gray-800">{tableTotalCount || returnRequests.length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Pending</p>
          <p className="text-2xl font-bold text-yellow-600">
            {statusCounts.pending}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Under Review</p>
          <p className="text-2xl font-bold text-blue-600">
            {statusCounts['under-review']}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Approved</p>
          <p className="text-2xl font-bold text-green-600">
            {statusCounts.approved}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Rejected</p>
          <p className="text-2xl font-bold text-red-600">
            {statusCounts.rejected}
          </p>
        </Card>
      </div>

      <Card className="!p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Search Returns</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-3">
            <select
              value={tableSearchBy}
              onChange={(e) => setTableSearchBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {TABLE_SEARCH_BY_OPTIONS.map((option) => (
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
                  handleSearchSubmit();
                }
              }}
              placeholder="Enter pattern to search..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
          <div className="md:col-span-3 flex gap-2">
            <Button onClick={handleSearchSubmit} className="w-full">Search</Button>
            <Button variant="secondary" onClick={handleSearchReset}>Reset</Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading return requests...</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={returnRequests}
          searchable={false}
          pageSize={TABLE_PAGE_SIZE}
          totalItems={tableTotalCount || returnRequests.length}
          currentPage={tablePage}
          onPageChange={handleTablePageChange}
          getExportRows={getExportRows}
          onRowClick={(row) => {
            setSelectedReturn(row);
            setShowModal(true);
          }}
        />
      )}

      {/* View Return Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedReturn(null);
        }}
        title="Return Request Details"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
            {canConfirmReceipt && ['pending', 'approved'].includes(selectedReturn?.status) && (
              <Button onClick={() => {
                setShowModal(false);
                setActionComment('');
                setShowReceiptModal(true);
              }}>
                Confirm Device Reached at PDIC
              </Button>
            )}
          </>
        }
      >
        {selectedReturn && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-orange-50 rounded-lg">
              <div className="w-16 h-16 bg-orange-100 rounded-xl flex items-center justify-center">
                <RotateCcw className="w-8 h-8 text-orange-600" />
              </div>
              <div className="flex-1">
                <DeviceIdentity
                  device={{
                    ...selectedReturn,
                    model: selectedReturn.model || selectedReturn.device_model || selectedReturn.device_name,
                    serial_number: selectedReturn.serial_number || selectedReturn.device_serial,
                  }}
                />
                <StatusBadge status={selectedReturn.status} />
              </div>
            </div>

              <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Reason</label>
                <p className="font-medium text-gray-800 capitalize">{selectedReturn.reason}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Status</label>
                <p className="font-medium"><StatusBadge status={selectedReturn.status} /></p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Initiated By</label>
                <p className="font-medium text-gray-800">{selectedReturn.requested_by_name || selectedReturn.initiated_by_name || 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Created At</label>
                <p className="font-medium text-gray-800">{selectedReturn.created_at ? new Date(selectedReturn.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
              {selectedReturn.return_approved_by_name && (
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider">Return Approved By</label>
                  <p className="font-medium text-gray-800">{selectedReturn.return_approved_by_name}</p>
                  {selectedReturn.return_approved_at && (
                    <p className="text-xs text-gray-500">{new Date(selectedReturn.return_approved_at).toLocaleDateString()}</p>
                  )}
                </div>
              )}
              {selectedReturn.received_date && (
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider">Received At PDIC</label>
                  <p className="font-medium text-gray-800">{new Date(selectedReturn.received_date).toLocaleDateString()}</p>
                </div>
              )}
            </div>

            {selectedReturn.description && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Description</label>
                <p className="text-gray-800 mt-1 p-3 bg-gray-50 rounded-lg">{selectedReturn.description}</p>
              </div>
            )}

            {selectedReturn.defect_report_id && (
              <div className="p-4 bg-red-50 rounded-lg">
                <label className="text-xs text-red-600 uppercase tracking-wider">Linked Defect Report</label>
                <p className="font-medium text-red-800">Report ID: {selectedReturn.defect_report_id}</p>
              </div>
            )}

            {/* Approval Timeline */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-3 block">Approval Timeline</label>
              <Timeline items={getTimelineItems(selectedReturn)} />
            </div>
          </div>
        )}
      </Modal>

      {/* Confirm Receipt Modal */}
      <Modal
        isOpen={showReceiptModal}
        onClose={() => {
          setShowReceiptModal(false);
          setActionComment('');
        }}
        title="Confirm Device Receipt at PDIC"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowReceiptModal(false)}>Cancel</Button>
            <Button onClick={handleConfirmReceipt}>
              <PackageCheck className="w-4 h-4 mr-1" /> Confirm Received
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="p-4 bg-purple-50 rounded-lg">
            <DeviceIdentity
              device={{
                ...selectedReturn,
                model: selectedReturn?.model || selectedReturn?.device_model || selectedReturn?.device_name,
                serial_number: selectedReturn?.serial_number || selectedReturn?.device_serial,
              }}
            />
            <p className="text-sm text-gray-500">
              Return ID: {selectedReturn?.return_id || selectedReturn?._id || 'N/A'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Requested by: {selectedReturn?.requested_by_name || 'N/A'}
            </p>
          </div>

          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <p className="text-sm text-green-800 font-medium">Confirming receipt will:</p>
            <ul className="text-sm text-green-700 mt-1 space-y-1 list-disc list-inside">
              <li>Mark the return as received</li>
              <li>Transfer device ownership back to PDIC</li>
              <li>Notify the operator that the return is complete</li>
            </ul>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Returns;

