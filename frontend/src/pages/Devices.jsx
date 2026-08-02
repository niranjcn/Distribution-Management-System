import { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import { devicesAPI, defectsAPI, changeRequestsAPI } from '../services/api';
import DateRangeFilter, { buildDateParams } from '../components/ui/DateRangeFilter';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { useQueryClient } from '@tanstack/react-query';
import { deviceKeys } from '../hooks';
import { Plus, Eye, Edit, Trash2, Box, Upload, Loader2, Users, Send, ArrowDownToLine, Link2, AlertTriangle, CheckCircle2, Save, Filter, Building2, Network, Factory, Search } from 'lucide-react';

const normalizeDeviceType = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  if (normalized === 'settopbox' || normalized === 'setupbox' || normalized === 'sb' || normalized === 'stb') {
    return 'SB';
  }
  return value;
};

const isSbDeviceType = (value) => normalizeDeviceType(value) === 'SB';

const asDisplayValue = (value) => {
  const text = String(value ?? '').trim();
  return text ? text : 'N/A';
};

const extractBoxType = (device) => {
  if (device?.box_type) return String(device.box_type).toUpperCase();
  return null;
};

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'nuid', label: 'NUID' },
  { value: 'mac_address', label: 'MAC Address' },
  { value: 'serial_number', label: 'Serial Number' },
  { value: 'manufacturer', label: 'Vendor' },
  { value: 'device_type', label: 'Type' },
  { value: 'model', label: 'Model' },
  { value: 'device_id', label: 'Device ID' },
];

