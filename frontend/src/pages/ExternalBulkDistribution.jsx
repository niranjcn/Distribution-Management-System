import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { externalInventoryAPI, usersAPI } from '../services/api';
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

const TEMPLATE_HEADERS = ['id', 'quantity'];

const ExternalBulkDistribution = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const fileInputRef = useRef(null);

  const [loadingRecipients, setLoadingRecipients] = useState(true);
  const [uploading, setUploading] = useState(false);

  const [file, setFile] = useState(null);
  const [notes, setNotes] = useState('');
  const [toUserId, setToUserId] = useState('');
  const [result, setResult] = useState(null);

  const [recipients, setRecipients] = useState([]);

  useEffect(() => {
    const fetchRecipients = async () => {
      setLoadingRecipients(true);
      try {
        const response = await usersAPI.getUsers({ status: 'active', page_size: 10000 });
        setRecipients(Array.isArray(response?.data) ? response.data : []);
      } catch (error) {
        showToast(error.message || 'Failed to load recipients', 'error');
        setRecipients([]);
      } finally {
        setLoadingRecipients(false);
      }
    };

    fetchRecipients();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedRecipient = useMemo(
    () => recipients.find((u) => String(u.id) === String(toUserId)) || null,
    [toUserId, recipients]
  );

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
      showToast('Please select a file to upload', 'error');
      return;
    }

    setUploading(true);
    setResult(null);
    try {
      const response = await externalInventoryAPI.bulkUploadDistribution(file, toUserId, notes);
      setResult(response.data || null);

      if ((response.data?.created_count || 0) > 0) {
        showToast('Distribution created successfully from upload', 'success');
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        showToast('Upload validated with errors. Fix rows and re-upload.', 'warning');
      }
    } catch (error) {
      showToast(error.message || 'Bulk distribution failed', 'error');
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = () => {
    const sampleRows = [
      ['1', '10'],
      ['2', '5'],
      ['3', '3'],
    ];
    const lines = [
      TEMPLATE_HEADERS.join(','),
      ...sampleRows.map((row) => row.join(',')),
    ];
    const blob = new Blob([`\uFEFF${lines.join('\n')}`], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'external-inventory-bulk-distribution-template.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/external-inventory')} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Distribution</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Upload CSV/Excel listing external inventory items by name, then send them all to a single recipient in one distribution.
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
              Required file column: <span className="font-medium text-gray-700">id</span>. Optional column:{' '}
              <span className="font-medium text-gray-700">quantity</span> (defaults to 1). The id must reference an
              existing item. Download the template to see the expected format.
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
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Recipient</label>
              <select
                value={toUserId}
                onChange={(event) => setToUserId(event.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select recipient...</option>
                {recipients.map((option) => (
                  <option key={option.id} value={option.id}>{option.name || option.email}</option>
                ))}
              </select>
            </div>

            {selectedRecipient && (
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-900">
                Sending to <strong>{selectedRecipient.name || selectedRecipient.email}</strong>
                {selectedRecipient.email && selectedRecipient.name ? ` (${selectedRecipient.email})` : ''}
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
            {uploading ? 'Uploading...' : 'Upload & Distribute'}
          </Button>
        </div>
      </Card>

      {file && <FilePreview file={file} />}

      {result && (
        <Card title="Distribution Result">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <AlertCircle className="w-6 h-6 text-blue-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-blue-700">{result.total_rows}</p>
              <p className="text-sm text-blue-600">Rows Processed</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-700">{result.created_count}</p>
              <p className="text-sm text-green-600">Distributed</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
              <p className="text-sm text-red-600">Errors</p>
            </div>
          </div>

          {result.errors_truncated && (
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 mb-4">
              <p className="text-sm text-slate-600">
                {result.error_count} rows need attention. Only the first 500 are shown below.
              </p>
            </div>
          )}

          {Array.isArray(result.errors) && result.errors.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-red-700 mb-2">Invalid Rows</h4>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.errors.map((errorItem, index) => (
                  <div
                    key={`${errorItem.row}-${index}`}
                    className="text-xs bg-red-50 border border-red-200 rounded px-3 py-2"
                  >
                    Row {errorItem.row} — {errorItem.name || 'name missing'}: {errorItem.error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(result.created) && result.created.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-green-700 mb-2">Distributed Items</h4>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.created.map((item, index) => (
                  <div key={`${item.history_id}-${index}`} className="text-xs bg-green-50 border border-green-200 rounded px-3 py-2">
                    {item.item_name} &times; {item.quantity} → {item.recipient_name}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.created_count > 0 && (
            <div className="mt-4">
              <Button onClick={() => navigate('/external-inventory')}>Back to Items</Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default ExternalBulkDistribution;