import { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import { distributionsAPI } from '../services/api';
import DateRangeFilter, { buildDateParams } from '../components/ui/DateRangeFilter';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { useQueryClient } from '@tanstack/react-query';
import { distributionKeys } from '../hooks';
import { Plus, Eye, Truck, CheckCircle, Loader2, AlertTriangle, PackageCheck, XCircle, Layers3, Factory, Upload, Download, Search } from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const ALL_DISTRIBUTIONS_PAGE_SIZE = 100000;

const SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'distribution_id', label: 'Distribution ID' },
  { value: 'from_user_name', label: 'From' },
  { value: 'to_user_name', label: 'To' },
  { value: 'digital_id', label: 'Digital ID' },
  { value: 'broadband_id', label: 'Broadband ID' },
  { value: 'status', label: 'Status' },
  { value: 'confirmed_by_name', label: 'Confirmed By' },
];

const STATUS_CARD_CONFIG = ['pending_receipt', 'approved', 'disputed'];

const toDisplayLabel = (value, fallback = 'Unknown') => {
  if (!value) return fallback;
  const normalized = String(value).trim();
  const normalizedKey = normalized.toLowerCase().replace(/[-_\s]+/g, '');
  if (['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedKey)) return 'SB';
  return normalized || fallback;
};

const isSetupBoxType = (deviceType) => {
  const normalized = String(deviceType || '').toLowerCase();
  return normalized.includes('setup') || normalized.includes('set top') || normalized.includes('stb') || normalized === 'sb';
};

const getSenderDisplayName = (dist) => {
  const senderType = String(dist?.from_user_type || '').toLowerCase();
  if (senderType === 'noc' || senderType === 'pdic_staff') return 'PDIC';
  return dist?.from_user_name || 'Unknown';
};

const Distributions = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [distributions, setDistributions] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [statusCounts, setStatusCounts] = useState({ pending_receipt: 0, approved: 0, disputed: 0 });
  const [pendingReceiptForMeCount, setPendingReceiptForMeCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedDist, setSelectedDist] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [deviceSummary, setDeviceSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [receiptNotes, setReceiptNotes] = useState('');
  const [receiptSubmitting, setReceiptSubmitting] = useState(false);
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [searchBy, setSearchBy] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [appliedSearch, setAppliedSearch] = useState({ by: 'all', query: '' });
  const queryVersionRef = useRef(0);
  const summaryRequestIdRef = useRef(0);

  const buildDistributionParams = () => {
    const params = {
      page: 1,
      page_size: ALL_DISTRIBUTIONS_PAGE_SIZE,
      ...buildDateParams(dateRange),
    };
    if (appliedSearch.query) {
      params.search = appliedSearch.query;
      if (appliedSearch.by && appliedSearch.by !== 'all') {
        params.search_by = appliedSearch.by;
      }
    }
    return params;
  };

  const getExportRows = async () => distributions;

  const buildDistributionCountParams = (status) => {
    const params = {
      page: 1,
      page_size: 1,
      status,
      ...buildDateParams(dateRange),
    };
    if (appliedSearch.query) {
      params.search = appliedSearch.query;
      if (appliedSearch.by && appliedSearch.by !== 'all') {
        params.search_by = appliedSearch.by;
      }
    }
    return params;
  };

  const loadDistributionStatusCounts = async () => {
    const queryVersion = queryVersionRef.current;
    try {
      const responses = await Promise.all(
        STATUS_CARD_CONFIG.map((status) => distributionsAPI.getDistributions(buildDistributionCountParams(status)))
      );
      if (queryVersion !== queryVersionRef.current) return;

      const nextCounts = STATUS_CARD_CONFIG.reduce((acc, status, index) => {
        const total = Number(responses[index]?.pagination?.total || 0);
        acc[status] = Number.isFinite(total) ? total : 0;
        return acc;
      }, {});

      setStatusCounts(nextCounts);
    } catch (error) {
      console.error('Failed to load distribution status counts:', error);
    }
  };

  const loadPendingReceiptForMeCount = async () => {
    const queryVersion = queryVersionRef.current;
    const currentUserId = String(user?.id || '');
    if (!currentUserId) {
      setPendingReceiptForMeCount(0);
      return;
    }

    try {
      const response = await distributionsAPI.getDistributions({
        page: 1,
        page_size: 1,
        status: 'pending_receipt',
        to_user_id: currentUserId,
      });
      if (queryVersion !== queryVersionRef.current) return;
      const total = Number(response?.pagination?.total || 0);
      setPendingReceiptForMeCount(Number.isFinite(total) ? total : 0);
    } catch (error) {
      console.error('Failed to load recipient pending receipt count:', error);
    }
  };

  const loadDistributions = async () => {
    const queryVersion = queryVersionRef.current;
    setLoading(true);
    try {
      const response = await distributionsAPI.getDistributions(buildDistributionParams());
      if (queryVersion !== queryVersionRef.current) return;

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setDistributions(rows);
      setTableTotalCount(total);
    } catch (error) {
      console.error('Failed to fetch distributions:', error);
      showToast('Failed to load distributions', 'error');
    } finally {
      setLoading(false);
    }
  };

  const resetAndLoadDistributions = async () => {
    queryVersionRef.current += 1;
    setDistributions([]);
    setTableTotalCount(0);
    setStatusCounts({ pending_receipt: 0, approved: 0, disputed: 0 });
    setPendingReceiptForMeCount(0);
    await Promise.all([
      loadDistributions(),
      loadDistributionStatusCounts(),
      loadPendingReceiptForMeCount(),
    ]);
  };

  const handleSearchSubmit = () => {
    const nextQuery = searchInput.trim();
    setAppliedSearch({ by: searchBy, query: nextQuery });
  };

  const handleSearchReset = () => {
    setSearchBy('all');
    setSearchInput('');
    setAppliedSearch({ by: 'all', query: '' });
  };

  const fetchDistributionSummary = async (requestId) => {
    const distributionId = selectedDist?._id || selectedDist?.id;
    if (!distributionId) return;

    try {
      setLoadingSummary(true);
      const response = await distributionsAPI.getDistributionDeviceSummary(distributionId);
      if (requestId !== summaryRequestIdRef.current) return;

      const data = response?.data || {};
      setDeviceSummary({
        device_types: Array.isArray(data.device_types) ? data.device_types : [],
        manufacturers: Array.isArray(data.manufacturers) ? data.manufacturers : [],
      });
    } catch (error) {
      console.error('Failed to fetch distribution device summary:', error);
      if (requestId === summaryRequestIdRef.current) {
        showToast(error.message || 'Failed to load device summary', 'error');
      }
    } finally {
      if (requestId === summaryRequestIdRef.current) {
        setLoadingSummary(false);
      }
    }
  };

  useEffect(() => {
    resetAndLoadDistributions();
  }, [appliedSearch, user?.id, dateRange]);

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: distributionKeys.all });
      resetAndLoadDistributions();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  useEffect(() => {
    if (showModal && selectedDist) {
      const requestId = ++summaryRequestIdRef.current;
      setDeviceSummary(null);
      fetchDistributionSummary(requestId);
    }
  }, [showModal, selectedDist]);

  const handleReceiptConfirm = async (received) => {
    if (!selectedDist) return;
    setReceiptSubmitting(true);
    try {
      await distributionsAPI.confirmReceipt(
        selectedDist._id || selectedDist.id,
        received,
        receiptNotes
      );
      const action = received ? 'Receipt confirmed — you can now redistribute the device(s)' : 'Dispute reported. Admin and manager have been notified.';
      showToast(action, received ? 'success' : 'warning');
      setShowReceiptModal(false);
      setShowModal(false);
      setReceiptNotes('');
      setSelectedDist(null);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to submit confirmation', 'error');
    } finally {
      setReceiptSubmitting(false);
    }
  };

  const canCreate = ['super_admin', 'manager', 'pdic_staff', 'sub_distributor', 'cluster', 'operator'].includes(user?.role);
  const isSubDistributionManager = user?.role === 'sub_distribution_manager';
  const canConfirmDisputedReturn = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const canRecipientIdentifierDownload =
    (
      ['super_admin', 'manager', 'pdic_staff'].includes(user?.role) ||
      (
        ['sub_distributor', 'cluster', 'operator'].includes(user?.role) &&
        selectedDist &&
        String(selectedDist.to_user_id) === String(user?.id)
      )
    );

  const handleDownloadMacNuidExport = async (format = 'csv') => {
    if (!selectedDist) return;

    try {
      const distributionId = selectedDist._id || selectedDist.id;
      const response = await distributionsAPI.downloadMacNuidExport(distributionId, format);
      const blob = response.blob;
      const disposition = response.contentDisposition || '';

      let fileName = `${selectedDist.distribution_id || 'distribution'}-mac-nuid.${format}`;
      const fileNameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
      if (fileNameMatch?.[1]) {
        fileName = fileNameMatch[1];
      }

      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);

      showToast(`Downloaded ${format.toUpperCase()} distribution details export`, 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download distribution details export', 'error');
    }
  };

  const handleConfirmDisputedReturn = async (dist) => {
    try {
      await distributionsAPI.confirmDisputedReturn(
        dist._id || dist.id,
        'PDIC confirmed devices are physically back with sender'
      );
      showToast('Disputed return confirmed and devices unlocked for redistribution', 'success');
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to confirm disputed return', 'error');
    }
  };

  const distributionInsights = useMemo(() => {
    const typeCounts = {};
    const manufacturerCounts = {};
    let setupBoxCount = 0;
    let totalDevices = 0;

    (deviceSummary?.device_types || []).forEach(([type, count]) => {
      const typeLabel = toDisplayLabel(type);
      const numericCount = Number(count) || 0;
      typeCounts[typeLabel] = (typeCounts[typeLabel] || 0) + numericCount;
      totalDevices += numericCount;
      if (isSetupBoxType(typeLabel)) {
        setupBoxCount += numericCount;
      }
    });

    (deviceSummary?.manufacturers || []).forEach(([manufacturer, count]) => {
      const manufacturerLabel = toDisplayLabel(manufacturer);
      manufacturerCounts[manufacturerLabel] = (manufacturerCounts[manufacturerLabel] || 0) + (Number(count) || 0);
    });

    const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
    const sortedManufacturers = Object.entries(manufacturerCounts).sort((a, b) => b[1] - a[1]);

    return {
      totalSent: selectedDist?.device_count || 0,
      loadedDetailsCount: totalDevices,
      setupBoxCount,
      types: sortedTypes,
      manufacturers: sortedManufacturers,
    };
  }, [deviceSummary, selectedDist]);

  const columns = [
    { key: 'distribution_id', label: 'Distribution ID' },
    { key: 'from_user_name', label: 'From' },
    { key: 'to_user_name', label: 'To' },
    { key: 'device_count', label: 'Devices', render: (value, row) => value || row.device_ids?.length || 0 },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    { key: 'created_at', label: 'Created', render: (value) => value ? new Date(value).toLocaleDateString() : '-' },
    {
      key: 'confirmed_by_name',
      label: 'Confirmed By',
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
            title="View Details"
          >
            <Eye className="w-4 h-4" />
          </button>
          {row.status === 'pending_receipt' && String(row.to_user_id) === String(user?.id) && !isSubDistributionManager && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedDist(row);
                setReceiptNotes('');
                setShowReceiptModal(true);
              }}
              className="p-1 text-orange-600 hover:bg-orange-50 rounded"
              title="Confirm or dispute receipt"
            >
              <PackageCheck className="w-4 h-4" />
            </button>
          )}
          {row.status === 'disputed' && canConfirmDisputedReturn && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleConfirmDisputedReturn(row);
              }}
              className="p-1 text-red-700 hover:bg-red-50 rounded"
              title="Confirm devices are back"
            >
              <CheckCircle className="w-4 h-4" />
            </button>
          )}
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Distributions</h1>
          <p className="text-gray-500 mt-1">Manage device distributions across the chain</p>
        </div>
        {canCreate && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <Link to="/distributions/bulk-upload">
              <Button variant="outline" icon={Upload} className="w-full sm:w-auto justify-center">Bulk Upload</Button>
            </Link>
            <Link to="/distributions/create">
              <Button icon={Plus} className="w-full sm:w-auto justify-center">Create Distribution</Button>
            </Link>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      {/* Pending Receipt Alert Banner */}
      {pendingReceiptForMeCount > 0 && (
        <div className="flex items-start gap-3 p-4 bg-orange-50 border border-orange-300 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-orange-800">
              You have {pendingReceiptForMeCount} distribution{pendingReceiptForMeCount > 1 ? 's' : ''} awaiting your receipt confirmation
            </p>
            <p className="text-sm text-orange-700 mt-1">
              You cannot redistribute these devices until you confirm receipt. Click the orange{' '}
              <PackageCheck className="inline w-4 h-4" /> icon on each row to confirm or dispute.
            </p>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-xl font-bold text-gray-800">{tableTotalCount || distributions.length}</p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <PackageCheck className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Awaiting Receipt</p>
              <p className="text-xl font-bold text-orange-600">
                {statusCounts.pending_receipt}
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
              <p className="text-sm text-gray-500">Confirmed</p>
              <p className="text-xl font-bold text-green-600">
                {statusCounts.approved}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Disputed</p>
              <p className="text-xl font-bold text-red-600">
                {statusCounts.disputed}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Card className="!p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Search Distributions</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-3">
            <select
              value={searchBy}
              onChange={(e) => setSearchBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {SEARCH_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-6">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
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
          <span className="ml-3 text-gray-500">Loading distributions...</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={distributions}
          searchable={false}
          pageSize={TABLE_PAGE_SIZE}
          pagination={false}
          totalItems={tableTotalCount || distributions.length}
          getExportRows={getExportRows}
          onRowClick={(row) => {
            setSelectedDist(row);
            setShowModal(true);
          }}
        />
      )}

      {/* View Distribution Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          summaryRequestIdRef.current += 1;
          setShowModal(false);
          setSelectedDist(null);
          setDeviceSummary(null);
        }}
        title="Distribution Details"
        size="lg"
        footer={
          <div className="flex gap-3">
            {selectedDist?.status === 'pending_receipt' && String(selectedDist?.to_user_id) === String(user?.id) && (
              <Button
                icon={PackageCheck}
                onClick={() => { setShowReceiptModal(true); }}
                className="bg-orange-500 hover:bg-orange-600 text-white"
              >
                Confirm Receipt
              </Button>
            )}
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
          </div>
        }
      >
        {selectedDist && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center">
                <Truck className="w-8 h-8 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-800">{selectedDist.distribution_id}</h3>
                <p className="text-gray-500">{getSenderDisplayName(selectedDist)} → {selectedDist.to_user_name}</p>
                <StatusBadge status={selectedDist.status} />
              </div>
              {canRecipientIdentifierDownload && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    icon={Download}
                    onClick={() => handleDownloadMacNuidExport('csv')}
                  >
                    Download CSV
                  </Button>
                  <Button
                    variant="outline"
                    icon={Download}
                    onClick={() => handleDownloadMacNuidExport('xlsx')}
                  >
                    Download Excel
                  </Button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Created At</label>
                <p className="font-medium text-gray-800">{selectedDist.created_at ? new Date(selectedDist.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device Count</label>
                <p className="font-medium text-gray-800">{selectedDist.device_count || selectedDist.device_ids?.length || 0}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Confirmed By</label>
                <p className="font-medium text-gray-800">{selectedDist.confirmed_by_name || selectedDist.from_user_name || 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Transfer Date</label>
                <p className="font-medium text-gray-800">
                  {selectedDist.date_of_distribution
                    ? new Date(selectedDist.date_of_distribution).toLocaleDateString()
                    : selectedDist.request_date
                      ? new Date(selectedDist.request_date).toLocaleDateString()
                      : selectedDist.created_at
                        ? new Date(selectedDist.created_at).toLocaleDateString()
                        : 'N/A'}
                </p>
              </div>
            </div>

            {selectedDist.notes && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Notes</label>
                <p className="text-gray-800 mt-1">{selectedDist.notes}</p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Total Sent</p>
                <p className="text-2xl font-bold text-blue-900 mt-1">{distributionInsights.totalSent}</p>
              </div>
              <div className="rounded-lg border border-green-100 bg-green-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-green-700">SB</p>
                <p className="text-2xl font-bold text-green-900 mt-1">{distributionInsights.setupBoxCount}</p>
              </div>
              <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">Total Devices</p>
                <p className="text-2xl font-bold text-amber-900 mt-1">{distributionInsights.loadedDetailsCount}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-gray-200 p-4 bg-white">
                <div className="flex items-center gap-2 mb-3">
                  <Layers3 className="w-4 h-4 text-indigo-600" />
                  <h4 className="text-sm font-semibold text-gray-800">By Device Type</h4>
                </div>
                {loadingSummary && !deviceSummary ? (
                  <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                    Loading device summary...
                  </div>
                ) : distributionInsights.types.length > 0 ? (
                  <div className="space-y-2">
                    {distributionInsights.types.map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
                        <span className="text-sm text-gray-700">{type}</span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No device type data available.</p>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 p-4 bg-white">
                <div className="flex items-center gap-2 mb-3">
                  <Factory className="w-4 h-4 text-rose-600" />
                  <h4 className="text-sm font-semibold text-gray-800">By Vendor</h4>
                </div>
                {loadingSummary && !deviceSummary ? (
                  <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                    Loading device summary...
                  </div>
                ) : distributionInsights.manufacturers.length > 0 ? (
                  <div className="space-y-2">
                    {distributionInsights.manufacturers.map(([manufacturer, count]) => (
                      <div key={manufacturer} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
                        <span className="text-sm text-gray-700">{manufacturer}</span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No vendor data available.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Receipt Confirmation Modal */}
      <Modal
        isOpen={showReceiptModal}
        onClose={() => { setShowReceiptModal(false); setReceiptNotes(''); }}
        title="Confirm Device Receipt"
        size="md"
        footer={null}
      >
        <div className="space-y-4">
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
            <p className="font-medium text-orange-900">
              Distribution: <span className="font-mono">{selectedDist?.distribution_id}</span>
            </p>
            <p className="text-sm text-orange-800 mt-1">
              Sent by <strong>{getSenderDisplayName(selectedDist)}</strong> — {selectedDist?.device_count || 0} device(s)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
            <textarea
              value={receiptNotes}
              onChange={e => setReceiptNotes(e.target.value)}
              rows={3}
              placeholder="Add any notes about receipt condition..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
            <strong>Note:</strong> You cannot redistribute these devices until you confirm receipt.
            If you select "Not Received", admin and manager will be alerted immediately.
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <Button
              variant="secondary"
              onClick={() => { setShowReceiptModal(false); setReceiptNotes(''); }}
              disabled={receiptSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              icon={XCircle}
              onClick={() => handleReceiptConfirm(false)}
              disabled={receiptSubmitting}
            >
              {receiptSubmitting ? 'Submitting...' : 'Not Received'}
            </Button>
            <Button
              icon={CheckCircle}
              onClick={() => handleReceiptConfirm(true)}
              disabled={receiptSubmitting}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {receiptSubmitting ? 'Confirming...' : 'Received'}
            </Button>
          </div>
        </div>
      </Modal>

    </div>
  );
};

export default Distributions;