const Devices = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [bulkSelectedIds, setBulkSelectedIds] = useState([]);
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false);
  const [bulkDeleteReason, setBulkDeleteReason] = useState('');
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [overview, setOverview] = useState(null);
  const [holderInsights, setHolderInsights] = useState({ sub_distributors: [], clusters: [] });
  const [tableRows, setTableRows] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [tableLoading, setTableLoading] = useState(false);
  const [defectsData, setDefectsData] = useState([]);
  const [replacementMap, setReplacementMap] = useState({ replacementIds: new Set(), defectiveIds: new Set(), defectByDeviceId: {} });
  const [loading, setLoading] = useState(true);
  const [deviceMeta, setDeviceMeta] = useState({ loaded_count: 0, total_count: 0, has_next: false, show_all: false });
  const [activeTab, setActiveTab] = useState('all');
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [searchBy, setSearchBy] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [appliedSearch, setAppliedSearch] = useState({ by: 'all', query: '' });
  const [tableFilters, setTableFilters] = useState({
    device_type: '',
    manufacturer: '',
    status: '',
    sub_distributor_id: '',
    cluster_id: '',
  });
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const tableQueryVersionRef = useRef(0);

  const deviceTypeOptions = ['ONT', 'ONU', 'OLT', 'Router', 'Switch', 'Modem', 'Access Point', 'SB', 'Other'];
  const bandTypeOptions = [
    { value: 'single_band', label: 'Single Band' },
    { value: 'dual_band', label: 'Dual Band' },
  ];

  // Edit form state
  const [editForm, setEditForm] = useState({
    model: '',
    manufacturer: '',
    serial_number: '',
    mac_address: '',
    device_type: 'ONT',
    band_type: 'single_band',
    box_type: 'HD',
    nuid: '',
    current_location: '',
  });
  const [editSubmitting, setEditSubmitting] = useState(false);

  const isManagement = ['super_admin', 'md_director', 'manager', 'pdic_staff'].includes(user?.role);
  const hasHierarchy = ['sub_distribution_manager', 'sub_distributor', 'cluster'].includes(user?.role);
  const isAllDevicesView = isManagement && activeTab === 'all';
  const canRegister = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const isStaff = user?.role === 'pdic_staff';
  const isAdminOrManager = ['super_admin', 'manager'].includes(user?.role);
  const canDeleteDevice = ['super_admin', 'manager'].includes(user?.role);

  const queryFingerprint = useMemo(() => {
    const filterPayload = isAllDevicesView
      ? tableFilters
      : {
          device_type: '',
          manufacturer: '',
          status: '',
          sub_distributor_id: '',
          cluster_id: '',
        };
    return JSON.stringify({
      scope: hasHierarchy ? activeTab : 'all',
      filters: filterPayload,
      search: appliedSearch,
      dateRange,
    });
  }, [activeTab, appliedSearch, hasHierarchy, isAllDevicesView, tableFilters, dateRange]);

  const loadOverviewCards = async () => {
    const response = await devicesAPI.getMyOverview({ page: 1, page_size: 1 });
    setOverview(response?.data || null);
  };

  const loadDefectMappings = async () => {
    const defectsResponse = await defectsAPI.getDefects({ page_size: 100 });
    const replacementIds = new Set();
    const defectiveIds = new Set();
    const defectByDeviceId = {};
    for (const defect of defectsResponse.data || []) {
      if (defect.replacement_device_id) {
        replacementIds.add(String(defect.replacement_device_id));
        defectiveIds.add(String(defect.device_id));
        defectByDeviceId[String(defect.replacement_device_id)] = defect;
        defectByDeviceId[String(defect.device_id)] = defect;
      } else if (defect.device_id) {
        defectByDeviceId[String(defect.device_id)] = defect;
        if (defect.status !== 'resolved') defectiveIds.add(String(defect.device_id));
      }
    }
    setDefectsData(defectsResponse.data || []);
    setReplacementMap({ replacementIds, defectiveIds, defectByDeviceId });
  };

  const loadHolderInsights = async () => {
    if (!isManagement) {
      setHolderInsights({ sub_distributors: [], clusters: [] });
      return;
    }
    const response = await devicesAPI.getManagementHolderInsights();
    setHolderInsights(response?.data || { sub_distributors: [], clusters: [] });
  };

  const buildTableQueryParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      paginate: true,
      page: windowPage,
      page_size: pageSize,
      scope: hasHierarchy ? activeTab : 'all',
      ...buildDateParams(dateRange),
    };

    if (isAllDevicesView) {
      if (tableFilters.device_type) params.device_type = tableFilters.device_type;
      if (tableFilters.manufacturer) params.manufacturer = tableFilters.manufacturer;
      if (tableFilters.status) params.status = tableFilters.status;
      if (tableFilters.sub_distributor_id) params.sub_distributor_id = tableFilters.sub_distributor_id;
      if (tableFilters.cluster_id) params.cluster_id = tableFilters.cluster_id;
    }

    if (appliedSearch.query) {
      params.search = appliedSearch.query;
      if (appliedSearch.by && appliedSearch.by !== 'all') {
        params.search_by = appliedSearch.by;
      }
    }

    return params;
  };

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await devicesAPI.getMyOverview(buildTableQueryParams(page, EXPORT_PAGE_SIZE));
      const rows = Array.isArray(response?.data?.all_under_me) ? response.data.all_under_me : [];
      const meta = response?.data?.meta || {};
      total = Number(meta.total_count || rows.length);
      collected = collected.concat(rows);

      if (!rows.length || collected.length >= total) {
        break;
      }

      page += 1;
    }

    return collected;
  };

  const loadTableWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = tableQueryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setTableLoading(true);

    try {
      const response = await devicesAPI.getMyOverview(buildTableQueryParams(windowPage));
      if (queryVersion !== tableQueryVersionRef.current) {
        return;
      }
      const rows = Array.isArray(response?.data?.all_under_me) ? response.data.all_under_me : [];
      const meta = response?.data?.meta || {};
      const totalCount = Number(meta.total_count || rows.length);

      setTableRows((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        setDeviceMeta({
          loaded_count: unique.length,
          total_count: totalCount,
          has_next: unique.length < totalCount,
          show_all: false,
        });
        return unique;
      });

      setTableTotalCount(totalCount);
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setTableLoading(false);
    }
  };

  const resetAndLoadTable = async () => {
    tableQueryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setTableRows([]);
    setTableTotalCount(0);
    setTablePage(1);
    await loadTableWindow(1, { reset: true, withLoading: true });
  };

  useEffect(() => {
    if (!user?.role) return;
    const run = async () => {
      try {
        setLoading(true);
        await Promise.all([loadOverviewCards(), loadDefectMappings(), loadHolderInsights()]);
      } catch (error) {
        console.error('Failed to load overview data:', error);
        showToast('Failed to load devices', 'error');
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [user?.role]);

  useEffect(() => {
    if (!user?.role) return;
    resetAndLoadTable();
  }, [user?.role, queryFingerprint]);

  const refreshAllData = async () => {
    try {
      setLoading(true);
      await Promise.all([loadOverviewCards(), loadDefectMappings(), loadHolderInsights()]);
      await resetAndLoadTable();
    } catch (error) {
      console.error('Failed to refresh devices:', error);
      showToast('Failed to refresh devices', 'error');
    } finally {
      setLoading(false);
    }
  };

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: deviceKeys.all });
      refreshAllData();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  const overviewStats = overview?.stats || {};

  const getEffectiveDeviceStatus = (device) => {
    const linked = replacementMap.defectByDeviceId[String(device.id)];
    if (
      linked &&
      String(linked.device_id) === String(device.id) &&
      Boolean(linked.replacement_device_id)
    ) {
      return 'replaced';
    }
    return device.status;
  };

  const displayedDevices = useMemo(() => {
    const getCategoryRank = (device) => {
      const id = String(device.id);
      if (replacementMap.replacementIds.has(id)) return 1;
      if (replacementMap.defectiveIds.has(id) || device.status === 'defective') return 2;
      return 0;
    };

    return [...tableRows].sort((a, b) => {
      const rankDiff = getCategoryRank(a) - getCategoryRank(b);
      if (rankDiff !== 0) return rankDiff;
      const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
      const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
      return bTime - aTime;
    });
  }, [replacementMap, tableRows]);

  const byTypeSummary = useMemo(() => {
    const aggregated = overview?.insights?.by_type;
    if (Array.isArray(aggregated) && aggregated.length > 0) {
      return aggregated
        .map((entry) => ({
          type: entry.type || 'Unknown',
          total: Number(entry.total || 0),
        }))
        .sort((a, b) => b.total - a.total);
    }

    return [];
  }, [overview?.insights?.by_type]);

  const subDistributorSummary = useMemo(() => {
    return Array.isArray(holderInsights?.sub_distributors) ? holderInsights.sub_distributors : [];
  }, [holderInsights?.sub_distributors]);

  const clusterSummary = useMemo(() => {
    return Array.isArray(holderInsights?.clusters) ? holderInsights.clusters : [];
  }, [holderInsights?.clusters]);

  const manufacturerSummary = useMemo(() => {
    const aggregated = overview?.insights?.by_vendor;
    if (Array.isArray(aggregated) && aggregated.length > 0) {
      return aggregated
        .map((item) => ({
          manufacturer: item.manufacturer || 'Unknown',
          total: Number(item.total || 0),
          distinctTypes: Number(item.distinctTypes || (Array.isArray(item.typeBreakdown) ? item.typeBreakdown.length : 0)),
          typeBreakdown: (item.typeBreakdown || [])
            .map((entry) => ({ type: entry.type || 'Unknown', count: Number(entry.count || 0) }))
            .sort((a, b) => b.count - a.count),
        }))
        .sort((a, b) => b.total - a.total);
    }

    return [];
  }, [overview?.insights?.by_vendor]);

  const holderOptionLabel = (item) => {
    const identities = Array.isArray(item?.digital_ids) ? item.digital_ids : [];
    const ids = identities.flatMap((di) => [di?.digital_id, di?.broadband_id]).filter(Boolean);
    return ids.length ? `${item.name} (${ids.join(', ')})` : item.name;
  };

  const filterOptions = useMemo(() => {
    const byType = Array.isArray(overview?.insights?.by_type) ? overview.insights.by_type : [];
    const byVendor = Array.isArray(overview?.insights?.by_vendor) ? overview.insights.by_vendor : [];
    const deviceTypes = [...new Set(byType.map((entry) => entry?.type).filter(Boolean))].sort();
    const manufacturers = [...new Set(byVendor.map((entry) => entry?.manufacturer).filter(Boolean))].sort();
    const subDistributors = subDistributorSummary.map((item) => ({ id: item.id, name: holderOptionLabel(item) }));
    const clusters = clusterSummary.map((item) => ({ id: item.id, name: holderOptionLabel(item) }));

    return { deviceTypes, manufacturers, subDistributors, clusters };
  }, [clusterSummary, overview?.insights?.by_type, overview?.insights?.by_vendor, subDistributorSummary]);

  const tableData = displayedDevices;

  const handleSearchSubmit = () => {
    const nextQuery = String(searchInput || '').trim();
    setAppliedSearch({ by: searchBy, query: nextQuery });
  };

  const handleSearchReset = () => {
    setSearchBy('all');
    setSearchInput('');
    setAppliedSearch({ by: 'all', query: '' });
  };

  const handleTablePageChange = (nextPage) => {
    setTablePage(nextPage);
    const requiredWindow = Math.ceil(nextPage / TABLE_WINDOW_PAGES);
    const loadedPageCount = Math.max(1, Math.ceil((tableRows.length || 0) / TABLE_PAGE_SIZE));
    const totalPageCount = Math.max(1, Math.ceil((tableTotalCount || 0) / TABLE_PAGE_SIZE));
    const totalWindows = Math.ceil((tableTotalCount || 0) / TABLE_WINDOW_SIZE);

    if (requiredWindow > loadedWindowRef.current) {
      loadTableWindow(requiredWindow, { reset: false, withLoading: false });
    }

    if (nextPage >= loadedPageCount && loadedPageCount < totalPageCount) {
      const nextWindow = loadedWindowRef.current + 1;
      if (nextWindow <= totalWindows && nextWindow > loadedWindowRef.current) {
        loadTableWindow(nextWindow, { reset: false, withLoading: false });
      }
    }
  };

  const getRowClassName = (row) => {
    const id = String(row.id);
    if (replacementMap.replacementIds.has(id)) return 'bg-emerald-50 border-l-4 border-l-emerald-400';
    if (replacementMap.defectiveIds.has(id) || row.status === 'defective') return 'bg-red-50 border-l-4 border-l-red-400';
    return '';
  };

  const openEditModal = (device) => {
    setSelectedDevice(device);
    setEditForm({
      model: device.model || '',
      manufacturer: device.manufacturer || '',
      serial_number: device.serial_number || '',
      mac_address: device.mac_address || '',
      device_type: normalizeDeviceType(device.device_type) || 'ONT',
      band_type: device.band_type || 'single_band',
      box_type: extractBoxType(device) || 'HD',
      nuid: device.nuid || '',
      current_location: device.current_location || '',
    });
    setShowEditModal(true);
  };

  const handleEditSubmit = async () => {
    const trimmedForm = {
      ...editForm,
      model: editForm.model?.trim() || '',
      manufacturer: editForm.manufacturer?.trim() || '',
      serial_number: editForm.serial_number?.trim() || '',
      mac_address: editForm.mac_address?.trim() || '',
      nuid: editForm.nuid?.trim() || '',
      current_location: editForm.current_location?.trim() || '',
    };

    if (!trimmedForm.model || !trimmedForm.manufacturer) {
      showToast('Model and Vendor are required.', 'error');
      return;
    }

    if (!isSbDeviceType(trimmedForm.device_type) && !trimmedForm.band_type) {
      showToast('Band Type is required for non-SB devices.', 'error');
      return;
    }

    if (!isSbDeviceType(trimmedForm.device_type) && (!trimmedForm.serial_number || !trimmedForm.mac_address)) {
      showToast('Serial Number and MAC Address are required for non-SB devices.', 'error');
      return;
    }

    if (isSbDeviceType(trimmedForm.device_type) && !trimmedForm.nuid) {
      showToast('NUID is required for SB devices.', 'error');
      return;
    }
    if (isSbDeviceType(trimmedForm.device_type) && !['HD', 'OTT'].includes(String(trimmedForm.box_type || '').toUpperCase())) {
      showToast('Box Type must be HD or OTT for SB devices.', 'error');
      return;
    }

    const updatePayload = {
      model: trimmedForm.model,
      manufacturer: trimmedForm.manufacturer,
      serial_number: isSbDeviceType(trimmedForm.device_type) ? null : trimmedForm.serial_number,
      mac_address: isSbDeviceType(trimmedForm.device_type) ? null : trimmedForm.mac_address,
      device_type: trimmedForm.device_type,
      band_type: isSbDeviceType(trimmedForm.device_type) ? null : trimmedForm.band_type,
      box_type: isSbDeviceType(trimmedForm.device_type) ? String(trimmedForm.box_type || '').toUpperCase() : null,
      nuid: isSbDeviceType(trimmedForm.device_type) ? trimmedForm.nuid : null,
      current_location: trimmedForm.current_location,
    };

    const hasChanges = Object.entries(updatePayload).some(([key, value]) => {
      const currentValue = selectedDevice?.[key] ?? null;
      return String(currentValue ?? '') !== String(value ?? '');
    });

    if (!hasChanges) {
      showToast('No changes detected.', 'info');
      return;
    }

    try {
      setEditSubmitting(true);
      if (isStaff) {
        // Staff must request approval — send notification to admins/managers
        await devicesAPI.requestDeviceEdit(selectedDevice.id, updatePayload);
        showToast('Edit request submitted. A manager or admin will review your proposed changes.', 'info');
      } else {
        // Admin/manager: apply directly
        await devicesAPI.updateDevice(selectedDevice.id, updatePayload);
        showToast('Device updated successfully.', 'success');
      }
      setShowEditModal(false);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to update device', 'error');
    } finally {
      setEditSubmitting(false);
    }
  };

  const columns = [
    {
      key: 'nuid',
      label: 'NUID',
      render: (value) => asDisplayValue(value),
    },
    {
      key: 'mac_address',
      label: 'MAC Address',
      render: (value, row) => (isSbDeviceType(row.device_type) ? 'N/A' : asDisplayValue(value)),
    },
    {
      key: 'serial_number',
      label: 'Serial Number',
      render: (value, row) => (isSbDeviceType(row.device_type) ? 'N/A' : asDisplayValue(value)),
    },
    { key: 'model', label: 'Model' },
    { key: 'manufacturer', label: 'Vendor' },
    {
      key: 'device_type',
      label: 'Type',
      render: (value) => <StatusBadge status={normalizeDeviceType(value)} size="sm" />
    },
    {
      key: 'status',
      label: 'Status',
      render: (_, row) => <StatusBadge status={getEffectiveDeviceStatus(row)} />
    },
    {
      key: 'replacement_relation',
      label: 'Relation',
      sortable: false,
      render: (_, row) => {
        const id = String(row.id);
        if (replacementMap.replacementIds.has(id)) {
          return <StatusBadge status="replacement" size="sm" />;
        }
        if (replacementMap.defectiveIds.has(id) || row.status === 'defective') {
          return <StatusBadge status="defective_device" size="sm" />;
        }
        return <span className="text-xs text-gray-500">Regular</span>;
      }
    },
    { key: 'current_holder_name', label: 'Current Holder', render: (value, row) => {
      if (value && value !== 'NOC') return value;
      if (!row.current_holder_type || row.current_holder_type === 'noc') return 'PDIC (Distribution)';
      return value || 'PDIC (Distribution)';
    } },
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
            title="View Details"
          >
            <Eye className="w-4 h-4" />
          </button>
          {canRegister && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  openEditModal(row);
                }}
                className="p-1 text-amber-600 hover:bg-amber-50 rounded"
                title={isStaff ? 'Request Edit (requires manager approval)' : 'Edit Device'}
              >
                <Edit className="w-4 h-4" />
              </button>
              {canDeleteDevice && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedDevice(row);
                    setShowDeleteModal(true);
                  }}
                  className="p-1 text-red-600 hover:bg-red-50 rounded"
                  title="Delete Device"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </>
          )}
        </div>
      )
    }
  ];

  const handleDelete = async () => {
    try {
      await devicesAPI.deleteDevice(selectedDevice.id);
      showToast(`Device ${selectedDevice.mac_address} deleted successfully`, 'success');
      setShowDeleteModal(false);
      setSelectedDevice(null);
      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast('Failed to delete device', 'error');
    }
  };

  const handleBulkDelete = async () => {
    if (bulkSelectedIds.length === 0) return;
    if (isStaff && !bulkDeleteReason.trim()) {
      showToast('A reason is required for staff delete requests', 'error');
      return;
    }
    setBulkDeleting(true);
    try {
      if (isStaff) {
        await changeRequestsAPI.submitDeviceDeleteRequest(bulkSelectedIds, bulkDeleteReason.trim());
        showToast(`Delete request submitted for ${bulkSelectedIds.length} device(s). A manager or admin will review.`, 'success');
      } else {
        const res = await devicesAPI.bulkDeleteDevices(bulkSelectedIds);
        showToast(res.message || `${res?.data?.deleted?.length || bulkSelectedIds.length} device(s) deleted successfully`, 'success');
      }
      setShowBulkDeleteModal(false);
      setBulkSelectedIds([]);
      setBulkDeleteReason('');
      window.dispatchEvent(new Event('appDataMutation'));
    } catch (error) {
      showToast(error.message || 'Failed to delete devices', 'error');
    } finally {
      setBulkDeleting(false);
    }
  };

  // Get the defect linked to the selected device (if any)
  const linkedDefect = selectedDevice
    ? replacementMap.defectByDeviceId[String(selectedDevice.id)]
    : null;
  const isReplacementDevice = selectedDevice ? replacementMap.replacementIds.has(String(selectedDevice.id)) : false;
  const selectedDeviceEffectiveStatus = selectedDevice ? getEffectiveDeviceStatus(selectedDevice) : null;
  const isDefectiveDevice = selectedDevice
    ? (
      (replacementMap.defectiveIds.has(String(selectedDevice.id)) || selectedDevice.status === 'defective') &&
      selectedDeviceEffectiveStatus !== 'replaced'
    )
    : false;

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Devices</h1>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">
            {isManagement ? 'All registered devices in the system'
              : hasHierarchy ? 'Devices across your entire distribution chain'
              : 'Your assigned devices'}
          </p>
        </div>
        {canRegister && (
          <div className="flex flex-col sm:flex-row gap-2">
            <Link to="/devices/bulk-import" className="w-full sm:w-auto">
              <Button variant="secondary" icon={Upload} className="w-full sm:w-auto">Bulk Import</Button>
            </Link>
            <Link to="/devices/register" className="w-full sm:w-auto">
              <Button icon={Plus} className="w-full sm:w-auto">Register Device</Button>
            </Link>
          </div>
        )}
      </div>

      {/* Stats Cards */}
      {!loading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {isManagement ? (
            <>
              <Card className="!p-4">
                <p className="text-sm text-gray-500">Total</p>
                <p className="text-2xl font-bold text-gray-800">{overviewStats.total ?? (overview?.all_under_me?.length || 0)}</p>
              </Card>
              <Card className="!p-4">
                <p className="text-sm text-gray-500">Available</p>
                <p className="text-2xl font-bold text-green-600">{overviewStats.available ?? (overview?.all_under_me || []).filter(d => d.status === 'available').length}</p>
              </Card>
              <Card className="!p-4">
                <p className="text-sm text-gray-500">Distributed</p>
                <p className="text-2xl font-bold text-blue-600">{(overviewStats.distributed ?? 0) + (overviewStats.in_use ?? 0) || (overview?.all_under_me || []).filter(d => d.status === 'distributed' || d.status === 'in_use').length}</p>
              </Card>
              <Card className="!p-4">
                <p className="text-sm text-gray-500">Defective</p>
                <p className="text-2xl font-bold text-red-600">{overviewStats.defective ?? (overview?.all_under_me || []).filter(d => d.status === 'defective').length}</p>
              </Card>
              <Card className="!p-4">
                <p className="text-sm text-gray-500">Returned</p>
                <p className="text-2xl font-bold text-orange-600">{overviewStats.returned ?? (overview?.all_under_me || []).filter(d => d.status === 'returned').length}</p>
              </Card>
            </>
          ) : (
            <>
              <Card className="!p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Box className="w-4 h-4 text-blue-500" />
                  <p className="text-xs text-gray-500">In My Hand</p>
                </div>
                <p className="text-2xl font-bold text-blue-600">{overviewStats.in_my_hand || 0}</p>
              </Card>
              {hasHierarchy && (
                <Card className="!p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Users className="w-4 h-4 text-purple-500" />
                    <p className="text-xs text-gray-500">Under My Chain</p>
                  </div>
                  <p className="text-2xl font-bold text-purple-600">{overviewStats.under_subordinates || 0}</p>
                </Card>
              )}
              <Card className="!p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Box className="w-4 h-4 text-gray-500" />
                  <p className="text-xs text-gray-500">Total in Chain</p>
                </div>
                <p className="text-2xl font-bold text-gray-700">{overviewStats.total_in_chain || 0}</p>
              </Card>
              <Card className="!p-4">
                <div className="flex items-center gap-2 mb-1">
                  <ArrowDownToLine className="w-4 h-4 text-green-500" />
                  <p className="text-xs text-gray-500">Total Received</p>
                </div>
                <p className="text-2xl font-bold text-green-600">{overviewStats.total_devices_received || 0}</p>
              </Card>
              <Card className="!p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Send className="w-4 h-4 text-orange-500" />
                  <p className="text-xs text-gray-500">Total Sent</p>
                </div>
                <p className="text-2xl font-bold text-orange-600">{overviewStats.total_devices_sent || 0}</p>
              </Card>
              <Card className="!p-4">
                <div className="flex items-center gap-2 mb-1">
                  <ArrowDownToLine className="w-4 h-4 text-indigo-500" />
                  <p className="text-xs text-gray-500">Transfers</p>
                </div>
                <p className="text-base font-bold text-indigo-600">
                  {overviewStats.total_distributions_received || 0} in / {overviewStats.total_distributions_sent || 0} out
                </p>
              </Card>
            </>
          )}
        </div>
      )}

      {/* Tabs for hierarchy roles */}
      {!loading && hasHierarchy && (
        <div className="flex border-b border-gray-200">
          {[
            { key: 'all', label: `All in Chain (${overviewStats.total_in_chain || 0})` },
            { key: 'mine', label: `In My Hand (${overviewStats.in_my_hand || 0})` },
            { key: 'hierarchy', label: `Under My Hierarchy (${overviewStats.under_subordinates || 0})` },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {!loading && isAllDevicesView && (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Card className="!p-4">
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-semibold text-gray-800">Sub Distribution Device Totals</h3>
              </div>
              {subDistributorSummary.length === 0 ? (
                <p className="text-sm text-gray-500">No devices currently held at sub distribution level.</p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {subDistributorSummary.map((item) => (
                    <div key={item.id} className="p-3 rounded-lg border border-gray-200 bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-medium text-gray-800 truncate pr-2">{item.name}</p>
                        <span className="text-sm font-semibold text-blue-700">{item.total}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {item.typeBreakdown.map((entry) => (
                          <span key={`${item.id}-${entry.type}`} className="px-2 py-0.5 text-xs rounded-full bg-white border border-gray-300 text-gray-700">
                            {entry.type}: {entry.count}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="!p-4">
              <div className="flex items-center gap-2 mb-3">
                <Network className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-semibold text-gray-800">Cluster Device Totals</h3>
              </div>
              {clusterSummary.length === 0 ? (
                <p className="text-sm text-gray-500">No devices currently held at cluster level.</p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {clusterSummary.map((item) => (
                    <div key={item.id} className="p-3 rounded-lg border border-gray-200 bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-medium text-gray-800 truncate pr-2">{item.name}</p>
                        <span className="text-sm font-semibold text-purple-700">{item.total}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {item.typeBreakdown.map((entry) => (
                          <span key={`${item.id}-${entry.type}`} className="px-2 py-0.5 text-xs rounded-full bg-white border border-gray-300 text-gray-700">
                            {entry.type}: {entry.count}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Card className="!p-4 xl:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <Box className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-semibold text-gray-800">Total By Device Type</h3>
              </div>
              {byTypeSummary.length === 0 ? (
                <p className="text-sm text-gray-500">No device type data found.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-1 gap-3 max-h-[30rem] overflow-y-auto pr-1">
                  {byTypeSummary.map((entry) => (
                    <div key={entry.type} className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                      <p className="text-sm font-semibold text-gray-700 mb-1">{entry.type}</p>
                      <p className="text-3xl font-bold text-gray-800 leading-none">{entry.total}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="!p-4 xl:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <Factory className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-semibold text-gray-800">Vendor Insights</h3>
              </div>
              {manufacturerSummary.length === 0 ? (
                <p className="text-sm text-gray-500">No vendor data found.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[30rem] overflow-y-auto pr-1">
                  {manufacturerSummary.map((item) => (
                    <div key={item.manufacturer} className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                        <p className="text-lg font-semibold text-gray-800 leading-tight">{item.manufacturer}</p>
                        <div className="text-right">
                          <p className="text-2xl font-bold text-gray-800 leading-none">{item.total}</p>
                          <p className="text-xs text-gray-600 font-medium">Types: {item.distinctTypes}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {item.typeBreakdown.map((entry) => (
                          <span key={`${item.manufacturer}-${entry.type}`} className="px-2.5 py-1 text-xs rounded-md bg-white border border-gray-300 text-gray-700 font-medium">
                            {entry.type}: {entry.count}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card className="!p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-semibold text-gray-800">Table Filters (ALL Devices)</h3>
              </div>
              <div className="flex items-center gap-2">
                <DateRangeFilter value={dateRange} onChange={setDateRange} />
                <Button
                  variant="secondary"
                  onClick={() => setShowAdvancedFilters((prev) => !prev)}
                  className="text-xs"
                >
                  {showAdvancedFilters ? 'Hide Filters' : 'Show Filters'}
                </Button>
              </div>
            </div>

            {showAdvancedFilters && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                <select
                  value={tableFilters.device_type}
                  onChange={(e) => setTableFilters((prev) => ({ ...prev, device_type: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">All Device Types</option>
                  {filterOptions.deviceTypes.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>

                <select
                  value={tableFilters.manufacturer}
                  onChange={(e) => setTableFilters((prev) => ({ ...prev, manufacturer: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">All Vendors</option>
                  {filterOptions.manufacturers.map((manufacturer) => (
                    <option key={manufacturer} value={manufacturer}>{manufacturer}</option>
                  ))}
                </select>

                <select
                  value={tableFilters.sub_distributor_id}
                  onChange={(e) => setTableFilters((prev) => ({ ...prev, sub_distributor_id: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">All Sub Distributions</option>
                  {filterOptions.subDistributors.map((entity) => (
                    <option key={entity.id} value={entity.id}>{entity.name}</option>
                  ))}
                </select>

                <select
                  value={tableFilters.cluster_id}
                  onChange={(e) => setTableFilters((prev) => ({ ...prev, cluster_id: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">All Clusters</option>
                  {filterOptions.clusters.map((entity) => (
                    <option key={entity.id} value={entity.id}>{entity.name}</option>
                  ))}
                </select>

                <div className="flex gap-2">
                  <select
                    value={tableFilters.status}
                    onChange={(e) => setTableFilters((prev) => ({ ...prev, status: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="">All Statuses</option>
                    <option value="available">available</option>
                    <option value="distributed">distributed</option>
                    <option value="in_use">in_use</option>
                    <option value="defective">defective</option>
                    <option value="replaced">replaced</option>
                    <option value="returned">returned</option>
                    <option value="maintenance">maintenance</option>
                  </select>
                  <Button
                    variant="secondary"
                    onClick={() => setTableFilters({
                      device_type: '',
                      manufacturer: '',
                      status: '',
                      sub_distributor_id: '',
                      cluster_id: '',
                    })}
                    className="whitespace-nowrap"
                  >
                    Reset
                  </Button>
                </div>
              </div>
            )}

            <p className="text-xs text-gray-500 mt-3">
              Loaded: {deviceMeta.loaded_count || tableData.length} / Total: {deviceMeta.total_count || overviewStats.total || tableData.length}
            </p>
          </Card>
        </>
      )}

      {loading || (tableLoading && tableData.length === 0) ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading devices...</span>
        </div>
      ) : (
        <>
          <Card className="!p-4">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-800">Search Devices</h3>
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
            <p className="text-xs text-gray-500 mt-3">
              Pattern search runs on the complete dataset (not only loaded rows).
            </p>
          </Card>

          {/* Color legend */}
          {(replacementMap.replacementIds.size > 0 || replacementMap.defectiveIds.size > 0) && (
            <div className="flex flex-wrap items-center gap-4 px-1 py-2 text-xs text-gray-500">
              <span className="font-medium text-gray-600">Row colours:</span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm bg-emerald-200 border border-emerald-400" />
                Replacement device
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm bg-red-200 border border-red-400" />
                Defective device
              </span>
            </div>
          )}
          <DataTable
            columns={columns}
            data={tableData}
            searchable={false}
            pageSize={TABLE_PAGE_SIZE}
            totalItems={tableTotalCount || tableData.length}
            currentPage={tablePage}
            onPageChange={handleTablePageChange}
            getExportRows={getExportRows}
            selectable={canRegister}
            onSelectionChange={setBulkSelectedIds}
            getRowClassName={getRowClassName}
            onRowClick={(row) => {
              setSelectedDevice(row);
              setShowModal(true);
            }}
          />
          {bulkSelectedIds.length > 0 && (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-blue-800">
                    {bulkSelectedIds.length} device(s) selected
                  </p>
                  <p className="text-xs text-blue-600">
                    {isStaff
                      ? 'Deletion requires manager/admin approval and will be submitted as a request.'
                      : 'Your changes will be applied immediately without approval.'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setBulkSelectedIds([])}>
                    Clear Selection
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => setShowBulkDeleteModal(true)}>
                    {isStaff ? 'Request Delete' : 'Delete Selected'}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

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
            {canRegister && (
              <Button variant="secondary" onClick={() => {
                setShowModal(false);
                openEditModal(selectedDevice);
              }}>
                <Edit className="w-4 h-4 mr-2" />
                Edit Device
              </Button>
            )}
            <Link to={`/track-device?q=${encodeURIComponent(selectedDevice?.serial_number || selectedDevice?.nuid || selectedDevice?.mac_address || '')}`}>
              <Button>Track Device</Button>
            </Link>
          </>
        }
      >
        {selectedDevice && (
          <div className="space-y-5">
            {/* Header with status */}
            <div className={`flex items-center gap-4 p-4 rounded-lg ${
              isReplacementDevice ? 'bg-emerald-50 border border-emerald-200' :
              isDefectiveDevice ? 'bg-red-50 border border-red-200' : 'bg-gray-50'
            }`}>
              <div className={`w-16 h-16 rounded-xl flex items-center justify-center ${
                isReplacementDevice ? 'bg-emerald-100' :
                isDefectiveDevice ? 'bg-red-100' : 'bg-blue-100'
              }`}>
                {isDefectiveDevice ? (
                  <AlertTriangle className="w-8 h-8 text-red-600" />
                ) : isReplacementDevice ? (
                  <CheckCircle2 className="w-8 h-8 text-emerald-600" />
                ) : (
                  <Box className="w-8 h-8 text-blue-600" />
                )}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedDevice.model || selectedDevice.device_type}</h3>
                <p className="text-gray-500">{selectedDevice.manufacturer || 'N/A'}</p>
                <div className="flex gap-2 mt-2 flex-wrap">
                  <StatusBadge status={selectedDeviceEffectiveStatus || selectedDevice.status} />
                  {isReplacementDevice && (
                    <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-full border border-emerald-300">
                      ✅ Replacement Device
                    </span>
                  )}
                  {isDefectiveDevice && !isReplacementDevice && (
                    <span className="px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-800 rounded-full border border-red-300">
                      🔴 Defective Device
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Core device info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">MAC Address</label>
                <p className="font-medium text-gray-800 font-mono">{isSbDeviceType(selectedDevice.device_type) ? 'N/A' : asDisplayValue(selectedDevice.mac_address)}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Serial Number</label>
                <p className="font-medium text-gray-800">{isSbDeviceType(selectedDevice.device_type) ? 'N/A' : asDisplayValue(selectedDevice.serial_number)}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device Type</label>
                <p className="font-medium text-gray-800">{normalizeDeviceType(selectedDevice.device_type)}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">
                  {(isSbDeviceType(selectedDevice.device_type) || Boolean(extractBoxType(selectedDevice))) ? 'Box Type' : 'Band Type'}
                </label>
                <p className="font-medium text-gray-800">
                  {(isSbDeviceType(selectedDevice.device_type) || Boolean(extractBoxType(selectedDevice)))
                    ? (extractBoxType(selectedDevice) || 'N/A')
                    : (selectedDevice.band_type ? selectedDevice.band_type.replace('_', ' ') : 'N/A')}
                </p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">NUID</label>
                <p className="font-medium text-gray-800">{asDisplayValue(selectedDevice.nuid)}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device ID</label>
                <p className="font-medium text-gray-800">{selectedDevice.device_id}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Current Location</label>
                <p className="font-medium text-gray-800">
                  {(() => {
                    const loc = selectedDevice.current_location;
                    if (!loc || loc === 'NOC' || loc === 'PDIC') return 'PDIC (Distribution)';
                    return loc;
                  })()}
                </p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Current Holder</label>
                <p className="font-medium text-gray-800">
                  {(() => {
                    const name = selectedDevice.current_holder_name;
                    const type = selectedDevice.current_holder_type;
                    if (!name || name === 'NOC' || (!name && type === 'noc')) return 'PDIC (Distribution)';
                    return name;
                  })()}
                </p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Created At</label>
                <p className="font-medium text-gray-800">{selectedDevice.created_at ? new Date(selectedDevice.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Registered By</label>
                <p className="font-medium text-gray-800">{selectedDevice.registered_by_name || 'N/A'}</p>
              </div>
            </div>

            {/* Replacement mapping section */}
            {linkedDefect && (
              <div className={`rounded-xl border-2 p-4 space-y-3 ${
                isReplacementDevice ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50'
              }`}>
                <div className="flex items-center gap-2">
                  <Link2 className={`w-4 h-4 flex-shrink-0 ${isReplacementDevice ? 'text-emerald-700' : 'text-red-700'}`} />
                  <p className={`text-sm font-semibold uppercase tracking-wider ${isReplacementDevice ? 'text-emerald-800' : 'text-red-800'}`}>
                    {isReplacementDevice ? 'Replacement Mapping — This is the Replacement Device' : 'Defect Mapping — This Device is Defective'}
                  </p>
                </div>
                <p className="text-xs text-gray-600">
                  Defect Report: <span className="font-semibold">{linkedDefect.report_id}</span> &middot; Status:{' '}
                  <StatusBadge status={linkedDefect.status} size="sm" />
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Defective device box */}
                  <div className="p-3 bg-red-100 border border-red-200 rounded-lg">
                    <p className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-1.5">🔴 Defective Device</p>
                    {linkedDefect.defective_device ? (
                      <>
                        <p className="text-sm font-semibold text-red-900">{linkedDefect.defective_device.device_id}</p>
                        {isSbDeviceType(linkedDefect.defective_device.device_type) ? (
                          <p className="text-xs text-red-800">NUID: {linkedDefect.defective_device.nuid || 'N/A'}</p>
                        ) : (
                          <>
                            <p className="text-xs text-red-800">Serial: {linkedDefect.defective_device.serial_number}</p>
                            <p className="text-xs text-red-800">MAC: {linkedDefect.defective_device.mac_address}</p>
                          </>
                        )}
                        <p className="text-xs text-red-800">Type: {linkedDefect.defective_device.device_type}</p>
                        <p className="text-xs text-red-800">Status: {linkedDefect.defective_device.status}</p>
                      </>
                    ) : (
                      <p className="text-xs text-red-700 italic">Details not available</p>
                    )}
                  </div>

                  {/* Replacement device box */}
                  <div className="p-3 bg-emerald-100 border border-emerald-200 rounded-lg">
                    <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wider mb-1.5">🟢 Replacement Device</p>
                    {linkedDefect.replacement_device ? (
                      <>
                        <p className="text-sm font-semibold text-emerald-900">{linkedDefect.replacement_device.device_id}</p>
                        {isSbDeviceType(linkedDefect.replacement_device.device_type) ? (
                          <p className="text-xs text-emerald-800">NUID: {linkedDefect.replacement_device.nuid || 'N/A'}</p>
                        ) : (
                          <>
                            <p className="text-xs text-emerald-800">Serial: {linkedDefect.replacement_device.serial_number}</p>
                            <p className="text-xs text-emerald-800">MAC: {linkedDefect.replacement_device.mac_address}</p>
                          </>
                        )}
                        <p className="text-xs text-emerald-800">Type: {linkedDefect.replacement_device.device_type}</p>
                        <p className="text-xs text-emerald-800">
                          Status: {linkedDefect.status === 'resolved' ? '✅ Confirmed & Active' : '⏳ Awaiting Confirmation'}
                        </p>
                      </>
                    ) : (
                      <p className="text-xs text-emerald-700 italic">No replacement assigned yet</p>
                    )}
                  </div>
                </div>

                {linkedDefect.resolution && (
                  <p className="text-xs text-gray-600 mt-1 italic">Note: {linkedDefect.resolution}</p>
                )}
              </div>
            )}

            {/* Full payload details */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">All Device Fields</label>
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="max-h-64 overflow-y-auto divide-y divide-gray-100">
                  {Object.entries(selectedDevice)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, value]) => {
                      let formattedValue = 'N/A';
                      if (value !== null && value !== undefined && value !== '') {
                        if (typeof value === 'object') {
                          try {
                            formattedValue = JSON.stringify(value);
                          } catch {
                            formattedValue = String(value);
                          }
                        } else {
                          formattedValue = String(value);
                        }
                      }

                      return (
                        <div key={key} className="grid grid-cols-12 gap-2 px-3 py-2 text-xs">
                          <p className="col-span-4 sm:col-span-3 font-semibold text-gray-600 break-all">{key}</p>
                          <p className="col-span-8 sm:col-span-9 text-gray-800 break-all">{formattedValue}</p>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Edit Device Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setSelectedDevice(null);
        }}
        title={isStaff ? 'Request Device Edit (Approval Required)' : 'Edit Device'}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowEditModal(false)}>Cancel</Button>
            <Button onClick={handleEditSubmit} disabled={editSubmitting}>
              {editSubmitting ? (
                <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Saving...</>
              ) : isStaff ? (
                <><Send className="w-4 h-4 mr-2" /> Submit for Approval</>
              ) : (
                <><Save className="w-4 h-4 mr-2" /> Save Changes</>
              )}
            </Button>
          </>
        }
      >
        {selectedDevice && (
          <div className="space-y-4">
            {/* Staff notice */}
            {isStaff && (
              <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm">
                  <p className="font-semibold text-amber-900">Approval Required</p>
                  <p className="text-amber-800 mt-0.5">
                    As a staff member, device edits require approval from a Manager or Admin before they take effect. Your request will be sent for review.
                  </p>
                </div>
              </div>
            )}

            {/* Device reference */}
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Editing Device</p>
              <p className="font-semibold text-gray-800">{selectedDevice.device_id}</p>
              <p className="text-sm text-gray-600">{normalizeDeviceType(selectedDevice.device_type)} · {isSbDeviceType(selectedDevice.device_type) ? 'NUID' : (selectedDevice.serial_number || 'N/A')}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Device Type
              </label>
              <select
                value={editForm.device_type}
                onChange={(e) => setEditForm(prev => ({ ...prev, device_type: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {deviceTypeOptions.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>

            {!isSbDeviceType(editForm.device_type) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Band Type
              </label>
              <select
                value={editForm.band_type}
                onChange={(e) => setEditForm(prev => ({ ...prev, band_type: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {bandTypeOptions.map((band) => (
                  <option key={band.value} value={band.value}>{band.label}</option>
                ))}
              </select>
            </div>
            )}

            {isSbDeviceType(editForm.device_type) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Box Type
              </label>
              <select
                value={editForm.box_type}
                onChange={(e) => setEditForm(prev => ({ ...prev, box_type: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="HD">HD</option>
                <option value="OTT">OTT</option>
              </select>
            </div>
            )}

            {!isSbDeviceType(editForm.device_type) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Serial Number
              </label>
              <input
                type="text"
                value={editForm.serial_number}
                onChange={(e) => setEditForm(prev => ({ ...prev, serial_number: e.target.value }))}
                placeholder={selectedDevice.serial_number || 'e.g. SN-2026-001'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            )}

            {!isSbDeviceType(editForm.device_type) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                MAC Address
              </label>
              <input
                type="text"
                value={editForm.mac_address}
                onChange={(e) => setEditForm(prev => ({ ...prev, mac_address: e.target.value }))}
                placeholder={selectedDevice.mac_address || 'AA:BB:CC:DD:EE:FF'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Model
              </label>
              <input
                type="text"
                value={editForm.model}
                onChange={(e) => setEditForm(prev => ({ ...prev, model: e.target.value }))}
                placeholder={selectedDevice.model || 'e.g. EchoLife HG8145'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {isSbDeviceType(editForm.device_type) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  NUID
                </label>
                <input
                  type="text"
                  value={editForm.nuid}
                  onChange={(e) => setEditForm(prev => ({ ...prev, nuid: e.target.value }))}
                  placeholder={selectedDevice.nuid || 'Enter SB NUID'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Vendor
              </label>
              <input
                type="text"
                value={editForm.manufacturer}
                onChange={(e) => setEditForm(prev => ({ ...prev, manufacturer: e.target.value }))}
                placeholder={selectedDevice.manufacturer || 'e.g. Huawei'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <input
                type="text"
                value={editForm.current_location}
                onChange={(e) => setEditForm(prev => ({ ...prev, current_location: e.target.value }))}
                placeholder={selectedDevice.current_location || 'e.g. Warehouse A'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {isAdminOrManager && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
                ✅ As {user?.role}, your changes will be applied immediately without approval.
              </div>
            )}
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
          Are you sure you want to delete device <span className="font-medium">{selectedDevice?.mac_address}</span>? 
          This action cannot be undone.
        </p>
      </Modal>

      {/* Bulk Delete Confirmation Modal */}
      <Modal
        isOpen={showBulkDeleteModal}
        onClose={() => setShowBulkDeleteModal(false)}
        title={isStaff ? 'Request Device Deletion' : 'Bulk Delete Devices'}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowBulkDeleteModal(false)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDeleting}>
              {bulkDeleting ? 'Processing...' : isStaff ? 'Submit Request' : `Delete ${bulkSelectedIds.length} Device(s)`}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            {isStaff ? (
              <>
                You are requesting deletion of <span className="font-medium">{bulkSelectedIds.length} device(s)</span>.
                A manager or admin must approve this request before the devices are deleted.
              </>
            ) : (
              <>
                Are you sure you want to delete <span className="font-medium">{bulkSelectedIds.length} device(s)</span>?
                This action cannot be undone.
              </>
            )}
          </p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reason {isStaff && <span className="text-red-500">*</span>}
            </label>
            <textarea
              value={bulkDeleteReason}
              onChange={(e) => setBulkDeleteReason(e.target.value)}
              rows={3}
              required={isStaff}
              placeholder={isStaff ? 'Explain why these devices should be deleted' : 'Optional reason for deletion'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Devices;

