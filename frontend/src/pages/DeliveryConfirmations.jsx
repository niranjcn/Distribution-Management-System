import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import { distributionsAPI, devicesAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import {
  PackageCheck,
  CheckCircle,
  XCircle,
  Loader2,
  Truck,
  Box,
  AlertTriangle,
  Clock,
  Eye,
  Download
} from 'lucide-react';

const getSenderDisplayName = (dist) => {
  const senderType = String(dist?.from_user_type || '').toLowerCase();
  if (senderType === 'noc' || senderType === 'pdic_staff') return 'PDIC';
  return dist?.from_user_name || 'Unknown';
};

const DeliveryConfirmations = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [distributions, setDistributions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDist, setSelectedDist] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [receiptNotes, setReceiptNotes] = useState('');
  const [receiptSubmitting, setReceiptSubmitting] = useState(false);
  const [distributionDevices, setDistributionDevices] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [downloadingManifestId, setDownloadingManifestId] = useState(null);

  const handleDownloadManifest = async (dist) => {
    const distributionKey = dist?._id || dist?.id;
    if (!distributionKey) return;

    setDownloadingManifestId(String(distributionKey));
    try {
      const { blob, contentDisposition } = await distributionsAPI.downloadManifest(distributionKey);
      const fallbackName = `${dist.distribution_id || 'distribution'}-devices.xlsx`;
      const match = /filename="?([^\";]+)"?/i.exec(contentDisposition || '');
      const fileName = (match && match[1]) || fallbackName;

      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);

      showToast('Device manifest downloaded successfully', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download manifest', 'error');
    } finally {
      setDownloadingManifestId(null);
    }
  };

  const fetchDistributions = async () => {
    try {
      setLoading(true);
      const response = await distributionsAPI.getDistributions({ status: 'pending_receipt' });
      const allDists = response.data || [];
      // Filter only distributions where current user is the recipient
      const myPending = allDists.filter(
        d => d.status === 'pending_receipt' && String(d.to_user_id) === String(user?.id)
      );
      setDistributions(myPending);
    } catch (error) {
      console.error('Failed to fetch delivery confirmations:', error);
      showToast('Failed to load delivery confirmations', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchDistributionDevices = async (deviceIds) => {
    if (!deviceIds || deviceIds.length === 0) {
      setDistributionDevices([]);
      return;
    }
    try {
      setLoadingDevices(true);
      const devicePromises = deviceIds.map(id => devicesAPI.getDevice(id));
      const responses = await Promise.all(devicePromises);
      setDistributionDevices(responses.map(res => res.data).filter(Boolean));
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      setDistributionDevices([]);
    } finally {
      setLoadingDevices(false);
    }
  };

  useEffect(() => {
    fetchDistributions();
  }, []);

  useEffect(() => {
    if (showDetailModal && selectedDist) {
      fetchDistributionDevices(selectedDist.device_ids);
    }
  }, [showDetailModal, selectedDist]);

  const handleReceiptConfirm = async (received) => {
    if (!selectedDist) return;
    setReceiptSubmitting(true);
    try {
      await distributionsAPI.confirmReceipt(
        selectedDist._id || selectedDist.id,
        received,
        receiptNotes
      );
      const msg = received
        ? 'Receipt confirmed — you can now redistribute the device(s)'
        : 'Dispute reported. Admin and manager have been notified.';
      showToast(msg, received ? 'success' : 'warning');
      setShowReceiptModal(false);
      setShowDetailModal(false);
      setReceiptNotes('');
      setSelectedDist(null);
      setDistributionDevices([]);
      fetchDistributions();
    } catch (error) {
      showToast(error.message || 'Failed to submit confirmation', 'error');
    } finally {
      setReceiptSubmitting(false);
    }
  };

  const openConfirmModal = (dist) => {
    setSelectedDist(dist);
    setReceiptNotes('');
    setShowReceiptModal(true);
  };

  const openDetailModal = (dist) => {
    setSelectedDist(dist);
    setShowDetailModal(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Delivery Confirmations</h1>
        <p className="text-gray-500 mt-1">
          Confirm receipt of devices sent to you. You cannot redistribute devices until you confirm delivery.
        </p>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <PackageCheck className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-blue-800">How it works</p>
          <p className="text-sm text-blue-700 mt-1">
            When someone sends you devices, they will appear here. Click <strong>"Confirm Received"</strong> if you
            have received them, or <strong>"Not Received"</strong> to dispute the delivery. Admin and manager will
            be notified of any disputes.
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <PackageCheck className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Awaiting Confirmation</p>
              <p className="text-xl font-bold text-orange-600">{distributions.length}</p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Box className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Devices Pending</p>
              <p className="text-xl font-bold text-blue-600">
                {distributions.reduce((sum, d) => sum + (d.device_count || d.device_ids?.length || 0), 0)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">From Senders</p>
              <p className="text-xl font-bold text-purple-600">
                {new Set(distributions.map(d => d.from_user_id)).size}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Pending Deliveries List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading deliveries...</span>
        </div>
      ) : distributions.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <CheckCircle className="w-16 h-16 text-green-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-800 mb-2">All Caught Up!</h3>
            <p className="text-gray-500">You have no pending delivery confirmations.</p>
            <Link to="/distributions" className="text-sm text-blue-600 hover:text-blue-700 mt-4 inline-block">
              View all distributions →
            </Link>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {distributions.map((dist) => (
            <Card key={dist.id} className="!p-0 overflow-hidden">
              <div className="flex flex-col sm:flex-row">
                {/* Left: Distribution Info */}
                <div className="flex-1 p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-gray-800">{dist.distribution_id}</h3>
                        <StatusBadge status={dist.status} size="sm" />
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        Sent by <span className="font-medium text-gray-700">{getSenderDisplayName(dist)}</span>
                      </p>
                    </div>
                    <button
                      onClick={() => openDetailModal(dist)}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="View Details"
                    >
                      <Eye className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-4 text-sm">
                    <div className="flex items-center gap-2 text-gray-600">
                      <Box className="w-4 h-4 text-gray-400" />
                      <span>{dist.device_count || dist.device_ids?.length || 0} device(s)</span>
                    </div>
                    <div className="flex items-center gap-2 text-gray-600">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span>{dist.created_at ? new Date(dist.created_at).toLocaleDateString() : 'N/A'}</span>
                    </div>
                  </div>

                  {dist.notes && (
                    <p className="text-sm text-gray-500 mt-2 bg-gray-50 rounded-lg p-2">
                      <span className="font-medium">Notes:</span> {dist.notes}
                    </p>
                  )}
                </div>

                {/* Right: Action Buttons */}
                <div className="flex sm:flex-col gap-2 p-5 sm:border-l border-t sm:border-t-0 border-gray-100 bg-gray-50 sm:w-48 justify-center items-center">
                  <Button
                    icon={Download}
                    onClick={() => handleDownloadManifest(dist)}
                    variant="outline"
                    className="w-full"
                    size="sm"
                    disabled={downloadingManifestId === String(dist._id || dist.id)}
                  >
                    {downloadingManifestId === String(dist._id || dist.id) ? 'Downloading...' : 'Download Excel'}
                  </Button>
                  <Button
                    icon={CheckCircle}
                    onClick={() => openConfirmModal(dist)}
                    className="bg-green-600 hover:bg-green-700 text-white w-full"
                    size="sm"
                  >
                    Confirm Received
                  </Button>
                  <Button
                    icon={XCircle}
                    variant="danger"
                    onClick={() => {
                      setSelectedDist(dist);
                      setReceiptNotes('');
                      setShowReceiptModal(true);
                    }}
                    size="sm"
                    className="w-full"
                  >
                    Not Received
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      <Modal
        isOpen={showDetailModal}
        onClose={() => {
          setShowDetailModal(false);
          setSelectedDist(null);
          setDistributionDevices([]);
        }}
        title="Distribution Details"
        size="lg"
        footer={
          <div className="flex gap-3">
            <Button
              icon={CheckCircle}
              onClick={() => {
                setShowDetailModal(false);
                openConfirmModal(selectedDist);
              }}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              Confirm Received
            </Button>
            <Button variant="secondary" onClick={() => setShowDetailModal(false)}>
              Close
            </Button>
          </div>
        }
      >
        {selectedDist && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="w-16 h-16 bg-orange-100 rounded-xl flex items-center justify-center">
                <PackageCheck className="w-8 h-8 text-orange-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-800">{selectedDist.distribution_id}</h3>
                <p className="text-gray-500">
                  {getSenderDisplayName(selectedDist)} → You
                </p>
                <StatusBadge status={selectedDist.status} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Sent Date</label>
                <p className="font-medium text-gray-800">
                  {selectedDist.created_at ? new Date(selectedDist.created_at).toLocaleDateString() : 'N/A'}
                </p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device Count</label>
                <p className="font-medium text-gray-800">
                  {selectedDist.device_count || selectedDist.device_ids?.length || 0}
                </p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Sent By</label>
                <p className="font-medium text-gray-800">{getSenderDisplayName(selectedDist)}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Sender Type</label>
                <p className="font-medium text-gray-800 capitalize">
                  {(selectedDist.from_user_type || '').replace(/_/g, ' ')}
                </p>
              </div>
            </div>

            {selectedDist.notes && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Notes</label>
                <p className="text-gray-800 mt-1">{selectedDist.notes}</p>
              </div>
            )}

            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider">Device Manifest</label>
              <div className="mt-2">
                <Button
                  icon={Download}
                  variant="outline"
                  onClick={() => handleDownloadManifest(selectedDist)}
                  disabled={downloadingManifestId === String(selectedDist._id || selectedDist.id)}
                >
                  {downloadingManifestId === String(selectedDist._id || selectedDist.id)
                    ? 'Downloading Excel...'
                    : 'Download Device List (Excel)'}
                </Button>
              </div>
            </div>

            {/* Devices */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Devices in this Delivery</label>
              {loadingDevices ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                  <span className="ml-2 text-gray-500">Loading devices...</span>
                </div>
              ) : distributionDevices.length > 0 ? (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {distributionDevices.map((device, index) => (
                    <div key={device._id || device.id || index} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="flex items-center justify-between">
                        <DeviceIdentity device={device} className="flex-1" />
                        <StatusBadge status={device.status} size="sm" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm py-2">No device details available</p>
              )}
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
              <strong>Important:</strong> You cannot redistribute these devices until you confirm receipt.
            </div>
          </div>
        )}
      </Modal>

      {/* Receipt Confirmation Modal */}
      <Modal
        isOpen={showReceiptModal}
        onClose={() => {
          setShowReceiptModal(false);
          setReceiptNotes('');
        }}
        title="Confirm Device Receipt"
        size="md"
        footer={null}
      >
        <div className="space-y-4">
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
            <p className="font-medium text-orange-900">
              Distribution: <span className="font-mono">{selectedDist?.distribution_id}</span>
            </p>
            <p className="text-sm text-orange-800 mt-1">
              Sent by <strong>{getSenderDisplayName(selectedDist)}</strong> — {selectedDist?.device_count || 0} device(s)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
            <textarea
              value={receiptNotes}
              onChange={e => setReceiptNotes(e.target.value)}
              rows={3}
              placeholder="Add any notes about the receipt condition..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
            <strong>Note:</strong> You cannot redistribute these devices until you confirm receipt.
            If you select "Not Received", admin and manager will be alerted immediately.
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <Button
              variant="secondary"
              onClick={() => {
                setShowReceiptModal(false);
                setReceiptNotes('');
              }}
              disabled={receiptSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              icon={XCircle}
              onClick={() => handleReceiptConfirm(false)}
              disabled={receiptSubmitting}
            >
              {receiptSubmitting ? 'Submitting...' : 'Not Received'}
            </Button>
            <Button
              icon={CheckCircle}
              onClick={() => handleReceiptConfirm(true)}
              disabled={receiptSubmitting}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {receiptSubmitting ? 'Confirming...' : 'Confirm Received'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default DeliveryConfirmations;
