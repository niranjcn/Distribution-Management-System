import { useMemo } from 'react';
import { Doughnut, Line, Bar } from 'react-chartjs-2';
import StatCard from '../ui/StatCard';
import Card from '../ui/Card';
import {
  Boxes, Cpu, AlertTriangle, Truck, HardHat, Activity, TrendingUp, Loader2
} from 'lucide-react';

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#5F6368', boxWidth: 12, font: { family: 'Inter, Segoe UI, sans-serif', size: 11 } },
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
    x: { ticks: { color: '#5F6368' }, grid: { color: 'rgba(0, 0, 0, 0.06)' } },
    y: { ticks: { color: '#5F6368' }, grid: { color: 'rgba(0, 0, 0, 0.06)' } },
  },
};

const UserKpiSection = ({ userKpi, loading }) => {
  const kpis = userKpi?.kpis || {};
  const charts = userKpi?.charts || {};
  const userInfo = userKpi?.user || {};

  const deviceStatusData = useMemo(() => {
    const ds = charts.device_status || {};
    return {
      labels: Object.keys(ds).length ? Object.keys(ds).map((s) => s.replace(/_/g, ' ')) : ['No data'],
      datasets: [{
        data: Object.keys(ds).length ? Object.values(ds) : [1],
        backgroundColor: ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#a855f7'],
        borderWidth: 1,
        borderColor: '#FFFFFF',
      }],
    };
  }, [charts.device_status]);

  const defectTrendData = useMemo(() => {
    const trend = charts.defect_trend_12m || [];
    return {
      labels: trend.map((d) => d.month),
      datasets: [
        {
          label: 'Reported',
          data: trend.map((d) => d.reported),
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.18)',
          fill: true,
          tension: 0.35,
        },
        {
          label: 'Resolved',
          data: trend.map((d) => d.resolved),
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.12)',
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }, [charts.defect_trend_12m]);

  const distributionTrendData = useMemo(() => {
    const trend = charts.distribution_trend_12m || [];
    return {
      labels: trend.map((d) => d.month),
      datasets: [
        {
          label: 'Total',
          data: trend.map((d) => d.total),
          backgroundColor: '#64748b',
        },
        {
          label: 'Delivered',
          data: trend.map((d) => d.delivered),
          backgroundColor: '#10b981',
        },
      ],
    };
  }, [charts.distribution_trend_12m]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!userKpi) {
    return null;
  }

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4">
        <p className="text-xs text-blue-500 uppercase tracking-wide font-medium">Scoped View</p>
        <p className="text-lg font-bold text-gray-800 mt-0.5">{userInfo.name}</p>
        <p className="text-sm text-gray-500 capitalize">{userInfo.role?.replace(/_/g, ' ')}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatCard title="Devices in Hand" value={kpis.devices_in_hand ?? 0} description="Held by user" icon={Boxes} color="total" />
        <StatCard title="Devices in Hierarchy" value={kpis.devices_in_hierarchy ?? 0} description="Under user's chain" icon={Cpu} color="online" />
        <StatCard title="Active Devices" value={kpis.hierarchy_active_devices ?? 0} description="Active in hierarchy" icon={TrendingUp} color="green" />
        <StatCard title="Inactive Devices" value={kpis.hierarchy_inactive_devices ?? 0} description="Inactive in hierarchy" icon={AlertTriangle} color="offline" />
        <StatCard title="Distributed" value={kpis.distributed_count ?? 0} description="Delivered distributions" icon={Truck} color="blue" />
        <StatCard title="Defects" value={kpis.total_defects ?? 0} description="Total reported" icon={HardHat} color="red" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card title="Device Status Distribution" icon={Cpu} className="industrial-chart-card" padding={false}>
          <div className="h-72 p-4 flex items-center justify-center">
            {Object.keys(charts.device_status || {}).length > 0 ? (
              <Doughnut data={deviceStatusData} options={chartOptions} />
            ) : (
              <p className="text-sm text-gray-400">No device data</p>
            )}
          </div>
        </Card>
        <Card title="Active vs Inactive" icon={Activity} className="industrial-chart-card" padding={false}>
          <div className="h-72 p-4">
            <Doughnut
              data={{
                labels: ['Active', 'Inactive'],
                datasets: [{
                  data: [kpis.hierarchy_active_devices ?? 0, kpis.hierarchy_inactive_devices ?? 0],
                  backgroundColor: ['#10b981', '#ef4444'],
                  borderColor: '#FFFFFF',
                  borderWidth: 1,
                }],
              }}
              options={chartOptions}
            />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card title="Defect Trend (12 Months)" icon={HardHat} className="industrial-chart-card" padding={false}>
          <div className="h-72 p-4">
            {(charts.defect_trend_12m || []).length > 0 ? (
              <Line data={defectTrendData} options={chartOptions} />
            ) : (
              <p className="text-sm text-gray-400 text-center pt-20">No defect data</p>
            )}
          </div>
        </Card>
        <Card title="Distribution Trend (12 Months)" icon={Truck} className="industrial-chart-card" padding={false}>
          <div className="h-72 p-4">
            {(charts.distribution_trend_12m || []).length > 0 ? (
              <Bar data={distributionTrendData} options={chartOptions} />
            ) : (
              <p className="text-sm text-gray-400 text-center pt-20">No distribution data</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default UserKpiSection;
