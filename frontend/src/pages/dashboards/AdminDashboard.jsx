import { Link } from 'react-router-dom';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import StatusBadge from '../../components/ui/StatusBadge';
import { dashboardStats, recentActivities, users, devices, defectReports, returnRequests } from '../../data/mockData';
import {
  Box,
  Users,
  AlertTriangle,
  RotateCcw,
  CheckSquare,
  Activity,
  TrendingUp,
  Clock,
  ArrowRight,
  Cpu
} from 'lucide-react';

const AdminDashboard = () => {
  const stats = dashboardStats.admin;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Admin Dashboard</h1>
        <p className="text-gray-500 mt-1">Welcome back! Here's an overview of your system.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          title="Total Devices"
          value={stats.totalDevices}
          icon={Box}
          color="blue"
          change={12}
          changeType="increase"
        />
        <StatCard
          title="Active Devices"
          value={stats.activeDevices}
          icon={Cpu}
          color="green"
          change={8}
          changeType="increase"
        />
        <StatCard
          title="Total Users"
          value={stats.totalUsers}
          icon={Users}
          color="purple"
          change={5}
          changeType="increase"
        />
        <StatCard
          title="Pending Approvals"
          value={stats.pendingApprovals}
          icon={CheckSquare}
          color="yellow"
        />
        <StatCard
          title="Defect Reports"
          value={stats.defectReports}
          icon={AlertTriangle}
          color="red"
        />
        <StatCard
          title="Return Requests"
          value={stats.returnRequests}
          icon={RotateCcw}
          color="indigo"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activities */}
        <Card
          title="Recent Activities"
          icon={Activity}
          action={
            <Link to="/reports" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all
            </Link>
          }
        >
          <div className="space-y-4">
            {recentActivities.slice(0, 5).map((activity) => (
              <div key={activity.id} className="flex items-start gap-3">
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <Activity className="w-4 h-4 text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{activity.action}</p>
                  <p className="text-sm text-gray-500 truncate">{activity.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400">{activity.user}</span>
                    <span className="text-xs text-gray-300">•</span>
                    <span className="text-xs text-gray-400">{activity.timestamp}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* System Overview */}
        <Card
          title="System Overview"
          icon={TrendingUp}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Box className="w-5 h-5 text-blue-600" />
                <span className="text-sm font-medium text-gray-700">Devices in Inventory</span>
              </div>
              <span className="text-sm font-bold text-gray-800">4</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Box className="w-5 h-5 text-green-600" />
                <span className="text-sm font-medium text-gray-700">Devices with Sub-distributors</span>
              </div>
              <span className="text-sm font-bold text-gray-800">3</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Box className="w-5 h-5 text-purple-600" />
                <span className="text-sm font-medium text-gray-700">Devices with Operators</span>
              </div>
              <span className="text-sm font-bold text-gray-800">5</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-yellow-600" />
                <span className="text-sm font-medium text-gray-700">In Transit</span>
              </div>
              <span className="text-sm font-bold text-gray-800">1</span>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Users */}
        <Card
          title="Recent Users"
          icon={Users}
          action={
            <Link to="/users" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              Manage users <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {users.slice(0, 5).map((user) => (
              <div key={user.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-sm font-medium text-blue-600">
                      {user.name.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{user.name}</p>
                    <p className="text-xs text-gray-500">{user.email}</p>
                  </div>
                </div>
                <StatusBadge status={user.role} size="sm" />
              </div>
            ))}
          </div>
        </Card>

        {/* Recent Defects */}
        <Card
          title="Recent Defect Reports"
          icon={AlertTriangle}
          action={
            <Link to="/defects" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          }
        >
          <div className="space-y-3">
            {defectReports.slice(0, 4).map((defect) => (
              <div key={defect.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-800">{defect.device.model}</p>
                    <StatusBadge status={defect.severity} size="sm" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1 truncate">{defect.description}</p>
                </div>
                <StatusBadge status={defect.status} size="sm" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AdminDashboard;
