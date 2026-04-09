import { useEffect, useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { changeRequestsAPI, defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { Loader2, PackageCheck, RefreshCw } from 'lucide-react';

const ReplacementConfirmation = () => {
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [confirmingId, setConfirmingId] = useState(null);
  const [enquiringId, setEnquiringId] = useState(null);
  const [requestingTransferId, setRequestingTransferId] = useState(null);
  const [activeEnquiryId, setActiveEnquiryId] = useState(null);
  const [activeTransferId, setActiveTransferId] = useState(null);
  const [enquiryDrafts, setEnquiryDrafts] = useState({});
  const [transferDrafts, setTransferDrafts] = useState({});
  const [submittedTransferIds, setSubmittedTransferIds] = useState(new Set());
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

  const handleEnquirySubmit = async (defectId) => {
    const message = (enquiryDrafts[defectId] || '').trim();
    if (!message) {
      showToast('Please enter an enquiry message first', 'error');
      return;
    }

    try {
      setEnquiringId(defectId);
      await defectsAPI.enquireReplacement(defectId, message);
      showToast('Enquiry sent to management successfully', 'success');
      setEnquiryDrafts((prev) => ({ ...prev, [defectId]: '' }));
      setActiveEnquiryId(null);
    } catch (error) {
      showToast(error.message || 'Failed to send enquiry', 'error');
    } finally {
      setEnquiringId(null);
    }
  };

  const handleTransferFixSubmit = async (defectId) => {
    const notes = (transferDrafts[defectId] || '').trim();
    try {
      setRequestingTransferId(defectId);
      await changeRequestsAPI.requestReplacementTransferFix(defectId, notes);
      showToast('Transfer-fix request submitted to management successfully', 'success');
      setTransferDrafts((prev) => ({ ...prev, [defectId]: '' }));
      setActiveTransferId(null);
      setSubmittedTransferIds((prev) => new Set([...prev, String(defectId)]));
    } catch (error) {
      const msg = String(error?.message || '');
      if (msg.toLowerCase().includes('already pending')) {
        // Keep UI consistent with backend state even if user retried.
        setSubmittedTransferIds((prev) => new Set([...prev, String(defectId)]));
        setActiveTransferId(null);
        showToast('A transfer-fix request is already pending for this defect.', 'info');
      } else {
        showToast(error.message || 'Failed to request transfer fix', 'error');
      }
    } finally {
      setRequestingTransferId(null);
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
                      <p className="text-sm text-red-800">Model: {defective.model || 'Unknown Model'}</p>
                      <p className="text-sm text-red-800">Serial: {defective.serial_number || defect.device_serial || 'N/A'}</p>
                      <p className="text-sm text-red-800">Type: {defective.device_type || defect.device_type || 'N/A'}</p>
                    </div>

                    <div className="p-3 rounded-lg border border-green-200 bg-green-50">
                      <p className="text-xs uppercase tracking-wider text-green-600 mb-2">Replacement Device</p>
                      <p className="text-sm text-green-900 font-medium">{replacement.device_id || 'N/A'}</p>
                      <p className="text-sm text-green-800">Model: {replacement.model || 'Unknown Model'}</p>
                      <p className="text-sm text-green-800">Serial: {replacement.serial_number || 'N/A'}</p>
                      <p className="text-sm text-green-800">Type: {replacement.device_type || 'N/A'}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => setActiveEnquiryId((prev) => (prev === id ? null : id))}
                      >
                        Enquire
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => setActiveTransferId((prev) => (prev === id ? null : id))}
                        disabled={requestingTransferId === id || submittedTransferIds.has(String(id))}
                      >
                        {submittedTransferIds.has(String(id)) ? 'Transfer Requested' : 'Request Transfer Fix'}
                      </Button>
                      <Button
                        onClick={() => handleConfirm(id)}
                        disabled={confirmingId === id}
                      >
                        {confirmingId === id ? 'Confirming...' : 'Confirm Receipt'}
                      </Button>
                    </div>

                    {activeEnquiryId === id && (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                        <textarea
                          value={enquiryDrafts[id] || ''}
                          onChange={(e) =>
                            setEnquiryDrafts((prev) => ({
                              ...prev,
                              [id]: e.target.value,
                            }))
                          }
                          rows={3}
                          placeholder="Ask management for the latest replacement shipment status..."
                          className="w-full px-3 py-2 border border-amber-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                        />
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" onClick={() => setActiveEnquiryId(null)}>
                            Cancel
                          </Button>
                          <Button
                            onClick={() => handleEnquirySubmit(id)}
                            disabled={enquiringId === id}
                          >
                            {enquiringId === id ? 'Sending...' : 'Send Enquiry'}
                          </Button>
                        </div>
                      </div>
                    )}

                    {activeTransferId === id && !submittedTransferIds.has(String(id)) && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-2">
                        <textarea
                          value={transferDrafts[id] || ''}
                          onChange={(e) =>
                            setTransferDrafts((prev) => ({
                              ...prev,
                              [id]: e.target.value,
                            }))
                          }
                          rows={3}
                          placeholder="Optional notes: replacement still not visible, wrong holder, shipment mismatch, etc."
                          className="w-full px-3 py-2 border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                        />
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" onClick={() => setActiveTransferId(null)}>
                            Cancel
                          </Button>
                          <Button
                            onClick={() => handleTransferFixSubmit(id)}
                            disabled={requestingTransferId === id}
                          >
                            {requestingTransferId === id ? 'Submitting...' : 'Submit Transfer Fix'}
                          </Button>
                        </div>
                      </div>
                    )}
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
