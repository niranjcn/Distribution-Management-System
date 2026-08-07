import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
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
  Building,
  Network,
} from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { usersAPI, dashboardAPI, approvalRequestsAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { normalizeRole, ROLES } from '../utils/roles';

const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];

const TEMPLATE = {
  filename: 'user-bulk-upload-template.csv',
  headers: ['email', 'password', 'name', 'digital_id', 'broadband_id', 'phone', 'network_name'],
  sample: 'user1@example.com,Pass@123,John Doe,SD001|DIG002|DIG003,BB001,+8801234567890,Fibrocom',
};

const BulkUploadUsers = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedMode, setSelectedMode] = useState(null);
  const [parentOptions, setParentOptions] = useState([]);
  const [selectedParentId, setSelectedParentId] = useState('');
  const [loadingParents, setLoadingParents] = useState(false);
  const [subDistOptions, setSubDistOptions] = useState([]);
  const [managerOptions, setManagerOptions] = useState([]);
  const [loadingSubDists, setLoadingSubDists] = useState(false);
  const [selectedSubDistId, setSelectedSubDistId] = useState('');

  const actorRole = normalizeRole(user?.role);
  const isManagement = [ROLES.SUPER_ADMIN, ROLES.MANAGER, ROLES.SUB_DISTRIBUTION_MANAGER].includes(actorRole);
  const isSubDist = actorRole === ROLES.SUB_DISTRIBUTOR;
  const isCluster = actorRole === ROLES.CLUSTER;
  const isEmployee = actorRole === ROLES.SUB_DISTRIBUTION_EMPLOYEE;

  const getModes = () => {
    if (isManagement) {
      return [
        {
          id: 'subdistributor',
          label: 'Upload Subdistributors',
          icon: Building,
          targetRole: 'sub_distributor',
          requiresParent: false,
          description: 'Create subdistributor accounts',
        },
        {
          id: 'cluster',
          label: 'Upload Clusters',
          icon: Network,
          targetRole: 'cluster',
          requiresParent: true,
          parentRole: 'sub_distributor',
          parentLabel: 'Parent Subdistributor',
          description: 'Create cluster accounts under a subdistributor',
        },
        {
          id: 'operator_to_sd',
          label: 'Operators (under Subdistributor)',
          icon: Users,
          targetRole: 'operator',
          requiresParent: true,
          parentRole: 'sub_distributor',
          parentLabel: 'Parent Subdistributor',
          description: 'Create operators assigned to a subdistributor',
        },
        {
          id: 'operator_to_cluster',
          label: 'Operators (under Cluster)',
          icon: Users,
          targetRole: 'operator',
          requiresParent: true,
          parentRole: 'cluster',
          parentLabel: 'Parent Cluster',
          hasSubFilter: true,
          description: 'Create operators under a specific cluster',
        },
      ];
    }
    if (isSubDist) {
      return [
        {
          id: 'clusters',
          label: 'Clusters (under me)',
          icon: Network,
          targetRole: 'cluster',
          requiresParent: false,
          parentId: String(user?.id),
          description: 'Create clusters under your sub distribution',
        },
        {
          id: 'operator_to_me',
          label: 'Operators (assign to me)',
          icon: Users,
          targetRole: 'operator',
          requiresParent: false,
          parentId: String(user?.id),
          description: 'Operators assigned directly to you',
        },
        {
          id: 'operator_to_cluster',
          label: 'Operators (under Cluster)',
          icon: Network,
          targetRole: 'operator',
          requiresParent: true,
          parentRole: 'cluster',
          parentLabel: 'Select Cluster',
          description: 'Operators under one of your clusters',
        },
      ];
    }
    if (isCluster) {
      return [
        {
          id: 'operator_to_me',
          label: 'Upload Operators',
          icon: Users,
          targetRole: 'operator',
          requiresParent: false,
          parentId: String(user?.id),
          description: 'Create operators under your cluster',
        },
      ];
    }
    if (isEmployee) {
      return [
        {
          id: 'clusters_to_branch',
          label: 'Clusters (under Sub Distribution)',
          icon: Network,
          targetRole: 'cluster',
          requiresParent: false,
          parentId: String(user?.parent_id || user?.id),
          description: 'Upload clusters that belong to your sub distribution',
        },
        {
          id: 'operator_to_branch',
          label: 'Operators (under Sub Distribution)',
          icon: Users,
          targetRole: 'operator',
          requiresParent: false,
          parentId: String(user?.parent_id || user?.id),
          description: 'Upload operators for approval — assigned to your sub distribution',
        },
        {
          id: 'operator_to_cluster_branch',
          label: 'Operators (under Cluster)',
          icon: Network,
          targetRole: 'operator',
          requiresParent: true,
          parentRole: 'cluster',
          parentLabel: 'Select Cluster',
          description: 'Upload operators under one of your sub distribution clusters',
        },
      ];
    }
    return [];
  };

  const modes = getModes();

  useEffect(() => {
    if (!selectedMode || !selectedMode.requiresParent) {
      setParentOptions([]);
      setSelectedParentId('');
      return;
    }

    const fetchParents = async () => {
      setLoadingParents(true);
      try {
        const params = { role: selectedMode.parentRole };
        if (isSubDist && selectedMode.parentRole === 'cluster') {
          params.parent_id = String(user?.id);
        }
        const res = await usersAPI.getUsers(params);
        const list = Array.isArray(res?.data) ? res.data : [];
        setParentOptions(list);
      } catch {
        setParentOptions([]);
      } finally {
        setLoadingParents(false);
      }
    };
    fetchParents();
  }, [selectedMode, isSubDist, user?.id]);

  useEffect(() => {
    if (!selectedMode?.hasSubFilter) {
      setSubDistOptions([]);
      setManagerOptions([]);
      setSelectedSubDistId('');
      return;
    }

    const loadSubDists = async () => {
      setLoadingSubDists(true);
      try {
        const [subRes, mgrRes] = await Promise.all([
          usersAPI.getUsers({ role: 'sub_distributor' }),
          usersAPI.getUsers({ role: 'sub_distribution_manager' }),
        ]);
        setSubDistOptions(Array.isArray(subRes?.data) ? subRes.data : []);
        setManagerOptions(Array.isArray(mgrRes?.data) ? mgrRes.data : []);
      } catch {
        setSubDistOptions([]);
        setManagerOptions([]);
      } finally {
        setLoadingSubDists(false);
      }
    };
    loadSubDists();
  }, [selectedMode]);

  const filteredParentOptions = useMemo(() => {
    if (!selectedMode?.hasSubFilter || !selectedSubDistId) return parentOptions;
    const managerIds = managerOptions
      .filter((m) => String(m.parent_id) === String(selectedSubDistId))
      .map((m) => String(m.id));
    return parentOptions.filter((c) => (
      String(c.parent_id) === String(selectedSubDistId)
      || managerIds.includes(String(c.parent_id))
    ));
  }, [selectedMode, selectedSubDistId, parentOptions, managerOptions]);

  const downloadTemplate = useCallback(() => {
    try {
      dashboardAPI.trackActivity({
        action: 'template_export',
        description: 'Exported bulk upload template',
        context: 'users_bulk_upload_template',
      });
    } catch {}
    const bom = '\uFEFF';
    const blob = new Blob([bom + TEMPLATE.headers.join(',') + '\n' + TEMPLATE.sample], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = TEMPLATE.filename;
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
    if (!file || !selectedMode) return;
    try {
      setUploading(true);
      setResult(null);
      const parentId = selectedMode.parentId || selectedParentId || undefined;
      if (isEmployee) {
        const formData = new FormData();
        formData.append('kind', 'users');
        formData.append('file', file);
        formData.append('role', selectedMode.targetRole);
        if (parentId) formData.append('parent_id', parentId);
        const staged = await approvalRequestsAPI.stageBulk(formData);
        const payload = staged?.data?.payload;
        if (!payload) throw new Error('Could not parse the uploaded file');
        await approvalRequestsAPI.submit({
          request_type: 'bulk_users',
          summary: `Bulk upload ${payload.rows?.length || 0} ${selectedMode.targetRole}(s): ${file.name}`,
          payload,
        });
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        showToast('Bulk user upload submitted for approval', 'success');
        navigate('/approval-requests');
        return;
      }
      const res = await usersAPI.bulkUpload(file, selectedMode.targetRole, parentId);
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

  const resetMode = () => {
    setSelectedMode(null);
    setFile(null);
    setResult(null);
    setSelectedParentId('');
    setParentOptions([]);
    setSelectedSubDistId('');
    setSubDistOptions([]);
    setManagerOptions([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const canUpload = file && selectedMode && (!selectedMode.requiresParent || selectedMode.parentId || selectedParentId);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Upload Users</h1>
          <p className="text-sm text-gray-500">
            {isSubDist
              ? 'Upload operators — assign to yourself or one of your clusters'
              : isCluster
                ? 'Upload operators under your cluster'
                : 'Upload subdistributors, clusters, or operators'}
          </p>
        </div>
      </div>

      {!selectedMode ? (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Choose what to upload</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {modes.map(mode => (
              <button
                key={mode.id}
                onClick={() => setSelectedMode(mode)}
                className="flex flex-col items-center gap-3 p-6 border-2 border-gray-200 rounded-xl hover:border-blue-400 hover:bg-blue-50/30 transition-all text-center"
              >
                <mode.icon className="w-10 h-10 text-blue-600" />
                <div>
                  <p className="font-semibold text-gray-800">{mode.label}</p>
                  <p className="text-xs text-gray-500 mt-1">{mode.description}</p>
                </div>
              </button>
            ))}
          </div>

          <Card title="Template" icon={FileSpreadsheet} className="mt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  <strong>Columns:</strong> {TEMPLATE.headers.join(', ')}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Use pipe (|) in digital_id to add multiple digital IDs (operators)
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  network_name is optional and applies to operators
                </p>
              </div>
              <Button variant="outline" onClick={downloadTemplate}>
                <Download className="w-4 h-4" /> Download Template
              </Button>
            </div>
          </Card>
        </div>
      ) : (
        <>
          <button
            onClick={resetMode}
            className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 mb-2"
          >
            ← Choose different upload type
          </button>

          <Card title={selectedMode.label} icon={selectedMode.icon}>
            <p className="text-sm text-gray-600 mb-4">{selectedMode.description}</p>

            {selectedMode.requiresParent && (
              <div className="mb-4 space-y-4">
                {selectedMode.hasSubFilter && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Select Sub Distribution
                    </label>
                    {loadingSubDists ? (
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Loader2 className="w-4 h-4 animate-spin" /> Loading...
                      </div>
                    ) : subDistOptions.length === 0 ? (
                      <p className="text-sm text-amber-600">No sub-distributors available</p>
                    ) : (
                      <select
                        value={selectedSubDistId}
                        onChange={(e) => {
                          setSelectedSubDistId(e.target.value);
                          setSelectedParentId('');
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select Sub Distribution...</option>
                        {subDistOptions.map((sd) => (
                          <option key={sd.id} value={sd.id}>{sd.name} ({sd.email})</option>
                        ))}
                      </select>
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {selectedMode.parentLabel}
                  </label>
                  {loadingParents ? (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" /> Loading...
                    </div>
                  ) : filteredParentOptions.length === 0 ? (
                    <p className="text-sm text-amber-600">
                      {selectedMode.hasSubFilter && !selectedSubDistId
                        ? 'Select a sub distribution first'
                        : `No ${selectedMode.parentRole}s available`}
                    </p>
                  ) : (
                    <select
                      value={selectedParentId}
                      onChange={e => setSelectedParentId(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select {selectedMode.parentLabel}...</option>
                      {filteredParentOptions.map(p => (
                        <option key={p.id} value={p.id}>{p.name} ({p.email})</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            )}

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
                  <Button variant="primary" onClick={handleUpload} disabled={uploading || !canUpload}>
                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {uploading ? 'Uploading...' : 'Upload'}
                  </Button>
                  <Button variant="ghost" onClick={handleClear}>Clear</Button>
                </div>
              </div>
            )}

            {file && <FilePreview file={file} />}
          </Card>
        </>
      )}

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

          {(result.skipped_truncated || result.errors_truncated) && (
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-xl px-4 py-3">
              <p className="text-sm text-slate-600">
                {result.skipped_count + result.error_count} rows need attention. Only the first 500 are shown below.
              </p>
            </div>
          )}

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
