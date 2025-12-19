import { Link } from 'react-router-dom';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import Button from '../../components/ui/Button';
import { dashboardStats, devices, distributions, subDistributors, defectReports, returnRequests } from '../../data/mockData';
import {
  Box,
  Truck,
  AlertTriangle,
  RotateCcw,
  Clock,
  Plus,
  Package,
  ArrowRight,
  CheckCircle,
  XCircle
} from 'lucide-react';

const DistributorDashboard = () => {
  const stats = dashboardStats.distributor;
  const inventoryDevices = devices.filter(d => d.currentLocation === 'main-distribution');
  const pendingApprovals = distributions.filter(d => d.status === 'pending' || d.status === 'in-transit');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Distributor Dashboard</h1>
          <p className="text-gray-500 mt-1">Manage your inventory and distributions.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/devices/register">
            <Button icon={Plus}>Register Device</Button>
          </Link>
          <Link to="/distributions/create">
            <Button variant="secondary" icon={Truck}>Create Distribution</Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard title="Inventory" value={stats.totalInventory} icon={Box} color="blue" />
        <StatCard title="Pending Dist." value={stats.pendingDistributions} icon={Clock} color="yellow" />
        <StatCard title="Awaiting Approval" value={stats.awaitingApproval} icon={CheckCircle} color="indigo" />
        <StatCard title="Defect Reports" value={stats.defectReports} icon={AlertTriangle} color="red" />
        <StatCard title="Returns" value={stats.returnRequests} icon={RotateCcw} color="purple" />
        <StatCard title="Distributed" value={stats.distributedThisMonth} icon={Truck} color="green" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Inventory */}
        <Card
          title="Current Inventory"
          icon={Box}
          action={
            <Link to="/devices" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {inventoryDevices.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No devices in inventory</p>
            ) : (
              inventoryDevices.slice(0, 4).map((device) => (
                <div key={device.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{device.model}</p>
                    <p className="text-xs text-gray-500">{device.macAddress}</p>
                  </div>
                  <StatusBadge status={device.condition} size="sm" />
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Pending Approvals */}
        <Card
          title="Awaiting Approval"
          icon={Clock}
          action={
            <Link to="/approvals" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {pendingApprovals.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No pending approvals</p>
            ) : (
              pendingApprovals.slice(0, 4).map((dist) => (
                <div key={dist.id} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-800">{dist.batchId}</p>
                    <StatusBadge status={dist.status} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">To: {dist.toDistributor}</p>
                  <p className="text-xs text-gray-400">{dist.deviceCount} devices</p>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Sub-distributors */}
        <Card
          title="Sub-distributors"
          icon={Package}
          action={
            <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {subDistributors.filter(sd => sd.status === 'active').slice(0, 4).map((sd) => (
              <div key={sd.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{sd.name}</p>
                  <p className="text-xs text-gray-500">{sd.location}</p>
                </div>
                <StatusBadge status={sd.status} size="sm" />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Defects */}
        <Card
          title="Recent Defect Reports"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-3">
            {defectReports.slice(0, 4).map((defect) => (
              <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-800">{defect.device.model}</p>
                    <StatusBadge status={defect.severity} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{defect.defectType} - {defect.subDistributor}</p>
                </div>
                <StatusBadge status={defect.status} />
              </div>
            ))}
          </div>
        </Card>

        {/* Return Requests */}
        <Card
          title="Return Requests"
          icon={RotateCcw}
          action={
            <Link to="/returns" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-3">
            {returnRequests.slice(0, 4).map((ret) => (
              <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{ret.device.model}</p>
                  <p className="text-xs text-gray-500">{ret.reason}</p>
                  <p className="text-xs text-gray-400 mt-1">By: {ret.initiatedBy}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={ret.status} />
                  {ret.status === 'pending' && ret.currentApprover === 'distributor' && (
                    <div className="flex gap-1">
                      <button className="p-1 text-green-600 hover:bg-green-50 rounded">
                        <CheckCircle className="w-4 h-4" />
                      </button>
                      <button className="p-1 text-red-600 hover:bg-red-50 rounded">
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default DistributorDashboard;
