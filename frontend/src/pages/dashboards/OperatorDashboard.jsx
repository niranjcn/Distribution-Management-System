import { Link } from 'react-router-dom';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import Button from '../../components/ui/Button';
import { dashboardStats, devices, defectReports, returnRequests } from '../../data/mockData';
import {
  Box,
  AlertTriangle,
  RotateCcw,
  Cpu,
  ArrowRight,
  Plus,
  Eye
} from 'lucide-react';

const OperatorDashboard = () => {
  const stats = dashboardStats.operator;
  const myDevices = devices.filter(d => 
    d.currentHolder === 'Tom Operator' || 
    d.currentHolder === 'Emma Wilson' ||
    d.currentHolder === 'Anna Smith'
  );
  const myDefects = defectReports.filter(d => 
    d.reportedBy === 'Tom Operator' || 
    d.reportedBy === 'Emma Wilson'
  );
  const myReturns = returnRequests.filter(r => 
    r.initiatedBy === 'Tom Operator' || 
    r.initiatedBy === 'Emma Wilson' ||
    r.initiatedBy === 'Anna Smith'
  );

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
          <Link to="/returns/create">
            <Button icon={RotateCcw} variant="secondary">Request Return</Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard title="Assigned Devices" value={stats.assignedDevices} icon={Box} color="blue" />
        <StatCard title="Active" value={stats.activeDevices} icon={Cpu} color="green" />
        <StatCard title="In Use" value={stats.inUseDevices} icon={Cpu} color="purple" />
        <StatCard title="My Defect Reports" value={stats.defectReports} icon={AlertTriangle} color="red" />
        <StatCard title="Pending Returns" value={stats.pendingReturns} icon={RotateCcw} color="yellow" />
      </div>

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
              <h4 className="font-medium text-gray-800">{device.model}</h4>
              <p className="text-sm text-gray-500 mt-1">{device.macAddress}</p>
              <p className="text-xs text-gray-400 mt-2">SN: {device.serialNumber}</p>
              <div className="flex items-center gap-2 mt-3">
                <Link to={`/devices/track?mac=${encodeURIComponent(device.macAddress)}`} className="flex-1">
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
                      <p className="text-sm font-medium text-gray-800">{defect.device.model}</p>
                      <StatusBadge status={defect.severity} size="sm" />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{defect.defectType}</p>
                    <p className="text-xs text-gray-400">{defect.reportedAt}</p>
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
                <Link to="/returns/create" className="text-sm text-blue-600 hover:text-blue-700 mt-2 inline-block">
                  Request a return
                </Link>
              </div>
            ) : (
              myReturns.map((ret) => (
                <div key={ret.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{ret.device.model}</p>
                    <p className="text-xs text-gray-500">{ret.reason}</p>
                    <p className="text-xs text-gray-400 mt-1">{ret.createdAt}</p>
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
