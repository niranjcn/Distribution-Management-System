import { useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Doughnut, Line, Bar } from 'react-chartjs-2';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import { dashboardAPI, distributionsAPI, returnsAPI } from '../../services/api';
import HierarchySelector from '../../components/dashboard/HierarchySelector';
import UserKpiSection from '../../components/dashboard/UserKpiSection';
import {
  Activity,
  Boxes,
  CheckSquare,
  Clock,
  Cpu,
  HardHat,
  Loader2,
  Radar,
  RotateCcw,
  Truck,
  Wrench,
  ArrowRight
} from 'lucide-react';

ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler
);

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#5F6368',
        boxWidth: 12,
      },
    },
    tooltip: {
      backgroundColor: '#FFFFFF',
      titleColor: '#1A1A1A',
      bodyColor: '#5F6368',
      borderColor: '#E0E0E0',
      borderWidth: 1,
    },
  },
  scales: {
    x: {
      ticks: { color: '#5F6368' },
      grid: { color: 'rgba(0, 0, 0, 0.06)' },
    },
    y: {
      ticks: { color: '#5F6368' },
      grid: { color: 'rgba(0, 0, 0, 0.06)' },
    },
  },
};

const ManagerDashboard = () => {
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [] });
  const [distributions, setDistributions] = useState([]);
  const [returnRequests, setReturnRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userKpi, setUserKpi] = useState(null);
  const [kpiLoading, setKpiLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [statsRes, advancedRes, distRes, retRes] = await Promise.all([
          dashboardAPI.getStats().catch(() => ({ data: {} })),
          dashboardAPI.getAdvancedMetrics().catch(() => ({ data: { kpis: {}, charts: {}, alerts: [] } })),
          distributionsAPI.getDistributions().catch(() => ({ data: [] })),
          returnsAPI.getReturns().catch(() => ({ data: [] }))
        ]);
        setStats(statsRes.data || {});
        setAdvanced(advancedRes.data || { kpis: {}, charts: {}, alerts: [] });
        setDistributions(distRes.data || []);
        setReturnRequests(retRes.data || []);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleHierarchySelect = async (selection) => {
    setSelectedUser(selection);
    if (selection && selection.id) {
      setKpiLoading(true);
      setUserKpi(null);
      try {
        const res = await dashboardAPI.getUserKpi(selection.id);
        setUserKpi(res.data || null);
      } catch {
        setUserKpi(null);
      } finally {
        setKpiLoading(false);
      }
    } else {
      setUserKpi(null);
    }
  };

  const kpis = advanced.kpis || {};
  const charts = advanced.charts || {};
  const alerts = advanced.alerts || [];

  const activeInactiveData = useMemo(() => ({
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [charts.device_active_split?.active || 0, charts.device_active_split?.inactive || 0],
      backgroundColor: ['#10b981', '#ef4444'],
      borderColor: '#FFFFFF',
      borderWidth: 1,
    }],
  }), [charts.device_active_split]);

  const defectTrendData = useMemo(() => ({
    labels: (charts.defect_trend_12m || []).map((d) => d.month),
    datasets: [
      {
        label: 'Reported',
        data: (charts.defect_trend_12m || []).map((d) => d.reported),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.16)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'Resolved',
        data: (charts.defect_trend_12m || []).map((d) => d.resolved),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.12)',
        fill: true,
        tension: 0.35,
      },
    ],
  }), [charts.defect_trend_12m]);

  const distributionTrendData = useMemo(() => ({
    labels: (charts.distribution_trend_12m || []).map((d) => d.month),
    datasets: [
      {
        label: 'Total',
        data: (charts.distribution_trend_12m || []).map((d) => d.total),
        backgroundColor: '#64748b',
      },
      {
        label: 'Delivered',
        data: (charts.distribution_trend_12m || []).map((d) => d.delivered),
        backgroundColor: '#10b981',
      },
    ],
  }), [charts.distribution_trend_12m]);

  const replacementData = useMemo(() => ({
    labels: ['Confirmed', 'Pending Confirmation'],
    datasets: [{
      data: [
        charts.replacement_pipeline?.confirmed || 0,
        charts.replacement_pipeline?.pending_confirmation || 0,
      ],
      backgroundColor: ['#10b981', '#f59e0b'],
      borderColor: '#FFFFFF',
      borderWidth: 1,
    }],
  }), [charts.replacement_pipeline]);

  const returnStatusData = useMemo(() => ({
    labels: ['Pending', 'Approved', 'Received', 'Rejected'],
    datasets: [{
      label: 'Returns',
      data: [
        charts.returns_by_status?.pending || 0,
        charts.returns_by_status?.approved || 0,
        charts.returns_by_status?.received || 0,
        charts.returns_by_status?.rejected || 0,
      ],
      backgroundColor: ['#f59e0b', '#3b82f6', '#10b981', '#ef4444'],
      borderColor: '#FFFFFF',
      borderWidth: 1,
    }],
  }), [charts.returns_by_status]);

  const workforceAccountSplitData = useMemo(() => ({
    labels: ['Sub Distributors', 'Clusters', 'Operators'],
    datasets: [
      {
        label: 'Active Accounts',
        data: [
          charts.sub_distributor_account_active_split?.active || 0,
          charts.cluster_account_active_split?.active || 0,
          charts.operator_account_active_split?.active || 0,
        ],
        backgroundColor: '#10b981',
      },
      {
        label: 'Inactive Accounts',
        data: [
          charts.sub_distributor_account_active_split?.inactive || 0,
          charts.cluster_account_active_split?.inactive || 0,
          charts.operator_account_active_split?.inactive || 0,
        ],
        backgroundColor: '#ef4444',
      },
    ],
  }), [charts]);

  const workforceDeviceSplitData = useMemo(() => ({
    labels: ['Sub Distributor Devices', 'Cluster Devices', 'Operator Devices'],
    datasets: [
      {
        label: 'Active Devices',
        data: [
          charts.sub_distributor_device_active_split?.active || 0,
          charts.cluster_device_active_split?.active || 0,
          charts.operator_device_active_split?.active || 0,
        ],
        backgroundColor: '#3b82f6',
      },
      {
        label: 'Inactive Devices',
        data: [
          charts.sub_distributor_device_active_split?.inactive || 0,
          charts.cluster_device_active_split?.inactive || 0,
          charts.operator_device_active_split?.inactive || 0,
        ],
        backgroundColor: '#f59e0b',
      },
    ],
  }), [charts]);

  const pendingActionQueueData = useMemo(() => ({
    labels: ['Approvals', 'Receipts', 'Returns'],
    datasets: [{
      label: 'Pending',
      data: [
        charts.pending_action_queue?.approvals || kpis.pending_approvals || 0,
        charts.pending_action_queue?.receipts || kpis.pending_receipts || 0,
        charts.pending_action_queue?.returns || 0,
      ],
      backgroundColor: ['#6366f1', '#f59e0b', '#ef4444'],
      borderColor: '#FFFFFF',
      borderWidth: 1,
    }],
  }), [charts.pending_action_queue, kpis.pending_approvals, kpis.pending_receipts]);

  return (
    <div className="space-y-6">
      <div className="industrial-hero relative overflow-hidden rounded-2xl p-5 sm:p-6 animate-fadeIn">
        <div className="absolute right-0 top-0 h-20 w-20 rounded-full bg-orange-400/20 blur-2xl" />
        <div className="relative z-10">
          <h1 className="text-2xl sm:text-3xl font-bold text-green-900 tracking-wide">Management Ops Console</h1>
          <p className="text-green-700 mt-1">Role-scoped analytics for throughput, defects, replacements, and return control.</p>
        </div>
      </div>

      <HierarchySelector onSelect={handleHierarchySelect} selectedUserId={selectedUser?.id} />
      {userKpi && <UserKpiSection userKpi={userKpi} loading={kpiLoading} />}

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 animate-slideUp">
        <StatCard title="Total Devices" value={kpis.total_devices || stats.total_devices || 0} description="Registered devices" icon={Boxes} color="total" />
        <StatCard title="Active Devices" value={kpis.active_devices || stats.active_devices || 0} description="Currently active" icon={Cpu} color="online" />
        <StatCard title="Defects (Month)" value={kpis.defects_this_month || 0} description="This month" icon={HardHat} color="offline" />
        <StatCard title="Defects (Year)" value={kpis.defects_this_year || 0} description="This year" icon={Radar} color="indigo" />
        <StatCard title="Awaiting Receipt" value={kpis.pending_receipts || stats.pending_receipts || 0} description="Pending receipt" icon={CheckSquare} color="pending" />
        <StatCard title="Replacements" value={kpis.replacements_total || 0} description="Total" icon={Wrench} color="purple" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Device Health" icon={Cpu} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Doughnut data={activeInactiveData} options={chartOptions} /></div>
        </Card>
        <Card title="Replacement Confirmation Pipeline" icon={Wrench} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Doughnut data={replacementData} options={chartOptions} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slideUp">
        <Card title="Sub Distribution, Cluster and Operator Account Health" icon={HardHat} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Bar data={workforceAccountSplitData} options={chartOptions} /></div>
        </Card>
        <Card title="Sub Distribution, Cluster and Operator Device Health" icon={Boxes} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Bar data={workforceDeviceSplitData} options={chartOptions} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slideUp">
        <Card title="Defect Trend (12 Months)" icon={Activity} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Line data={defectTrendData} options={chartOptions} /></div>
        </Card>
        <Card title="Distribution Throughput" icon={Truck} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Bar data={distributionTrendData} options={chartOptions} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slideUp">
        <Card title="Returns By Status" icon={RotateCcw} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Bar data={returnStatusData} options={chartOptions} /></div>
        </Card>

        <Card title="Pending Action Queue" icon={CheckSquare} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Bar data={pendingActionQueueData} options={chartOptions} /></div>
        </Card>

      </div>

      <div className="grid grid-cols-1 lg:grid-cols-1 gap-6 animate-slideUp">
        <Card title="Operational Alerts" icon={Clock}>
          <div className="space-y-3">
            {alerts.length === 0 ? (
              <p className="text-sm text-gray-500">No active alerts.</p>
            ) : alerts.map((alert, idx) => (
              <Link
                key={`${alert.title}-${idx}`}
                to={alert.link || '/dashboard'}
                className="block p-3 rounded-lg border border-gray-200 hover:bg-gray-50"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-gray-800">{alert.title}</p>
                  <StatusBadge status={alert.type === 'error' ? 'critical' : 'pending'} size="sm" />
                </div>
                <p className="text-xs text-gray-600 mt-1">{alert.message}</p>
              </Link>
            ))}
            <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
              <p className="text-xs text-slate-500">Replacement Success Rate</p>
              <p className="text-2xl font-bold text-slate-900">{kpis.replacement_success_rate || 0}%</p>
              <p className="text-xs text-slate-500 mt-1">Confirmed replacement completion</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Recent Distributions"
          icon={Truck}
          action={
            <Link to="/distributions" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>
          ) : (
            <div className="space-y-3">
              {distributions.slice(0, 5).map((dist) => (
                <div key={dist.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{dist.distribution_id}</p>
                    <p className="text-xs text-gray-500">{dist.from_user_name} to {dist.to_user_name}</p>
                    <p className="text-xs text-gray-400 mt-1">{dist.device_count || dist.device_ids?.length || 0} devices</p>
                  </div>
                  <StatusBadge status={dist.status} />
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Pending Returns"
          icon={RotateCcw}
          action={
            <Link to="/returns" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {returnRequests.filter((r) => r.status !== 'approved').slice(0, 4).map((ret) => (
              <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{ret.device_name || ret.device_type || 'Unknown'}</p>
                  <p className="text-xs text-gray-500">{ret.reason}</p>
                  <p className="text-xs text-gray-400 mt-1">By: {ret.initiated_by_name || 'Unknown'}</p>
                </div>
                <StatusBadge status={ret.status} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-2xl font-bold text-green-600">{distributions.filter((d) => d.status === 'approved').length}</p>
            <p className="text-sm text-gray-600 mt-1">Approved</p>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <p className="text-2xl font-bold text-yellow-600">{distributions.filter((d) => d.status === 'pending').length}</p>
            <p className="text-sm text-gray-600 mt-1">Pending</p>
          </div>
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-2xl font-bold text-blue-600">{distributions.filter((d) => d.status === 'in_transit' || d.status === 'in-transit').length}</p>
            <p className="text-sm text-gray-600 mt-1">In Transit</p>
          </div>
          <div className="text-center p-4 bg-red-50 rounded-lg">
            <p className="text-2xl font-bold text-red-600">{distributions.filter((d) => d.status === 'rejected').length}</p>
            <p className="text-sm text-gray-600 mt-1">Rejected</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ManagerDashboard;
