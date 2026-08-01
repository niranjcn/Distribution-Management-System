import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import StatCard from '../components/ui/StatCard';
import { dashboardAPI, devicesAPI, defectsAPI, returnsAPI, distributionsAPI, usersAPI } from '../services/api';
import DateRangeFilter, { buildDateParams } from '../components/ui/DateRangeFilter';
import { ArrowLeft, Activity, CheckSquare, ShieldCheck, Users, HardHat, RotateCcw, Package } from 'lucide-react';

const ROLE_LABELS = {
  sub_distributor: 'Sub Distributor',
  sub_distribution_manager: 'Sub Distribution Manager',
  cluster: 'Cluster',
  operator: 'Operator',
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

const ViewAsDashboard = () => {
  const { userId } = useParams();
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const dateParams = buildDateParams(dateRange);
        const res = await dashboardAPI.getViewAsDashboard(userId, dateParams);
        if (!res.success) throw new Error(res.message || 'Failed');
        setData(res.data);
      } catch (err) {
        setError(err.message || 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [userId, dateRange]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-700 font-medium">{error || 'Failed to load dashboard'}</p>
          <Link to="/view-as" className="text-sm text-red-600 underline mt-2 inline-block">Back to search</Link>
        </div>
      </div>
    );
  }

  const { user, stats, advanced, devices, users } = data;
  const kpis = advanced?.kpis || {};
  const charts = advanced?.charts || {};

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <Link to="/view-as" className="text-sm text-green-600 hover:text-green-700 flex items-center gap-1 mb-2">
            <ArrowLeft className="w-4 h-4" /> Back to search
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{user.name}</h1>
              <p className="text-sm text-gray-500">{ROLE_LABELS[user.role] || user.role} &middot; ID: {user.id}</p>
            </div>
          </div>
        </div>
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="My Devices" value={stats?.my_devices ?? 0} description={`Devices held in ${periodLabel(dateRange.range)}`} color="total" />
        {stats?.available_devices !== undefined && (
          <StatCard title="Available" value={stats.available_devices} description="Ready for use" color="online" />
        )}
        {stats?.distributions_sent !== undefined && (
          <StatCard title="Sent" value={stats.distributions_sent} description={`Distributions sent in ${periodLabel(dateRange.range)}`} color="blue" />
        )}
        {stats?.distributions_received !== undefined && (
          <StatCard title="Received" value={stats.distributions_received} description={`Distributions received in ${periodLabel(dateRange.range)}`} color="teal" />
        )}
        {stats?.pending_distributions !== undefined && (
          <StatCard title="Pending" value={stats.pending_distributions} description="Awaiting action" color="pending" />
        )}
        {stats?.my_defects !== undefined && (
          <StatCard title="My Defects" value={stats.my_defects} description={`Defects in ${periodLabel(dateRange.range)}`} color="red" />
        )}
        {stats?.my_returns !== undefined && (
          <StatCard title="My Returns" value={stats.my_returns} description={`Returns in ${periodLabel(dateRange.range)}`} color="purple" />
        )}
        {stats?.operator_count !== undefined && (
          <StatCard title="Operators" value={stats.operator_count} description="Under me" color="indigo" />
        )}
        {stats?.defect_reports !== undefined && (
          <StatCard title="Defect Reports" value={stats.defect_reports} description={`Defects in ${periodLabel(dateRange.range)}`} color="red" />
        )}
        {stats?.return_requests !== undefined && (
          <StatCard title="Return Requests" value={stats.return_requests} description={`Returns in ${periodLabel(dateRange.range)}`} color="purple" />
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 animate-slideUp">
        {kpis.hierarchy_active_devices !== undefined && (
          <StatCard title="Active Devices" value={kpis.hierarchy_active_devices ?? 0} icon={Activity} color="online" />
        )}
        {kpis.hierarchy_inactive_devices !== undefined && (
          <StatCard title="Inactive Devices" value={kpis.hierarchy_inactive_devices ?? 0} icon={ShieldCheck} color="offline" />
        )}
        {kpis.hierarchy_total_devices !== undefined && (
          <StatCard title="Total in Hierarchy" value={kpis.hierarchy_total_devices ?? 0} icon={Package} color="total" />
        )}
      </div>

      {devices && devices.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Devices ({devices.length})</h2>
          </div>
          <div className="overflow-auto max-h-80">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">ID</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Device ID</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Type</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Holder</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {devices.map((d) => (
                  <tr key={d.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-800">{d.id}</td>
                    <td className="px-5 py-3 text-gray-800">{d.device_id || '-'}</td>
                    <td className="px-5 py-3 text-gray-600">{d.device_type || '-'}</td>
                    <td className="px-5 py-3"><span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">{d.status}</span></td>
                    <td className="px-5 py-3 text-gray-600">{d.current_holder_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {user.role === 'sub_distributor' && users && users.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">My Operators ({users.length})</h2>
          </div>
          <div className="overflow-auto max-h-60">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">ID</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Email</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-800">{u.id}</td>
                    <td className="px-5 py-3 font-medium text-gray-900">{u.name || 'Unnamed'}</td>
                    <td className="px-5 py-3 text-gray-600">{u.email || '-'}</td>
                    <td className="px-5 py-3"><span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${u.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{u.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {charts.my_device_active_split && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-slideUp">
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-3">Device Status Split</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Active</span>
                <span className="text-sm font-bold text-green-600">{charts.my_device_active_split.active ?? 0}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2.5">
                <div className="bg-green-500 h-2.5 rounded-full" style={{ width: `${((charts.my_device_active_split.active || 0) / ((charts.my_device_active_split.active || 0) + (charts.my_device_active_split.inactive || 0) || 1)) * 100}%` }} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Inactive</span>
                <span className="text-sm font-bold text-red-600">{charts.my_device_active_split.inactive ?? 0}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2.5">
                <div className="bg-red-500 h-2.5 rounded-full" style={{ width: `${((charts.my_device_active_split.inactive || 0) / ((charts.my_device_active_split.active || 0) + (charts.my_device_active_split.inactive || 0) || 1)) * 100}%` }} />
              </div>
            </div>
          </div>

          {charts.cluster_operator_active_split && (
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-3">Cluster/Operator Split</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Cluster Active</span>
                  <span className="text-sm font-bold text-blue-600">{charts.cluster_operator_active_split.cluster_active ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Cluster Inactive</span>
                  <span className="text-sm font-bold text-red-600">{charts.cluster_operator_active_split.cluster_inactive ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Operator Active</span>
                  <span className="text-sm font-bold text-blue-600">{charts.cluster_operator_active_split.operator_active ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Operator Inactive</span>
                  <span className="text-sm font-bold text-red-600">{charts.cluster_operator_active_split.operator_inactive ?? 0}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ViewAsDashboard;
