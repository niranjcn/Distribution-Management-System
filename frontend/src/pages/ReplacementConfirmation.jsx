import { useEffect, useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { Loader2, PackageCheck, RefreshCw } from 'lucide-react';

const ReplacementConfirmation = () => {
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [confirmingId, setConfirmingId] = useState(null);
  const [items, setItems] = useState([]);

  const fetchPending = async () => {
    try {
      setLoading(true);
      const response = await defectsAPI.getDefects({
        status: 'replacement_pending_confirmation',
        page_size: 100,
      });
      setItems(response.data || []);
    } catch (error) {
      showToast(error.message || 'Failed to load replacement confirmations', 'error');
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const handleConfirm = async (defectId) => {
    try {
      setConfirmingId(defectId);
      await defectsAPI.confirmReplacementReceipt(defectId);
      showToast('Replacement device receipt confirmed successfully', 'success');
      await fetchPending();
    } catch (error) {
      const msg = String(error?.message || '');
      if (msg.toLowerCase().includes('not pending')) {
        showToast('This replacement is already confirmed. Refreshing list.', 'info');
        await fetchPending();
      } else {
        showToast(error.message || 'Failed to confirm replacement receipt', 'error');
      }
    } finally {
      setConfirmingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Replacement Confirmation</h1>
          <p className="text-gray-500 mt-1">Confirm replacement device transfer from PDIC to your account</p>
        </div>
        <Button variant="secondary" icon={RefreshCw} onClick={fetchPending}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading pending confirmations...</span>
        </div>
      ) : items.length === 0 ? (
        <Card>
          <div className="text-center py-10">
            <PackageCheck className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-700 font-medium">No pending replacement confirmations</p>
            <p className="text-gray-500 text-sm mt-1">When PDIC assigns a replacement device, it will appear here.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((defect) => {
            const defective = defect.defective_device || {};
            const replacement = defect.replacement_device || {};
            const id = defect._id || defect.id;

            return (
              <Card key={id}>
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-gray-800">{defect.report_id}</p>
                      <p className="text-sm text-gray-500">Defect Type: {defect.defect_type} | Severity: {defect.severity}</p>
                    </div>
                    <StatusBadge status={defect.status} />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg border border-red-200 bg-red-50">
                      <p className="text-xs uppercase tracking-wider text-red-600 mb-2">Defective Device</p>
                      <p className="text-sm text-red-900 font-medium">{defective.device_id || 'N/A'}</p>
                      <DeviceIdentity
                        className="mt-2"
                        device={{ ...defect, ...defective, serial_number: defective.serial_number || defect.device_serial }}
                      />
                    </div>

                    <div className="p-3 rounded-lg border border-green-200 bg-green-50">
                      <p className="text-xs uppercase tracking-wider text-green-600 mb-2">Replacement Device</p>
                      <p className="text-sm text-green-900 font-medium">{replacement.device_id || 'N/A'}</p>
                      <DeviceIdentity className="mt-2" device={replacement} />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        onClick={() => handleConfirm(id)}
                        disabled={confirmingId === id}
                      >
                        {confirmingId === id ? 'Confirming...' : 'Confirm Receipt'}
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ReplacementConfirmation;
