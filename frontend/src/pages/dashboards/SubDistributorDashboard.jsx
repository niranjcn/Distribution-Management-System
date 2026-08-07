import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import Skeleton from '../../components/ui/Skeleton';
import StatusBadge from '../../components/ui/StatusBadge';
import Button from '../../components/ui/Button';
import ErrorBoundary from '../../components/ui/ErrorBoundary';
import DateRangeFilter, { buildDateParams } from '../../components/ui/DateRangeFilter';
import { dashboardAPI, devicesAPI, distributionsAPI, usersAPI, defectsAPI, returnsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useNotifications } from '../../context/NotificationContext';
import {
  Box,
  Users,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  Package,
  ArrowRight,
  CheckCircle,
  XCircle,
  Send,
  Loader2
} from 'lucide-react';

ChartJS.register(ArcElement, Tooltip, Legend);

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' },
  },
};

const SubDistributorDashboard = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const role = String(user?.role || '').toLowerCase();
  const isSubDistributionManager = role === 'sub_distribution_manager';
  const isCluster = role === 'cluster';
  const isEmployee = role === 'sub_distribution_employee';
  // Branch-scope an employee's dashboard to its parent sub-distributor so all
  // the metrics shown to the sub distributor are shown exactly to the employee.
  const effectiveId = (isEmployee ? user?.parent_id : user?.id);
  const canAssign = role !== 'sub_distribution_manager';
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [] });
  const [myDevices, setMyDevices] = useState([]);
  const [deviceStats, setDeviceStats] = useState({});
  const [distributions, setDistributions] = useState([]);
  const [myOperators, setMyOperators] = useState([]);
  const [defectReports, setDefectReports] = useState([]);
  const [returnRequests, setReturnRequests] = useState([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [advancedLoading, setAdvancedLoading] = useState(true);
  const [listsLoading, setListsLoading] = useState(true);

  useEffect(() => {
    const dateParams = buildDateParams(dateRange);
    let active = true;

    // Batch 1 — authoritative stat cards from /dashboard/stats (fast).
    setStatsLoading(true);
    dashboardAPI.getStats(dateParams)
      .then((res) => { if (active) setStats(res.data || {}); })
      .catch((err) => {
        console.error('Failed to load stats:', err);
        if (active) showToast('Failed to load dashboard stats', 'error');
      })
      .finally(() => { if (active) setStatsLoading(false); });

    // Batch 2 — charts + device chain (advanced-metrics + my device overview).
    setAdvancedLoading(true);
    dashboardAPI.getAdvancedMetrics(dateParams)
      .then((res) => { if (active) setAdvanced(res.data || { kpis: {}, charts: {}, alerts: [] }); })
      .catch((err) => {
        console.error('Failed to load advanced metrics:', err);
        if (active) showToast('Failed to load analytics', 'error');
      });
    const devicePromise = ['sub_distribution_manager', 'sub_distributor', 'sub_distribution_employee', 'cluster'].includes(role)
      ? devicesAPI.getMyOverview({ show_all: true, limit: 10 })
      : devicesAPI.getDevices();
    devicePromise
      .then((res) => {
        if (!active) return;
        setMyDevices(Array.isArray(res.data) ? res.data : (res.data?.all_under_me || []));
        setDeviceStats(res.data?.stats || {});
      })
      .catch((err) => {
        console.error('Failed to load devices:', err);
        if (active) showToast('Failed to load devices', 'error');
      })
      .finally(() => { if (active) setAdvancedLoading(false); });

    // Batch 3 — bottom lists, slightly deferred so they do not compete with
    // the top-heavy initial render.
    setListsLoading(true);
    const loadLists = async () => {
      const [distRes, usersRes, defRes, retRes] = await Promise.all([
        distributionsAPI.getDistributions({ status: 'pending_receipt' }).catch(err => { console.error('Failed to load distributions:', err); return { data: [] }; }),
        usersAPI.getUsers({ role: 'operator', page_size: 10 }).catch(err => { console.error('Failed to load operators:', err); return { data: [] }; }),
        defectsAPI.getDefects(dateParams).catch(err => { console.error('Failed to load defects:', err); return { data: [] }; }),
        returnsAPI.getReturns(dateParams).catch(err => { console.error('Failed to load returns:', err); return { data: [] }; }),
      ]);
      if (active) {
        setDistributions(distRes.data || []);
        setMyOperators(usersRes.data || []);
        setDefectReports(defRes.data || []);
        setReturnRequests(retRes.data || []);
      }
    };
    const listTimer = window.setTimeout(() => loadLists().finally(() => { if (active) setListsLoading(false); }), 400);

    return () => {
      active = false;
      window.clearTimeout(listTimer);
    };
  }, [dateRange]);

  const charts = advanced.charts || {};
  const myDeviceSplitData = useMemo(() => ({
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [
        charts.my_device_active_split?.active || myDevices.filter((d) => ['active', 'available', 'distributed', 'in_use'].includes(d.status)).length,
        charts.my_device_active_split?.inactive || myDevices.filter((d) => !['active', 'available', 'distributed', 'in_use'].includes(d.status)).length,
      ],
      backgroundColor: ['#10b981', '#ef4444'],
      borderWidth: 1,
    }],
  }), [charts.my_device_active_split, myDevices]);

  const managedUserSplitData = useMemo(() => ({
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [
        charts.cluster_account_active_split?.active || charts.operator_account_active_split?.active || 0,
        charts.cluster_account_active_split?.inactive || charts.operator_account_active_split?.inactive || 0,
      ],
      backgroundColor: ['#3b82f6', '#f59e0b'],
      borderWidth: 1,
    }],
  }), [charts.cluster_account_active_split, charts.operator_account_active_split]);

  const pendingReceipts = distributions.filter(
    d => d.status === 'pending_receipt' && String(d.to_user_id) === String(effectiveId)
  );

  const receivedDevicesCount = isCluster
    ? (stats.my_devices ?? 0)
    : (stats.received_devices ?? myDevices.length);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800 break-words">{isSubDistributionManager ? 'Sub Distribution Manager Dashboard' : isCluster ? 'Cluster Dashboard' : isEmployee ? 'Sub Distribution Employee Dashboard' : 'Sub-Distributor Dashboard'}</h1>
          <p className="text-gray-500 mt-1">
            {isSubDistributionManager ? 'Monitor branch devices and operator activity.' : isCluster ? 'Manage cluster devices and operator assignments.' : isEmployee ? 'Monitor your sub distribution and submit proposals for approval.' : 'Manage received devices and operator assignments.'}
          </p>
        </div>
        {canAssign && (
          <Link to="/distributions/create">
            <Button icon={Send}>Assign to Operator</Button>
          </Link>
        )}
      </div>

      <div className="flex justify-end">
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <ErrorBoundary name="Stats">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <StatCard title="Received Devices" value={receivedDevicesCount} icon={Box} color="blue" loading={statsLoading} />
          <StatCard title="Pending Confirmations" value={pendingReceipts.length} icon={CheckSquare} color="orange" loading={listsLoading} />
          <StatCard title="My Operators" value={stats.operator_count || myOperators.length} icon={Users} color="purple" loading={statsLoading} />
          <StatCard title="Defect Reports" value={stats.defect_reports || defectReports.length} icon={AlertTriangle} color="red" loading={statsLoading} />
          <StatCard title="Returns" value={stats.return_requests || returnRequests.length} icon={RotateCcw} color="indigo" loading={statsLoading} />
          <StatCard title="Distributions" value={stats.distributions_sent || 0} icon={Package} color="green" loading={statsLoading} />
        </div>
      </ErrorBoundary>

      <ErrorBoundary name="Device Chain Card">
        <Card title="Devices Under My Chain" icon={Box}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Box className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                {advancedLoading ? (
                  <Skeleton className="h-8 w-16 mb-2" />
                ) : (
                  <p className="text-2xl font-bold text-gray-800">
                    {Number(deviceStats.total_in_chain ?? (myDevices.length || 0))}
                  </p>
                )}
                <p className="text-sm text-gray-500">Total Devices</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <Package className="w-5 h-5 text-green-600" />
              </div>
              <div>
                {advancedLoading ? (
                  <Skeleton className="h-8 w-16 mb-2" />
                ) : (
                  <p className="text-2xl font-bold text-gray-800">
                    {Number(deviceStats.in_my_hand ?? (myDevices.filter((d) => String(d.current_holder_id) === String(user?.id)).length || 0))}
                  </p>
                )}
                <p className="text-sm text-gray-500">Total Devices In Hand</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <Users className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                {advancedLoading ? (
                  <Skeleton className="h-8 w-16 mb-2" />
                ) : (
                  <p className="text-2xl font-bold text-gray-800">
                    {Number(deviceStats.under_subordinates ?? 0)}
                  </p>
                )}
                <p className="text-sm text-gray-500">Under the Chain</p>
              </div>
            </div>
          </div>
        </Card>
      </ErrorBoundary>

      <ErrorBoundary name="Charts">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card title="My Device Active vs Inactive" icon={Box} padding={false}>
            <div className="h-72 p-4"><Doughnut data={myDeviceSplitData} options={doughnutOptions} /></div>
          </Card>
          <Card
            title={user?.role === 'cluster' ? 'Operator Account Active vs Inactive' : 'Cluster/Operator Account Active vs Inactive'}
            icon={Users}
            padding={false}
          >
            <div className="h-72 p-4"><Doughnut data={managedUserSplitData} options={doughnutOptions} /></div>
          </Card>
        </div>
      </ErrorBoundary>

      {/* Pending Receipt Confirmations Banner */}
      <ErrorBoundary name="Receipt Banner">
      {pendingReceipts.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center">
                <Package className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="font-medium text-orange-800">
                  You have {pendingReceipts.length} delivery(ies) to confirm
                </p>
                <p className="text-sm text-orange-600">Confirm that you have received the devices before you can redistribute them</p>
              </div>
            </div>
            <Link to="/delivery-confirmations">
              <Button variant="warning" size="sm">Confirm Now</Button>
            </Link>
          </div>
        </div>
      )}
      </ErrorBoundary>

      <ErrorBoundary name="Cards Grid">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* My Devices */}
        <Card
          title="My Devices"
          icon={Box}
          action={
            <Link to="/devices" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myDevices.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No devices assigned</p>
            ) : (
              myDevices.slice(0, 4).map((device) => (
                <div key={device.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{device.model || device.device_type}</p>
                    <p className="text-xs text-gray-500">{device.mac_address}</p>
                  </div>
                  <StatusBadge status={device.status} size="sm" />
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Pending Receipt Confirmations */}
        <Card
          title="Pending Confirmations"
          icon={Package}
          action={
            <Link to="/delivery-confirmations" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {pendingReceipts.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No pending confirmations</p>
            ) : (
              pendingReceipts.map((dist) => (
                <div key={dist.id} className="p-3 bg-orange-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-gray-800">{dist.distribution_id}</p>
                    <StatusBadge status={dist.status} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500">From: {dist.from_user_name}</p>
                  <p className="text-xs text-gray-400 mb-2">{dist.device_count || dist.device_ids?.length || 0} devices</p>
                  <Link to="/delivery-confirmations" className="block">
                    <button className="w-full flex items-center justify-center gap-1 px-2 py-1 text-xs font-medium text-orange-700 bg-orange-100 rounded hover:bg-orange-200">
                      <Package className="w-3 h-3" /> Confirm Receipt
                    </button>
                  </Link>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* My Operators */}
        <Card
          title="My Operators"
          icon={Users}
          action={
            <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myOperators.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No operators found</p>
            ) : (
              myOperators.slice(0, 4).map((op) => (
                <div key={op.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-xs font-medium text-blue-600">
                        {String(op.name || '').split(' ').filter(Boolean).map(n => n[0]).join('') || '?'}
                      </span>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{op.name || 'Unknown'}</p>
                      <p className="text-xs text-gray-500">{op.email || '-'}</p>
                    </div>
                  </div>
                  <StatusBadge status={op.status} size="sm" />
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
      </ErrorBoundary>

      <ErrorBoundary name="Defects & Returns">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Defect Reports to Review */}
        <Card
          title="Defect Reports to Review"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-3">
            {defectReports.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No defect reports</p>
            ) : (
              defectReports
                .filter((d) => !['resolved', 'rejected'].includes(String(d.status || '').toLowerCase()))
                .slice(0, 3)
                .map((defect) => (
                  <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-800">{defect.device_name || defect.device_type || 'Unknown'}</p>
                        <StatusBadge status={defect.severity} size="sm" />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{defect.defect_type || '-'}</p>
                      <p className="text-xs text-gray-400">Reported by: {defect.reported_by_name || 'Unknown'}</p>
                    </div>
                    <StatusBadge status={defect.status} />
                  </div>
                ))
            )}
          </div>
        </Card>

        {/* Return Requests */}
        <Card
          title="Return Requests"
          icon={RotateCcw}
          action={
            <Link to="/returns" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-3">
            {returnRequests.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No return requests</p>
            ) : (
              returnRequests.slice(0, 3).map((ret) => (
                <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{ret.device_name || ret.device_type || ret.device_model || 'Unknown'}</p>
                    <p className="text-xs text-gray-500">{ret.reason || '-'}</p>
                    <p className="text-xs text-gray-400 mt-1">By: {ret.requested_by_name || ret.initiated_by_name || 'Unknown'}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={ret.status} />
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
      </ErrorBoundary>
    </div>
  );
};

export default SubDistributorDashboard;
