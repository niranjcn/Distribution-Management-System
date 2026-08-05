import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import DataTable from '../components/ui/DataTable';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const PendingReplacements = () => {
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [counts, setCounts] = useState({ awaiting: 0, ready: 0, waiting: 0 });
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

  const buildPendingParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    return {
      page: windowPage,
      page_size: pageSize,
    };
  };

  const loadPendingWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoading(true);

    try {
      const response = await defectsAPI.getPendingReplacements(buildPendingParams(windowPage));
      if (queryVersion !== queryVersionRef.current) return;

      const fetchedRows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || fetchedRows.length);

      setRows((prev) => {
        const merged = reset ? fetchedRows : [...prev, ...fetchedRows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.id || row?._id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setTableTotalCount(total);
      setCounts({
        awaiting: Number(response?.counts?.awaiting ?? total),
        ready: Number(response?.counts?.ready ?? 0),
        waiting: Number(response?.counts?.waiting ?? total),
      });
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load pending replacements', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoading(false);
    }
  };

  const resetAndLoadPending = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setRows([]);
    setTableTotalCount(0);
    setTablePage(1);
    await loadPendingWindow(1, { reset: true, withLoading: true });
  };

  const handleTablePageChange = async (nextPage) => {
    setTablePage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(rows.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && rows.length < tableTotalCount;
    if (needsNextWindow) {
      await loadPendingWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  useEffect(() => {
    resetAndLoadPending();
  }, []);

  useEffect(() => {
    const handler = () => {
      resetAndLoadPending();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await defectsAPI.getPendingReplacements(buildPendingParams(page, EXPORT_PAGE_SIZE));
      const fetchedRows = Array.isArray(response?.data) ? response.data : [];
      total = Number(response?.pagination?.total || fetchedRows.length);
      collected = collected.concat(fetchedRows);

      if (!fetchedRows.length || collected.length >= total) {
        break;
      }

      page += 1;
    }

    return collected;
  };

  const columns = [
    { key: 'report_id', label: 'Defect Report' },
    {
      key: 'defective_device',
      label: 'Defective Device',
      render: (value, row) => {
        const defective = value || {};
        return (
          <DeviceIdentity
            device={{
              ...row,
              ...defective,
              serial_number: defective.serial_number || row.device_serial,
              model: defective.model || row.device_name,
            }}
          />
        );
      },
    },
    {
      key: 'severity',
      label: 'Severity',
      render: (value) => <StatusBadge status={value} size="sm" />,
    },
    { key: 'reported_by_name', label: 'Reported By', render: (value) => value || 'N/A' },
    {
      key: 'auto_return_status',
      label: 'Return Status',
      render: (value, row) => (
        <StatusBadge status={value || (row.auto_return_id ? 'pending' : 'n/a')} size="sm" />
      ),
    },
    {
      key: 'replacement_ready',
      label: 'Replacement Readiness',
      render: (value) =>
        value ? (
          <span className="text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded">
            Ready to assign
          </span>
        ) : (
          <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
            Wait for return receipt
          </span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Pending Replacements</h1>
          <p className="text-gray-500 mt-1">Defective devices waiting for replacement assignment</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/replacements">
            <Button variant="outline">Back to Replacements</Button>
          </Link>
          <Button variant="secondary" onClick={resetAndLoadPending} icon={RefreshCw}>Refresh</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Awaiting Replacement</p>
          <p className="text-2xl font-bold text-amber-700">{counts.awaiting}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Ready To Replace</p>
          <p className="text-2xl font-bold text-green-700">{counts.ready}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Waiting Return Receipt</p>
          <p className="text-2xl font-bold text-red-700">{counts.waiting}</p>
        </Card>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-3 text-gray-500">Loading pending replacements...</span>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={rows}
            searchable={false}
            pageSize={TABLE_PAGE_SIZE}
            totalItems={tableTotalCount || rows.length}
            currentPage={tablePage}
            onPageChange={handleTablePageChange}
            getExportRows={getExportRows}
          />
        )}
      </Card>
    </div>
  );
};

export default PendingReplacements;
