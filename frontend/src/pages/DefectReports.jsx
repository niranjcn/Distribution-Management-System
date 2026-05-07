import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { defectsAPI, devicesAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import {
  Plus, Eye, AlertTriangle, MessageSquare, Loader2, RefreshCw,
  Search, Link2, CheckCircle2, Bell, Package, Info, DollarSign
} from 'lucide-react';

const DEVICE_TYPE_OPTIONS = [
  'ONU',
  'ONT',
  'Router',
  'Switch',
  'Modem',
  'Access Point',
  'SB',
  'Other',
];

const BAND_TYPE_OPTIONS = [
  { value: 'single_band', label: 'Single Band' },
  { value: 'dual_band', label: 'Dual Band' },
];

const BOX_TYPE_OPTIONS = ['HD', 'OTT'];

const normalizeDeviceType = (deviceType) => {
  if (!deviceType) return 'ONT';
  const normalized = String(deviceType).trim().toLowerCase().replace(/[-_\s]+/g, '');
  if (normalized === 'settopbox' || normalized === 'setupbox' || normalized === 'sb' || normalized === 'stb') {
    return 'SB';
  }
  const match = DEVICE_TYPE_OPTIONS.find((option) => option.toLowerCase() === String(deviceType).toLowerCase());
  return match || 'Other';
};

const isSetupBoxType = (deviceType) => normalizeDeviceType(deviceType) === 'SB';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const TABLE_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'report_id', label: 'Report ID' },
  { value: 'device_serial', label: 'Device Serial' },
  { value: 'description', label: 'Description' },
  { value: 'defect_type', label: 'Defect Type' },
  { value: 'severity', label: 'Severity' },
  { value: 'status', label: 'Status' },
  { value: 'reported_by_name', label: 'Reported By' },
  { value: 'device_type', label: 'Device Type' },
];

const DEFECT_STATUS_CARD_CONFIG = ['reported', 'under_review', 'resolved'];

