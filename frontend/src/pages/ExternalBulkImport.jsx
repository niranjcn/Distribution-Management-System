import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import FilePreview from '../components/ui/FilePreview';
import { externalInventoryAPI } from '../services/api';
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

const IDENTIFIER_TYPE_OPTIONS = ['NU ID', 'IMEI', 'Serial Ref', 'MAC ID', 'Asset Tag', 'Other'];
const ITEM_TYPE_OPTIONS = ['OTT Box', 'OLT', 'Remote', 'SB', 'Adapter', 'Others'];

const REQUIRED_COLUMNS = ['name'];
const OPTIONAL_COLUMNS = [
  'identifier_type',
  'identifier',
  'device_type',
  'price',
  'quantity',
  'supplier_name',
  'location',
  'warranty_start_date',
  'warranty_duration',
  'notes',
];

const FIELD_DESCRIPTIONS = [
  { field: 'name', required: true, description: 'Display name of the item (e.g. OLT Device).' },
  { field: 'identifier_type', required: false, description: 'One of the accepted identifier types below. Required if identifier is provided.' },
  { field: 'identifier', required: false, description: 'The item identifier value matching its identifier_type. Required if identifier_type is provided.' },
  { field: 'device_type', required: false, description: 'One of the item types below (OTT Box, OLT, Remote, SB, Adapter, Others).' },
  { field: 'price', required: false, description: 'Unit price. Numeric, defaults to 0.' },
  { field: 'quantity', required: false, description: 'Available stock. Positive integer, defaults to 1.' },
  { field: 'supplier_name', required: false, description: 'Supplier of the item.' },
  { field: 'location', required: false, description: 'Storage/warehouse location.' },
  { field: 'warranty_start_date', required: false, description: 'Warranty start date in YYYY-MM-DD format.' },
  { field: 'warranty_duration', required: false, description: 'Warranty duration in whole months. Non-negative integer.' },
  { field: 'notes', required: false, description: 'Any additional notes.' },
];

const TEMPLATE_HEADERS = [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS.filter((c) => c !== 'name')];

const MAX_FILE_SIZE_MB = 10;
const MAX_ROWS = 15001;

