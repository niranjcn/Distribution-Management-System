import { memo, useMemo } from 'react'
import { Doughnut, Pie, Line } from 'react-chartjs-2'
import { ShieldCheck, Cpu, Activity } from 'lucide-react'
import Card from '../ui/Card'
import { chartOptions } from '../../utils/chartConfig'

const DeviceCharts = ({ charts }) => {
  const activeInactiveData = useMemo(() => ({
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [charts.device_active_split?.active || 0, charts.device_active_split?.inactive || 0],
      backgroundColor: ['#10b981', '#ef4444'],
      borderColor: ['#065F46', '#7F1D1D'],
      borderWidth: 1,
    }],
  }), [charts.device_active_split])

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
  }), [charts.device_status])

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
  }), [charts.defect_trend_12m])

  return (
    <>
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
    </>
  )
}

export default memo(DeviceCharts)
