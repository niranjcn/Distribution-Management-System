import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, RefreshCw } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import DataTable from '../components/ui/DataTable';
import { dashboardAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { useQueryClient } from '@tanstack/react-query';
import { activityKeys } from '../hooks';
import { normalizeRole } from '../utils/roles';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const Activities = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);
  const [activities, setActivities] = useState([]);
  const [totalActivities, setTotalActivities] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);
  const [filters, setFilters] = useState({
    actor: '',
    category: 'all',
    search: '',
    start_date: '',
    end_date: '',
  });
  const [appliedFilters, setAppliedFilters] = useState({
    actor: '',
    category: 'all',
    search: '',
    start_date: '',
    end_date: '',
  });

  const appliedFilterKey = useMemo(
    () => JSON.stringify(appliedFilters),
    [appliedFilters]
  );

  const buildActivityParams = (windowPage) => {
    const params = {
      page: windowPage,
      page_size: TABLE_WINDOW_SIZE,
      category: appliedFilters.category,
    };

    if (appliedFilters.actor.trim()) params.actor = appliedFilters.actor.trim();
    if (appliedFilters.search.trim()) params.search = appliedFilters.search.trim();
    if (appliedFilters.start_date) params.start_date = appliedFilters.start_date;
    if (appliedFilters.end_date) params.end_date = appliedFilters.end_date;

    return params;
  };

  const buildActivityExportParams = (page) => {
    const params = {
      page,
      page_size: EXPORT_PAGE_SIZE,
      category: appliedFilters.category,
    };

    if (appliedFilters.actor.trim()) params.actor = appliedFilters.actor.trim();
    if (appliedFilters.search.trim()) params.search = appliedFilters.search.trim();
    if (appliedFilters.start_date) params.start_date = appliedFilters.start_date;
    if (appliedFilters.end_date) params.end_date = appliedFilters.end_date;

    return params;
  };

  const getExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await dashboardAPI.getActivities(buildActivityExportParams(page));
      const rows = Array.isArray(response?.data) ? response.data : [];
      const pagination = response?.pagination || {};
      total = Number(pagination.total || rows.length);
      collected = collected.concat(rows);

      if (!rows.length || collected.length >= total) {
        break;
      }

      page += 1;
    }

    return collected;
  };

  const loadActivityWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setTableLoading(true);

    try {
      const response = await dashboardAPI.getActivities(buildActivityParams(windowPage));
      if (queryVersion !== queryVersionRef.current) {
        return;
      }

      const rows = Array.isArray(response?.data) ? response.data : [];
      const pagination = response?.pagination || {};
      const total = Number(pagination.total || rows.length);

      setActivities((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });

      setTotalActivities(total);
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load activities', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setTableLoading(false);
    }
  };

  const resetAndLoadActivities = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setActivities([]);
    setTotalActivities(0);
    setTablePage(1);
    await loadActivityWindow(1, { reset: true, withLoading: true });
  };

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: activityKeys.all });
      resetAndLoadActivities();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        await resetAndLoadActivities();
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [appliedFilterKey]);

  const handleApplyFilters = () => {
    setAppliedFilters(filters);
  };

  const handleResetFilters = () => {
    const reset = {
      actor: '',
      category: 'all',
      search: '',
      start_date: '',
      end_date: '',
    };
    setFilters(reset);
    setAppliedFilters(reset);
  };

  const handleTablePageChange = (nextPage) => {
    setTablePage(nextPage);

    const requiredWindow = Math.ceil(nextPage / TABLE_WINDOW_PAGES);
    const loadedPageCount = Math.max(1, Math.ceil((activities.length || 0) / TABLE_PAGE_SIZE));
    const totalPageCount = Math.max(1, Math.ceil((totalActivities || 0) / TABLE_PAGE_SIZE));
    const totalWindows = Math.ceil((totalActivities || 0) / TABLE_WINDOW_SIZE);

    if (requiredWindow > loadedWindowRef.current) {
      loadActivityWindow(requiredWindow, { reset: false, withLoading: false });
    }

    if (nextPage >= loadedPageCount && loadedPageCount < totalPageCount) {
      const nextWindow = loadedWindowRef.current + 1;
      if (nextWindow <= totalWindows && nextWindow > loadedWindowRef.current) {
        loadActivityWindow(nextWindow, { reset: false, withLoading: false });
      }
    }
  };

  const columns = [
    { key: 'actor', label: 'Actor' },
    {
      key: 'category',
      label: 'Type',
      render: (value) => (
        <span className="inline-flex items-center rounded-full border border-slate-400/40 bg-slate-800/70 px-2.5 py-1 text-xs font-semibold text-slate-100">
          {String(value || '-').toUpperCase()}
        </span>
      ),
    },
    { key: 'description', label: 'Description' },
    {
      key: 'date',
      label: 'Date',
      render: (value) => {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
      },
    },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-400/30 bg-slate-900/65 p-6">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-50">Activities</h1>
        <p className="mt-1 text-sm text-slate-200">
          {normalizeRole(user?.role) === 'sub_distributor'
            ? 'Actions performed by your sub-distribution employees.'
            : normalizeRole(user?.role) === 'manager'
              ? 'Timeline of actions performed by your team and staff.'
              : 'Admin-wide timeline of meaningful actions performed by users.'}
        </p>
      </div>

      <Card title="Filters" icon={Filter}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            placeholder="Actor name"
            value={filters.actor}
            onChange={(e) => setFilters((prev) => ({ ...prev, actor: e.target.value }))}
          />
          <select
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            value={filters.category}
            onChange={(e) => setFilters((prev) => ({ ...prev, category: e.target.value }))}
          >
            <option value="all">All</option>
            <option value="device">Device</option>
            <option value="inventory">Inventory</option>
            <option value="api">API</option>
          </select>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            placeholder="Search description/action"
            value={filters.search}
            onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value }))}
          />
          <input
            type="datetime-local"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            value={filters.start_date}
            onChange={(e) => setFilters((prev) => ({ ...prev, start_date: e.target.value }))}
          />
          <input
            type="datetime-local"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            value={filters.end_date}
            onChange={(e) => setFilters((prev) => ({ ...prev, end_date: e.target.value }))}
          />
        </div>
        <div className="mt-3 flex gap-2">
          <Button variant="secondary" icon={RefreshCw} onClick={handleApplyFilters}>
            Apply
          </Button>
          <Button variant="ghost" onClick={handleResetFilters}>
            Reset
          </Button>
        </div>
      </Card>

      <Card title="Activity Log" subtitle="Actor, description and date for all recorded actions" padding={false}>
        <DataTable
          columns={columns}
          data={activities}
          pageSize={TABLE_PAGE_SIZE}
          totalItems={totalActivities || activities.length}
          currentPage={tablePage}
          onPageChange={handleTablePageChange}
          getExportRows={getExportRows}
          onRowClick={(row) => {
            if (row?.link) {
              navigate(row.link);
            }
          }}
          exportTableName="activity log"
          searchable={false}
          exportable={true}
          emptyMessage={loading || tableLoading ? 'Loading activities...' : 'No activities found'}
        />
      </Card>
    </div>
  );
};

export default Activities;