const ExternalBulkImport = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

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
    if (selected.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      showToast(`File is too large. Maximum size is ${MAX_FILE_SIZE_MB} MB`, 'error');
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
    if (dropped.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      showToast(`File is too large. Maximum size is ${MAX_FILE_SIZE_MB} MB`, 'error');
      return;
    }
    setFile(dropped);
    setResult(null);
  };

  const handleImport = async () => {
    if (!file) {
      showToast('Please select a file to import', 'error');
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      showToast(`File is too large. Maximum size is ${MAX_FILE_SIZE_MB} MB`, 'error');
      return;
    }

    setImporting(true);
    setResult(null);
    try {
      const response = await externalInventoryAPI.bulkUploadItems(file);
      setResult(response.data || {});
      if ((response.data?.created_count || 0) > 0) {
        showToast(response.message || 'Import completed', 'success');
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        showToast('Upload validated with errors. Fix rows and re-upload.', 'warning');
      }
    } catch (error) {
      showToast(error.message || 'Import failed', 'error');
    } finally {
      setImporting(false);
    }
  };

  const escapeCsvCell = (value) => {
    const text = String(value ?? '');
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };

  const downloadTemplate = () => {
    const sampleRows = [
      {
        name: 'Sample OLT Device',
        identifier_type: '',
        identifier: '',
        device_type: 'OLT',
        price: '2799',
        quantity: '10',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse A',
        warranty_start_date: '2026-01-15',
        warranty_duration: '12',
        notes: 'OLT example',
      },
      {
        name: 'Sample Router Device',
        identifier_type: 'MAC ID',
        identifier: 'AA:BB:CC:DD:EE:FF',
        device_type: 'Router',
        price: '1599',
        quantity: '5',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse B',
        warranty_start_date: '2026-02-01',
        warranty_duration: '6',
        notes: 'Router example',
      },
    ];
    const headers = [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS.filter((c) => c !== 'name')];
    const lines = [
      headers.join(','),
      ...sampleRows.map((row) => headers.map((key) => escapeCsvCell(row[key])).join(',')),
    ];
    const blob = new Blob([`\uFEFF${lines.join('\n')}`], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'external-inventory-import-model.csv';
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
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Bulk Import Items</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Upload a CSV/Excel file to add many external inventory items at once.
          </p>
        </div>
      </div>

      <Card>
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <FileSpreadsheet className="w-6 h-6 text-blue-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-800 mb-1">File Requirements</h3>
            <ul className="text-sm text-gray-500 space-y-1 list-disc list-inside mb-3">
              <li>
                Supports <span className="font-medium text-gray-700">.csv</span>,{' '}
                <span className="font-medium text-gray-700">.xlsx</span>, and{' '}
                <span className="font-medium text-gray-700">.xls</span> files up to{' '}
                <span className="font-medium text-gray-700">{MAX_FILE_SIZE_MB} MB</span>.
              </li>
              <li>
                Maximum of <span className="font-medium text-gray-700">{MAX_ROWS.toLocaleString()}</span> data rows
                per file.
              </li>
              <li>
                Required column: <span className="font-medium text-gray-700">name</span>. All other columns are
                optional.
              </li>
              <li>
                If you provide an <span className="font-medium text-gray-700">identifier</span>, an{' '}
                <span className="font-medium text-gray-700">identifier_type</span> is required, and each{' '}
                <span className="font-medium text-gray-700">identifier_type + identifier</span> pair must be unique.
              </li>
            </ul>

            <h4 className="text-sm font-semibold text-gray-700 mb-2">Accepted Identifier Types</h4>
            <div className="flex flex-wrap gap-2 mb-4">
              {IDENTIFIER_TYPE_OPTIONS.map((option) => (
                <span
                  key={option}
                  className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
                >
                  {option}
                </span>
              ))}
            </div>

            <Button variant="outline" icon={Download} onClick={downloadTemplate}>
              Download CSV Model
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Accepted Columns">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-gray-600">
            <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 font-medium">Column</th>
                <th className="px-4 py-3 font-medium">Required</th>
                <th className="px-4 py-3 font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {FIELD_DESCRIPTIONS.map((desc) => (
                <tr key={desc.field} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium whitespace-nowrap">{desc.field}</td>
                  <td className="px-4 py-2">
                    {desc.required ? (
                      <span className="text-xs font-medium bg-red-50 text-red-700 rounded-full px-2 py-0.5">Yes</span>
                    ) : (
                      <span className="text-xs font-medium bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">No</span>
                    )}
                  </td>
                  <td className="px-4 py-2">{desc.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-sm text-gray-500 mr-1">Accepted item types:</span>
          {ITEM_TYPE_OPTIONS.map((option) => (
            <span
              key={option}
              className="inline-flex items-center rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-700"
            >
              {option}
            </span>
          ))}
        </div>
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
              <p className="font-medium text-gray-700">Drop your import file here, or click to browse</p>
              <p className="text-sm text-gray-400 mt-1">Supports .xlsx, .xls, and .csv (max {MAX_FILE_SIZE_MB} MB)</p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls,text/csv"
            className="hidden"
            onChange={handleFileChange}
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
          <Button icon={Upload} onClick={handleImport} disabled={importing}>
            {importing ? 'Importing...' : 'Import Items'}
          </Button>
        </div>
      </Card>

      {file && <FilePreview file={file} />}

      {result && (
        <Card title="Import Result">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <AlertCircle className="w-6 h-6 text-blue-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-blue-700">{result.total ?? result.created_count ?? 0}</p>
              <p className="text-sm text-blue-600">Rows Processed</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-green-700">{result.created_count ?? 0}</p>
              <p className="text-sm text-green-600">Created</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600 mx-auto mb-1" />
              <p className="text-2xl font-bold text-red-700">{(result.error_count ?? 0) + (result.skipped_count ?? 0)}</p>
              <p className="text-sm text-red-600">Skipped / Errors</p>
            </div>
          </div>

          {result.errors_truncated || result.skipped_truncated ? (
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 mb-4">
              <p className="text-sm text-slate-600">Only the first 500 skipped/error rows are shown below.</p>
            </div>
          ) : null}

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

          {Array.isArray(result.skipped) && result.skipped.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-amber-700 mb-2">Skipped Rows</h4>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.skipped.map((item, index) => (
                  <div
                    key={`${item.row}-${index}`}
                    className="text-xs bg-amber-50 border border-amber-200 rounded px-3 py-2"
                  >
                    Row {item.row} — {item.name || item.email || 'name missing'}: {item.reason || item.error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.created_count > 0 && (
            <div className="mt-4">
              <Button onClick={() => navigate('/external-inventory')}>View Items</Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default ExternalBulkImport;