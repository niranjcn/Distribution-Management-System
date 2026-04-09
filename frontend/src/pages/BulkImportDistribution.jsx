import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { distributionsAPI, usersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  Download,
  FileSpreadsheet,
  Upload,
  XCircle,
} from 'lucide-react';

const ROLE_LABELS = {
  sub_distributor: 'Sub Distributor',
  cluster: 'Cluster',
  operator: 'Operator',
};

const ALLOWED_RECIPIENT_TYPES = {
  super_admin: ['sub_distributor', 'cluster', 'operator'],
  manager: ['sub_distributor', 'cluster', 'operator'],
  pdic_staff: ['sub_distributor', 'cluster', 'operator'],
  sub_distributor: ['cluster', 'operator'],
  cluster: ['operator'],
  operator: ['operator'],
};

const TEMPLATE_HEADERS = ['mac_address', 'nuid'];

const BulkImportDistribution = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const fileInputRef = useRef(null);

  const [loadingRecipients, setLoadingRecipients] = useState(true);
  const [uploading, setUploading] = useState(false);

  const [file, setFile] = useState(null);
  const [notes, setNotes] = useState('');
  const [result, setResult] = useState(null);

  const [recipientType, setRecipientType] = useState('');
  const [filterSubDistId, setFilterSubDistId] = useState('');
  const [filterClusterId, setFilterClusterId] = useState('');
  const [toUserId, setToUserId] = useState('');

  const [subDists, setSubDists] = useState([]);
  const [allClusters, setAllClusters] = useState([]);
  const [allOperators, setAllOperators] = useState([]);

  const role = user?.role;
  const isManagement = ['super_admin', 'manager', 'pdic_staff'].includes(role);
  const allowedTypes = ALLOWED_RECIPIENT_TYPES[role] || [];

  useEffect(() => {
    if (allowedTypes.length === 1 && !recipientType) {
      setRecipientType(allowedTypes[0]);
    }
  }, [allowedTypes, recipientType]);

  useEffect(() => {
    const fetchRecipients = async () => {
      if (!role) return;
      setLoadingRecipients(true);
      try {
        if (isManagement) {
          const [sdRes, clRes, opRes] = await Promise.all([
            usersAPI.getUsers({ role: 'sub_distributor', status: 'active', page_size: 100 }).catch(() => ({ data: [] })),
            usersAPI.getUsers({ role: 'cluster', status: 'active', page_size: 100 }).catch(() => ({ data: [] })),
            usersAPI.getUsers({ role: 'operator', status: 'active', page_size: 100 }).catch(() => ({ data: [] })),
          ]);
          setSubDists(sdRes.data || []);
          setAllClusters(clRes.data || []);
          setAllOperators(opRes.data || []);
        } else if (role === 'sub_distributor') {
          const [clRes, opRes] = await Promise.all([
            usersAPI.getUsers({ role: 'cluster', status: 'active', page_size: 100 }).catch(() => ({ data: [] })),
            usersAPI.getUsers({ role: 'operator', status: 'active', page_size: 100 }).catch(() => ({ data: [] })),
          ]);
          setAllClusters(clRes.data || []);
          setAllOperators(opRes.data || []);
        } else if (role === 'cluster') {
          const opRes = await usersAPI.getUsers({ role: 'operator', status: 'active', page_size: 100 }).catch(() => ({ data: [] }));
          setAllOperators(opRes.data || []);
        } else if (role === 'operator') {
          const opRes = await usersAPI.getUsers({ role: 'operator', status: 'active', page_size: 100 }).catch(() => ({ data: [] }));
          setAllOperators((opRes.data || []).filter(o => String(o.id) !== String(user?.id)));
        }
      } finally {
        setLoadingRecipients(false);
      }
    };

    fetchRecipients();
  }, [role, isManagement, user?.id]);

  const visibleClusters = useMemo(() => {
    if (isManagement) {
      return filterSubDistId
        ? allClusters.filter(c => String(c.parent_id) === String(filterSubDistId))
        : allClusters;
    }
    return allClusters;
  }, [allClusters, filterSubDistId, isManagement]);

  const visibleOperators = useMemo(() => {
    if (filterClusterId) {
      return allOperators.filter(o => String(o.parent_id) === String(filterClusterId));
    }

    if (isManagement && filterSubDistId) {
      const clusterIds = new Set(
        allClusters
          .filter(c => String(c.parent_id) === String(filterSubDistId))
          .map(c => String(c.id))
      );
      return allOperators.filter(o => clusterIds.has(String(o.parent_id)));
    }

    return allOperators;
  }, [allOperators, allClusters, filterClusterId, filterSubDistId, isManagement]);

  const recipientOptions = useMemo(() => {
    if (recipientType === 'sub_distributor') return subDists;
    if (recipientType === 'cluster') return visibleClusters;
    if (recipientType === 'operator') return visibleOperators;
    return [];
  }, [recipientType, subDists, visibleClusters, visibleOperators]);

  const selectedRecipient = useMemo(() => {
    if (!toUserId) return null;
    return [...subDists, ...allClusters, ...allOperators].find(u => String(u.id) === String(toUserId));
  }, [toUserId, subDists, allClusters, allOperators]);

  const handleRecipientTypeChange = (type) => {
    setRecipientType(type);
    setFilterSubDistId('');
    setFilterClusterId('');
    setToUserId('');
  };

  const validateFile = (candidate) => {
    const fileName = (candidate?.name || '').toLowerCase();
    return fileName.endsWith('.xlsx') || fileName.endsWith('.xls') || fileName.endsWith('.csv');
  };

  const handleFileChange = (event) => {
    const selected = event.target.files[0];
    if (!selected) return;

    if (!validateFile(selected)) {
      showToast('Please select an Excel (.xlsx, .xls) or CSV (.csv) file', 'error');
      return;
    }

    setFile(selected);
    setResult(null);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    const dropped = event.dataTransfer.files[0];
    if (!dropped) return;

    if (!validateFile(dropped)) {
      showToast('Please drop an Excel (.xlsx, .xls) or CSV (.csv) file', 'error');
      return;
    }

    setFile(dropped);
    setResult(null);
  };

  const handleUpload = async () => {
    if (!toUserId) {
      showToast('Please select a recipient first', 'error');
      return;
    }

    if (!file) {
      showToast('Please choose an upload file', 'error');
      return;
    }

    setUploading(true);
    setResult(null);
    try {
      const response = await distributionsAPI.bulkUpload(file, toUserId, notes);
      setResult(response.data || null);

      if (response.data?.created) {
        showToast('Distribution created successfully from upload', 'success');
      } else {
        showToast('Upload validated with errors. Fix rows and re-upload.', 'warning');
      }
    } catch (error) {
      showToast(error.message || 'Bulk upload failed', 'error');
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = () => {
    const rows = [
      TEMPLATE_HEADERS.join(','),
      'AA:BB:CC:DD:EE:01,',
      ',NUID-00021',
      'AA:BB:CC:DD:EE:99,NUID-00099',
    ];

    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'distribution_bulk_upload_template.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/distributions')} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Bulk Upload Distribution</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Upload CSV/Excel with MAC address or NUID, then send all valid registered devices in one distribution.
          </p>
        </div>
      </div>

      <Card>
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <FileSpreadsheet className="w-6 h-6 text-blue-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-800 mb-1">Template</h3>
            <p className="text-sm text-gray-500 mb-3">
              Required file columns: <span className="font-medium text-gray-700">mac_address</span> or{' '}
              <span className="font-medium text-gray-700">nuid</span>. You can provide either one per row.
            </p>
            <Button variant="outline" icon={Download} onClick={downloadTemplate}>
              Download CSV Template
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Select Recipient">
        {loadingRecipients ? (
          <p className="text-sm text-gray-500">Loading recipients...</p>
        ) : (
          <div className="space-y-4">
            {allowedTypes.length > 1 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Recipient Type</label>
                <div className="flex flex-wrap gap-2">
                  {allowedTypes.map(type => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => handleRecipientTypeChange(type)}
                      className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                        recipientType === type
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {ROLE_LABELS[type]}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {recipientType === 'operator' && isManagement && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Sub Distributor</label>
                  <select
                    value={filterSubDistId}
                    onChange={(event) => {
                      setFilterSubDistId(event.target.value);
                      setFilterClusterId('');
                      setToUserId('');
                    }}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Sub Distributors</option>
                    {subDists.map(sd => (
                      <option key={sd.id} value={sd.id}>{sd.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Cluster</label>
                  <select
                    value={filterClusterId}
                    onChange={(event) => {
                      setFilterClusterId(event.target.value);
                      setToUserId('');
                    }}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Clusters</option>
                    {visibleClusters.map(cluster => (
                      <option key={cluster.id} value={cluster.id}>{cluster.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {recipientType === 'cluster' && isManagement && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Sub Distributor</label>
                <select
                  value={filterSubDistId}
                  onChange={(event) => {
                    setFilterSubDistId(event.target.value);
                    setToUserId('');
                  }}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Sub Distributors</option>
                  {subDists.map(sd => (
                    <option key={sd.id} value={sd.id}>{sd.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recipient</label>
              <select
                value={toUserId}
                onChange={(event) => setToUserId(event.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select recipient...</option>
                {recipientOptions.map(option => (
                  <option key={option.id} value={option.id}>{option.name}</option>
                ))}
              </select>
            </div>

            {selectedRecipient && (
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-900">
                Sending to <strong>{selectedRecipient.name}</strong> ({ROLE_LABELS[selectedRecipient.role] || selectedRecipient.role})
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="Upload File">
        <div
          onDrop={handleDrop}
          onDragOver={(event) => event.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
        >
          <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
          {file ? (
            <div>
              <p className="font-medium text-gray-800">{file.name}</p>
              <p className="text-sm text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div>
              <p className="font-medium text-gray-700">Drop your upload file here, or click to browse</p>
              <p className="text-sm text-gray-400 mt-1">Supports .xlsx, .xls, and .csv</p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={3}
            placeholder="Add optional notes for this distribution"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="mt-4 flex gap-3 justify-end">
          <Button
            variant="outline"
            onClick={() => {
              setFile(null);
              setResult(null);
            }}
          >
            Clear
          </Button>
          <Button icon={Upload} onClick={handleUpload} disabled={uploading || loadingRecipients}>
            {uploading ? 'Uploading...' : 'Upload & Create Distribution'}
          </Button>
        </div>
      </Card>

      {result && (
        <Card title="Upload Result">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <AlertCircle className="w-6 h-6 text-blue-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-blue-700">{result.total_rows}</p>
              <p className="text-sm text-blue-600">Rows Processed</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-700">{result.valid_count}</p>
              <p className="text-sm text-green-600">Valid Devices</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
              <p className="text-sm text-red-600">Errors</p>
            </div>
          </div>

          {result.created ? (
            <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-green-900 text-sm mb-4">
              Distribution <strong>{result.distribution?.distribution_id || ''}</strong> created and sent to{' '}
              <strong>{result.distribution?.to_user_name || selectedRecipient?.name || 'recipient'}</strong>.
            </div>
          ) : (
            <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-900 text-sm mb-4">
              Distribution was not created because some rows are invalid or unregistered.
            </div>
          )}

          {Array.isArray(result.errors) && result.errors.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-red-700 mb-2">Invalid Rows</h4>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.errors.map((errorItem, index) => (
                  <div key={`${errorItem.row}-${index}`} className="text-xs bg-red-50 border border-red-200 rounded px-3 py-2">
                    Row {errorItem.row} — {errorItem.identifier || 'identifier missing'}: {errorItem.error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.created && (
            <div className="mt-4">
              <Button onClick={() => navigate('/distributions')}>Go to Distributions</Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default BulkImportDistribution;

