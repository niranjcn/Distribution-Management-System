import { useState, useEffect, useMemo } from 'react';
import Card from '../components/ui/Card';
import { reportsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { 
  BarChart3,
  Box, Package, AlertTriangle, RotateCcw, Loader2
} from 'lucide-react';

const LOCATION_LABELS = {
  noc: 'PDIC / NOC',
  staff: 'pdic_staff',
  sub_distributor: 'Sub-Distributors',
  cluster: 'Clusters',
  operator: 'Operators',
};

const CONDITION_STYLES = [
  { label: 'Available', key: 'available', color: 'bg-emerald-500', stroke: '#10b981' },
  { label: 'Distributed', key: 'distributed', color: 'bg-blue-500', stroke: '#3b82f6' },
  { label: 'In Use', key: 'in_use', color: 'bg-cyan-500', stroke: '#06b6d4' },
  { label: 'Defective', key: 'defective', color: 'bg-red-500', stroke: '#ef4444' },
  { label: 'Returned', key: 'returned', color: 'bg-amber-500', stroke: '#f59e0b' },
  { label: 'Maintenance', key: 'maintenance', color: 'bg-violet-500', stroke: '#8b5cf6' },
];

const toMonthDate = (monthValue) => {
  if (!monthValue) return null;
  const parsed = new Date(monthValue);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const buildRangeStart = (range) => {
  const now = new Date();
  const start = new Date(now);

  if (range === 'today') {
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (range === 'last7') {
    start.setDate(start.getDate() - 6);
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (range === 'last30') {
    start.setDate(start.getDate() - 29);
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (range === 'last90') {
    start.setDate(start.getDate() - 89);
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (range === 'thisYear') {
    return new Date(now.getFullYear(), 0, 1);
  }
  return null;
};

const safePct = (num, den) => {
  if (!den || den <= 0) return 0;
  return Math.round((num / den) * 100);
};

const isSbDeviceType = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  return normalized === 'sb' || normalized === 'stb' || normalized === 'settopbox' || normalized === 'setupbox';
};

const toDeviceTypeLabel = (value) => (isSbDeviceType(value) ? 'SB' : (value || '-'));

const Reports = () => {
  const { showToast } = useNotifications();
  const [dateRange, setDateRange] = useState('last30');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [reportType, setReportType] = useState('overview');
  const [inventoryReport, setInventoryReport] = useState(null);
  const [distributionSummary, setDistributionSummary] = useState(null);
  const [defectSummary, setDefectSummary] = useState(null);
  const [returnSummary, setReturnSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const start = buildRangeStart(dateRange);
        const params = {};
        if (start && dateRange !== 'all') {
          params.start_date = start.toISOString();
        }

        const [invRes, distRes, defRes, retRes] = await Promise.all([
          reportsAPI.getInventoryReport(params).catch(err => { console.error('Failed to load inventory report:', err); showToast('Failed to load inventory report', 'error'); return { data: null }; }),
          reportsAPI.getDistributionSummary(params).catch(err => { console.error('Failed to load distribution summary:', err); showToast('Failed to load distribution summary', 'error'); return { data: null }; }),
          reportsAPI.getDefectSummary(params).catch(err => { console.error('Failed to load defect summary:', err); showToast('Failed to load defect summary', 'error'); return { data: null }; }),
          reportsAPI.getReturnSummary(params).catch(err => { console.error('Failed to load return summary:', err); showToast('Failed to load return summary', 'error'); return { data: null }; })
        ]);
        setInventoryReport(invRes.data || null);
        setDistributionSummary(distRes.data || null);
        setDefectSummary(defRes.data || null);
        setReturnSummary(retRes.data || null);
      } catch (error) {
        console.error('Failed to load report data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [dateRange]);

  const monthlyActivity = useMemo(() => {
    const distByMonth = distributionSummary?.by_month || [];
    const retByMonth = returnSummary?.by_month || [];
    const defByMonth = defectSummary?.by_month || [];

    const monthMap = {};
    [...distByMonth, ...retByMonth, ...defByMonth].forEach((entry) => {
      if (entry?.month) {
        monthMap[entry.month] = monthMap[entry.month] || {
          month: entry.month,
          distributions: 0,
          returns: 0,
          defects: 0,
        };
      }
    });

    distByMonth.forEach((entry) => {
      if (entry?.month && monthMap[entry.month]) {
        monthMap[entry.month].distributions = Number(entry.count || 0);
      }
    });
    retByMonth.forEach((entry) => {
      if (entry?.month && monthMap[entry.month]) {
        monthMap[entry.month].returns = Number(entry.count || 0);
      }
    });
    defByMonth.forEach((entry) => {
      if (entry?.month && monthMap[entry.month]) {
        monthMap[entry.month].defects = Number(entry.count || 0);
      }
    });

    const allMonths = Object.values(monthMap).sort((a, b) => {
      const da = toMonthDate(a.month);
      const db = toMonthDate(b.month);
      if (!da || !db) return 0;
      return da.getTime() - db.getTime();
    });

    const start = buildRangeStart(dateRange);
    if (!start || dateRange === 'all') return allMonths;

    return allMonths.filter((entry) => {
      const d = toMonthDate(entry.month);
      if (!d) return false;
      return d >= start;
    });
  }, [distributionSummary, returnSummary, defectSummary, dateRange]);

  const devicesByLocation = useMemo(() => {
    const byLocation = inventoryReport?.by_location || {};
    const total = Number(inventoryReport?.total_devices || 0);
    const rows = Object.entries(byLocation).map(([key, value]) => {
      const count = Number(value || 0);
      return {
        location: LOCATION_LABELS[key] || key.replace(/_/g, ' '),
        count,
        percentage: safePct(count, total),
      };
    });
    return rows.sort((a, b) => b.count - a.count);
  }, [inventoryReport]);

  const devicesByCondition = useMemo(() => {
    const byStatus = inventoryReport?.by_status || {};
    return CONDITION_STYLES
      .map((item) => ({
        condition: item.label,
        count: Number(byStatus[item.key] || 0),
        color: item.color,
        stroke: item.stroke,
      }))
      .filter((item) => item.count > 0);
  }, [inventoryReport]);

  // Calculate statistics
  const stats = {
    totalDevices: Number(inventoryReport?.total_devices || 0),
    activeDevices: Number((inventoryReport?.by_status?.available || 0) + (inventoryReport?.by_status?.distributed || 0) + (inventoryReport?.by_status?.in_use || 0)),
    inStockDevices: Number(inventoryReport?.by_status?.available || 0),
    distributedDevices: Number((inventoryReport?.by_status?.distributed || 0) + (inventoryReport?.by_status?.in_use || 0)),
    defectiveDevices: Number(inventoryReport?.by_status?.defective || 0),
    totalDistributions: Number(distributionSummary?.total || 0),
    pendingDistributions: Number((distributionSummary?.by_status?.pending || 0) + (distributionSummary?.by_status?.in_transit || 0)),
    completedDistributions: Number((distributionSummary?.by_status?.approved || 0) + (distributionSummary?.by_status?.delivered || 0)),
    totalDefects: Number(defectSummary?.total || 0),
    pendingDefects: Number((defectSummary?.by_status?.reported || 0) + (defectSummary?.by_status?.under_review || 0)),
    totalReturns: Number(returnSummary?.total || 0),
    pendingReturns: Number((returnSummary?.by_status?.pending || 0) + (returnSummary?.by_status?.in_transit || 0))
  };

  const reportTypes = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Reports & Analytics</h1>
          <p className="text-gray-500 mt-1">View system statistics and generate reports</p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Report Type</label>
            <div className="flex flex-wrap gap-2">
              {reportTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => setReportType(type.id)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                    reportType === type.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  <type.icon className="w-4 h-4" />
                  {type.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
            <div className="flex gap-2">
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="today">Today</option>
                <option value="last7">Last 7 Days</option>
                <option value="last30">Last 30 Days</option>
                <option value="last90">Last 90 Days</option>
                <option value="thisYear">This Year</option>
                <option value="all">All Time</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            {dateRange === 'custom' && (
              <div className="flex gap-2 mt-2">
                <input
                  type="date"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <span className="self-center text-gray-500">to</span>
                <input
                  type="date"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Overview Stats */}
      {reportType === 'overview' && (
        <div className="space-y-6">
          {loading && (
            <Card>
              <div className="py-16 flex flex-col items-center justify-center">
                <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
                <p className="text-sm text-gray-500 mt-4">Loading report data...</p>
              </div>
            </Card>
          )}
          {!loading && (
          <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="inline-flex p-3 rounded-lg bg-blue-100 mb-2">
            <Box className="w-6 h-6 text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-gray-800">{stats.totalDevices}</p>
          <p className="text-sm text-gray-500">Total Devices</p>
        </Card>
        <Card className="text-center">
          <div className="inline-flex p-3 rounded-lg bg-green-100 mb-2">
            <Package className="w-6 h-6 text-green-600" />
          </div>
          <p className="text-2xl font-bold text-gray-800">{stats.totalDistributions}</p>
          <p className="text-sm text-gray-500">Distributions</p>
        </Card>
        <Card className="text-center">
          <div className="inline-flex p-3 rounded-lg bg-red-100 mb-2">
            <AlertTriangle className="w-6 h-6 text-red-600" />
          </div>
          <p className="text-2xl font-bold text-gray-800">{stats.totalDefects}</p>
          <p className="text-sm text-gray-500">Defect Reports</p>
        </Card>
        <Card className="text-center">
          <div className="inline-flex p-3 rounded-lg bg-orange-100 mb-2">
            <RotateCcw className="w-6 h-6 text-orange-600" />
          </div>
          <p className="text-2xl font-bold text-gray-800">{stats.totalReturns}</p>
          <p className="text-sm text-gray-500">Return Requests</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Devices by Location */}
        <Card title="Devices by Location">
          <div className="space-y-4">
            {devicesByLocation.length === 0 ? (
              <p className="text-sm text-gray-500">No location data available yet.</p>
            ) : (
              devicesByLocation.map((item, index) => (
                <div key={`${item.location}-${index}`}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700">{item.location}</span>
                    <span className="font-medium text-gray-800">{item.count} ({item.percentage}%)</span>
                  </div>
                  <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-blue-500 to-cyan-500"
                      style={{ width: `${item.percentage}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Devices by Condition */}
        <Card title="Devices by Condition">
          <div className="flex items-center justify-center gap-8 py-4">
            <div className="relative w-32 h-32">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                {devicesByCondition.length === 0 ? (
                  <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="20" />
                ) : (
                  devicesByCondition.reduce((acc, item, index) => {
                    const total = devicesByCondition.reduce((sum, i) => sum + i.count, 0);
                    const percentage = total > 0 ? (item.count / total) * 100 : 0;
                    const previousPercentage = devicesByCondition
                      .slice(0, index)
                      .reduce((sum, i) => sum + (total > 0 ? (i.count / total) * 100 : 0), 0);

                    acc.push(
                      <circle
                        key={index}
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke={item.stroke}
                        strokeWidth="20"
                        strokeDasharray={`${percentage * 2.51} ${251 - percentage * 2.51}`}
                        strokeDashoffset={`${-previousPercentage * 2.51}`}
                      />
                    );
                    return acc;
                  }, [])
                )}
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-800">
                    {devicesByCondition.reduce((sum, i) => sum + i.count, 0)}
                  </p>
                  <p className="text-xs text-gray-500">Total</p>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              {devicesByCondition.length === 0 ? (
                <p className="text-sm text-gray-500">No condition data available yet.</p>
              ) : (
                devicesByCondition.map((item, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${item.color}`} />
                    <span className="text-sm text-gray-700">{item.condition}</span>
                    <span className="text-sm font-medium text-gray-800">{item.count}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </Card>

        {/* Monthly Activity */}
        <Card title="Monthly Activity" className="lg:col-span-2">
          <div className="h-64 flex items-end gap-2 pt-4">
            {monthlyActivity.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-sm text-gray-500">
                No activity data available for the selected range.
              </div>
            ) : (
              monthlyActivity.map((month, index) => {
                const peak = Math.max(
                  ...monthlyActivity.map((m) => Math.max(m.distributions, m.returns, m.defects)),
                  1
                );
                return (
                  <div key={index} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex gap-1 h-48">
                      <div
                        className="flex-1 bg-blue-500 rounded-t"
                        style={{ height: `${(month.distributions / peak) * 100}%` }}
                        title={`Distributions: ${month.distributions}`}
                      />
                      <div
                        className="flex-1 bg-orange-500 rounded-t"
                        style={{ height: `${(month.returns / peak) * 100}%` }}
                        title={`Returns: ${month.returns}`}
                      />
                      <div
                        className="flex-1 bg-red-500 rounded-t"
                        style={{ height: `${(month.defects / peak) * 100}%` }}
                        title={`Defects: ${month.defects}`}
                      />
                    </div>
                    <span className="text-xs text-gray-500">{month.month.slice(0, 3)}</span>
                  </div>
                );
              })
            )}
          </div>
          <div className="flex justify-center gap-6 mt-4 pt-4 border-t">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-blue-500 rounded" />
              <span className="text-sm text-gray-600">Distributions</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-orange-500 rounded" />
              <span className="text-sm text-gray-600">Returns</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded" />
              <span className="text-sm text-gray-600">Defects</span>
            </div>
          </div>
        </Card>
      </div>

      

      {/* Summary Table */}
      <Card title="Summary Statistics">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Metric</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Total</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Pending</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Completed</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr className="hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <Box className="w-4 h-4 text-blue-500" />
                    <span className="text-gray-800">Devices</span>
                  </div>
                </td>
                <td className="text-right py-3 px-4 font-medium">{stats.totalDevices}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.inStockDevices}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.distributedDevices}</td>
                <td className="text-right py-3 px-4">
                  <span className="text-green-600">
                    {safePct(stats.distributedDevices, stats.totalDevices)}%
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <Package className="w-4 h-4 text-green-500" />
                    <span className="text-gray-800">Distributions</span>
                  </div>
                </td>
                <td className="text-right py-3 px-4 font-medium">{stats.totalDistributions}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.pendingDistributions}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.completedDistributions}</td>
                <td className="text-right py-3 px-4">
                  <span className="text-green-600">
                    {safePct(stats.completedDistributions, stats.totalDistributions)}%
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    <span className="text-gray-800">Defect Reports</span>
                  </div>
                </td>
                <td className="text-right py-3 px-4 font-medium">{stats.totalDefects}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.pendingDefects}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.totalDefects - stats.pendingDefects}</td>
                <td className="text-right py-3 px-4">
                  <span className="text-yellow-600">
                    {safePct(stats.totalDefects - stats.pendingDefects, stats.totalDefects)}%
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <RotateCcw className="w-4 h-4 text-orange-500" />
                    <span className="text-gray-800">Returns</span>
                  </div>
                </td>
                <td className="text-right py-3 px-4 font-medium">{stats.totalReturns}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.pendingReturns}</td>
                <td className="text-right py-3 px-4 text-gray-600">{stats.totalReturns - stats.pendingReturns}</td>
                <td className="text-right py-3 px-4">
                  <span className="text-green-600">
                    {safePct(stats.totalReturns - stats.pendingReturns, stats.totalReturns)}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
        </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Reports;

