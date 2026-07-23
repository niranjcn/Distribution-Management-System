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
import { Doughnut, Pie, Line, Bar } from 'react-chartjs-2';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import DateRangeFilter, { buildDateParams } from '../../components/ui/DateRangeFilter';
import { dashboardAPI, usersAPI, defectsAPI, reassignmentRequestsAPI } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';
import HierarchySelector from '../../components/dashboard/HierarchySelector';
import UserKpiSection from '../../components/dashboard/UserKpiSection';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckSquare,
  Clock,
  Cpu,
  Loader2,
  ShieldCheck,
  Truck,
  UserCog,
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
        font: {
          family: 'Inter, Segoe UI, sans-serif',
          size: 11,
        },
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

const AdminDashboard = () => {
  const { showToast } = useNotifications();
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } });
  const [recentActivities, setRecentActivities] = useState([]);
  const [users, setUsers] = useState([]);
  const [defectReports, setDefectReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userKpi, setUserKpi] = useState(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [pendingReassignments, setPendingReassignments] = useState(0);
  const [distribAnalytics, setDistribAnalytics] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const dateParams = buildDateParams(dateRange);
        const [statsRes, advancedRes, usersRes, defectsRes, distribAnalyticsRes] = await Promise.all([
          dashboardAPI.getStats(dateParams).catch(err => { console.error('Failed to load stats:', err); showToast('Failed to load dashboard stats', 'error'); return { data: {} }; }),
          dashboardAPI.getAdvancedMetrics(dateParams).catch(err => { console.error('Failed to load advanced metrics:', err); showToast('Failed to load analytics', 'error'); return { data: { kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } } }; }),
          usersAPI.getUsers().catch(err => { console.error('Failed to load users:', err); showToast('Failed to load users', 'error'); return { data: [] }; }),
          defectsAPI.getDefects().catch(err => { console.error('Failed to load defects:', err); showToast('Failed to load defects', 'error'); return { data: [] }; }),
          dashboardAPI.getDistributionDeviceAnalytics().catch(err => { console.error('Failed to load distribution analytics:', err); showToast('Failed to load distribution analytics', 'error'); return { data: null }; }),
        ]);
        setStats(statsRes.data || {});
        setAdvanced(advancedRes.data || { kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } });
        setUsers(usersRes.data || []);
        setDefectReports(defectsRes.data || []);
        setDistribAnalytics(distribAnalyticsRes.data || null);

        try {
          const activitiesRes = await dashboardAPI.getRecentActivities();
          setRecentActivities(activitiesRes.data || []);
        } catch {
          setRecentActivities([]);
        }

        try {
          const reassignRes = await reassignmentRequestsAPI.getRequests({ status: 'pending', page_size: 1 });
          setPendingReassignments(reassignRes?.pagination?.total || 0);
        } catch {
          setPendingReassignments(0);
        }
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
  const reliabilitySummary = advanced.reliability?.summary || {};

  const activeInactiveData = useMemo(() => ({
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [charts.device_active_split?.active || 0, charts.device_active_split?.inactive || 0],
      backgroundColor: ['#10b981', '#ef4444'],
      borderColor: ['#065F46', '#7F1D1D'],
      borderWidth: 1,
    }],
  }), [charts.device_active_split]);

  const deviceStatusData = useMemo(() => ({
    labels: ['Available', 'Distributed', 'In Use', 'Defective', 'Returned'],
    datasets: [{
      data: [
        charts.device_status?.available || 0,
        charts.device_status?.distributed || 0,
        charts.device_status?.in_use || 0,
        charts.device_status?.defective || 0,
        charts.device_status?.returned || 0,
      ],
      backgroundColor: ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#a855f7'],
      borderWidth: 1,
      borderColor: '#FFFFFF',
    }],
  }), [charts.device_status]);

  const defectTrendData = useMemo(() => ({
    labels: (charts.defect_trend_12m || []).map((d) => d.month),
    datasets: [
      {
        label: 'Reported',
        data: (charts.defect_trend_12m || []).map((d) => d.reported),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.18)',
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
      {
        label: 'Replaced',
        data: (charts.defect_trend_12m || []).map((d) => d.replaced),
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.12)',
        fill: true,
        tension: 0.35,
      },
    ],
  }), [charts.defect_trend_12m]);

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="industrial-hero relative overflow-hidden rounded-2xl p-5 sm:p-6 animate-fadeIn">
        <div className="absolute right-0 top-0 h-20 w-20 rounded-full bg-orange-400/20 blur-2xl" />
        <div className="absolute left-8 bottom-0 h-16 w-16 rounded-full bg-red-500/20 blur-2xl" />
        <div className="relative z-10 flex flex-col gap-2">
        <h1 className="text-2xl sm:text-3xl font-bold text-green-900 tracking-wide">Operations Command Center</h1>
          <p className="text-green-700 text-sm sm:text-base">Overview of fleet health, defects, replacements, and workforce distribution.</p>
        </div>
      </div>

      <div className="flex justify-end">
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="Total Devices" value={stats.total_devices ?? 0} description="All registered devices" color="total" />
        <StatCard title="Total Active Devices" value={stats.total_active_devices ?? 0} description="Currently active" color="online" />
        <StatCard title="Total Distributed Devices" value={stats.total_distributed_devices ?? 0} description="Currently distributed" color="teal" />
        <StatCard title="Total Inactive Devices" value={stats.total_inactive_devices ?? 0} description="Currently inactive" color="offline" />
        <StatCard title="Total Defective Devices" value={stats.total_defective_devices ?? 0} description="Currently defective" color="red" />
        <StatCard title="Total Replaced Devices" value={stats.total_replaced_devices ?? 0} description="Ever replaced" color="purple" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="Registered in Period" value={stats.registered_in_range ?? 0} description={`Devices created in ${periodLabel(dateRange.range)}`} color="total" />
        <StatCard title="Distributed in Period" value={stats.distributed_in_range ?? 0} description={`Devices distributed in ${periodLabel(dateRange.range)}`} color="blue" />
        <StatCard title="Inactive in Period" value={stats.inactive_in_range ?? 0} description={`Became inactive in ${periodLabel(dateRange.range)}`} color="offline" />
        <StatCard title="Defective in Period" value={stats.defective_in_range ?? 0} description={`Became defective in ${periodLabel(dateRange.range)}`} color="red" />
        <StatCard title="Replacements in Period" value={stats.replacements_in_range ?? 0} description={`Replaced in ${periodLabel(dateRange.range)}`} color="purple" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 animate-slideUp">
        <StatCard
          title="Defect Incidence"
          value={`${reliabilitySummary.defect_incidence_percentage ?? 0}%`}
          icon={Activity}
          color="red"
          description={`Defects in ${periodLabel(dateRange.range)}`}
        />
        <StatCard
          title="Repaired in 60 Days"
          value={reliabilitySummary.repaired_within_sla_devices ?? 0}
          icon={CheckSquare}
          color="green"
          description={`Resolved within 60 days in ${periodLabel(dateRange.range)}`}
        />
        <StatCard
          title="60-Day Repair Rate"
          value={`${reliabilitySummary.repaired_within_sla_percentage ?? 0}%`}
          icon={ShieldCheck}
          color="indigo"
          description={`Of resolved defects in ${periodLabel(dateRange.range)}`}
        />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slideUp">
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Operators</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_operators ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Sub Distributors</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_sub_distributors ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Clusters</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_clusters ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Staff</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_staff ?? 0}</p></div>
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

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 animate-slideUp">
        <Card title="Device Active vs Inactive" icon={ShieldCheck} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Doughnut data={activeInactiveData} options={chartOptions} /></div>
        </Card>
        <Card title="Device Status Composition" icon={Cpu} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Pie data={deviceStatusData} options={chartOptions} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 animate-slideUp">
        <Card title="12-Month Defect Trend" icon={Activity} className="industrial-chart-card" padding={false}>
          <div className="h-80 p-4"><Line data={defectTrendData} options={chartOptions} /></div>
        </Card>
      </div>



      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Recent Activities"
          icon={Activity}
          action={
            <Link to="/reports" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>
          ) : (
            <div className="space-y-4">
              {recentActivities.slice(0, 5).map((activity) => (
                <div key={activity.id} className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                    <Activity className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{activity.action}</p>
                    <p className="text-sm text-gray-500 truncate">{activity.description}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-gray-400">{activity.user_name || activity.user}</span>
                      <span className="text-xs text-gray-300">.</span>
                      <span className="text-xs text-gray-400">{activity.timestamp ? new Date(activity.timestamp).toLocaleString() : ''}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Critical Ops Alerts" icon={Clock}>
          <div className="space-y-3">
            {pendingReassignments > 0 && (
              <Link
                to="/reassignment-requests"
                className="block rounded-lg border border-amber-200 bg-amber-50 p-3 hover:bg-amber-100 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-amber-800">Reassignment Requests</p>
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-200 text-amber-800">
                    {pendingReassignments} pending
                  </span>
                </div>
                <p className="text-xs text-amber-700 mt-1">
                  Users need reassignment before deletion can complete.
                </p>
              </Link>
            )}
            {alerts.length === 0 ? (
              <p className="text-sm text-gray-500">No active alerts right now.</p>
            ) : alerts.map((alert, idx) => (
              <Link
                key={`${alert.title}-${idx}`}
                to={alert.link || '/dashboard'}
                className="block rounded-lg border border-gray-200 p-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-gray-800">{alert.title}</p>
                  <StatusBadge status={alert.type === 'error' ? 'critical' : 'pending'} size="sm" />
                </div>
                <p className="text-xs text-gray-600 mt-1">{alert.message}</p>
              </Link>
            ))}
            <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
              <p className="text-sm font-semibold text-slate-700">Replacement Success</p>
              <p className="text-2xl font-bold text-slate-900">{kpis.replacement_success_rate ?? 0}%</p>
              <p className="text-xs text-slate-500 mt-1">Confirmed replacement completion ratio</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Recent Users"
          icon={UserCog}
          action={
            <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              Manage users <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {users.slice(0, 5).map((user) => (
              <div key={user.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-sm font-medium text-blue-600">{user.name.split(' ').map((n) => n[0]).join('')}</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{user.name}</p>
                    <p className="text-xs text-gray-500">{user.email}</p>
                  </div>
                </div>
                <StatusBadge status={user.role} size="sm" />
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Recent Defect Reports"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {defectReports.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No defect reports yet</p>
            ) : defectReports.slice(0, 4).map((defect) => (
              <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-800">{defect.device_type || 'Unknown'}</p>
                    <StatusBadge status={defect.severity} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{defect.device_serial || defect.report_id}</p>
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{defect.description}</p>
                </div>
                <StatusBadge status={defect.status} size="sm" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AdminDashboard;

