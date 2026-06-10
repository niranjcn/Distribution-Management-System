import { useState, useEffect } from 'react';
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
import StatusBadge from '../../components/ui/StatusBadge';
import DeviceIdentity from '../../components/ui/DeviceIdentity';
import Button from '../../components/ui/Button';
import { useAuth } from '../../context/AuthContext';
import { dashboardAPI, devicesAPI, defectsAPI, returnsAPI, distributionsAPI } from '../../services/api';
import {
  Box,
  AlertTriangle,
  RotateCcw,
  Cpu,
  ArrowRight,
  Plus,
  Eye,
  Package,
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

const OperatorDashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({});
  const [advanced, setAdvanced] = useState({ kpis: {}, charts: {}, alerts: [] });
  const [myDevices, setMyDevices] = useState([]);
  const [myDefects, setMyDefects] = useState([]);
  const [myReturns, setMyReturns] = useState([]);
  const [distributions, setDistributions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [statsRes, advancedRes, devRes, defRes, retRes, distRes] = await Promise.all([
          dashboardAPI.getStats().catch(() => ({ data: {} })),
          dashboardAPI.getAdvancedMetrics().catch(() => ({ data: { kpis: {}, charts: {}, alerts: [] } })),
          devicesAPI.getDevices().catch(() => ({ data: [] })),
          defectsAPI.getDefects().catch(() => ({ data: [] })),
          returnsAPI.getReturns().catch(() => ({ data: [] })),
          distributionsAPI.getDistributions({ status: 'pending_receipt' }).catch(() => ({ data: [] }))
        ]);
        setStats(statsRes.data || {});
        setAdvanced(advancedRes.data || { kpis: {}, charts: {}, alerts: [] });
        setMyDevices(devRes.data || []);
        setMyDefects(defRes.data || []);
        setMyReturns(retRes.data || []);
        setDistributions(distRes.data || []);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const pendingReceipts = distributions.filter(
    d => d.status === 'pending_receipt' && String(d.to_user_id) === String(user?.id)
  );

  const charts = advanced.charts || {};
  const myDeviceSplitData = {
    labels: ['Active', 'Inactive'],
    datasets: [{
      data: [
        charts.my_device_active_split?.active || myDevices.filter((d) => ['active', 'available', 'distributed', 'in_use'].includes(d.status)).length,
        charts.my_device_active_split?.inactive || myDevices.filter((d) => !['active', 'available', 'distributed', 'in_use'].includes(d.status)).length,
      ],
      backgroundColor: ['#10b981', '#ef4444'],
      borderWidth: 1,
    }],
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Operator Dashboard</h1>
          <p className="text-gray-500 mt-1">View your assigned devices and manage reports.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/defects/create">
            <Button icon={AlertTriangle} variant="danger">Report Defect</Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard title="Assigned Devices" value={stats.assigned_devices || myDevices.length} icon={Box} color="blue" />
        <StatCard title="Active" value={stats.active_devices || myDevices.filter(d => d.status === 'active').length} icon={Cpu} color="green" />
        <StatCard title="In Use" value={stats.in_use_devices || myDevices.filter(d => d.status === 'in_use').length} icon={Cpu} color="purple" />
        <StatCard title="My Defect Reports" value={stats.defect_reports || myDefects.length} icon={AlertTriangle} color="red" />
        <StatCard title="Pending Returns" value={stats.pending_returns || myReturns.filter(r => r.status === 'pending').length} icon={RotateCcw} color="yellow" />
      </div>

      <Card title="My Device Active vs Inactive" icon={Cpu} padding={false}>
        <div className="h-72 p-4"><Doughnut data={myDeviceSplitData} options={doughnutOptions} /></div>
      </Card>

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

      {/* My Devices */}
      <Card
        title="My Assigned Devices"
        icon={Box}
        action={
          <Link to="/devices" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {myDevices.slice(0, 6).map((device) => (
            <div key={device.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Box className="w-5 h-5 text-blue-600" />
                </div>
                <StatusBadge status={device.status} />
              </div>
              <DeviceIdentity device={device} />
              <div className="flex items-center gap-2 mt-3">
                <Link to={`/devices/track?serial=${encodeURIComponent(device.serial_number)}`} className="flex-1">
                  <Button variant="outline" size="sm" className="w-full" icon={Eye}>
                    View
                  </Button>
                </Link>
                <Link to="/defects/create" className="flex-1">
                  <Button variant="ghost" size="sm" className="w-full text-red-600" icon={AlertTriangle}>
                    Report
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
        {myDevices.length === 0 && (
          <div className="text-center py-8">
            <Box className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No devices assigned to you yet</p>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* My Defect Reports */}
        <Card
          title="My Defect Reports"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myDefects.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-gray-500">No defect reports</p>
                <Link to="/defects/create" className="text-sm text-blue-600 hover:text-blue-700 mt-2 inline-block">
                  Report a defect
                </Link>
              </div>
            ) : (
              myDefects.map((defect) => (
                <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-800">{defect.device_name || defect.device_type || 'Unknown'}</p>
                      <StatusBadge status={defect.severity} size="sm" />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{defect.defect_type}</p>
                    <p className="text-xs text-gray-400">{defect.created_at}</p>
                  </div>
                  <StatusBadge status={defect.status} />
                </div>
              ))
            )}
          </div>
        </Card>

        {/* My Return Requests */}
        <Card
          title="My Return Requests"
          icon={RotateCcw}
          action={
            <Link to="/returns" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myReturns.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-gray-500">No return requests</p>
              </div>
            ) : (
              myReturns.map((ret) => (
                <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{ret.device_name || ret.device_type || 'Unknown'}</p>
                    <p className="text-xs text-gray-500">{ret.reason}</p>
                    <p className="text-xs text-gray-400 mt-1">{ret.created_at}</p>
                  </div>
                  <StatusBadge status={ret.status} />
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default OperatorDashboard;
