import { useState, useEffect } from 'react';
import { buildDateParams } from '../../components/ui/DateRangeFilter';
import { dashboardAPI, usersAPI, defectsAPI } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';
import DateRangeFilter from '../../components/ui/DateRangeFilter';
import ErrorBoundary from '../../components/ui/ErrorBoundary';
import HierarchySelector from '../../components/dashboard/HierarchySelector';
import UserKpiSection from '../../components/dashboard/UserKpiSection';
import DashboardStatCards from '../../components/dashboard/DashboardStatCards';
import DistribAnalyticsCards from '../../components/dashboard/DistribAnalyticsCards';
import DeviceCharts from '../../components/dashboard/DeviceCharts';
import RecentUsersList from '../../components/dashboard/RecentUsersList';
import RecentDefectsList from '../../components/dashboard/RecentDefectsList';

const AdminDashboard = () => {
  const { showToast } = useNotifications();
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } });
  const [users, setUsers] = useState([]);
  const [defectReports, setDefectReports] = useState([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [advancedLoading, setAdvancedLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userKpi, setUserKpi] = useState(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [distribAnalytics, setDistribAnalytics] = useState(null);

  useEffect(() => {
    const dateParams = buildDateParams(dateRange);
    let active = true;

    // Fetch in priority batches so sections render as their own data arrives
    // instead of waiting for the slowest endpoint (advanced-metrics).

    // Batch 1 — critical stat cards (fast: /dashboard/stats).
    setStatsLoading(true);
    dashboardAPI.getStats(dateParams)
      .then((res) => { if (active) setStats(res.data || {}); })
      .catch((err) => {
        console.error('Failed to load stats:', err);
        if (active) showToast('Failed to load dashboard stats', 'error');
      })
      .finally(() => { if (active) setStatsLoading(false); });

    // Batch 2 — reliability/KPI cards + charts + distribution analytics.
    setAdvancedLoading(true);
    dashboardAPI.getAdvancedMetrics(dateParams)
      .then((res) => { if (active) setAdvanced(res.data || { kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } }); })
      .catch((err) => {
        console.error('Failed to load advanced metrics:', err);
        if (active) showToast('Failed to load analytics', 'error');
        setAdvanced({ kpis: {}, charts: {}, alerts: [], reliability: { summary: {}, trend: [] } });
      })
      .finally(() => { if (active) setAdvancedLoading(false); });

    dashboardAPI.getDistributionDeviceAnalytics(dateParams)
      .then((res) => { if (active) setDistribAnalytics(res.data || null); })
      .catch((err) => {
        console.error('Failed to load distribution analytics:', err);
        if (active) showToast('Failed to load distribution analytics', 'error');
      });

    // Batch 3 — bottom "Recent Users" / "Recent Defects" lists. Slightly
    // deferred so they do not compete with the top-heavy initial render.
    const loadRecent = async () => {
      try {
        const [usersRes, defectsRes] = await Promise.all([
          usersAPI.getUsers({ page_size: 10 }).catch((err) => { console.error('Failed to load users:', err); return { data: [] }; }),
          defectsAPI.getDefects(dateParams).catch((err) => { console.error('Failed to load defects:', err); return { data: [] }; }),
        ]);
        if (active) {
          setUsers(usersRes.data || []);
          setDefectReports(defectsRes.data || []);
        }
      } catch (error) {
        console.error('Failed to load recent data:', error);
      }
    };
    const recentTimer = window.setTimeout(loadRecent, 400);

    return () => {
      active = false;
      window.clearTimeout(recentTimer);
    };
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
  const reliabilitySummary = advanced.reliability?.summary || {};

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

      <ErrorBoundary name="Stat Cards"><DashboardStatCards stats={stats} kpis={kpis} reliabilitySummary={reliabilitySummary} dateRange={dateRange} statsLoading={statsLoading} advancedLoading={advancedLoading} /></ErrorBoundary>

      <ErrorBoundary name="Distribution Analytics"><DistribAnalyticsCards data={distribAnalytics} /></ErrorBoundary>

      <ErrorBoundary name="Hierarchy Selector">
        <HierarchySelector onSelect={handleHierarchySelect} selectedUserId={selectedUser?.id} />
        {userKpi && <UserKpiSection userKpi={userKpi} loading={kpiLoading} />}
      </ErrorBoundary>

      <ErrorBoundary name="Charts"><DeviceCharts charts={charts} /></ErrorBoundary>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary name="Recent Users"><RecentUsersList users={users} /></ErrorBoundary>
        <ErrorBoundary name="Recent Defects"><RecentDefectsList defects={defectReports} /></ErrorBoundary>
      </div>
    </div>
  );
};

export default AdminDashboard;
