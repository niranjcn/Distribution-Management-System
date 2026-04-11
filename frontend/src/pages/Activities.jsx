import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, RefreshCw } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import DataTable from '../components/ui/DataTable';
import { dashboardAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';

const Activities = () => {
  const navigate = useNavigate();
  const { showToast } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [activities, setActivities] = useState([]);
  const [filters, setFilters] = useState({
    actor: '',
    category: 'all',
    search: '',
    start_date: '',
    end_date: '',
  });

  const loadActivities = async (appliedFilters = filters) => {
    try {
      setLoading(true);
      const params = {
        page: 1,
        page_size: 100,
        category: appliedFilters.category,
      };

      if (appliedFilters.actor.trim()) params.actor = appliedFilters.actor.trim();
      if (appliedFilters.search.trim()) params.search = appliedFilters.search.trim();
      if (appliedFilters.start_date) params.start_date = appliedFilters.start_date;
      if (appliedFilters.end_date) params.end_date = appliedFilters.end_date;

      const response = await dashboardAPI.getActivities(params);
      setActivities(response.data || []);
    } catch (error) {
      showToast(error.message || 'Failed to load activities', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivities();
  }, []);

  const handleApplyFilters = () => {
    loadActivities(filters);
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
    loadActivities(reset);
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
        <h1 className="text-2xl font-bold text-slate-50">Activities</h1>
        <p className="mt-1 text-sm text-slate-200">Admin-wide timeline of meaningful actions performed by users.</p>
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
          onRowClick={(row) => {
            if (row?.link) {
              navigate(row.link);
            }
          }}
          exportTableName="activity log"
          searchable={false}
          exportable={true}
          emptyMessage={loading ? 'Loading activities...' : 'No activities found'}
        />
      </Card>
    </div>
  );
};

export default Activities;
