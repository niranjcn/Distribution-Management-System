import { Link } from 'react-router-dom';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import Button from '../../components/ui/Button';
import { dashboardStats, devices, distributions, operators, defectReports, returnRequests } from '../../data/mockData';
import {
  Box,
  Users,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  Package,
  ArrowRight,
  CheckCircle,
  XCircle,
  Send
} from 'lucide-react';

const SubDistributorDashboard = () => {
  const stats = dashboardStats['sub-distributor'];
  const myDevices = devices.filter(d => d.currentHolder === 'Sub Distributor Alpha');
  const pendingDistributions = distributions.filter(d => d.toDistributor === 'Sub Distributor Alpha' && d.status === 'pending');
  const myOperators = operators.filter(op => op.subDistributor === 'sd1');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Sub-Distributor Dashboard</h1>
          <p className="text-gray-500 mt-1">Manage received devices and operator assignments.</p>
        </div>
        <Link to="/distributions/create">
          <Button icon={Send}>Assign to Operator</Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard title="Received Devices" value={stats.receivedDevices} icon={Box} color="blue" />
        <StatCard title="Pending Approvals" value={stats.pendingApprovals} icon={CheckSquare} color="yellow" />
        <StatCard title="My Operators" value={stats.operatorCount} icon={Users} color="purple" />
        <StatCard title="Defect Reports" value={stats.defectReports} icon={AlertTriangle} color="red" />
        <StatCard title="Returns" value={stats.returnRequests} icon={RotateCcw} color="indigo" />
        <StatCard title="Assigned" value={stats.assignedToOperators} icon={Package} color="green" />
      </div>

      {/* Pending Approvals Banner */}
      {pendingDistributions.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                <CheckSquare className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="font-medium text-yellow-800">
                  You have {pendingDistributions.length} distribution(s) awaiting your approval
                </p>
                <p className="text-sm text-yellow-600">Review and approve received devices</p>
              </div>
            </div>
            <Link to="/approvals">
              <Button variant="warning" size="sm">Review Now</Button>
            </Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* My Devices */}
        <Card
          title="My Devices"
          icon={Box}
          action={
            <Link to="/devices" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myDevices.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No devices assigned</p>
            ) : (
              myDevices.slice(0, 4).map((device) => (
                <div key={device.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{device.model}</p>
                    <p className="text-xs text-gray-500">{device.macAddress}</p>
                  </div>
                  <StatusBadge status={device.status} size="sm" />
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Pending Distributions */}
        <Card
          title="Pending Approvals"
          icon={CheckSquare}
          action={
            <Link to="/approvals" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {pendingDistributions.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No pending approvals</p>
            ) : (
              pendingDistributions.map((dist) => (
                <div key={dist.id} className="p-3 bg-yellow-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-gray-800">{dist.batchId}</p>
                    <StatusBadge status={dist.status} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500">From: {dist.fromDistributor}</p>
                  <p className="text-xs text-gray-400 mb-2">{dist.deviceCount} devices</p>
                  <div className="flex gap-2">
                    <button className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-100 rounded hover:bg-green-200">
                      <CheckCircle className="w-3 h-3" /> Approve
                    </button>
                    <button className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded hover:bg-red-200">
                      <XCircle className="w-3 h-3" /> Reject
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* My Operators */}
        <Card
          title="My Operators"
          icon={Users}
          action={
            <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {myOperators.map((op) => (
              <div key={op.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-xs font-medium text-blue-600">
                      {op.name.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{op.name}</p>
                    <p className="text-xs text-gray-500">{op.assignedDevices} devices</p>
                  </div>
                </div>
                <StatusBadge status={op.status} size="sm" />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Defect Reports to Review */}
        <Card
          title="Defect Reports to Review"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-3">
            {defectReports.filter(d => d.subDistributor === 'Sub Distributor Alpha').slice(0, 3).map((defect) => (
              <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-800">{defect.device.model}</p>
                    <StatusBadge status={defect.severity} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{defect.defectType}</p>
                  <p className="text-xs text-gray-400">Reported by: {defect.reportedBy}</p>
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
            {returnRequests.filter(r => r.currentApprover === 'sub-distributor').slice(0, 3).map((ret) => (
              <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-gray-800">{ret.device.model}</p>
                  <p className="text-xs text-gray-500">{ret.reason}</p>
                  <p className="text-xs text-gray-400 mt-1">By: {ret.initiatedBy}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={ret.status} />
                  <div className="flex gap-1">
                    <button className="p-1 text-green-600 hover:bg-green-50 rounded">
                      <CheckCircle className="w-4 h-4" />
                    </button>
                    <button className="p-1 text-red-600 hover:bg-red-50 rounded">
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default SubDistributorDashboard;