const DefectReports = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [defectReports, setDefectReports] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [statusCounts, setStatusCounts] = useState({
    reported: 0,
    under_review: 0,
    resolved: 0,
    critical: 0,
  });
  const [tablePage, setTablePage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedDefect, setSelectedDefect] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [reviewComment, setReviewComment] = useState('');
  const [replaceData, setReplaceData] = useState({ notes: '' });
  const [replaceReturnAmount, setReplaceReturnAmount] = useState('');
  const [replaceServiceCharge, setReplaceServiceCharge] = useState('');
  const [replacePaymentBillFile, setReplacePaymentBillFile] = useState(null);
  const [replacementMode, setReplacementMode] = useState('existing');
  const [replacementFilter, setReplacementFilter] = useState('all');
  const [availableDevices, setAvailableDevices] = useState([]);
  const [loadingAvailableDevices, setLoadingAvailableDevices] = useState(false);
  const [replacementSearch, setReplacementSearch] = useState('');
  const [replacementDeviceType, setReplacementDeviceType] = useState('all');
  const [selectedReplacementDeviceId, setSelectedReplacementDeviceId] = useState('');
  const [selectedReplacementDevice, setSelectedReplacementDevice] = useState(null);
  const [tableSearchBy, setTableSearchBy] = useState('all');
  const [tableSearchInput, setTableSearchInput] = useState('');
  const [appliedTableSearch, setAppliedTableSearch] = useState({ by: 'all', query: '' });
  const [newDeviceData, setNewDeviceData] = useState({
    device_type: 'ONT',
    model: '',
    manufacturer: '',
    serial_number: '',
    mac_address: '',
    band_type: 'single_band',
    box_type: 'HD',
    nuid: ''
  });
  const [confirmPaymentNotes, setConfirmPaymentNotes] = useState('');
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

  const buildDefectParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
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

  const buildDefectCountParams = (extraParams = {}) => {
    const params = {
      page: 1,
      page_size: 1,
      ...extraParams,
    };
    if (appliedTableSearch.query) {
      params.search = appliedTableSearch.query;
      if (appliedTableSearch.by && appliedTableSearch.by !== 'all') {
        params.search_by = appliedTableSearch.by;
      }
    }
    return params;
  };

  const loadDefectStatusCounts = async () => {
    const queryVersion = queryVersionRef.current;
    try {
      const statusResponses = await Promise.all(
        DEFECT_STATUS_CARD_CONFIG.map((status) => defectsAPI.getDefects(buildDefectCountParams({ status })))
      );
      const criticalResponse = await defectsAPI.getDefects(buildDefectCountParams({ severity: 'critical' }));
      if (queryVersion !== queryVersionRef.current) return;

      const nextCounts = DEFECT_STATUS_CARD_CONFIG.reduce((acc, status, index) => {
        const total = Number(statusResponses[index]?.pagination?.total || 0);
        acc[status] = Number.isFinite(total) ? total : 0;
        return acc;
      }, {});
      const criticalTotal = Number(criticalResponse?.pagination?.total || 0);
      nextCounts.critical = Number.isFinite(criticalTotal) ? criticalTotal : 0;

      setStatusCounts(nextCounts);
    } catch (error) {
      console.error('Failed to load defect status counts:', error);
    }
  };

  const loadDefectWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoading(true);

    try {
      const response = await defectsAPI.getDefects(buildDefectParams(windowPage));
      if (queryVersion !== queryVersionRef.current) return;

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setDefectReports((prev) => {
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
      console.error('Failed to fetch defects:', error);
      showToast('Failed to load defect reports', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoading(false);
    }
  };

  const resetAndLoadDefects = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setDefectReports([]);
    setTableTotalCount(0);
    setStatusCounts({ reported: 0, under_review: 0, resolved: 0, critical: 0 });
    setTablePage(1);
    await Promise.all([
      loadDefectWindow(1, { reset: true, withLoading: true }),
      loadDefectStatusCounts(),
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
    const loadedPages = Math.max(1, Math.ceil(defectReports.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && defectReports.length < tableTotalCount;
    if (needsNextWindow) {
      await loadDefectWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  useEffect(() => {
    resetAndLoadDefects();
  }, [appliedTableSearch]);

  useEffect(() => {
    setTablePage(1);
  }, [replacementFilter]);

  const canReport = ['operator', 'sub_distributor', 'cluster'].includes(user?.role);
  const canReview = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const canConfirmPayment = ['super_admin', 'manager'].includes(user?.role);
  const canForwardToManagement = user?.role === 'sub_distributor';
  const canReplace = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const canConfirmReplacement = ['operator', 'cluster', 'sub_distributor'].includes(user?.role);

  const getDefectId = (defect) => String(defect?._id || defect?.id || '');

  const handleForwardToManagement = async (defect) => {
    const id = getDefectId(defect);
    try {
      await defectsAPI.forwardToManagement(id, 'Forwarded by sub distributor for manager/admin review');
      showToast('Defect forwarded to manager/admin successfully', 'success');
      setShowReviewModal(false);
      setReviewComment('');
      resetAndLoadDefects();
    } catch (error) {
      showToast(error.message || 'Failed to forward defect', 'error');
    }
  };

  // Pending replacements for operators (defects where they need to confirm receipt)
  const pendingConfirmations = defectReports.filter(
    (d) =>
      d.status === 'replacement_pending_confirmation' &&
      (String(d.reported_by) === String(user?.id) ||
        String(d?.defective_device?.current_holder_id) === String(user?.id))
  );

  const urgentDefects = defectReports.filter(
    (d) => d.status === 'reported' && ['critical', 'high'].includes(String(d.severity || '').toLowerCase())
  );

  const reviewQueue = defectReports.filter((d) => d.status === 'reported');

  const pendingDefectiveReturnReceipts = defectReports.filter(
    (d) => d.status === 'approved' && d.auto_return_id && d.auto_return_status !== 'received'
  );

  const pendingReplacementAssignment = defectReports.filter(
    (d) => d.status === 'approved' && !d.replacement_device_id
  );

  const openReplaceModal = async (row) => {
    setSelectedDefect(row);
    setReplacementMode('existing');
    setReplaceData({ notes: '' });
    setReplaceReturnAmount(row?.return_amount != null ? String(row.return_amount) : '');
    setReplaceServiceCharge(row?.service_charge != null ? String(row.service_charge) : '');
    setReplacePaymentBillFile(null);
    setReplacementSearch('');
    setReplacementDeviceType(normalizeDeviceType(row?.device_type));
    setSelectedReplacementDeviceId('');
    setSelectedReplacementDevice(null);
    setNewDeviceData({
      device_type: normalizeDeviceType(row?.device_type),
      model: '',
      manufacturer: '',
      serial_number: '',
      mac_address: '',
      band_type: 'single_band',
      box_type: 'HD',
      nuid: ''
    });
    setShowReplaceModal(true);
    await fetchAvailableReplacementDevices(row);
  };

  const fetchAvailableReplacementDevices = async (row) => {
    try {
      setLoadingAvailableDevices(true);
      // Use the dedicated management endpoint which returns all available/returned devices
      const response = await devicesAPI.getDevicesForReplacement(row?.device_id || null);
      setAvailableDevices(response.data || []);
    } catch (error) {
      console.error('Failed to load available devices:', error);
      showToast('Failed to load available replacement devices', 'error');
      setAvailableDevices([]);
    } finally {
      setLoadingAvailableDevices(false);
    }
  };

  const applyReplacementFilter = (rows) => {
    if (replacementFilter === 'pending') {
      return rows.filter((defect) => defect.status === 'approved' || defect.status === 'replacement_pending_confirmation');
    }
    if (replacementFilter === 'replaced') {
      return rows.filter((defect) => defect.status === 'resolved' && Boolean(defect.replacement_device_id));
    }
    return rows;
  };

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await defectsAPI.getDefects(buildDefectParams(page, EXPORT_PAGE_SIZE));
      const rows = Array.isArray(response?.data) ? response.data : [];
      total = Number(response?.pagination?.total || rows.length);
      collected = collected.concat(rows);

      if (!rows.length || collected.length >= total) {
        break;
      }

      page += 1;
    }

    return applyReplacementFilter(collected);
  };

  const filteredDefectReports = applyReplacementFilter(defectReports);

  const selectableReplacementDevices = availableDevices.filter((device) => {
    if (
      replacementDeviceType !== 'all' &&
      normalizeDeviceType(device.device_type) !== normalizeDeviceType(replacementDeviceType)
    ) {
      return false;
    }
    if (!replacementSearch) {
      return true;
    }
    const query = replacementSearch.toLowerCase();
    return [device.device_id, device.serial_number, device.mac_address, device.model, device.manufacturer, device.nuid]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  const renderPaymentStatus = (row) => {
    const amount = Number(row?.return_amount || 0);
    const dueName = row?.payment_due_user_name || row?.reported_by_name || 'N/A';

    if (amount <= 0) {
      return <span className="text-xs text-gray-500">N/A</span>;
    }

    if (row?.payment_confirmed) {
      const confirmer = row?.payment_confirmed_by_name || 'Management';
      return (
        <div className="text-xs">
          <span className="inline-flex items-center px-2 py-1 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 font-semibold">
            Confirmed
          </span>
          <p className="text-gray-500 mt-1">By: {confirmer}</p>
        </div>
      );
    }

    return (
      <div className="text-xs">
        <span className="inline-flex items-center px-2 py-1 rounded border border-amber-200 bg-amber-50 text-amber-700 font-semibold">
          Pending Payment
        </span>
        <p className="text-gray-500 mt-1">Due To: {dueName}</p>
      </div>
    );
  };

  const columns = [
    {
      key: 'device_name',
      label: 'Device',
      render: (value, row) => (
        <DeviceIdentity device={{ ...row, model: value || row.model }} />
      )
    },
    { key: 'defect_type', label: 'Type' },
    {
      key: 'severity',
      label: 'Severity',
      render: (value) => <StatusBadge status={value} size="sm" />
    },
    { key: 'reported_by_name', label: 'Reported By' },
    { key: 'created_at', label: 'Date', render: (value) => value ? new Date(value).toLocaleDateString() : '-' },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    {
      key: 'payment_status',
      label: 'Payment Status',
      render: (_, row) => renderPaymentStatus(row)
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex flex-col gap-2 min-w-[220px]">
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedDefect(row);
                setShowModal(true);
              }}
              className="p-1 text-blue-600 hover:bg-blue-50 rounded"
              title="View Details"
            >
              <Eye className="w-4 h-4" />
            </button>
            {canReview && row.status === 'reported' && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedDefect(row);
                  setShowReviewModal(true);
                }}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
                title="Review Defect"
              >
                <MessageSquare className="w-4 h-4" />
              </button>
            )}
            {canForwardToManagement &&
              row.status === 'reported' &&
              row.report_target === 'sub_distributor' &&
              !row.forwarded_to_management && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedDefect(row);
                  setShowReviewModal(true);
                }}
                className="px-2 py-1 text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 rounded"
                title="Forward to Manager/Admin"
              >
                Forward
              </button>
            )}
            {canReplace && row.status === 'approved' && (!row.auto_return_id || row.auto_return_status === 'received') && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  openReplaceModal(row);
                }}
                className="p-1 text-purple-600 hover:bg-purple-50 rounded"
                title="Replace Device"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
            {canConfirmReplacement &&
              row.status === 'replacement_pending_confirmation' &&
              (String(row.reported_by) === String(user?.id) ||
                String(row?.defective_device?.current_holder_id) === String(user?.id)) && (
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    try {
                      await defectsAPI.confirmReplacementReceipt(row._id || row.id);
                      showToast('Replacement receipt confirmed! The device is now active in your account.', 'success');
                      resetAndLoadDefects();
                    } catch (error) {
                      showToast(error.message || 'Failed to confirm replacement receipt', 'error');
                    }
                  }}
                  className="flex items-center gap-1 px-2 py-1 bg-emerald-600 text-white text-xs font-medium rounded hover:bg-emerald-700 transition-colors"
                  title="Confirm Replacement Receipt"
                >
                  <CheckCircle2 className="w-3 h-3" />
                  Confirm
                </button>
              )}
            {canConfirmPayment &&
              Number(row.return_amount || 0) > 0 &&
              !row.payment_confirmed &&
              row.auto_return_status === 'received' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleConfirmPayment(row);
                  }}
                  className="flex items-center gap-1 px-2 py-1 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors"
                  title="Confirm payment"
                >
                  <DollarSign className="w-3 h-3" />
                  Confirm Payment
                </button>
              )}
          </div>

        </div>
      )
    }
  ];

  const handleReview = async (action) => {
    try {
      await defectsAPI.updateDefectStatus(
        selectedDefect._id || selectedDefect.id,
        action,
        reviewComment
      );
      showToast(
        action === 'approved'
          ? 'Defect approved — return request automatically created'
          : 'Defect report rejected',
        action === 'approved' ? 'success' : 'warning'
      );
      setShowReviewModal(false);
      setReviewComment('');
      resetAndLoadDefects();
    } catch (error) {
      showToast(error.message || 'Failed to update defect report', 'error');
    }
  };

  const handleConfirmPayment = async (defectRow) => {
    try {
      await defectsAPI.confirmPayment(defectRow._id || defectRow.id, confirmPaymentNotes);
      showToast('Payment confirmed successfully', 'success');
      setConfirmPaymentNotes('');
      resetAndLoadDefects();
      if (selectedDefect && String(selectedDefect._id || selectedDefect.id) === String(defectRow._id || defectRow.id)) {
        setShowModal(false);
      }
    } catch (error) {
      showToast(error.message || 'Failed to confirm payment', 'error');
    }
  };

  const handleOpenPaymentBill = async (defectRow) => {
    const billPath = defectRow?.payment_bill_url;
    if (!billPath) return;
    try {
      const { blob } = await defectsAPI.fetchPaymentBillBlob(billPath);
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (error) {
      showToast(error.message || 'Failed to open bill file', 'error');
    }
  };

  const handleReplace = async () => {
    if (replacementMode === 'existing' && !selectedReplacementDeviceId) {
      showToast('Select an existing replacement device first', 'error');
      return;
    }

    if (replacementMode === 'new') {
      const requiredFields = ['device_type', 'model', 'manufacturer'];
      if (!isSetupBoxType(newDeviceData.device_type)) {
        requiredFields.push('serial_number', 'mac_address');
      }
      const missingField = requiredFields.find((field) => !newDeviceData[field]);
      if (missingField) {
        showToast('Fill all required fields for new device registration', 'error');
        return;
      }

      if (isSetupBoxType(newDeviceData.device_type) && !String(newDeviceData.nuid || '').trim()) {
        showToast('NUID is required for SB replacement devices', 'error');
        return;
      }
      if (isSetupBoxType(newDeviceData.device_type) && !BOX_TYPE_OPTIONS.includes(String(newDeviceData.box_type || '').toUpperCase())) {
        showToast('Box Type must be HD or OTT for SB replacement devices', 'error');
        return;
      }
    }

    const cleanedNewDeviceData = {
      ...newDeviceData,
      model: String(newDeviceData.model || '').trim(),
      manufacturer: String(newDeviceData.manufacturer || '').trim(),
      serial_number: isSetupBoxType(newDeviceData.device_type) ? '' : String(newDeviceData.serial_number || '').trim(),
      mac_address: isSetupBoxType(newDeviceData.device_type) ? '' : String(newDeviceData.mac_address || '').trim(),
      band_type: isSetupBoxType(newDeviceData.device_type) ? null : newDeviceData.band_type,
      box_type: isSetupBoxType(newDeviceData.device_type) ? String(newDeviceData.box_type || '').toUpperCase() : null,
      nuid: String(newDeviceData.nuid || '').trim() || undefined,
    };

    const sameDeviceId = selectedDefect?.device_id ? String(selectedDefect.device_id) : '';

    const payload = {
      notes: replaceData.notes || undefined,
      ...(replacementMode === 'existing'
        ? { replacement_device_id: selectedReplacementDeviceId }
        : replacementMode === 'same'
        ? { replacement_device_id: sameDeviceId }
        : { register_device: cleanedNewDeviceData })
    };

    const shouldSendDueAmount = replacementMode !== 'same';
    const amountValue = shouldSendDueAmount
      ? (replaceReturnAmount === '' ? null : Number(replaceReturnAmount))
      : null;
    if (amountValue !== null && (!Number.isFinite(amountValue) || amountValue < 0)) {
      showToast('Enter a valid due amount', 'error');
      return;
    }

    const shouldSendServiceCharge = replacementMode === 'same';
    const serviceChargeValue = shouldSendServiceCharge
      ? (replaceServiceCharge === '' ? null : Number(replaceServiceCharge))
      : null;
    if (serviceChargeValue !== null && (!Number.isFinite(serviceChargeValue) || serviceChargeValue < 0)) {
      showToast('Enter a valid service charge amount', 'error');
      return;
    }

    try {
      let uploadedBillUrl = null;
      if (replacePaymentBillFile) {
        const uploadRes = await defectsAPI.uploadPaymentBill(selectedDefect._id || selectedDefect.id, replacePaymentBillFile);
        uploadedBillUrl = uploadRes?.data?.payment_bill_url || null;
      }

      const finalPayload = {
        ...payload,
        ...(amountValue !== null ? { return_amount: amountValue } : {}),
        ...(serviceChargeValue !== null ? { service_charge: serviceChargeValue } : {}),
        ...(uploadedBillUrl ? { payment_bill_url: uploadedBillUrl } : {}),
      };
      await defectsAPI.replaceDevice(selectedDefect._id || selectedDefect.id, finalPayload);
      const deviceLabel =
        replacementMode === 'existing' && selectedReplacementDevice
          ? `${selectedReplacementDevice.device_id} (${selectedReplacementDevice.serial_number})`
          : replacementMode === 'same'
          ? `Serviced same device (${selectedDefect?.defective_device?.device_id || selectedDefect?.device_serial || 'N/A'})`
          : replacementMode === 'new'
          ? `New ${cleanedNewDeviceData.device_type} (${cleanedNewDeviceData.serial_number})`
          : 'selected device';
      showToast(
        `Replacement assigned: ${deviceLabel}. Operator will receive an alert and must confirm receipt before it appears in their account.`,
        'success'
      );
      setShowReplaceModal(false);
      setReplaceData({ notes: '' });
      setReplaceReturnAmount('');
      setReplaceServiceCharge('');
      setReplacePaymentBillFile(null);
      resetAndLoadDefects();
    } catch (error) {
      showToast(error.message || 'Failed to replace device', 'error');
    }
  };

  return (
    <div className="space-y-6">
      {/* Operator Pending Replacement Alert Banner */}
      {canConfirmReplacement && pendingConfirmations.length > 0 && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-300 rounded-xl">
          <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
            <Bell className="w-5 h-5 text-amber-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-amber-900">
              {pendingConfirmations.length === 1
                ? 'You have a replacement device waiting for your confirmation!'
                : `You have ${pendingConfirmations.length} replacement devices waiting for confirmation!`}
            </p>
            <p className="text-sm text-amber-700 mt-1">
              A replacement device has been assigned for your defective device. Please confirm receipt to activate it in your account.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {pendingConfirmations.map((d) => (
                <div key={d.id} className="flex items-center gap-2 bg-amber-100 border border-amber-200 rounded-lg px-3 py-2">
                  <Package className="w-4 h-4 text-amber-700 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-amber-900">{d.report_id}</p>
                    <p className="text-xs text-amber-700">
                      Replacement: {d.replacement_device?.device_id || d.replacement_device?.serial_number || 'Assigned'}
                    </p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        await defectsAPI.confirmReplacementReceipt(d._id || d.id);
                        showToast('Replacement receipt confirmed! The device is now active in your account.', 'success');
                        resetAndLoadDefects();
                      } catch (error) {
                        showToast(error.message || 'Failed to confirm replacement receipt', 'error');
                      }
                    }}
                    className="ml-2 flex items-center gap-1 px-3 py-1 bg-emerald-600 text-white text-xs font-medium rounded-lg hover:bg-emerald-700 transition-colors"
                  >
                    <CheckCircle2 className="w-3 h-3" />
                    Confirm Receipt
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {(canReview || canReplace) && (
        <div className="space-y-3">
          {(urgentDefects.length > 0 || reviewQueue.length > 0) && (
            <div className="p-4 rounded-xl border border-red-300 bg-red-50">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <p className="font-semibold text-red-900">Defect Attention Center</p>
              </div>
              <p className="text-sm text-red-800">
                {urgentDefects.length} urgent defects and {reviewQueue.length} total reports need review.
              </p>
              <div className="mt-3 space-y-2">
                {urgentDefects.slice(0, 4).map((item) => (
                  <div key={item._id || item.id} className="flex items-center justify-between p-2 rounded bg-white border border-red-200">
                    <div>
                      <p className="text-sm font-medium text-gray-800">{item.report_id} • {item.device_name || item.device_type || 'Device'}</p>
                      <p className="text-xs text-gray-500">{item.reported_by_name || 'Unknown'} • {item.defect_type || 'Defect'}</p>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedDefect(item);
                        setShowReviewModal(true);
                      }}
                      className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700"
                    >
                      Review Now
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {pendingDefectiveReturnReceipts.length > 0 && (
            <div className="p-4 rounded-xl border border-amber-300 bg-amber-50">
              <div className="flex items-center gap-2 mb-2">
                <Bell className="w-5 h-5 text-amber-600" />
                <p className="font-semibold text-amber-900">Defective Device Return Pending</p>
              </div>
              <p className="text-sm text-amber-800">
                {pendingDefectiveReturnReceipts.length} approved defects are waiting for defective-device return receipt at PDIC.
              </p>
              <div className="mt-3 space-y-2">
                {pendingDefectiveReturnReceipts.slice(0, 4).map((item) => (
                  <div key={item._id || item.id} className="p-2 rounded bg-white border border-amber-200">
                    <p className="text-sm font-medium text-gray-800">{item.report_id} • Return {item.auto_return_id}</p>
                    <p className="text-xs text-gray-500">Status: {item.auto_return_status || 'pending'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {pendingReplacementAssignment.length > 0 && (
            <div className="p-4 rounded-xl border border-purple-300 bg-purple-50">
              <div className="flex items-center gap-2 mb-2">
                <RefreshCw className="w-5 h-5 text-purple-600" />
                <p className="font-semibold text-purple-900">Replacement Assignment Queue</p>
              </div>
              <p className="text-sm text-purple-800">
                {pendingReplacementAssignment.length} defective devices are approved and waiting for replacement assignment.
              </p>
              <div className="mt-3">
                <Link
                  to="/replacements/pending"
                  className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded bg-purple-700 text-white hover:bg-purple-800"
                >
                  Open Pending Replacement Page
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Defect Reports</h1>
          <p className="text-gray-500 mt-1">View and manage device defect reports</p>
        </div>
        {canReport && (
          <Link to="/defects/create">
            <Button icon={Plus}>Report Defect</Button>
          </Link>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Total</p>
          <p className="text-2xl font-bold text-gray-800">{tableTotalCount || defectReports.length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Open</p>
          <p className="text-2xl font-bold text-yellow-600">
            {statusCounts.reported}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Under Review</p>
          <p className="text-2xl font-bold text-blue-600">
            {statusCounts.under_review}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Resolved</p>
          <p className="text-2xl font-bold text-green-600">
            {statusCounts.resolved}
          </p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Critical</p>
          <p className="text-2xl font-bold text-red-600">
            {statusCounts.critical}
          </p>
        </Card>
      </div>

      <Card className="!p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Search Defects</h3>
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
          <span className="ml-3 text-gray-500">Loading defect reports...</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={filteredDefectReports}
          searchable={false}
          pageSize={TABLE_PAGE_SIZE}
          totalItems={replacementFilter === 'all' ? (tableTotalCount || filteredDefectReports.length) : filteredDefectReports.length}
          currentPage={tablePage}
          onPageChange={handleTablePageChange}
          getExportRows={getExportRows}
          actions={
            <div className="flex items-center gap-2">
              <button
                onClick={() => setReplacementFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  replacementFilter === 'all'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setReplacementFilter('pending')}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  replacementFilter === 'pending'
                    ? 'bg-yellow-500 text-white border-yellow-500'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                Pending Replacement
              </button>
              <button
                onClick={() => setReplacementFilter('replaced')}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  replacementFilter === 'replaced'
                    ? 'bg-green-600 text-white border-green-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                Replaced
              </button>
            </div>
          }
          onRowClick={(row) => {
            setSelectedDefect(row);
            setShowModal(true);
          }}
        />
      )}

      {/* View Defect Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedDefect(null);
        }}
        title="Defect Report Details"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
            {canReview && selectedDefect?.status === 'reported' && (
              <Button onClick={() => {
                setShowModal(false);
                setShowReviewModal(true);
              }}>
                Review Defect
              </Button>
            )}
            {canForwardToManagement &&
              selectedDefect?.status === 'reported' &&
              selectedDefect?.report_target === 'sub_distributor' &&
              !selectedDefect?.forwarded_to_management && (
              <Button onClick={() => {
                setShowModal(false);
                setShowReviewModal(true);
              }}>
                Forward to Manager/Admin
              </Button>
            )}
            {canConfirmReplacement &&
              selectedDefect?.status === 'replacement_pending_confirmation' &&
              (String(selectedDefect?.reported_by) === String(user?.id) ||
                String(selectedDefect?.defective_device?.current_holder_id) === String(user?.id)) && (
              <Button
                onClick={async () => {
                  try {
                    await defectsAPI.confirmReplacementReceipt(selectedDefect._id || selectedDefect.id);
                    showToast('Replacement receipt confirmed! The device is now active in your account.', 'success');
                    setShowModal(false);
                    resetAndLoadDefects();
                  } catch (error) {
                    showToast(error.message || 'Failed to confirm replacement receipt', 'error');
                  }
                }}
              >
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Confirm Replacement Receipt
              </Button>
            )}
            {canConfirmPayment &&
              Number(selectedDefect?.return_amount || 0) > 0 &&
              !selectedDefect?.payment_confirmed &&
              selectedDefect?.auto_return_status === 'received' && (
              <Button onClick={() => handleConfirmPayment(selectedDefect)}>
                <DollarSign className="w-4 h-4 mr-2" />
                Confirm Payment
              </Button>
            )}
          </>
        }
      >
        {selectedDefect && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-red-50 rounded-lg">
              <div className="w-16 h-16 bg-red-100 rounded-xl flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-red-600" />
              </div>
              <div className="flex-1">
                <DeviceIdentity device={selectedDefect} />
                <div className="flex gap-2 mt-2">
                  <StatusBadge status={selectedDefect.severity} />
                  <StatusBadge status={selectedDefect.status} />
                </div>
              </div>
            </div>

            {/* Pending confirmation notice */}
            {selectedDefect.status === 'replacement_pending_confirmation' && (
              <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <Bell className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-amber-900">Replacement Device Ready</p>
                  <p className="text-sm text-amber-700 mt-0.5">
                    A replacement device has been assigned. The recipient must confirm receipt for it to be activated.
                  </p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Defect Type</label>
                <p className="font-medium text-gray-800">{selectedDefect.defect_type}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Reported By</label>
                <p className="font-medium text-gray-800">{selectedDefect.reported_by_name || 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Reported At</label>
                <p className="font-medium text-gray-800">{selectedDefect.created_at ? new Date(selectedDefect.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Location</label>
                <p className="font-medium text-gray-800">{selectedDefect.location || 'N/A'}</p>
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider">Description</label>
              <p className="text-gray-800 mt-1 p-3 bg-gray-50 rounded-lg">{selectedDefect.description}</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-xs text-red-600 uppercase tracking-wider mb-2 font-semibold">🔴 Defective Device</p>
                <DeviceIdentity device={selectedDefect?.defective_device || selectedDefect} />
                <p className="text-sm text-red-800">Status: {selectedDefect?.defective_device?.status || 'defective'}</p>
              </div>

              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-xs text-green-600 uppercase tracking-wider mb-2 font-semibold">🟢 Replacement Device</p>
                {selectedDefect?.replacement_device ? (
                  <>
                    <DeviceIdentity device={selectedDefect.replacement_device} />
                    <p className="text-sm text-green-800">
                      Status: {selectedDefect.status === 'resolved' ? '✅ Confirmed & Active' : '⏳ Awaiting Confirmation'}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-green-800 italic">No replacement assigned yet.</p>
                )}
              </div>
            </div>

            {selectedDefect.auto_return_id && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <label className="text-xs text-green-600 uppercase tracking-wider">Auto-Created Return Request</label>
                <p className="font-medium text-green-800 mt-1">{selectedDefect.auto_return_id}</p>
              </div>
            )}

            {Number(selectedDefect.return_amount || 0) > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                <label className="text-xs text-amber-700 uppercase tracking-wider">Payment Due Tracking</label>
                <p className="font-semibold text-amber-900">Amount Due: {Number(selectedDefect.return_amount).toFixed(2)}</p>
                <p className="text-sm text-amber-800">Due User: {selectedDefect.payment_due_user_name || selectedDefect.reported_by_name || 'N/A'}</p>
                <p className="text-sm text-amber-800">
                  Payment Status: {selectedDefect.payment_confirmed ? 'Confirmed' : 'Pending Confirmation'}
                </p>
                {selectedDefect.payment_bill_url && (
                  <button
                    onClick={() => handleOpenPaymentBill(selectedDefect)}
                    className="text-sm px-3 py-1.5 rounded bg-amber-700 text-white hover:bg-amber-800"
                  >
                    View Uploaded Bill
                  </button>
                )}
              </div>
            )}

            {selectedDefect.resolution && (
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                <label className="text-xs text-purple-600 uppercase tracking-wider">Replacement Mapping Note</label>
                <p className="font-medium text-purple-800 mt-1">{selectedDefect.resolution}</p>
              </div>
            )}

            {selectedDefect.images && selectedDefect.images.length > 0 && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Photos</label>
                <div className="grid grid-cols-3 gap-2">
                  {selectedDefect.images.map((photo, index) => (
                    <div key={index} className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center">
                      <span className="text-xs text-gray-500">{photo}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedDefect.review_comments && (
              <div className="p-4 bg-blue-50 rounded-lg">
                <label className="text-xs text-blue-600 uppercase tracking-wider">Review Comments</label>
                <p className="text-gray-800 mt-1">{selectedDefect.review_comments}</p>
                <p className="text-xs text-gray-500 mt-2">By: {selectedDefect.reviewed_by_name || 'N/A'}</p>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Review Modal */}
      <Modal
        isOpen={showReviewModal}
        onClose={() => {
          setShowReviewModal(false);
          setReviewComment('');
        }}
        title="Review Defect Report"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowReviewModal(false)}>Cancel</Button>
            {canReview && (
              <>
                <Button variant="danger" onClick={() => handleReview('rejected')}>Reject</Button>
                <Button onClick={() => handleReview('approved')}>Approve &amp; Initiate Return</Button>
              </>
            )}
            {canForwardToManagement &&
              selectedDefect?.report_target === 'sub_distributor' &&
              !selectedDefect?.forwarded_to_management && (
              <Button onClick={() => handleForwardToManagement(selectedDefect)}>Forward to Manager/Admin</Button>
            )}
          </>
        }
      >
        <div className="space-y-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="font-medium text-gray-800">{selectedDefect?.device_name || selectedDefect?.device_type || 'Unknown'}</p>
            <p className="text-sm text-gray-500">{selectedDefect?.defect_type} - {selectedDefect?.severity}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Review Comments <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reviewComment}
              onChange={(e) => setReviewComment(e.target.value)}
              rows={4}
              placeholder="Add your review comments..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            {canReview ? (
              <p className="text-sm text-yellow-800">
                Approving this defect will automatically create a return request for the device.
              </p>
            ) : (
              <p className="text-sm text-yellow-800">
                Forward this routed defect so it appears in manager/admin review queue.
              </p>
            )}
          </div>

        </div>
      </Modal>

      {/* Replace Device Modal */}
      <Modal
        isOpen={showReplaceModal}
        onClose={() => {
          setShowReplaceModal(false);
          setReplaceData({ notes: '' });
          setReplaceReturnAmount('');
          setReplaceServiceCharge('');
          setReplacePaymentBillFile(null);
          setSelectedReplacementDevice(null);
          setSelectedReplacementDeviceId('');
        }}
        title="Replace Defective Device"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowReplaceModal(false)}>Cancel</Button>
            <Button onClick={handleReplace}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Assign Replacement
            </Button>
          </>
        }
      >
        <div className="space-y-5">
          {/* Defective device summary */}
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-xs text-red-600 uppercase tracking-wider font-semibold mb-2">🔴 Defective Device Being Replaced</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <div><span className="text-gray-500">ID:</span> <span className="font-medium text-red-900">{selectedDefect?.defective_device?.device_id || selectedDefect?.device_serial || 'N/A'}</span></div>
              <div><span className="text-gray-500">Type:</span> <span className="font-medium text-red-900">{selectedDefect?.device_type || selectedDefect?.defective_device?.device_type || 'N/A'}</span></div>
              <div><span className="text-gray-500">Serial:</span> <span className="font-medium text-red-900">{selectedDefect?.defective_device?.serial_number || 'N/A'}</span></div>
              <div><span className="text-gray-500">Operator:</span> <span className="font-medium text-red-900">{selectedDefect?.reported_by_name || 'N/A'}</span></div>
            </div>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setReplacementMode('existing');
                setSelectedReplacementDevice(null);
                setSelectedReplacementDeviceId('');
              }}
              className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                replacementMode === 'existing'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              Select Existing Device
            </button>
            <button
              type="button"
              onClick={() => {
                setReplacementMode('same');
                setSelectedReplacementDevice(null);
                setSelectedReplacementDeviceId('');
              }}
              className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                replacementMode === 'same'
                  ? 'bg-amber-600 text-white border-amber-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              Use Same Device (Serviced)
            </button>
            <button
              type="button"
              onClick={() => {
                setReplacementMode('new');
                setSelectedReplacementDevice(null);
                setSelectedReplacementDeviceId('');
              }}
              className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                replacementMode === 'new'
                  ? 'bg-emerald-600 text-white border-emerald-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              Register New Device
            </button>
          </div>

          {replacementMode === 'existing' ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Type</label>
                  <select
                    value={replacementDeviceType}
                    onChange={(e) => setReplacementDeviceType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  >
                    <option value="all">All Types</option>
                    {DEVICE_TYPE_OPTIONS.map((deviceType) => (
                      <option key={deviceType} value={deviceType}>{deviceType}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={replacementSearch}
                      onChange={(e) => setReplacementSearch(e.target.value)}
                      placeholder="ID, serial, MAC, model..."
                      className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="max-h-52 overflow-y-auto border border-gray-200 rounded-lg divide-y divide-gray-100">
                {loadingAvailableDevices ? (
                  <div className="p-4 flex items-center gap-2 text-sm text-gray-500">
                    <Loader2 className="w-4 h-4 animate-spin" /> Loading available devices...
                  </div>
                ) : selectableReplacementDevices.length === 0 ? (
                  <div className="p-4 text-sm text-gray-500 text-center">
                    <Info className="w-5 h-5 mx-auto mb-1 text-gray-400" />
                    No available devices found in stock.
                  </div>
                ) : (
                  selectableReplacementDevices.map((device) => (
                    <label
                      key={device.id}
                      className={`flex items-start gap-3 p-3 cursor-pointer transition-colors ${
                        String(selectedReplacementDeviceId) === String(device.id)
                          ? 'bg-blue-50 border-l-4 border-l-blue-600'
                          : 'bg-white hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="replacement_device"
                        checked={String(selectedReplacementDeviceId) === String(device.id)}
                        onChange={() => {
                          setSelectedReplacementDeviceId(String(device.id));
                          setSelectedReplacementDevice(device);
                        }}
                        className="mt-1"
                      />
                      <div className="text-sm flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-semibold text-gray-800">{device.device_id}</p>
                          <StatusBadge status={device.device_type} size="sm" />
                          <StatusBadge status={device.status} size="sm" />
                        </div>
                        <DeviceIdentity device={device} className="mt-1" />
                        <p className="text-gray-600 mt-0.5">{device.manufacturer || 'Unknown Vendor'}</p>
                        {device.nuid && <p className="text-gray-500 text-xs">NUID: {device.nuid}</p>}
                      </div>
                    </label>
                  ))
                )}
              </div>

              {/* Selected device preview */}
              {selectedReplacementDevice && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-xs text-blue-600 uppercase tracking-wider font-semibold mb-2">🟢 Selected Replacement Details</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    <div><span className="text-gray-500">Device ID:</span> <span className="font-semibold text-blue-900">{selectedReplacementDevice.device_id}</span></div>
                    <div><span className="text-gray-500">Vendor:</span> <span className="font-medium text-blue-900">{selectedReplacementDevice.manufacturer || 'N/A'}</span></div>
                    <div className="col-span-2"><DeviceIdentity device={selectedReplacementDevice} /></div>
                    <div>
                      <span className="text-gray-500">{isSetupBoxType(selectedReplacementDevice.device_type) ? 'Box Type:' : 'Band:'}</span>{' '}
                      <span className="font-medium text-blue-900">
                        {isSetupBoxType(selectedReplacementDevice.device_type)
                          ? (selectedReplacementDevice.box_type || selectedReplacementDevice.metadata?.box_type || 'N/A')
                          : (selectedReplacementDevice.band_type || 'N/A')}
                      </span>
                    </div>
                    <div><span className="text-gray-500">NUID:</span> <span className="font-medium text-blue-900">{selectedReplacementDevice.nuid || 'N/A'}</span></div>
                    <div><span className="text-gray-500">Status:</span> <span className="font-medium text-blue-900">{selectedReplacementDevice.status}</span></div>
                    <div><span className="text-gray-500">Current Holder:</span> <span className="font-medium text-blue-900">{selectedReplacementDevice.current_holder_name || 'PDIC (Stock)'}</span></div>
                  </div>
                </div>
              )}
            </div>
          ) : replacementMode === 'same' ? (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs text-amber-600 uppercase tracking-wider font-semibold mb-2">🛠️ Serviced Same Device</p>
              <p className="text-sm text-amber-900">
                This keeps the same defective device and marks it as serviced after operator confirmation.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-600 font-medium">Enter details for the new device to register and assign as replacement:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Device Type <span className="text-red-500">*</span></label>
                  <select
                    value={newDeviceData.device_type}
                    onChange={(e) => {
                      const nextType = e.target.value;
                      setNewDeviceData(prev => ({
                        ...prev,
                        device_type: nextType,
                        nuid: isSetupBoxType(nextType) ? prev.nuid : ''
                      }));
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {DEVICE_TYPE_OPTIONS.map((deviceType) => (
                      <option key={deviceType} value={deviceType}>{deviceType}</option>
                    ))}
                  </select>
                </div>

                {!isSetupBoxType(newDeviceData.device_type) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Band Type <span className="text-red-500">*</span></label>
                  <select
                    value={newDeviceData.band_type}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, band_type: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {BAND_TYPE_OPTIONS.map((band) => (
                      <option key={band.value} value={band.value}>{band.label}</option>
                    ))}
                  </select>
                </div>
                )}

                {isSetupBoxType(newDeviceData.device_type) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Box Type <span className="text-red-500">*</span></label>
                  <select
                    value={newDeviceData.box_type}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, box_type: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {BOX_TYPE_OPTIONS.map((boxType) => (
                      <option key={boxType} value={boxType}>{boxType}</option>
                    ))}
                  </select>
                </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Model <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={newDeviceData.model}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, model: e.target.value }))}
                    placeholder="e.g. EchoLife HG8145"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Vendor <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={newDeviceData.manufacturer}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, manufacturer: e.target.value }))}
                    placeholder="e.g. Huawei"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {!isSetupBoxType(newDeviceData.device_type) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Serial Number <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={newDeviceData.serial_number}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, serial_number: e.target.value }))}
                    placeholder="e.g. SN-12345678"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                )}

                {!isSetupBoxType(newDeviceData.device_type) && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">MAC Address <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={newDeviceData.mac_address}
                    onChange={(e) => setNewDeviceData(prev => ({ ...prev, mac_address: e.target.value }))}
                    placeholder="e.g. AA:BB:CC:DD:EE:FF"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                )}

                {isSetupBoxType(newDeviceData.device_type) && (
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">NUID <span className="text-red-500">*</span></label>
                    <input
                      type="text"
                      value={newDeviceData.nuid}
                      onChange={(e) => setNewDeviceData(prev => ({ ...prev, nuid: e.target.value }))}
                      placeholder="e.g. NUID-00021"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Replacement Notes (Optional)
            </label>
            <textarea
              value={replaceData.notes}
              onChange={(e) => setReplaceData(prev => ({ ...prev, notes: e.target.value }))}
              rows={2}
              placeholder="Add any note for this replacement mapping..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {replacementMode !== 'same' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Due Amount (Optional)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={replaceReturnAmount}
                  onChange={(e) => setReplaceReturnAmount(e.target.value)}
                  placeholder="Set amount user should pay"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
            {replacementMode === 'same' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Service Charge (Optional)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={replaceServiceCharge}
                  onChange={(e) => setReplaceServiceCharge(e.target.value)}
                  placeholder="Set service charge amount"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Upload Bill (Optional)</label>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                onChange={(e) => setReplacePaymentBillFile(e.target.files?.[0] || null)}
                className="w-full text-sm"
              />
              {replacePaymentBillFile && (
                <p className="text-xs text-gray-500 mt-1">Selected: {replacePaymentBillFile.name}</p>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg border border-indigo-200 bg-indigo-50 text-sm text-indigo-900 flex items-start gap-2">
            <Link2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>
              After assignment, the operator will receive an alert. The replacement device will only appear in their account
              after they confirm receipt. The defective device remains tracked in its own section.
            </span>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default DefectReports;

