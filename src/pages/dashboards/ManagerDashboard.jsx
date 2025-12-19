import { Link } from 'react-router-dom';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import { dashboardStats, distributions, defectReports, returnRequests } from '../../data/mockData';
import {
  Box,
  Truck,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  BarChart3,
  ArrowRight,
  TrendingUp
} from 'lucide-react';

const ManagerDashboard = () => {
  const stats = dashboardStats.manager;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Manager Dashboard</h1>
        <p className="text-gray-500 mt-1">Monitor distribution activities and manage approvals.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard title="Total Devices" value={stats.totalDevices} icon={Box} color="blue" />
        <StatCard title="Pending Approvals" value={stats.pendingApprovals} icon={CheckSquare} color="yellow" />
        <StatCard title="Defect Reports" value={stats.defectReports} icon={AlertTriangle} color="red" />
        <StatCard title="Return Requests" value={stats.returnRequests} icon={RotateCcw} color="indigo" />
        <StatCard title="This Month" value={stats.distributionThisMonth} icon={Truck} color="green" />
        <StatCard title="Resolved" value={stats.resolvedDefects} icon={TrendingUp} color="purple" />
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
          <div className="space-y-3">
            {distributions.slice(0, 5).map((dist) => (
              <div key={dist.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{dist.batchId}</p>
                  <p className="text-xs text-gray-500">{dist.fromDistributor} → {dist.toDistributor}</p>
                  <p className="text-xs text-gray-400 mt-1">{dist.deviceCount} devices</p>
                </div>
                <StatusBadge status={dist.status} />
              </div>
            ))}
          </div>
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
            {returnRequests.filter(r => r.status !== 'approved').slice(0, 4).map((ret) => (
              <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{ret.device.model}</p>
                  <p className="text-xs text-gray-500">{ret.reason}</p>
                  <p className="text-xs text-gray-400 mt-1">By: {ret.initiatedBy}</p>
                </div>
                <StatusBadge status={ret.status} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card
        title="Distribution Analytics"
        icon={BarChart3}
        action={
          <Link to="/reports" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
            Full Report
          </Link>
        }
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-2xl font-bold text-green-600">
              {distributions.filter(d => d.status === 'approved').length}
            </p>
            <p className="text-sm text-gray-600 mt-1">Approved</p>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <p className="text-2xl font-bold text-yellow-600">
              {distributions.filter(d => d.status === 'pending').length}
            </p>
            <p className="text-sm text-gray-600 mt-1">Pending</p>
          </div>
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-2xl font-bold text-blue-600">
              {distributions.filter(d => d.status === 'in-transit').length}
            </p>
            <p className="text-sm text-gray-600 mt-1">In Transit</p>
          </div>
          <div className="text-center p-4 bg-red-50 rounded-lg">
            <p className="text-2xl font-bold text-red-600">
              {distributions.filter(d => d.status === 'rejected').length}
            </p>
            <p className="text-sm text-gray-600 mt-1">Rejected</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ManagerDashboard;
