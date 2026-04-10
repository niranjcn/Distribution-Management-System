import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';

const PendingReplacements = () => {
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);

  const fetchPending = async () => {
    try {
      setLoading(true);
      const response = await defectsAPI.getPendingReplacements({ page_size: 100 });
      setRows(response.data || []);
    } catch (error) {
      showToast(error.message || 'Failed to load pending replacements', 'error');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
      const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
      return bTime - aTime;
    });
  }, [rows]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Pending Replacements</h1>
          <p className="text-gray-500 mt-1">Defective devices waiting for replacement assignment</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/replacements">
            <Button variant="outline">Back to Replacements</Button>
          </Link>
          <Button variant="secondary" onClick={fetchPending} icon={RefreshCw}>Refresh</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Awaiting Replacement</p>
          <p className="text-2xl font-bold text-amber-700">{sortedRows.length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Ready To Replace</p>
          <p className="text-2xl font-bold text-green-700">{sortedRows.filter((r) => r.replacement_ready).length}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Waiting Return Receipt</p>
          <p className="text-2xl font-bold text-red-700">{sortedRows.filter((r) => !r.replacement_ready).length}</p>
        </Card>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-3 text-gray-500">Loading pending replacements...</span>
          </div>
        ) : sortedRows.length === 0 ? (
          <div className="text-center py-10">
            <AlertTriangle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-700 font-medium">No pending replacements</p>
            <p className="text-gray-500 text-sm mt-1">All approved defects currently have replacement mappings.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200 text-gray-600">
                  <th className="py-3 px-3">Defect Report</th>
                  <th className="py-3 px-3">Defective Device</th>
                  <th className="py-3 px-3">Severity</th>
                  <th className="py-3 px-3">Reported By</th>
                  <th className="py-3 px-3">Return Status</th>
                  <th className="py-3 px-3">Replacement Readiness</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row._id || row.id} className="border-b border-gray-100">
                    <td className="py-3 px-3 font-semibold text-gray-800">{row.report_id}</td>
                    <td className="py-3 px-3">
                      <DeviceIdentity
                        device={{
                          ...row,
                          ...(row.defective_device || {}),
                          serial_number: row.defective_device?.serial_number || row.device_serial,
                          model: row.defective_device?.model || row.device_name,
                        }}
                      />
                    </td>
                    <td className="py-3 px-3"><StatusBadge status={row.severity} size="sm" /></td>
                    <td className="py-3 px-3">{row.reported_by_name || 'N/A'}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={row.auto_return_status || (row.auto_return_id ? 'pending' : 'n/a')} size="sm" />
                    </td>
                    <td className="py-3 px-3">
                      {row.replacement_ready ? (
                        <span className="text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded">Ready to assign</span>
                      ) : (
                        <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">Wait for return receipt</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

export default PendingReplacements;
