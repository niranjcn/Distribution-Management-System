import { useState, useEffect } from 'react';
import { buildDateParams } from '../../components/ui/DateRangeFilter';
import { dashboardAPI, usersAPI, defectsAPI, reassignmentRequestsAPI } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';
import DateRangeFilter from '../../components/ui/DateRangeFilter';
import ErrorBoundary from '../../components/ui/ErrorBoundary';
import HierarchySelector from '../../components/dashboard/HierarchySelector';
import UserKpiSection from '../../components/dashboard/UserKpiSection';
import DashboardStatCards from '../../components/dashboard/DashboardStatCards';
import DistribAnalyticsCards from '../../components/dashboard/DistribAnalyticsCards';
import DeviceCharts from '../../components/dashboard/DeviceCharts';
import RecentActivitiesList from '../../components/dashboard/RecentActivitiesList';
import CriticalAlertsCard from '../../components/dashboard/CriticalAlertsCard';
import RecentUsersList from '../../components/dashboard/RecentUsersList';
import RecentDefectsList from '../../components/dashboard/RecentDefectsList';

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
          usersAPI.getUsers({ page_size: 10 }).catch(err => { console.error('Failed to load users:', err); showToast('Failed to load users', 'error'); return { data: [] }; }),
          defectsAPI.getDefects(dateParams).catch(err => { console.error('Failed to load defects:', err); showToast('Failed to load defects', 'error'); return { data: [] }; }),
          dashboardAPI.getDistributionDeviceAnalytics(dateParams).catch(err => { console.error('Failed to load distribution analytics:', err); showToast('Failed to load distribution analytics', 'error'); return { data: null }; }),
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

      <ErrorBoundary name="Stat Cards"><DashboardStatCards stats={stats} kpis={kpis} reliabilitySummary={reliabilitySummary} dateRange={dateRange} loading={loading} /></ErrorBoundary>

      <ErrorBoundary name="Distribution Analytics"><DistribAnalyticsCards data={distribAnalytics} /></ErrorBoundary>

      <ErrorBoundary name="Hierarchy Selector">
        <HierarchySelector onSelect={handleHierarchySelect} selectedUserId={selectedUser?.id} />
        {userKpi && <UserKpiSection userKpi={userKpi} loading={kpiLoading} />}
      </ErrorBoundary>

      <ErrorBoundary name="Charts"><DeviceCharts charts={charts} /></ErrorBoundary>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary name="Recent Activities"><RecentActivitiesList activities={recentActivities} loading={loading} /></ErrorBoundary>
        <ErrorBoundary name="Critical Alerts"><CriticalAlertsCard alerts={alerts} pendingReassignments={pendingReassignments} replacementSuccessRate={kpis.replacement_success_rate} /></ErrorBoundary>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary name="Recent Users"><RecentUsersList users={users} /></ErrorBoundary>
        <ErrorBoundary name="Recent Defects"><RecentDefectsList defects={defectReports} /></ErrorBoundary>
      </div>
    </div>
  );
};

export default AdminDashboard;
