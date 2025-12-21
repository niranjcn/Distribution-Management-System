import { useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { dashboardStats, devices, distributions, defectReports, returnRequests } from '../data/mockData';
import { 
  BarChart3, PieChart, TrendingUp, Download, Calendar, 
  Filter, Box, Package, AlertTriangle, RotateCcw 
} from 'lucide-react';

const Reports = () => {
  const [dateRange, setDateRange] = useState('last30');
  const [reportType, setReportType] = useState('overview');

  // Calculate statistics
  const stats = {
    totalDevices: devices.length,
    activeDevices: devices.filter(d => d.status === 'active').length,
    inStockDevices: devices.filter(d => d.status === 'in-stock').length,
    distributedDevices: devices.filter(d => d.status === 'distributed').length,
    defectiveDevices: devices.filter(d => d.condition === 'defective').length,
    totalDistributions: distributions.length,
    pendingDistributions: distributions.filter(d => d.status === 'pending').length,
    completedDistributions: distributions.filter(d => d.status === 'delivered').length,
    totalDefects: defectReports.length,
    pendingDefects: defectReports.filter(d => d.status === 'pending').length,
    totalReturns: returnRequests.length,
    pendingReturns: returnRequests.filter(r => r.status === 'pending').length
  };

  const devicesByLocation = [
    { location: 'NOC Warehouse', count: 45, percentage: 25 },
    { location: 'Main Distributor', count: 90, percentage: 50 },
    { location: 'Sub-Distributors', count: 27, percentage: 15 },
    { location: 'Operators', count: 18, percentage: 10 }
  ];

  const devicesByCondition = [
    { condition: 'New', count: 120, color: 'bg-green-500' },
    { condition: 'Good', count: 45, color: 'bg-blue-500' },
    { condition: 'Fair', count: 12, color: 'bg-yellow-500' },
    { condition: 'Defective', count: 3, color: 'bg-red-500' }
  ];

  const monthlyActivity = [
    { month: 'Jan', distributions: 45, returns: 5, defects: 3 },
    { month: 'Feb', distributions: 52, returns: 8, defects: 2 },
    { month: 'Mar', distributions: 61, returns: 4, defects: 5 },
    { month: 'Apr', distributions: 48, returns: 6, defects: 4 },
    { month: 'May', distributions: 55, returns: 7, defects: 3 },
    { month: 'Jun', distributions: 70, returns: 9, defects: 6 }
  ];

  const reportTypes = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'devices', label: 'Device Reports', icon: Box },
    { id: 'distributions', label: 'Distribution Reports', icon: Package },
    { id: 'defects', label: 'Defect Reports', icon: AlertTriangle },
    { id: 'returns', label: 'Return Reports', icon: RotateCcw }
  ];

  const handleExport = (format) => {
    // In a real app, this would generate and download the report
    console.log(`Exporting ${reportType} report as ${format}`);
    alert(`Report exported as ${format.toUpperCase()}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Reports & Analytics</h1>
          <p className="text-gray-500 mt-1">View system statistics and generate reports</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" icon={Download} onClick={() => handleExport('pdf')}>
            Export PDF
          </Button>
          <Button variant="outline" icon={Download} onClick={() => handleExport('csv')}>
            Export CSV
          </Button>
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
            </select>
          </div>
        </div>
      </Card>

      {/* Overview Stats */}
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
            {devicesByLocation.map((item, index) => (
              <div key={index}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700">{item.location}</span>
                  <span className="font-medium text-gray-800">{item.count} ({item.percentage}%)</span>
                </div>
                <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-500 rounded-full transition-all duration-500"
                    style={{ width: `${item.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Devices by Condition */}
        <Card title="Devices by Condition">
          <div className="flex items-center justify-center gap-8 py-4">
            <div className="relative w-32 h-32">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                {devicesByCondition.reduce((acc, item, index) => {
                  const total = devicesByCondition.reduce((sum, i) => sum + i.count, 0);
                  const percentage = (item.count / total) * 100;
                  const previousPercentage = devicesByCondition
                    .slice(0, index)
                    .reduce((sum, i) => sum + (i.count / total) * 100, 0);
                  
                  const colors = ['#22c55e', '#3b82f6', '#eab308', '#ef4444'];
                  
                  acc.push(
                    <circle
                      key={index}
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke={colors[index]}
                      strokeWidth="20"
                      strokeDasharray={`${percentage * 2.51} ${251 - percentage * 2.51}`}
                      strokeDashoffset={`${-previousPercentage * 2.51}`}
                    />
                  );
                  return acc;
                }, [])}
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
              {devicesByCondition.map((item, index) => (
                <div key={index} className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${item.color}`} />
                  <span className="text-sm text-gray-700">{item.condition}</span>
                  <span className="text-sm font-medium text-gray-800">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Monthly Activity */}
        <Card title="Monthly Activity" className="lg:col-span-2">
          <div className="h-64 flex items-end gap-2 pt-4">
            {monthlyActivity.map((month, index) => (
              <div key={index} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex gap-1 h-48">
                  <div 
                    className="flex-1 bg-blue-500 rounded-t"
                    style={{ height: `${(month.distributions / 80) * 100}%` }}
                    title={`Distributions: ${month.distributions}`}
                  />
                  <div 
                    className="flex-1 bg-orange-500 rounded-t"
                    style={{ height: `${(month.returns / 80) * 100}%` }}
                    title={`Returns: ${month.returns}`}
                  />
                  <div 
                    className="flex-1 bg-red-500 rounded-t"
                    style={{ height: `${(month.defects / 80) * 100}%` }}
                    title={`Defects: ${month.defects}`}
                  />
                </div>
                <span className="text-xs text-gray-500">{month.month}</span>
              </div>
            ))}
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
                    {Math.round((stats.distributedDevices / stats.totalDevices) * 100)}%
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
                    {Math.round((stats.completedDistributions / stats.totalDistributions) * 100)}%
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
                    {Math.round(((stats.totalDefects - stats.pendingDefects) / stats.totalDefects) * 100)}%
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
                    {Math.round(((stats.totalReturns - stats.pendingReturns) / stats.totalReturns) * 100)}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default Reports;
