import { useEffect, useMemo, useState } from 'react';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { ArrowLeftRight, Loader2 } from 'lucide-react';

const Replacements = () => {
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [selectedRow, setSelectedRow] = useState(null);

  const fetchReplacements = async () => {
    try {
      setLoading(true);
      const response = await defectsAPI.getReplacements({ page_size: 100 });
      setRows(response.data || []);
    } catch (error) {
      showToast(error.message || 'Failed to load replacements', 'error');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReplacements();
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
          <h1 className="text-2xl font-bold text-gray-800">Replacements</h1>
          <p className="text-gray-500 mt-1">Track defective-to-replacement device mappings</p>
        </div>
        <Button variant="secondary" onClick={fetchReplacements}>Refresh</Button>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-3 text-gray-500">Loading replacement mappings...</span>
          </div>
        ) : sortedRows.length === 0 ? (
          <div className="text-center py-10">
            <ArrowLeftRight className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-700 font-medium">No replacement mappings found</p>
            <p className="text-gray-500 text-sm mt-1">Replacement assignments will appear here.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-gray-200 text-gray-600">
                  <th className="py-3 px-3">Defect Report ID</th>
                  <th className="py-3 px-3">Defective Device</th>
                  <th className="py-3 px-3 text-center">Mapping</th>
                  <th className="py-3 px-3">Replacement Device</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => {
                  const id = row._id || row.id;
                  const defective = row.defective_device || {};
                  const replacement = row.replacement_device || {};
                  const confirmed = row.status === 'resolved';
                  return (
                    <tr
                      key={id}
                      onClick={() => setSelectedRow(row)}
                      className={`border-b border-gray-100 cursor-pointer transition-colors ${
                        confirmed
                          ? 'bg-emerald-50 hover:bg-emerald-100'
                          : 'bg-amber-50 hover:bg-amber-100'
                      }`}
                    >
                      <td className="py-3 px-3 font-semibold text-gray-800">{row.report_id}</td>
                      <td className="py-3 px-3">
                        <p className="font-medium text-gray-800">{defective.serial_number || row.device_serial || 'N/A'}</p>
                        <p className="text-xs text-gray-600">{defective.mac_address || 'N/A'} | {defective.device_type || row.device_type || 'N/A'}</p>
                      </td>
                      <td className="py-3 px-3 text-center text-gray-500">-&gt;</td>
                      <td className="py-3 px-3">
                        <p className="font-medium text-gray-800">{replacement.serial_number || 'N/A'}</p>
                        <p className="text-xs text-gray-600">{replacement.mac_address || 'N/A'} | {replacement.device_type || 'N/A'}</p>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={row.status} size="sm" />
                      </td>
                      <td className="py-3 px-3 text-gray-700">
                        {row.updated_at ? new Date(row.updated_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        isOpen={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        title="Replacement Details"
        size="lg"
        footer={<Button variant="secondary" onClick={() => setSelectedRow(null)}>Close</Button>}
      >
        {selectedRow && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-gray-800">{selectedRow.report_id}</p>
              <StatusBadge status={selectedRow.status} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-xs uppercase tracking-wider text-red-700 mb-2">Defective Device</p>
                <p className="text-sm text-red-900">Device ID: {selectedRow.defective_device?.device_id || 'N/A'}</p>
                <p className="text-sm text-red-800">Serial: {selectedRow.defective_device?.serial_number || selectedRow.device_serial || 'N/A'}</p>
                <p className="text-sm text-red-800">MAC: {selectedRow.defective_device?.mac_address || 'N/A'}</p>
                <p className="text-sm text-red-800">Type: {selectedRow.defective_device?.device_type || selectedRow.device_type || 'N/A'}</p>
                <p className="text-sm text-red-800">Model: {selectedRow.defective_device?.model || 'N/A'}</p>
              </div>

              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p className="text-xs uppercase tracking-wider text-emerald-700 mb-2">Replacement Device</p>
                <p className="text-sm text-emerald-900">Device ID: {selectedRow.replacement_device?.device_id || 'N/A'}</p>
                <p className="text-sm text-emerald-800">Serial: {selectedRow.replacement_device?.serial_number || 'N/A'}</p>
                <p className="text-sm text-emerald-800">MAC: {selectedRow.replacement_device?.mac_address || 'N/A'}</p>
                <p className="text-sm text-emerald-800">Type: {selectedRow.replacement_device?.device_type || 'N/A'}</p>
                <p className="text-sm text-emerald-800">Model: {selectedRow.replacement_device?.model || 'N/A'}</p>
              </div>
            </div>

            {selectedRow.resolution && (
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-900">
                {selectedRow.resolution}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Replacements;
