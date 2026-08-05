import { useEffect, useMemo, useState, useRef } from 'react';
import Card from '../components/ui/Card';
import DataTable from '../components/ui/DataTable';
import Modal from '../components/ui/Modal';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import DeviceIdentity from '../components/ui/DeviceIdentity';
import DateRangeFilter, { buildDateParams } from '../components/ui/DateRangeFilter';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { ArrowLeftRight, Loader2 } from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const Replacements = () => {
  const { showToast } = useNotifications();
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [selectedRow, setSelectedRow] = useState(null);
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

  const buildReplacementParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    return {
      page: windowPage,
      page_size: pageSize,
      ...buildDateParams(dateRange),
    };
  };

  const loadReplacementWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoading(true);

    try {
      const response = await defectsAPI.getReplacements(buildReplacementParams(windowPage));
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
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load replacements', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoading(false);
    }
  };

  const resetAndLoadReplacements = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setRows([]);
    setTableTotalCount(0);
    setTablePage(1);
    await loadReplacementWindow(1, { reset: true, withLoading: true });
  };

  const handleTablePageChange = async (nextPage) => {
    setTablePage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(rows.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && rows.length < tableTotalCount;
    if (needsNextWindow) {
      await loadReplacementWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  useEffect(() => {
    resetAndLoadReplacements();
  }, [dateRange]);

  useEffect(() => {
    const handler = () => {
      resetAndLoadReplacements();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await defectsAPI.getReplacements(buildReplacementParams(page, EXPORT_PAGE_SIZE));
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

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
      const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
      return bTime - aTime;
    });
  }, [rows]);

  const columns = [
    { key: 'report_id', label: 'Defect Report ID' },
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
            }}
          />
        );
      },
    },
    { key: 'mapping', label: 'Mapping', render: () => <span className="text-gray-500">-&gt;</span> },
    {
      key: 'replacement_device',
      label: 'Replacement Device',
      render: (value) => <DeviceIdentity device={value || {}} />,
    },
    {
      key: 'status',
      label: 'Status',
      render: (value) => <StatusBadge status={value} size="sm" />,
    },
    {
      key: 'updated_at',
      label: 'Date',
      render: (value) => (value ? new Date(value).toLocaleDateString() : '-'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Replacements</h1>
          <p className="text-gray-500 mt-1">Track defective-to-replacement device mappings</p>
        </div>
        <div className="flex items-center gap-2">
          <DateRangeFilter value={dateRange} onChange={setDateRange} />
          <Button variant="secondary" onClick={resetAndLoadReplacements}>Refresh</Button>
        </div>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-3 text-gray-500">Loading replacement mappings...</span>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={sortedRows}
            searchable={false}
            pageSize={TABLE_PAGE_SIZE}
            totalItems={tableTotalCount || sortedRows.length}
            currentPage={tablePage}
            onPageChange={handleTablePageChange}
            getExportRows={getExportRows}
            getRowClassName={(row) =>
              row.status === 'resolved' ? 'bg-emerald-50 hover:bg-emerald-100' : 'bg-amber-50 hover:bg-amber-100'
            }
            onRowClick={(row) => setSelectedRow(row)}
          />
        )}
      </Card>

      <Modal
        isOpen={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        title="Replacement Details"
        size="lg"
        footer={<Button variant="secondary" onClick={() => setSelectedRow(null)}>Close</Button>}
      >
        {selectedRow && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-gray-800">{selectedRow.report_id}</p>
              <StatusBadge status={selectedRow.status} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-xs uppercase tracking-wider text-red-700 mb-2">Defective Device</p>
                <p className="text-sm text-red-900">Device ID: {selectedRow.defective_device?.device_id || 'N/A'}</p>
                <DeviceIdentity
                  className="mt-2"
                  device={{
                    ...selectedRow,
                    ...(selectedRow.defective_device || {}),
                    serial_number: selectedRow.defective_device?.serial_number || selectedRow.device_serial,
                  }}
                />
              </div>

              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p className="text-xs uppercase tracking-wider text-emerald-700 mb-2">Replacement Device</p>
                <p className="text-sm text-emerald-900">Device ID: {selectedRow.replacement_device?.device_id || 'N/A'}</p>
                <DeviceIdentity className="mt-2" device={selectedRow.replacement_device || {}} />
              </div>
            </div>

            {selectedRow.resolution && (
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-900">
                {selectedRow.resolution}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Replacements;
