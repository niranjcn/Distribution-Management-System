import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { dashboardAPI, devicesAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { Upload, FileSpreadsheet, CheckCircle, XCircle, AlertCircle, Download, ArrowLeft } from 'lucide-react';

const REGULAR_TEMPLATE_HEADERS = ['Vendor', 'device_type', 'model', 'mac_address', 'serial_number', 'band_type'];
const VALID_TYPES = ['ONU', 'ONT', 'OLT', 'Router', 'Switch', 'Modem', 'Access Point', 'SB', 'Other'];
const VALID_BANDS = ['single_band', 'dual_band'];

const BulkImportDevices = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (!selected.name.endsWith('.xlsx') && !selected.name.endsWith('.xls') && !selected.name.endsWith('.csv')) {
        showToast('Please select an Excel (.xlsx, .xls) or CSV (.csv) file', 'error');
        return;
      }
      setFile(selected);
      setResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      if (!dropped.name.endsWith('.xlsx') && !dropped.name.endsWith('.xls') && !dropped.name.endsWith('.csv')) {
        showToast('Please drop an Excel (.xlsx, .xls) or CSV (.csv) file', 'error');
        return;
      }
      setFile(dropped);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await devicesAPI.bulkUpload(file);
      setResult(res.data);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (res.data.created_count > 0) {
        showToast(`${res.data.created_count} devices created successfully`, 'success');
      }
    } catch (err) {
      showToast(err.message || 'Upload failed', 'error');
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      await dashboardAPI.trackActivity({
        action: 'template_export',
        description: 'Exported device bulk upload template',
        context: 'devices_bulk_upload_template',
      });
    } catch {
      // Continue template export even if activity tracking fails.
    }

    // Build a regular-device CSV template users can open in Excel.
    const rows = [
      REGULAR_TEMPLATE_HEADERS.join(','),
      'Huawei,ONT,HG8145V5,,SN-ONT-1001,single_band',
      'Nokia,OLT,7360 ISAM FX,,,,',
    ];
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'device_bulk_upload_template.csv'; // Upload this CSV directly or open in Excel and save as .xls/.xlsx
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/devices')} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Import Devices</h1>
          <p className="text-gray-500 mt-1 text-sm">Upload an Excel or CSV file to register multiple devices at once</p>
        </div>
      </div>

      {/* Template download */}
      <Card>
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <FileSpreadsheet className="w-6 h-6 text-blue-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-800 mb-1">Download Template</h3>
            <p className="text-sm text-gray-500 mb-3">
              Upload either of these two formats:{' '}
              <span className="font-medium text-gray-700">Regular: Vendor, device_type, model, serial_number (mac_address optional, band_type optional)</span>{' '}
              or{' '}
              <span className="font-medium text-gray-700">SB: vendor, device_type, model, nuid, box_type</span>.
            </p>
            <p className="text-xs text-gray-400 mb-3">
              Valid device types: {VALID_TYPES.join(', ')}. If provided, valid band_type values are: {VALID_BANDS.join(', ')}.
              SB rows do not need Serial Number or MAC Address. For SB, box_type must be HD or OTT.
            </p>
            <Button variant="outline" icon={Download} onClick={downloadTemplate}>
              Download Template
            </Button>
          </div>
        </div>
      </Card>

      {/* File upload */}
      <Card title="Upload File">
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
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
              <p className="font-medium text-gray-700">Drop your Excel file here, or click to browse</p>
              <p className="text-sm text-gray-400 mt-1">Supports .xlsx, .xls, and .csv · max 15,001 rows</p>
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

        {file && (
          <div className="mt-4 flex gap-3 justify-end">
            <Button variant="outline" onClick={() => { setFile(null); setResult(null); }}>
              Clear
            </Button>
            <Button icon={Upload} onClick={handleUpload} disabled={uploading}>
              {uploading ? 'Uploading...' : 'Upload & Import'}
            </Button>
          </div>
        )}
      </Card>

      {file && <FilePreview file={file} />}

      {/* Results */}
      {result && (
        <Card title="Import Results">
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-700">{result.created_count}</p>
              <p className="text-sm text-green-600">Created</p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <AlertCircle className="w-6 h-6 text-yellow-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-yellow-700">{result.skipped_count}</p>
              <p className="text-sm text-yellow-600">Skipped (duplicates)</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
              <p className="text-sm text-red-600">Errors</p>
            </div>
          </div>

          {(result.skipped_truncated || result.errors_truncated) && (
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 mb-4">
              <p className="text-sm text-slate-600">
                {result.skipped_count + result.error_count} rows need attention. Only the first 500 are shown below.
              </p>
            </div>
          )}

          {result.skipped.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-yellow-700 mb-2">Skipped Rows</h4>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {result.skipped.map((s, i) => (
                  <div key={i} className="text-xs bg-yellow-50 border border-yellow-200 rounded px-3 py-2">
                    Row {s.row} — {s.serial}: {s.reason}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.errors.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-red-700 mb-2">Errors</h4>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {result.errors.map((e, i) => (
                  <div key={i} className="text-xs bg-red-50 border border-red-200 rounded px-3 py-2">
                    Row {e.row} — {e.serial || ''}: {e.error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.created_count > 0 && (
            <Button onClick={() => navigate('/devices')}>
              View Devices
            </Button>
          )}
        </Card>
      )}
    </div>
  );
};

export default BulkImportDevices;
