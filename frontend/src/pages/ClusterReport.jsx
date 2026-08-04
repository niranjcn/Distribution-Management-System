import { useState, useEffect, useMemo } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Pagination from '../components/ui/Pagination';
import ReportFilter from '../components/ui/ReportFilter';
import DateRangeFilter, { buildDateParams } from '../components/ui/DateRangeFilter';
import { reportsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { RefreshCw, BarChart3, Layers, Building2, Loader2 } from 'lucide-react';

const PAGE_SIZE = 15;

const VIEW_TABS = [
  { key: 'total', label: 'Total', icon: BarChart3 },
  { key: 'sb', label: 'SB', icon: Layers },
  { key: 'ont', label: 'ONT', icon: Building2 },
];

const thClass = 'text-left py-3 px-4 text-sm font-medium text-gray-600 whitespace-nowrap';
const tdClass = 'py-3 px-4 text-sm text-gray-700';
const selectClass = 'px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500';

const formatIds = (row, key) => {
  if (Array.isArray(row?.digital_ids)) {
    const list = row.digital_ids.map(e => e?.[key] || '').filter(Boolean);
    return list.length ? list.join(', ') : '—';
  }
  return row?.[key] || '—';
};

const ClusterReport = () => {
  const { showToast } = useNotifications();
  const [activeView, setActiveView] = useState('total');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
  const [subFilter, setSubFilter] = useState('');
  const [page, setPage] = useState(1);
  const [searchBy, setSearchBy] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [appliedSearch, setAppliedSearch] = useState({ by: 'all', query: '' });

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await reportsAPI.getClusterReport(buildDateParams(dateRange));
      setRows(res.data?.clusters || []);
    } catch (err) {
      showToast(err.message || 'Failed to load cluster report', 'error');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [dateRange]);

  const subOptions = useMemo(() => {
    const map = new Map();
    rows.forEach(r => {
      if (r.sub_id != null) map.set(String(r.sub_id), r.sub_name);
    });
    return [...map.entries()]
      .sort((a, b) => String(a[1]).localeCompare(String(b[1])))
      .map(([id, name]) => ({ id, name }));
  }, [rows]);

  const filteredRows = useMemo(() => {
    if (!subFilter) return rows;
    return rows.filter(r => String(r.sub_id) === String(subFilter));
  }, [rows, subFilter]);

  const searchableFields = {
    name: (row) => row?.cluster_name,
    email: (row) => row?.email,
    phone: (row) => row?.phone,
    digital_id: (row) => Array.isArray(row?.digital_ids)
      ? row.digital_ids.map(di => di?.digital_id || '').join(' ')
      : row?.digital_id,
    broadband_id: (row) => Array.isArray(row?.digital_ids)
      ? row.digital_ids.map(di => di?.broadband_id || '').join(' ')
      : row?.broadband_id,
  };

  const searchedRows = useMemo(() => {
    const query = String(appliedSearch.query || '').trim().toLowerCase();
    if (!query) return filteredRows;
    const by = String(appliedSearch.by || 'all');
    if (by !== 'all' && searchableFields[by]) {
      return filteredRows.filter(r => String(searchableFields[by](r) || '').toLowerCase().includes(query));
    }
    return filteredRows.filter(r => Object.values(searchableFields).some(getter => String(getter(r) || '').toLowerCase().includes(query)));
  }, [filteredRows, appliedSearch]);

  const sbRows = useMemo(() => searchedRows.filter(r => r.digital_id), [searchedRows]);
  const ontRows = useMemo(() => searchedRows.filter(r => r.broadband_id), [searchedRows]);

  const sbVendors = useMemo(() => {
    const vendorSet = new Set();
    sbRows.forEach(r => Object.keys(r.sb_by_vendor || {}).forEach(v => vendorSet.add(v)));
    return [...vendorSet].sort();
  }, [sbRows]);

  const ontVendors = useMemo(() => {
    const vendorSet = new Set();
    ontRows.forEach(r => Object.keys(r.ont_by_vendor || {}).forEach(v => vendorSet.add(v)));
    return [...vendorSet].sort();
  }, [ontRows]);

  const viewRows = useMemo(() => {
    if (activeView === 'sb') return sbRows;
    if (activeView === 'ont') return ontRows;
    return searchedRows;
  }, [activeView, searchedRows, sbRows, ontRows]);

  const pagedRows = useMemo(
    () => viewRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [viewRows, page]
  );

  useEffect(() => { setPage(1); }, [activeView, subFilter, appliedSearch]);

  const handleSearchSubmit = () => {
    setAppliedSearch({ by: searchBy, query: searchInput.trim() });
  };

  const handleSearchReset = () => {
    setSearchBy('all');
    setSearchInput('');
    setAppliedSearch({ by: 'all', query: '' });
  };

  const renderTotal = () => (
    <Card>
      {searchedRows.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>No cluster data found</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className={thClass}>Sl No</th>
                <th className={thClass}>Cluster</th>
                <th className={thClass}>Digital ID</th>
                <th className={thClass}>Broadband ID</th>
                <th className={thClass}>Sub Distribution</th>
                <th className={thClass}>Total Operators</th>
                <th className={thClass}>Device Count</th>
                <th className={thClass}>SB</th>
                <th className={thClass}>ONT</th>
                <th className={thClass}>Other</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pagedRows.map((r, idx) => (
                <tr key={r.cluster_id} className="hover:bg-gray-50">
                  <td className={tdClass}>{(page - 1) * PAGE_SIZE + idx + 1}</td>
                  <td className={`${tdClass} font-medium text-gray-800`}>{r.cluster_name}</td>
                  <td className={tdClass}>{formatIds(r, 'digital_id')}</td>
                  <td className={tdClass}>{formatIds(r, 'broadband_id')}</td>
                  <td className={tdClass}>{r.sub_name || '—'}</td>
                  <td className={tdClass}>{r.total_operators || 0}</td>
                  <td className={`${tdClass} font-medium`}>{r.device_count || 0}</td>
                  <td className={tdClass}>{r.sb_device_count || 0}</td>
                  <td className={tdClass}>{r.ont_device_count || 0}</td>
                  <td className={tdClass}>{r.other_device_count || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
          <Pagination page={page} totalItems={searchedRows.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
        </>
      )}
    </Card>
  );

  const renderSbOnt = (kind) => {
    const data = kind === 'sb' ? sbRows : ontRows;
    const vendors = kind === 'sb' ? sbVendors : ontVendors;
    const Icon = kind === 'sb' ? Layers : Building2;

    if (data.length === 0) {
      return (
        <Card>
          <div className="text-center py-12 text-gray-400">
            <Icon className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p>No clusters have {kind === 'sb' ? 'a digital ID' : 'a broadband ID'}</p>
          </div>
        </Card>
      );
    }

    return (
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className={thClass}>Sl No</th>
                <th className={thClass}>{kind === 'sb' ? 'Digital ID' : 'Broadband ID'}</th>
                <th className={thClass}>Cluster</th>
                <th className={thClass}>Total Operators</th>
                {vendors.map(v => (
                  <th key={v} className={`${thClass} text-right`}>{v}</th>
                ))}
                <th className={`${thClass} text-right`}>Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pagedRows.map((r, idx) => {
                const byVendor = kind === 'sb' ? (r.sb_by_vendor || {}) : (r.ont_by_vendor || {});
                const rowTotal = Object.values(byVendor).reduce((a, b) => a + b, 0);
                return (
                  <tr key={r.cluster_id} className="hover:bg-gray-50">
                    <td className={tdClass}>{(page - 1) * PAGE_SIZE + idx + 1}</td>
                    <td className={`${tdClass} font-medium text-gray-800`}>{kind === 'sb' ? formatIds(r, 'digital_id') : formatIds(r, 'broadband_id')}</td>
                    <td className={tdClass}>{r.cluster_name}</td>
                    <td className={tdClass}>{kind === 'sb' ? (r.operators_with_digital_id || 0) : (r.operators_with_broadband_id || 0)}</td>
                    {vendors.map(v => (
                      <td key={v} className={`${tdClass} text-right tabular-nums`}>{byVendor[v] || 0}</td>
                    ))}
                    <td className={`${tdClass} text-right font-medium tabular-nums`}>{rowTotal}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Pagination page={page} totalItems={data.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-800">Cluster Report</h1>
          <p className="text-gray-500 mt-1 text-sm">Cluster-wise summary grouped under sub-distributions</p>
        </div>
        <div className="flex items-center gap-3">
          <DateRangeFilter value={dateRange} onChange={setDateRange} />
          <Button variant="outline" icon={RefreshCw} onClick={fetchData}>Refresh</Button>
        </div>
      </div>

      <ReportFilter
        searchBy={searchBy}
        searchInput={searchInput}
        onSearchByChange={setSearchBy}
        onSearchInputChange={setSearchInput}
        onSearch={handleSearchSubmit}
        onReset={handleSearchReset}
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium text-gray-600">Sub Distribution</label>
        <select
          value={subFilter}
          onChange={(e) => setSubFilter(e.target.value)}
          className={selectClass}
        >
          <option value="">All</option>
          {subOptions.map(o => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-2">
        {VIEW_TABS.map(v => (
          <button
            key={v.key}
            onClick={() => setActiveView(v.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              activeView === v.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Card>
          <div className="text-center py-12 text-gray-400">
            <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin opacity-40" />
            <p>Loading report...</p>
          </div>
        </Card>
      ) : (
        <>
          {activeView === 'total' && renderTotal()}
          {activeView === 'sb' && renderSbOnt('sb')}
          {activeView === 'ont' && renderSbOnt('ont')}
        </>
      )}
    </div>
  );
};

export default ClusterReport;
