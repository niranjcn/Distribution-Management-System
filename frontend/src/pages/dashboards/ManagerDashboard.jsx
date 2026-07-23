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
import DateRangeFilter, { buildDateParams } from '../../components/ui/DateRangeFilter';
import { dashboardAPI, distributionsAPI, returnsAPI } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';
import HierarchySelector from '../../components/dashboard/HierarchySelector';
import UserKpiSection from '../../components/dashboard/UserKpiSection';
import {
  Activity,
  Clock,
  Cpu,
  Loader2,
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

const periodLabel = (range) => ({
  all: 'all time',
  today: 'today',
  last7: 'last 7 days',
  last30: 'last 30 days',
  last90: 'last 90 days',
  thisYear: 'this year',
  custom: 'selected period',
}[range] || 'selected period');

const ManagerDashboard = () => {
  const { showToast } = useNotifications();
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [] });
  const [distributions, setDistributions] = useState([]);
  const [returnRequests, setReturnRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userKpi, setUserKpi] = useState(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [distribAnalytics, setDistribAnalytics] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const dateParams = buildDateParams(dateRange);
        const [statsRes, advancedRes, distRes, retRes, distribAnalyticsRes] = await Promise.all([
          dashboardAPI.getStats(dateParams).catch(err => { console.error('Failed to load stats:', err); showToast('Failed to load dashboard stats', 'error'); return { data: {} }; }),
          dashboardAPI.getAdvancedMetrics(dateParams).catch(err => { console.error('Failed to load advanced metrics:', err); showToast('Failed to load analytics', 'error'); return { data: { kpis: {}, charts: {}, alerts: [] } }; }),
          distributionsAPI.getDistributions().catch(err => { console.error('Failed to load distributions:', err); showToast('Failed to load distributions', 'error'); return { data: [] }; }),
          returnsAPI.getReturns().catch(err => { console.error('Failed to load returns:', err); showToast('Failed to load returns', 'error'); return { data: [] }; }),
          dashboardAPI.getDistributionDeviceAnalytics().catch(err => { console.error('Failed to load distribution analytics:', err); showToast('Failed to load distribution analytics', 'error'); return { data: null }; }),
        ]);
        setStats(statsRes.data || {});
        setAdvanced(advancedRes.data || { kpis: {}, charts: {}, alerts: [] });
        setDistributions(distRes.data || []);
        setReturnRequests(retRes.data || []);
        setDistribAnalytics(distribAnalyticsRes.data || null);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [dateRange]);

  const handleHierarchySelect = async (selection) => {
    setSelectedUser(selection);
    if (selection && selection.id) {
      setKpiLoading(true);
      setUserKpi(null);
      try {
        const dateParams = buildDateParams(dateRange);
        const res = await dashboardAPI.getUserKpi(selection.id, dateParams);
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

  return (
    <div className="space-y-6">
      <div className="industrial-hero relative overflow-hidden rounded-2xl p-5 sm:p-6 animate-fadeIn">
        <div className="absolute right-0 top-0 h-20 w-20 rounded-full bg-orange-400/20 blur-2xl" />
        <div className="relative z-10">
          <h1 className="text-2xl sm:text-3xl font-bold text-green-900 tracking-wide">Management Ops Console</h1>
          <p className="text-green-700 mt-1">Role-scoped analytics for throughput, defects, replacements, and return control.</p>
        </div>
      </div>

      <div className="flex justify-end">
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 animate-slideUp">
        <StatCard title="Total Devices" value={stats.total_devices ?? 0} description="All registered devices" color="total" />
        <StatCard title="Total Active Devices" value={stats.total_active_devices ?? 0} description="Currently active" color="online" />
        <StatCard title="Total Distributed Devices" value={stats.total_distributed_devices ?? 0} description="Currently distributed" color="teal" />
        <StatCard title="Total Inactive Devices" value={stats.total_inactive_devices ?? 0} description="Currently inactive" color="offline" />
        <StatCard title="Total Defective Devices" value={stats.total_defective_devices ?? 0} description="Currently defective" color="red" />
        <StatCard title="Total Replaced Devices" value={stats.total_replaced_devices ?? 0} description="Ever replaced" color="purple" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 animate-slideUp">
        <StatCard title="Registered in Period" value={stats.registered_in_range ?? 0} description={`Devices created in ${periodLabel(dateRange.range)}`} color="total" />
        <StatCard title="Distributed in Period" value={stats.distributed_in_range ?? 0} description={`Devices distributed in ${periodLabel(dateRange.range)}`} color="blue" />
        <StatCard title="Inactive in Period" value={stats.inactive_in_range ?? 0} description={`Became inactive in ${periodLabel(dateRange.range)}`} color="offline" />
        <StatCard title="Defective in Period" value={stats.defective_in_range ?? 0} description={`Became defective in ${periodLabel(dateRange.range)}`} color="red" />
        <StatCard title="Replacements in Period" value={stats.replacements_in_range ?? 0} description={`Replaced in ${periodLabel(dateRange.range)}`} color="purple" />
      </div>

      {distribAnalytics && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slideUp">
            <div className="bg-gradient-to-br from-blue-50 to-white border border-blue-200 rounded-xl p-4 shadow-sm">
              <p className="text-xs font-semibold text-blue-500 uppercase tracking-wider">Sent to Distribution</p>
              <p className="text-2xl font-bold text-blue-700 mt-1">{distribAnalytics.total_sent_to_distribution ?? 0}</p>
              <p className="text-xs text-blue-400 mt-0.5">Devices distributed/in use</p>
            </div>
            <div className="bg-gradient-to-br from-green-50 to-white border border-green-200 rounded-xl p-4 shadow-sm">
              <p className="text-xs font-semibold text-green-500 uppercase tracking-wider">Remaining Available</p>
              <p className="text-2xl font-bold text-green-700 mt-1">{distribAnalytics.remaining_available_devices ?? 0}</p>
              <p className="text-xs text-green-400 mt-0.5">In stock</p>
            </div>
            {(distribAnalytics.sent_by_type || []).map((item, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{item.device_type}</p>
                <div className="flex items-center justify-between gap-4">
                  <div className="text-center flex-1">
                    <p className="text-lg font-bold text-indigo-700">{item.sent}</p>
                    <p className="text-[10px] text-indigo-400 font-medium uppercase tracking-wide mt-0.5">Distributed</p>
                  </div>
                  <div className="w-px h-10 bg-gray-200" />
                  <div className="text-center flex-1">
                    <p className="text-lg font-bold text-emerald-700">{item.remaining}</p>
                    <p className="text-[10px] text-emerald-400 font-medium uppercase tracking-wide mt-0.5">Remaining</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <HierarchySelector onSelect={handleHierarchySelect} selectedUserId={selectedUser?.id} />
      {userKpi && <UserKpiSection userKpi={userKpi} loading={kpiLoading} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Device Health" icon={Cpu} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Doughnut data={activeInactiveData} options={chartOptions} /></div>
        </Card>
        <Card title="Replacement Confirmation Pipeline" icon={Wrench} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Doughnut data={replacementData} options={chartOptions} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slideUp">
        <Card title="Defect Trend (12 Months)" icon={Activity} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Line data={defectTrendData} options={chartOptions} /></div>
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
