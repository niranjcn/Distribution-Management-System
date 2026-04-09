import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Search, Download, ChevronDown, MoreVertical } from 'lucide-react';
import { dashboardAPI } from '../../services/api';

const DataTable = ({
  columns,
  data,
  onRowClick,
  selectable = false,
  onSelectionChange,
  actions,
  searchable = true,
  exportable = true,
  pageSize = 10,
  searchPlaceholder = "Search...",
  getRowClassName,
  exportTableName,
}) => {
  const INITIAL_PROGRESSIVE_PAGES = 50;
  const PROGRESSIVE_STEP_PAGES = 25;

  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [selectedRows, setSelectedRows] = useState([]);
  const [expandedRow, setExpandedRow] = useState(null);
  const [renderCount, setRenderCount] = useState(() => pageSize * INITIAL_PROGRESSIVE_PAGES);

  useEffect(() => {
    const initial = Math.max(pageSize, pageSize * INITIAL_PROGRESSIVE_PAGES);
    setRenderCount(Math.min(data.length, initial));
  }, [data, pageSize]);

  useEffect(() => {
    const requiredRows = currentPage * pageSize;
    if (requiredRows > renderCount) {
      setRenderCount(Math.min(data.length, requiredRows));
    }
  }, [currentPage, pageSize, renderCount, data.length]);

  useEffect(() => {
    if (renderCount >= data.length) return undefined;

    const step = Math.max(pageSize, pageSize * PROGRESSIVE_STEP_PAGES);
    const timer = setTimeout(() => {
      setRenderCount((prev) => Math.min(data.length, prev + step));
    }, 120);

    return () => clearTimeout(timer);
  }, [renderCount, data.length, pageSize]);

  const renderWindow = useMemo(
    () => data.slice(0, Math.max(renderCount, currentPage * pageSize)),
    [data, renderCount, currentPage, pageSize]
  );

  // Filter data based on search
  const filteredData = renderWindow.filter((row) => {
    if (!searchQuery) return true;
    return columns.some((col) => {
      const value = row[col.key];
      return value?.toString().toLowerCase().includes(searchQuery.toLowerCase());
    });
  });

  // Sort data
  const sortedData = [...filteredData].sort((a, b) => {
    if (!sortConfig.key) return 0;
    const aVal = a[sortConfig.key];
    const bVal = b[sortConfig.key];
    if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
    return 0;
  });

  // Paginate data
  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = sortedData.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const handleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      const allIds = paginatedData.map((row) => row.id);
      setSelectedRows(allIds);
      onSelectionChange?.(allIds);
    } else {
      setSelectedRows([]);
      onSelectionChange?.([]);
    }
  };

  const handleSelectRow = (id) => {
    setSelectedRows((prev) => {
      const newSelection = prev.includes(id)
        ? prev.filter((i) => i !== id)
        : [...prev, id];
      onSelectionChange?.(newSelection);
      return newSelection;
    });
  };

  const handleExport = async () => {
    const tableName =
      (exportTableName && String(exportTableName).trim()) ||
      (typeof window !== 'undefined' && window.location?.pathname
        ? window.location.pathname.replace(/^\/+/, '').replace(/[-_]/g, ' ') || 'table'
        : 'table');
    const normalizedTableName = tableName
      .split(' ')
      .filter(Boolean)
      .join(' ');

    try {
      await dashboardAPI.trackActivity({
        action: 'table_export',
        description: `Exported ${normalizedTableName} table with ${filteredData.length} row(s)`,
        context: normalizedTableName.toLowerCase().replace(/\s+/g, '_'),
      });
    } catch {
      // Export should still proceed if activity tracking fails.
    }

    const headers = columns.map((col) => col.label).join(',');
    const rows = filteredData.map((row) =>
      columns.map((col) => row[col.key]).join(',')
    );
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.csv';
    a.click();
  };

  return (
    <div className="glass-panel rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border-b border-gray-200">
        {searchable && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search..."
              className="pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-full sm:w-64"
            />
          </div>
        )}

        <div className="flex items-center gap-2">
          {actions}
          {exportable && (
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-100 bg-slate-700/70 hover:bg-slate-600/80 rounded-lg transition-colors border border-slate-500/40"
            >
              <Download className="w-4 h-4" />
              Export
            </button>
          )}
        </div>
      </div>

      {renderCount < data.length && (
        <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-100 bg-gray-50">
          Rendering {renderCount.toLocaleString()} of {data.length.toLocaleString()} rows. Remaining rows are loading progressively.
        </div>
      )}

      {/* Table - Desktop View */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {selectable && (
                <th className="px-4 py-3 w-12">
                  <input
                    type="checkbox"
                    checked={selectedRows.length === paginatedData.length && paginatedData.length > 0}
                    onChange={handleSelectAll}
                    className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                  className={`px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider ${
                    col.sortable !== false ? 'cursor-pointer hover:bg-gray-100' : ''
                  }`}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    {sortConfig.key === col.key && (
                      <ChevronDown
                        className={`w-4 h-4 transition-transform ${
                          sortConfig.direction === 'desc' ? 'rotate-180' : ''
                        }`}
                      />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {paginatedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-4 py-8 text-center text-gray-500"
                >
                  No data found
                </td>
              </tr>
            ) : (
              paginatedData.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onRowClick?.(row)}
                  className={`hover:brightness-95 transition-colors ${
                    onRowClick ? 'cursor-pointer' : ''
                  } ${selectedRows.includes(row.id) ? 'bg-blue-50' : getRowClassName ? getRowClassName(row) : ''}`}
                >
                  {selectable && (
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedRows.includes(row.id)}
                        onChange={() => handleSelectRow(row.id)}
                        className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-sm text-gray-800">
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden divide-y divide-gray-200">
        {paginatedData.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500">
            No data found
          </div>
        ) : (
          paginatedData.map((row) => {
            const primaryCol = columns[0];
            const secondaryCol = columns[1];
            const actionCol = columns.find(c => c.key === 'actions');
            const otherCols = columns.filter(c => c !== primaryCol && c !== secondaryCol && c.key !== 'actions');
            const isExpanded = expandedRow === row.id;
            
            return (
              <div
                key={row.id}
                className={`p-4 ${selectedRows.includes(row.id) ? 'bg-blue-50' : getRowClassName ? getRowClassName(row) : ''}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0" onClick={() => onRowClick?.(row)}>
                    {/* Primary info */}
                    <div className="mb-1">
                      {primaryCol?.render ? primaryCol.render(row[primaryCol.key], row) : row[primaryCol?.key]}
                    </div>
                    {/* Secondary info */}
                    {secondaryCol && (
                      <div className="text-sm text-gray-500">
                        {secondaryCol.render ? secondaryCol.render(row[secondaryCol.key], row) : row[secondaryCol.key]}
                      </div>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {actionCol && (
                      <div onClick={(e) => e.stopPropagation()}>
                        {actionCol.render ? actionCol.render(row[actionCol.key], row) : row[actionCol.key]}
                      </div>
                    )}
                    {otherCols.length > 0 && (
                      <button
                        onClick={() => setExpandedRow(isExpanded ? null : row.id)}
                        className="p-1.5 hover:bg-gray-100 rounded-lg"
                      >
                        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </button>
                    )}
                  </div>
                </div>
                
                {/* Expanded details */}
                {isExpanded && otherCols.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-2 gap-3">
                    {otherCols.map((col) => (
                      <div key={col.key}>
                        <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{col.label}</p>
                        <div className="text-sm text-gray-800">
                          {col.render ? col.render(row[col.key], row) : row[col.key] || '-'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pagination */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-t border-gray-200">
        <div className="text-sm text-gray-600 text-center sm:text-left">
          Showing {((currentPage - 1) * pageSize) + 1} to{' '}
          {Math.min(currentPage * pageSize, sortedData.length)} of{' '}
          {sortedData.length} entries
        </div>

        <div className="flex items-center justify-center gap-1">
          <button
            onClick={() => setCurrentPage(1)}
            disabled={currentPage === 1}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hidden sm:block"
          >
            <ChevronsLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Mobile: Show current/total */}
          <span className="sm:hidden px-3 py-1 text-sm text-gray-600">
            {currentPage} / {totalPages || 1}
          </span>

          {/* Desktop: Show page numbers */}
          <div className="hidden sm:flex items-center gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (currentPage <= 3) {
                pageNum = i + 1;
              } else if (currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = currentPage - 2 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setCurrentPage(pageNum)}
                  className={`w-8 h-8 text-sm font-medium rounded-lg ${
                    currentPage === pageNum
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages || totalPages === 0}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCurrentPage(totalPages)}
            disabled={currentPage === totalPages || totalPages === 0}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hidden sm:block"
          >
            <ChevronsRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default DataTable;
