import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Card from '../components/ui/Card';
import { distributionsAPI, devicesAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { Plus, Eye, Truck, CheckCircle, Loader2, AlertTriangle, PackageCheck, XCircle, Layers3, Factory, Upload, Download } from 'lucide-react';

const toDisplayLabel = (value, fallback = 'Unknown') => {
  if (!value) return fallback;
  const normalized = String(value).trim();
  const normalizedKey = normalized.toLowerCase().replace(/[-_\s]+/g, '');
  if (['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedKey)) return 'SB';
  return normalized || fallback;
};

const isSetupBoxType = (deviceType) => {
  const normalized = String(deviceType || '').toLowerCase();
  return normalized.includes('setup') || normalized.includes('set top') || normalized.includes('stb') || normalized === 'sb';
};

const getSenderDisplayName = (dist) => {
  const senderType = String(dist?.from_user_type || '').toLowerCase();
  if (senderType === 'noc' || senderType === 'pdic_staff') return 'PDIC';
  return dist?.from_user_name || 'Unknown';
};

const Distributions = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [distributions, setDistributions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDist, setSelectedDist] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [distributionDevices, setDistributionDevices] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [receiptNotes, setReceiptNotes] = useState('');
  const [receiptSubmitting, setReceiptSubmitting] = useState(false);

  const fetchDistributions = async () => {
    try {
      setLoading(true);
      const response = await distributionsAPI.getDistributions();
      setDistributions(response.data || []);
    } catch (error) {
      console.error('Failed to fetch distributions:', error);
      showToast('Failed to load distributions', 'error');
    } finally {
      setLoading(false);
    }
  };

  const parseDeviceIds = (rawDeviceIds) => {
    if (!rawDeviceIds) return [];
    if (Array.isArray(rawDeviceIds)) return rawDeviceIds.map((id) => String(id)).filter(Boolean);
    if (typeof rawDeviceIds === 'string') {
      try {
        const parsed = JSON.parse(rawDeviceIds);
        if (Array.isArray(parsed)) return parsed.map((id) => String(id)).filter(Boolean);
      } catch {
        return rawDeviceIds.split(',').map((id) => String(id).trim()).filter(Boolean);
      }
    }
    return [];
  };

  const fetchDistributionDevices = async (rawDeviceIds) => {
    const deviceIds = parseDeviceIds(rawDeviceIds);
    if (!deviceIds.length) {
      setDistributionDevices([]);
      return;
    }

    try {
      setLoadingDevices(true);
      const devices = [];
      const chunkSize = 100;

      for (let i = 0; i < deviceIds.length; i += chunkSize) {
        const chunk = deviceIds.slice(i, i + chunkSize);
        const settled = await Promise.allSettled(chunk.map((id) => devicesAPI.getDevice(id)));
        settled.forEach((result) => {
          if (result.status === 'fulfilled' && result.value?.data) {
            devices.push(result.value.data);
          }
        });
      }

      setDistributionDevices(devices);
    } catch (error) {
      console.error('Failed to fetch distribution devices:', error);
      setDistributionDevices([]);
    } finally {
      setLoadingDevices(false);
    }
  };

  useEffect(() => {
    fetchDistributions();
  }, []);

  useEffect(() => {
    if (showModal && selectedDist) {
      fetchDistributionDevices(selectedDist.device_ids);
    }
  }, [showModal, selectedDist]);

  const pendingReceiptForMe = distributions.filter(
    d => d.status === 'pending_receipt' && String(d.to_user_id) === String(user?.id)
  );

  const handleReceiptConfirm = async (received) => {
    if (!selectedDist) return;
    setReceiptSubmitting(true);
    try {
      await distributionsAPI.confirmReceipt(
        selectedDist._id || selectedDist.id,
        received,
        receiptNotes
      );
      const action = received ? 'Receipt confirmed — you can now redistribute the device(s)' : 'Dispute reported. Admin and manager have been notified.';
      showToast(action, received ? 'success' : 'warning');
      setShowReceiptModal(false);
      setShowModal(false);
      setReceiptNotes('');
      setSelectedDist(null);
      fetchDistributions();
    } catch (error) {
      showToast(error.message || 'Failed to submit confirmation', 'error');
    } finally {
      setReceiptSubmitting(false);
    }
  };

  const canCreate = ['super_admin', 'manager', 'pdic_staff', 'sub_distributor', 'cluster', 'operator'].includes(user?.role);
  const canConfirmDisputedReturn = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const canRecipientIdentifierDownload =
    ['sub_distributor', 'cluster', 'operator'].includes(user?.role) &&
    selectedDist &&
    String(selectedDist.to_user_id) === String(user?.id);

  const handleDownloadMacNuidExport = async (format = 'csv') => {
    if (!selectedDist) return;

    try {
      const distributionId = selectedDist._id || selectedDist.id;
      const response = await distributionsAPI.downloadMacNuidExport(distributionId, format);
      const blob = response.blob;
      const disposition = response.contentDisposition || '';

      let fileName = `${selectedDist.distribution_id || 'distribution'}-mac-nuid.${format}`;
      const fileNameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
      if (fileNameMatch?.[1]) {
        fileName = fileNameMatch[1];
      }

      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);

      showToast(`Downloaded ${format.toUpperCase()} MAC/NUID export`, 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download MAC/NUID export', 'error');
    }
  };

  const handleConfirmDisputedReturn = async (dist) => {
    try {
      await distributionsAPI.confirmDisputedReturn(
        dist._id || dist.id,
        'PDIC confirmed devices are physically back with sender'
      );
      showToast('Disputed return confirmed and devices unlocked for redistribution', 'success');
      fetchDistributions();
    } catch (error) {
      showToast(error.message || 'Failed to confirm disputed return', 'error');
    }
  };

  const distributionInsights = useMemo(() => {
    const typeCounts = {};
    const manufacturerCounts = {};
    let setupBoxCount = 0;

    distributionDevices.forEach((device) => {
      const typeLabel = toDisplayLabel(device.device_type);
      const manufacturerLabel = toDisplayLabel(device.manufacturer);

      typeCounts[typeLabel] = (typeCounts[typeLabel] || 0) + 1;
      manufacturerCounts[manufacturerLabel] = (manufacturerCounts[manufacturerLabel] || 0) + 1;

      if (isSetupBoxType(typeLabel)) {
        setupBoxCount += 1;
      }
    });

    const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
    const sortedManufacturers = Object.entries(manufacturerCounts).sort((a, b) => b[1] - a[1]);

    return {
      totalSent: selectedDist?.device_count || selectedDist?.device_ids?.length || 0,
      loadedDetailsCount: distributionDevices.length,
      setupBoxCount,
      types: sortedTypes,
      manufacturers: sortedManufacturers,
    };
  }, [distributionDevices, selectedDist]);

  const columns = [
    { key: 'distribution_id', label: 'Distribution ID' },
    { key: 'from_user_name', label: 'From' },
    { key: 'to_user_name', label: 'To' },
    { key: 'device_count', label: 'Devices', render: (value, row) => value || row.device_ids?.length || 0 },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} />
    },
    { key: 'created_at', label: 'Created', render: (value) => value ? new Date(value).toLocaleDateString() : '-' },
    {
      key: 'approved_by_name',
      label: 'Approved By',
      render: (value) => value || '-'
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedDist(row);
              setShowModal(true);
            }}
            className="p-1 text-blue-600 hover:bg-blue-50 rounded"
            title="View Details"
          >
            <Eye className="w-4 h-4" />
          </button>
          {row.status === 'pending_receipt' && String(row.to_user_id) === String(user?.id) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedDist(row);
                setReceiptNotes('');
                setShowReceiptModal(true);
              }}
              className="p-1 text-orange-600 hover:bg-orange-50 rounded"
              title="Confirm or dispute receipt"
            >
              <PackageCheck className="w-4 h-4" />
            </button>
          )}
          {row.status === 'disputed' && canConfirmDisputedReturn && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleConfirmDisputedReturn(row);
              }}
              className="p-1 text-red-700 hover:bg-red-50 rounded"
              title="Confirm devices are back"
            >
              <CheckCircle className="w-4 h-4" />
            </button>
          )}
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Distributions</h1>
          <p className="text-gray-500 mt-1">Manage device distributions across the chain</p>
        </div>
        {canCreate && (
          <div className="flex items-center gap-2">
            <Link to="/distributions/bulk-upload">
              <Button variant="outline" icon={Upload}>Bulk Upload</Button>
            </Link>
            <Link to="/distributions/create">
              <Button icon={Plus}>Create Distribution</Button>
            </Link>
          </div>
        )}
      </div>

      {/* Pending Receipt Alert Banner */}
      {pendingReceiptForMe.length > 0 && (
        <div className="flex items-start gap-3 p-4 bg-orange-50 border border-orange-300 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-orange-800">
              You have {pendingReceiptForMe.length} distribution{pendingReceiptForMe.length > 1 ? 's' : ''} awaiting your receipt confirmation
            </p>
            <p className="text-sm text-orange-700 mt-1">
              You cannot redistribute these devices until you confirm receipt. Click the orange{' '}
              <PackageCheck className="inline w-4 h-4" /> icon on each row to confirm or dispute.
            </p>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Truck className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-xl font-bold text-gray-800">{distributions.length}</p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <PackageCheck className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Awaiting Receipt</p>
              <p className="text-xl font-bold text-orange-600">
                {distributions.filter(d => d.status === 'pending_receipt').length}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Confirmed</p>
              <p className="text-xl font-bold text-green-600">
                {distributions.filter(d => d.status === 'approved').length}
              </p>
            </div>
          </div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Disputed</p>
              <p className="text-xl font-bold text-red-600">
                {distributions.filter(d => d.status === 'disputed').length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Loading distributions...</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={distributions}
          onRowClick={(row) => {
            setSelectedDist(row);
            setShowModal(true);
          }}
        />
      )}

      {/* View Distribution Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedDist(null);
          setDistributionDevices([]);
        }}
        title="Distribution Details"
        size="lg"
        footer={
          <div className="flex gap-3">
            {selectedDist?.status === 'pending_receipt' && String(selectedDist?.to_user_id) === String(user?.id) && (
              <Button
                icon={PackageCheck}
                onClick={() => { setShowReceiptModal(true); }}
                className="bg-orange-500 hover:bg-orange-600 text-white"
              >
                Confirm Receipt
              </Button>
            )}
            <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
          </div>
        }
      >
        {selectedDist && (
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center">
                <Truck className="w-8 h-8 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-800">{selectedDist.distribution_id}</h3>
                <p className="text-gray-500">{getSenderDisplayName(selectedDist)} → {selectedDist.to_user_name}</p>
                <StatusBadge status={selectedDist.status} />
              </div>
              {canRecipientIdentifierDownload && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    icon={Download}
                    onClick={() => handleDownloadMacNuidExport('csv')}
                  >
                    Download CSV
                  </Button>
                  <Button
                    variant="outline"
                    icon={Download}
                    onClick={() => handleDownloadMacNuidExport('xlsx')}
                  >
                    Download Excel
                  </Button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Created At</label>
                <p className="font-medium text-gray-800">{selectedDist.created_at ? new Date(selectedDist.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Device Count</label>
                <p className="font-medium text-gray-800">{selectedDist.device_count || selectedDist.device_ids?.length || 0}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Transferred By</label>
                <p className="font-medium text-gray-800">{selectedDist.approved_by_name || selectedDist.from_user_name || 'N/A'}</p>
              </div>
              {selectedDist.approval_date && (
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider">Transfer Date</label>
                  <p className="font-medium text-gray-800">{new Date(selectedDist.approval_date).toLocaleDateString()}</p>
                </div>
              )}
            </div>

            {selectedDist.notes && (
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider">Notes</label>
                <p className="text-gray-800 mt-1">{selectedDist.notes}</p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Total Sent</p>
                <p className="text-2xl font-bold text-blue-900 mt-1">{distributionInsights.totalSent}</p>
              </div>
              <div className="rounded-lg border border-green-100 bg-green-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-green-700">SB</p>
                <p className="text-2xl font-bold text-green-900 mt-1">{distributionInsights.setupBoxCount}</p>
              </div>
              <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">Details Loaded</p>
                <p className="text-2xl font-bold text-amber-900 mt-1">{distributionInsights.loadedDetailsCount}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-gray-200 p-4 bg-white">
                <div className="flex items-center gap-2 mb-3">
                  <Layers3 className="w-4 h-4 text-indigo-600" />
                  <h4 className="text-sm font-semibold text-gray-800">By Device Type</h4>
                </div>
                {distributionInsights.types.length > 0 ? (
                  <div className="space-y-2">
                    {distributionInsights.types.map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
                        <span className="text-sm text-gray-700">{type}</span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No device type data available.</p>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 p-4 bg-white">
                <div className="flex items-center gap-2 mb-3">
                  <Factory className="w-4 h-4 text-rose-600" />
                  <h4 className="text-sm font-semibold text-gray-800">By Vendor</h4>
                </div>
                {distributionInsights.manufacturers.length > 0 ? (
                  <div className="space-y-2">
                    {distributionInsights.manufacturers.map(([manufacturer, count]) => (
                      <div key={manufacturer} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
                        <span className="text-sm text-gray-700">{manufacturer}</span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No vendor data available.</p>
                )}
              </div>
            </div>

            {/* Devices List */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Device Details</label>
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
                        <div className="flex-1">
                          <p className="font-medium text-gray-800">{device.model || device.device_type}</p>
                          {isSetupBoxType(device.device_type) ? (
                            <p className="text-sm text-gray-500 font-mono">NUID: {device.nuid || 'N/A'}</p>
                          ) : (
                            <>
                              <p className="text-sm text-gray-500 font-mono">{device.serial_number}</p>
                              <p className="text-xs text-gray-400">{device.mac_address || 'No MAC'}</p>
                            </>
                          )}
                          <div className="mt-1 flex flex-wrap gap-2">
                            <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
                              Type: {toDisplayLabel(device.device_type)}
                            </span>
                            <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">
                              Vendor: {toDisplayLabel(device.manufacturer)}
                            </span>
                          </div>
                        </div>
                        <StatusBadge status={device.status} size="sm" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm py-2">No device details available</p>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Receipt Confirmation Modal */}
      <Modal
        isOpen={showReceiptModal}
        onClose={() => { setShowReceiptModal(false); setReceiptNotes(''); }}
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
              placeholder="Add any notes about receipt condition..."
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
              onClick={() => { setShowReceiptModal(false); setReceiptNotes(''); }}
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
              {receiptSubmitting ? 'Confirming...' : 'Received'}
            </Button>
          </div>
        </div>
      </Modal>

    </div>
  );
};

export default Distributions;

