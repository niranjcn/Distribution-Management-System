import { useState, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';
import Timeline from '../components/ui/Timeline';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { devicesAPI, changeRequestsAPI, defectsAPI, usersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Search, Box, MapPin, Clock, User, ChevronRight, ChevronDown, Loader2, Edit, Send, RefreshCw, Link2, AlertTriangle, Filter } from 'lucide-react';

const DEVICE_STATUSES = [
  { value: 'available', label: 'Available' },
  { value: 'distributed', label: 'Distributed' },
  { value: 'in_use', label: 'In Use' },
  { value: 'defective', label: 'Defective' },
  { value: 'replaced', label: 'Replaced' },
  { value: 'returned', label: 'Returned' },
  { value: 'maintenance', label: 'Maintenance' },
];

const TRACK_PAGE_SIZE = 30;

const TrackDevice = () => {
  const [searchParams] = useSearchParams();
  const { user: currentUser } = useAuth();
  const { showToast } = useNotifications();
  const initialQuery = searchParams.get('q') || searchParams.get('mac') || searchParams.get('serial') || searchParams.get('nuid') || '';
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [searchResult, setSearchResult] = useState(null);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [allDevices, setAllDevices] = useState([]);
  const [devicesPage, setDevicesPage] = useState(1);
  const [hasMoreDevices, setHasMoreDevices] = useState(false);
  const [totalDevices, setTotalDevices] = useState(0);
  const [loadingMoreDevices, setLoadingMoreDevices] = useState(false);
  const [hierarchyUsers, setHierarchyUsers] = useState([]);
  const [overviewInsights, setOverviewInsights] = useState({ by_type: [], by_vendor: [] });
  const [replacementMappings, setReplacementMappings] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [deviceHistory, setDeviceHistory] = useState([]);
  const fetchSequenceRef = useRef(0);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [tableFilters, setTableFilters] = useState({
    device_type: '',
    manufacturer: '',
    status: '',
    sub_distributor_id: '',
    cluster_id: '',
  });

  // Availability status change state
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState('');
  const [statusNotes, setStatusNotes] = useState('');
  const [statusSubmitting, setStatusSubmitting] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [requestStatus, setRequestStatus] = useState('');
  const [requestReason, setRequestReason] = useState('');
  const [requestSubmitting, setRequestSubmitting] = useState(false);

  const isManagement = ['super_admin', 'manager', 'pdic_staff'].includes(currentUser?.role);

  const activeFilterKey = useMemo(() => {
    if (!isManagement) return '';
    return JSON.stringify(tableFilters);
  }, [isManagement, tableFilters]);

  const buildOverviewParams = (page) => {
    const params = {
      page,
      page_size: TRACK_PAGE_SIZE,
      paginate: true,
    };

    if (isManagement) {
      if (tableFilters.device_type) params.device_type = tableFilters.device_type;
      if (tableFilters.manufacturer) params.manufacturer = tableFilters.manufacturer;
      if (tableFilters.status) params.status = tableFilters.status;
      if (tableFilters.sub_distributor_id) params.sub_distributor_id = tableFilters.sub_distributor_id;
      if (tableFilters.cluster_id) params.cluster_id = tableFilters.cluster_id;
    }

    return params;
  };

  const fetchAllDevices = async ({ page = 1, append = false } = {}) => {
    const requestId = ++fetchSequenceRef.current;
    const isInitialPage = page === 1 && !append;

    try {
      if (isInitialPage) {
        setDevicesLoading(true);
      }
      if (append) {
        setLoadingMoreDevices(true);
      }

      const [overviewResponse, replacementsResponse] = await Promise.all([
        devicesAPI.getMyOverview(buildOverviewParams(page)),
        isInitialPage ? defectsAPI.getReplacements({ page_size: 100 }) : Promise.resolve(null),
      ]);

      if (requestId !== fetchSequenceRef.current) {
        return;
      }

      const pageDevices = Array.isArray(overviewResponse?.data?.all_under_me)
        ? overviewResponse.data.all_under_me
        : [];

      setAllDevices((previous) => (append ? [...previous, ...pageDevices] : pageDevices));

      const meta = overviewResponse?.data?.meta || {};
      setDevicesPage(page);
      setHasMoreDevices(Boolean(meta.has_next));
      setTotalDevices(Number(meta.total_count || pageDevices.length));

      if (isManagement && overviewResponse?.data?.insights) {
        setOverviewInsights(overviewResponse.data.insights);
      }

      if (isInitialPage) {
        setReplacementMappings(Array.isArray(replacementsResponse?.data) ? replacementsResponse.data : []);

        if (isManagement) {
          try {
            const [subsResponse, clustersResponse] = await Promise.all([
              usersAPI.getUsers({ role: 'sub_distributor', page_size: 100 }),
              usersAPI.getUsers({ role: 'cluster', page_size: 100 }),
            ]);

            const collect = (response) => {
              const payload = response?.data;
              if (Array.isArray(payload)) return payload;
              if (Array.isArray(payload?.users)) return payload.users;
              return [];
            };

            setHierarchyUsers([...collect(subsResponse), ...collect(clustersResponse)]);
          } catch {
            setHierarchyUsers([]);
          }
        } else {
          setHierarchyUsers([]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      if (!append) {
        setAllDevices([]);
        setHasMoreDevices(false);
        setTotalDevices(0);
      }
    } finally {
      if (requestId === fetchSequenceRef.current) {
        setDevicesLoading(false);
        setLoadingMoreDevices(false);
      }
    }
  };

  useEffect(() => {
    if (!currentUser?.role) return;
    fetchAllDevices({ page: 1, append: false });
  }, [currentUser?.role, activeFilterKey]);

  // Auto-search if query param is present
  useEffect(() => {
    if (initialQuery) {
      handleSearchBySerial(initialQuery);
    }
  }, []);

  const replacementMapByDefectiveId = replacementMappings.reduce((acc, defect) => {
    if (defect?.device_id) {
      acc[String(defect.device_id)] = defect;
    }
    return acc;
  }, {});

  const hierarchyIndex = useMemo(() => {
    const subDistributors = hierarchyUsers.filter((u) => u.role === 'sub_distributor');
    const clusters = hierarchyUsers.filter((u) => u.role === 'cluster');
    const clustersBySub = {};
    for (const cluster of clusters) {
      const parentKey = String(cluster.parent_id || '');
      if (!parentKey) continue;
      if (!clustersBySub[parentKey]) clustersBySub[parentKey] = [];
      clustersBySub[parentKey].push(cluster);
    }
    return { subDistributors, clusters, clustersBySub };
  }, [hierarchyUsers]);

  const filterOptions = useMemo(() => {
    const insightTypes = Array.isArray(overviewInsights?.by_type)
      ? overviewInsights.by_type.map((item) => item?.type).filter(Boolean)
      : [];
    const insightManufacturers = Array.isArray(overviewInsights?.by_vendor)
      ? overviewInsights.by_vendor.map((item) => item?.manufacturer).filter(Boolean)
      : [];

    const loadedTypes = allDevices.map((d) => d.device_type).filter(Boolean);
    const loadedManufacturers = allDevices.map((d) => (d.manufacturer || '').trim()).filter(Boolean);

    const deviceTypes = [...new Set([...insightTypes, ...loadedTypes])].sort();
    const manufacturers = [...new Set([...insightManufacturers, ...loadedManufacturers])].sort();
    const subDistributors = hierarchyIndex.subDistributors.map((item) => ({ id: String(item.id), name: item.name }));
    const clusters = hierarchyIndex.clusters.map((item) => ({ id: String(item.id), name: item.name }));
    return { deviceTypes, manufacturers, subDistributors, clusters };
  }, [allDevices, hierarchyIndex, overviewInsights]);

  const filteredAllDevices = allDevices;

  const activeDevices = filteredAllDevices.filter((device) => device.status !== 'replaced');
  const replacedDevices = filteredAllDevices.filter((device) => device.status === 'replaced');

  const searchedReplacementMapping = searchResult
    ? replacementMapByDefectiveId[String(searchResult.id)]
    : null;

  const handleSearchBySerial = async (serialOrMac) => {
    setLoading(true);
    setSearched(true);
    try {
      const response = await devicesAPI.trackDeviceBySerial(serialOrMac);
      if (response.success && response.data) {
        setSearchResult(response.data);
        setDeviceHistory(response.data.history || []);
      } else {
        setSearchResult(null);
        setDeviceHistory([]);
      }
    } catch (error) {
      console.error('Device not found:', error);
      setSearchResult(null);
      setDeviceHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    await handleSearchBySerial(searchQuery.trim());
  };

  const handleDeviceClick = async (device) => {
    const identifier = device?.serial_number || device?.nuid || device?.mac_address || '';
    setSearchQuery(identifier);
    await handleSearchBySerial(identifier);
  };

  const handleLoadMoreDevices = async () => {
    if (loadingMoreDevices || !hasMoreDevices) return;
    await fetchAllDevices({ page: devicesPage + 1, append: true });
  };

  const getFormattedHistory = () => {
    if (!deviceHistory || deviceHistory.length === 0) return [];
    return deviceHistory.map((item, index) => {
      const action = (item.action || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      let title = action;

      // Build a descriptive title with from/to user names
      if (item.action === 'distributed' && item.from_user_name && item.to_user_name) {
        title = `${action}: ${item.from_user_name} → ${item.to_user_name}`;
      } else if (item.action === 'registered' && item.performed_by_name) {
        title = `${action} by ${item.performed_by_name}`;
      } else if (item.action === 'status_changed') {
        const before = item.status_before ? item.status_before.replace(/_/g, ' ') : '';
        const after = item.status_after ? item.status_after.replace(/_/g, ' ') : '';
        title = `Status Changed: ${before} → ${after}`;
      }

      return {
        title,
        description: item.notes || '',
        timestamp: item.timestamp ? new Date(item.timestamp).toLocaleString() : '',
        user: item.performed_by_name || '',
        fromUser: item.from_user_name || null,
        toUser: item.to_user_name || null,
        status: index === 0 ? 'current' : 'completed'
      };
    });
  };

  const getLocationColor = (holderType) => {
    if (!holderType) return 'bg-blue-100 text-blue-800';
    const t = holderType.toLowerCase();
    if (t === 'noc' || t.includes('pdic')) return 'bg-blue-100 text-blue-800';
    if (t === 'sub_distributor') return 'bg-purple-100 text-purple-800';
    if (t === 'cluster') return 'bg-indigo-100 text-indigo-800';
    if (t === 'operator') return 'bg-green-100 text-green-800';
    if (t.includes('transit')) return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getHolderTypeLabel = (holderType) => {
    if (!holderType || holderType === 'noc') return 'PDIC (Distribution)';
    if (holderType === 'sub_distributor') return 'Sub Distributor';
    if (holderType === 'cluster') return 'Cluster';
    if (holderType === 'operator') return 'Operator';
    return holderType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  const getLocationLabel = (location) => {
    if (!location || location.toUpperCase() === 'NOC') return 'PDIC (Distribution)';
    return location;
  };

  const getRegisteredBy = () => {
    if (!deviceHistory || deviceHistory.length === 0) return null;
    const entry = [...deviceHistory].reverse().find(h => h.action === 'registered');
    return entry ? entry.performed_by_name : null;
  };

  const canChangeStatusDirectly = currentUser && ['super_admin', 'manager'].includes(currentUser.role);
  const canRequestStatusChange = currentUser && currentUser.role === 'pdic_staff';

  const refreshTrackedDevice = async (deviceId) => {
    if (!deviceId) return;
    try {
      const [deviceResponse, historyResponse] = await Promise.all([
        devicesAPI.getDevice(deviceId),
        devicesAPI.getDeviceHistory(deviceId),
      ]);
      setSearchResult(deviceResponse?.data || null);
      setDeviceHistory(historyResponse?.data || []);
    } catch (error) {
      showToast(error.message || 'Failed to refresh tracked device', 'error');
    }
  };

  const handleRepairHolder = async () => {
    if (!searchResult) return;
    try {
      await devicesAPI.repairDeviceHolder(searchResult.id);
      showToast('Device holder repaired successfully', 'success');
      await refreshTrackedDevice(searchResult.id);
    } catch (err) {
      showToast(err.message || 'Failed to repair device holder', 'error');
    }
  };

  const handleDirectStatusChange = async () => {
    if (!selectedStatus || !searchResult) return;
    setStatusSubmitting(true);
    try {
      await devicesAPI.updateDeviceStatus(searchResult.id, selectedStatus, statusNotes);
      showToast('Device availability status updated successfully', 'success');
      setShowStatusModal(false);
      setStatusNotes('');
      await refreshTrackedDevice(searchResult.id);
    } catch (err) {
      showToast(err.message || 'Failed to update status', 'error');
    } finally {
      setStatusSubmitting(false);
    }
  };

  const handleStatusChangeRequest = async () => {
    if (!requestStatus || !requestReason.trim() || !searchResult) return;
    setRequestSubmitting(true);
    try {
      await changeRequestsAPI.submit({
        request_type: 'device_status_change',
        device_id: searchResult.id,
        requested_status: requestStatus,
        reason: requestReason,
      });
      showToast('Status change request submitted. Awaiting admin/manager approval.', 'success');
      setShowRequestModal(false);
      setRequestReason('');
      setRequestStatus('');
    } catch (err) {
      showToast(err.message || 'Failed to submit request', 'error');
    } finally {
      setRequestSubmitting(false);
    }
  };

  const getHolderType = (type) => {
    if (!type) return 'Unknown';
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Track Device</h1>
        <p className="text-gray-500 mt-1">Search and track device journey through the distribution chain</p>
      </div>

      {/* Search Form */}
      <Card>
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter serial number, NUID, or MAC to track device..."
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <Button type="submit" size="lg" disabled={loading}>
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Track Device'}
          </Button>
        </form>
      </Card>

      {/* All Devices List */}
      {!searched && (
        <Card title={['super_admin', 'manager', 'pdic_staff'].includes(currentUser?.role) ? 'All Devices' : 'Devices In My Chain'} icon={Box}>
          {devicesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <span className="ml-3 text-gray-500">Loading devices...</span>
            </div>
          ) : allDevices.length === 0 ? (
            <div className="text-center py-12">
              <Box className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-800 mb-2">No Devices Found</h3>
              <p className="text-gray-500">No devices have been registered yet. Register a device first to start tracking.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {isManagement && (
                <div className="p-4 rounded-lg border border-gray-200 bg-gray-50 mb-2">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      <Filter className="w-4 h-4 text-blue-600" />
                      <h3 className="text-sm font-semibold text-gray-800">Table Filters (ALL Devices)</h3>
                    </div>
                    <Button
                      variant="secondary"
                      onClick={() => setShowAdvancedFilters((prev) => !prev)}
                      className="text-xs"
                    >
                      {showAdvancedFilters ? 'Hide Filters' : 'Show Filters'}
                    </Button>
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
                    Showing {filteredAllDevices.length} of {totalDevices || filteredAllDevices.length} devices
                  </p>
                </div>
              )}
              <p className="text-sm text-gray-500 mb-2">Active devices are listed first. Replaced devices are shown in a separate section below.</p>
              <p className="text-xs text-gray-500 mb-3">
                Loaded: {filteredAllDevices.length} / {totalDevices || filteredAllDevices.length}
              </p>

              <h3 className="text-sm font-semibold text-gray-700 mt-2">Active Devices</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {activeDevices.map((device) => (
                  <div
                    key={device.id}
                    onClick={() => handleDeviceClick(device)}
                    className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all"
                  >
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Box className="w-5 h-5 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <DeviceIdentity device={device} />
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <StatusBadge status={device.status} size="sm" />
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-4 mt-4 border-t border-gray-200">
                <h3 className="text-sm font-semibold text-red-700 line-through decoration-red-500 mb-3">Replaced Devices</h3>
                {replacedDevices.length === 0 ? (
                  <p className="text-sm text-gray-500">No replaced devices in your current scope.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {replacedDevices.map((device) => {
                      const mapping = replacementMapByDefectiveId[String(device.id)];
                      return (
                        <div
                          key={device.id}
                          onClick={() => handleDeviceClick(device)}
                          className="flex items-center gap-3 p-4 border border-red-200 rounded-lg cursor-pointer hover:border-red-400 hover:bg-red-50 transition-all"
                        >
                          <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center flex-shrink-0">
                            <AlertTriangle className="w-5 h-5 text-red-600" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <DeviceIdentity device={device} />
                            <p className="text-xs text-red-600 truncate">
                              {mapping?.replacement_device?.device_id
                                ? `Replaced by ${mapping.replacement_device.device_id}`
                                : 'Replacement mapping available'}
                            </p>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <StatusBadge status="replaced" size="sm" />
                            <ChevronRight className="w-4 h-4 text-gray-400" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {hasMoreDevices && (
                <div className="pt-4 mt-4 border-t border-gray-200 flex justify-center">
                  <Button
                    variant="secondary"
                    onClick={handleLoadMoreDevices}
                    disabled={loadingMoreDevices}
                    icon={ChevronDown}
                  >
                    {loadingMoreDevices ? 'Loading next 30...' : 'Load Next 30 Devices'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Search Results */}
      {searched && (
        <>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <span className="ml-3 text-gray-500">Tracking device...</span>
            </div>
          ) : searchResult ? (
            <div className="space-y-6">
              {/* Back to all devices */}
              <button
                onClick={() => { setSearched(false); setSearchResult(null); setSearchQuery(''); }}
                className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
              >
                ← Back to all devices
              </button>

              {(searchResult.status === 'replaced' || searchedReplacementMapping) && (
                <div className="p-4 bg-gray-100 border border-gray-300 rounded-lg">
                  <p className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                    <Link2 className="w-4 h-4" />
                    This device was replaced
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    This device is no longer active. Use the link below to open the replacement device mapping.
                  </p>
                  {searchedReplacementMapping?.replacement_device && (
                    <button
                      onClick={() => {
                        const replacementIdentifier = searchedReplacementMapping.replacement_device?.serial_number || searchedReplacementMapping.replacement_device?.nuid || searchedReplacementMapping.replacement_device?.mac_address;
                        if (!replacementIdentifier) {
                          showToast('Replacement device serial is unavailable for quick open', 'warning');
                          return;
                        }
                        handleDeviceClick(searchedReplacementMapping.replacement_device);
                      }}
                      className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700"
                    >
                      Open Replacement Device {searchedReplacementMapping.replacement_device.device_id || ''}
                    </button>
                  )}
                </div>
              )}

              {/* Device Info Card */}
              <Card>
                <div className="flex flex-col lg:flex-row lg:items-start gap-6">
                  <div className="flex items-center gap-4">
                    <div className="w-20 h-20 bg-blue-100 rounded-xl flex items-center justify-center">
                      <Box className="w-10 h-10 text-blue-600" />
                    </div>
                    <div>
                      <DeviceIdentity device={searchResult} />
                      <p className="text-gray-500 mt-1">{searchResult.manufacturer || 'Unknown Vendor'}</p>
                      <div className="flex gap-2 mt-2">
                        <StatusBadge status={searchResult.status} />
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4 lg:border-l lg:border-gray-200 lg:pl-6">
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">MAC Address</p>
                      <p className="font-mono font-medium text-gray-800">
                        {['sb', 'stb', 'settopbox', 'setupbox'].includes(String(searchResult.device_type || '').toLowerCase().replace(/[-_\s]+/g, ''))
                          ? 'N/A'
                          : (searchResult.mac_address || 'N/A')}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Serial Number</p>
                      <p className="font-medium text-gray-800">
                        {['sb', 'stb', 'settopbox', 'setupbox'].includes(String(searchResult.device_type || '').toLowerCase().replace(/[-_\s]+/g, ''))
                          ? 'N/A'
                          : (searchResult.serial_number || 'N/A')}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Device Type</p>
                      <p className="font-medium text-gray-800">
                        {['sb', 'stb', 'settopbox', 'setupbox'].includes(String(searchResult.device_type || '').toLowerCase().replace(/[-_\s]+/g, '')) ? 'SB' : searchResult.device_type}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider">Device ID</p>
                      <p className="font-medium text-gray-800">{searchResult.device_id}</p>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Current Location & Journey */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-1">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-gray-500" />
                    Current Location
                  </h3>
                  <div className={`p-4 rounded-lg ${getLocationColor(searchResult.current_holder_type)}`}>
                    <p className="text-sm font-medium uppercase tracking-wider opacity-75">
                      {getHolderTypeLabel(searchResult.current_holder_type)}
                    </p>
                    <p className="text-lg font-bold mt-1">
                      {searchResult.current_holder_name || getLocationLabel(searchResult.current_location)}
                    </p>
                  </div>

                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-3 text-sm">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">
                        Registered: {searchResult.created_at ? new Date(searchResult.created_at).toLocaleDateString() : 'N/A'}
                      </span>
                    </div>
                    {getRegisteredBy() && (
                      <div className="flex items-center gap-3 text-sm">
                        <User className="w-4 h-4 text-gray-400" />
                        <span className="text-gray-600">Registered by: <span className="font-medium">{getRegisteredBy()}</span></span>
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-sm">
                      <MapPin className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">Location: {getLocationLabel(searchResult.current_location)}</span>
                    </div>
                  </div>

                  {/* Availability Status Change */}
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Availability Status</p>
                    <StatusBadge status={searchResult.status} />
                    <div className="mt-3 flex flex-col gap-2">
                      {canChangeStatusDirectly && (
                        <Button
                          size="sm"
                          variant="outline"
                          icon={Edit}
                          onClick={() => { setSelectedStatus(searchResult.status); setShowStatusModal(true); }}
                        >
                          Change Status
                        </Button>
                      )}
                      {canChangeStatusDirectly && (
                        <Button
                          size="sm"
                          variant="outline"
                          icon={RefreshCw}
                          onClick={handleRepairHolder}
                          title="Re-apply the most recent distribution to fix a corrupted holder"
                        >
                          Fix Holder
                        </Button>
                      )}
                      {canRequestStatusChange && (
                        <Button
                          size="sm"
                          variant="outline"
                          icon={Send}
                          onClick={() => { setRequestStatus(searchResult.status); setShowRequestModal(true); }}
                        >
                          Request Status Change
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>

                {/* Device Journey */}
                <Card className="lg:col-span-2">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <Clock className="w-5 h-5 text-gray-500" />
                    Device Journey
                  </h3>

                  {deviceHistory.length > 0 ? (
                    <Timeline items={getFormattedHistory()} />
                  ) : (
                    <div className="text-center py-8">
                      <Clock className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                      <p className="text-gray-500">No journey history available for this device</p>
                    </div>
                  )}
                </Card>
              </div>

              {/* Distribution Flow */}
              <Card title="Distribution Flow">
                <div className="flex flex-col sm:flex-row items-center justify-center gap-4 py-4">
                  <div className={`text-center ${(!searchResult.current_holder_type || searchResult.current_holder_type === 'noc') ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-blue-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">PDIC</p>
                    <p className="text-xs text-gray-500">Distribution</p>
                  </div>

                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />

                  <div className={`text-center ${searchResult.current_holder_type === 'sub_distributor' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-purple-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Sub Distributor</p>
                    <p className="text-xs text-gray-500">Regional</p>
                  </div>

                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />

                  <div className={`text-center ${searchResult.current_holder_type === 'cluster' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto">
                      <Box className="w-8 h-8 text-indigo-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Cluster</p>
                    <p className="text-xs text-gray-500">Zone</p>
                  </div>

                  <ChevronRight className="w-6 h-6 text-gray-300 rotate-90 sm:rotate-0" />

                  <div className={`text-center ${searchResult.current_holder_type === 'operator' ? 'ring-2 ring-blue-500 rounded-lg p-2' : ''}`}>
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                      <User className="w-8 h-8 text-green-600" />
                    </div>
                    <p className="text-sm font-medium text-gray-800 mt-2">Operator</p>
                    <p className="text-xs text-gray-500">End User</p>
                  </div>
                </div>
              </Card>

              {/* Change Status Modal (Admin / Manager) */}
              <Modal
                isOpen={showStatusModal}
                onClose={() => { setShowStatusModal(false); setStatusNotes(''); }}
                title="Change Device Availability Status"
                size="sm"
              >
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">New Status</label>
                    <select
                      value={selectedStatus}
                      onChange={e => setSelectedStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      {DEVICE_STATUSES.map(s => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                    <textarea
                      value={statusNotes}
                      onChange={e => setStatusNotes(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="Reason for status change..."
                    />
                  </div>
                  <div className="flex justify-end gap-3">
                    <Button variant="outline" onClick={() => { setShowStatusModal(false); setStatusNotes(''); }}>Cancel</Button>
                    <Button onClick={handleDirectStatusChange} disabled={statusSubmitting}>
                      {statusSubmitting ? 'Saving...' : 'Save'}
                    </Button>
                  </div>
                </div>
              </Modal>

              {/* Request Status Change Modal (Staff) */}
              <Modal
                isOpen={showRequestModal}
                onClose={() => { setShowRequestModal(false); setRequestReason(''); }}
                title="Request Availability Status Change"
                size="sm"
              >
                <div className="space-y-4">
                  <p className="text-sm text-gray-500">This request will be sent to an admin or manager for approval.</p>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Requested Status</label>
                    <select
                      value={requestStatus}
                      onChange={e => setRequestStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      {DEVICE_STATUSES.map(s => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason <span className="text-red-500">*</span></label>
                    <textarea
                      value={requestReason}
                      onChange={e => setRequestReason(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="Explain why the status needs to change..."
                      required
                    />
                  </div>
                  <div className="flex justify-end gap-3">
                    <Button variant="outline" onClick={() => { setShowRequestModal(false); setRequestReason(''); }}>Cancel</Button>
                    <Button onClick={handleStatusChangeRequest} disabled={requestSubmitting || !requestReason.trim()}>
                      {requestSubmitting ? 'Submitting...' : 'Submit Request'}
                    </Button>
                  </div>
                </div>
              </Modal>
            </div>
          ) : (
            <div>
              <button
                onClick={() => { setSearched(false); setSearchResult(null); setSearchQuery(''); }}
                className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1 mb-4"
              >
                ← Back to all devices
              </button>
              <Card>
                <div className="text-center py-12">
                  <Box className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-800 mb-2">No Device Found</h3>
                  <p className="text-gray-500 max-w-md mx-auto">
                    We couldn't find a device matching "{searchQuery}". Please check the serial number and try again.
                  </p>
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default TrackDevice;

