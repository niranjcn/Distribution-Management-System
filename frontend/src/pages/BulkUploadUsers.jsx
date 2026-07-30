import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  Download,
  FileSpreadsheet,
  CheckCircle,
  XCircle,
  AlertCircle,
  ArrowLeft,
  Loader2,
  Users,
} from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { usersAPI, dashboardAPI } from '../services/api';

const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];

const TEMPLATES = {
  sub_distributor: {
    filename: 'user-template-sub-distributor.csv',
    headers: ['role', 'email', 'password', 'name', 'digital_id', 'broadband_id', 'phone', 'designation', 'location'],
    sample: 'sub_distributor,sd1@example.com,Pass@123,Sub Distributor One,SD001,BB001,+911234567890,Designation A,Location A',
    label: 'Sub Distributor',
    description: 'role, email, password, name, digital_id, broadband_id, phone, designation, location',
  },
  cluster: {
    filename: 'user-template-cluster.csv',
    headers: ['role', 'email', 'password', 'name', 'cluster_id', 'phone', 'designation', 'location', 'sub_distributor_email'],
    sample: 'cluster,cluster1@example.com,Pass@123,Cluster One,CL001,+911234567890,Designation B,Location B,sd1@example.com',
    label: 'Cluster',
    description: 'role, email, password, name, cluster_id, phone, designation, location, sub_distributor_email',
  },
  operator: {
    filename: 'user-template-operator.csv',
    headers: ['role', 'email', 'password', 'name', 'operator_id', 'phone', 'designation', 'location', 'sub_distributor_email', 'cluster_email'],
    sample: 'operator,op1@example.com,Pass@123,Operator One,OP001,+911234567890,Designation C,Location C,,cluster1@example.com',
    label: 'Operator',
    description: 'role, email, password, name, operator_id, phone, designation, location, sub_distributor_email, cluster_email',
  },
};

const BulkUploadUsers = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const downloadTemplate = useCallback(async (key) => {
    const tpl = TEMPLATES[key];
    if (!tpl) return;
    try {
      await dashboardAPI.trackActivity({
        action: 'template_export',
        description: `Exported ${tpl.label} bulk upload template`,
        context: 'users_bulk_upload_template',
      });
    } catch {}
    const bom = '\uFEFF';
    const blob = new Blob([bom + tpl.headers.join(',') + '\n' + tpl.sample], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = tpl.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    const ext = '.' + selected.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      alert('Please select a .csv, .xlsx, or .xls file');
      e.target.value = '';
      return;
    }
    setFile(selected);
    setResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    const ext = '.' + dropped.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) return;
    setFile(dropped);
    setResult(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploading(true);
      setResult(null);
      const res = await usersAPI.bulkUpload(file);
      setResult(res.data);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setResult({ error: err.message || 'Upload failed' });
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Upload Users</h1>
          <p className="text-sm text-gray-500">Upload sub-distributors, clusters, and operators via CSV or Excel</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card title="Templates" icon={FileSpreadsheet} className="lg:col-span-1">
          <p className="text-sm text-gray-600 mb-4">
            Download a CSV template for the user role you want to upload, fill in the data, and upload it back.
          </p>
          <div className="space-y-3">
            {Object.entries(TEMPLATES).map(([key, tpl]) => (
              <div key={key} className="p-3 border border-gray-200 rounded-lg">
                <p className="text-sm font-medium text-gray-800 mb-1">{tpl.label}</p>
                <p className="text-xs text-gray-500 mb-2">{tpl.description}</p>
                <Button variant="outline" size="sm" onClick={() => downloadTemplate(key)}>
                  <Download className="w-4 h-4" />
                  Download
                </Button>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Upload File" icon={Upload} className="lg:col-span-2">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
              className="hidden"
            />
            <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
            <p className="text-sm text-gray-600 font-medium">
              {file ? file.name : 'Drop your file here or click to browse'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Supports .csv, .xlsx, .xls</p>
          </div>

          {file && (
            <div className="mt-4 flex items-center justify-between p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-blue-600" />
                <span className="text-sm font-medium text-gray-700">{file.name}</span>
                <span className="text-xs text-gray-400">({(file.size / 1024).toFixed(1)} KB)</span>
              </div>
              <div className="flex gap-2">
                <Button variant="primary" onClick={handleUpload} disabled={uploading}>
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {uploading ? 'Uploading...' : 'Upload'}
                </Button>
                <Button variant="ghost" onClick={handleClear}>Clear</Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {file && <FilePreview file={file} />}

      {uploading && (
        <div className="flex justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      )}

      {result && !result.error && (
        <div className="space-y-4 animate-fadeIn">
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
              <CheckCircle className="w-8 h-8 text-green-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-700">{result.created_count || 0}</p>
              <p className="text-sm text-green-600">Created</p>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-center">
              <AlertCircle className="w-8 h-8 text-yellow-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-yellow-700">{result.skipped_count || 0}</p>
              <p className="text-sm text-yellow-600">Skipped</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
              <XCircle className="w-8 h-8 text-red-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-red-700">{result.error_count || 0}</p>
              <p className="text-sm text-red-600">Errors</p>
            </div>
          </div>

          {result.created?.length > 0 && (
            <Card title={`Created Users (${result.created.length})`} icon={CheckCircle}>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {result.created.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-gray-700">
                    <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                    <span className="font-mono text-xs">{c.email}</span>
                    <span className="text-xs text-gray-400 capitalize">({c.role})</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {result.errors?.length > 0 && (
            <Card title={`Errors (${result.errors.length})`} icon={XCircle}>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {result.errors.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-red-700">
                    <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-mono text-xs">Row {e.row}: {e.email || '(no email)'}</span>
                      <p className="text-xs text-red-500">{e.error}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {result.skipped?.length > 0 && (
            <Card title={`Skipped (${result.skipped.length})`} icon={AlertCircle}>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {result.skipped.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-yellow-700">
                    <AlertCircle className="w-3.5 h-3.5 text-yellow-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-mono text-xs">Row {s.row}: {s.email}</span>
                      <p className="text-xs text-yellow-500">{s.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {result?.error && (
        <Card title="Upload Failed" icon={XCircle}>
          <p className="text-sm text-red-600">{result.error}</p>
        </Card>
      )}
    </div>
  );
};

export default BulkUploadUsers;
