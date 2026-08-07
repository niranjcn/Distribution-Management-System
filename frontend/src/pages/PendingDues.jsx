import { useEffect, useState, useRef } from 'react';
import Card from '../components/ui/Card';
import DataTable from '../components/ui/DataTable';
import Button from '../components/ui/Button';
import StatusBadge from '../components/ui/StatusBadge';
import { defectsAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import { Loader2, Receipt, DollarSign, Search } from 'lucide-react';

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;

const PENDING_DUES_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'user_name', label: 'User' },
  { value: 'user_role', label: 'Role' },
  { value: 'parent_name', label: 'Parent' },
  { value: 'digital_id', label: 'Digital ID' },
  { value: 'broadband_id', label: 'Broadband ID' },
  { value: 'total_due', label: 'Total Due' },
];

const PendingDues = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [users, setUsers] = useState([]);
  const [tableTotalCount, setTableTotalCount] = useState(0);
  const [tablePage, setTablePage] = useState(1);
  const [summary, setSummary] = useState({ users_count: 0, total_due: 0, total_items: 0 });
  const [selectedUser, setSelectedUser] = useState(null);
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [tableSearchBy, setTableSearchBy] = useState('all');
  const [tableSearchInput, setTableSearchInput] = useState('');
  const [appliedTableSearch, setAppliedTableSearch] = useState({ by: 'all', query: '' });
  const [openingBillId, setOpeningBillId] = useState(null);
  const loadedWindowRef = useRef(0);
  const loadingWindowsRef = useRef(new Set());
  const queryVersionRef = useRef(0);

  const role = String(user?.role || '').toLowerCase();
  const isOperatorView = role === 'operator';
  const isHierarchyView = !isOperatorView;
  const canConfirmPayment = ['super_admin', 'manager', 'pdic_staff'].includes(role);

  const buildUsersParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      page: windowPage,
      page_size: pageSize,
    };
    if (appliedTableSearch.query) {
      params.search = appliedTableSearch.query;
      if (appliedTableSearch.by && appliedTableSearch.by !== 'all') {
        params.search_by = appliedTableSearch.by;
      }
    }
    return params;
  };

  const loadUsersWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (loadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = queryVersionRef.current;
    loadingWindowsRef.current.add(windowPage);
    if (withLoading) setLoadingUsers(true);

    try {
      const response = await defectsAPI.getPendingDueUsers(buildUsersParams(windowPage));
      if (queryVersion !== queryVersionRef.current) return;

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setUsers((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.user_id ?? row?.id ?? '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setTableTotalCount(total);
      setSummary({
        users_count: Number(response?.summary?.users_count ?? total),
        total_due: Number(response?.summary?.total_due ?? 0),
        total_items: Number(response?.summary?.total_items ?? 0),
      });
      loadedWindowRef.current = Math.max(loadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load pending dues', 'error');
    } finally {
      loadingWindowsRef.current.delete(windowPage);
      if (withLoading) setLoadingUsers(false);
    }
  };

  const resetAndLoadUsers = async () => {
    queryVersionRef.current += 1;
    loadedWindowRef.current = 0;
    loadingWindowsRef.current = new Set();
    setUsers([]);
    setTableTotalCount(0);
    setTablePage(1);
    setSelectedUser(null);
    setDetails(null);
    await loadUsersWindow(1, { reset: true, withLoading: true });
  };

  const handleTablePageChange = async (nextPage) => {
    setTablePage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(users.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && users.length < tableTotalCount;
    if (needsNextWindow) {
      await loadUsersWindow(loadedWindowRef.current + 1, { withLoading: true });
    }
  };

  const fetchUsers = async () => {
    if (isHierarchyView) {
      await resetAndLoadUsers();
    } else {
      try {
        setLoadingUsers(true);
        setSelectedUser(null);
        setLoadingDetails(true);
        const response = await defectsAPI.getMyPendingDues();
        setDetails(response.data || null);
      } catch (error) {
        showToast(error.message || 'Failed to load pending dues', 'error');
      } finally {
        setLoadingUsers(false);
        setLoadingDetails(false);
      }
    }
  };

  const loadUserDetails = async (userId, userRow = null) => {
    try {
      setLoadingDetails(true);
      const response = await defectsAPI.getPendingDuesForUser(userId);
      setDetails(response.data || null);
      setSelectedUser(userRow || users.find((u) => String(u.user_id) === String(userId)) || null);
    } catch (error) {
      showToast(error.message || 'Failed to load due details', 'error');
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [isHierarchyView, appliedTableSearch]);

  const handleSearchSubmit = () => {
    setAppliedTableSearch({ by: tableSearchBy, query: tableSearchInput.trim() });
  };

  const handleSearchReset = () => {
    setTableSearchBy('all');
    setTableSearchInput('');
    setAppliedTableSearch({ by: 'all', query: '' });
  };

  const userColumns = [
    { key: 'user_name', label: 'User' },
    {
      key: 'user_role',
      label: 'Role',
      render: (value) => String(value || '-').replace(/_/g, ' '),
    },
    {
      key: 'parent_name',
      label: 'Parent',
      render: (value) => value || '-',
    },
    { key: 'due_count', label: 'Pending Defects' },
    {
      key: 'total_due',
      label: 'Total Due',
      render: (value) => <span className="font-semibold text-amber-700">{Number(value || 0).toFixed(2)}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-800">{isHierarchyView ? 'Pending Dues' : 'Pending Payments'}</h1>
        <p className="text-gray-500 mt-1">
          {isHierarchyView
            ? 'Track unpaid dues in your hierarchy branch by role.'
            : 'View all pending payments awaiting confirmation for your defective device returns.'}
        </p>
      </div>

      <div className={`grid grid-cols-1 ${isHierarchyView ? 'md:grid-cols-3' : 'md:grid-cols-2'} gap-4`}>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">{isHierarchyView ? 'Users with Dues' : 'Pending Items'}</p>
          <p className="text-2xl font-bold text-gray-800">{isHierarchyView ? summary.users_count : Number(details?.count || 0)}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-sm text-gray-500">Outstanding Amount</p>
          <p className="text-2xl font-bold text-amber-700">{(isHierarchyView ? summary.total_due : Number(details?.total_due || 0)).toFixed(2)}</p>
        </Card>
        {isHierarchyView && (
          <Card className="!p-4">
            <p className="text-sm text-gray-500">Pending Items</p>
            <p className="text-2xl font-bold text-blue-700">{summary.total_items}</p>
          </Card>
        )}
      </div>

      <div className={`grid grid-cols-1 ${isHierarchyView ? 'lg:grid-cols-5' : ''} gap-6`}>
        {isHierarchyView && (
          <div className="lg:col-span-2">
            <Card title="Users" icon={DollarSign}>
              {loadingUsers ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading users...
                </div>
              ) : (
                <>
                  <div className="mb-3">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                      <div className="md:col-span-3">
                        <select
                          value={tableSearchBy}
                          onChange={(e) => setTableSearchBy(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        >
                          {PENDING_DUES_SEARCH_BY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="md:col-span-6 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text"
                          value={tableSearchInput}
                          onChange={(e) => setTableSearchInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              handleSearchSubmit();
                            }
                          }}
                          placeholder="Enter pattern to search..."
                          className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm"
                        />
                      </div>
                      <div className="md:col-span-3 flex gap-2">
                        <Button onClick={handleSearchSubmit} className="w-full">Search</Button>
                        <Button variant="secondary" onClick={handleSearchReset}>Reset</Button>
                      </div>
                    </div>
                  </div>
                  <DataTable
                    columns={userColumns}
                    data={users}
                    searchable={false}
                    pageSize={TABLE_PAGE_SIZE}
                    totalItems={tableTotalCount || users.length}
                    currentPage={tablePage}
                    onPageChange={handleTablePageChange}
                    onRowClick={(row) => loadUserDetails(row.user_id, row)}
                  />
                </>
              )}
            </Card>
          </div>
        )}

        <div className={isHierarchyView ? 'lg:col-span-3' : ''}>
          <Card title={selectedUser ? `Due Details - ${selectedUser.user_name}` : 'Due Details'} icon={Receipt}>
            {loadingDetails ? (
              <div className="flex items-center justify-center py-10 text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading details...
              </div>
            ) : !details || !details.items || details.items.length === 0 ? (
              <p className="text-gray-500">{isHierarchyView ? 'No pending due items for the selected user.' : 'No pending payments right now.'}</p>
            ) : (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900">
                  {isHierarchyView ? 'Outstanding for this user:' : 'Your total pending amount:'}{' '}
                  <span className="font-semibold">{Number(details.total_due || 0).toFixed(2)}</span>
                </div>

                {details.items.map((item) => (
                  <div key={item.id} className="p-4 rounded-lg border border-gray-200 bg-white space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-gray-800">{item.report_id} • {item.device_model || item.device_type || 'Device'}</p>
                        <p className="text-sm text-gray-500">{item.device_nuid ? `NUID: ${item.device_nuid}` : `Serial: ${item.device_serial || 'N/A'}`} • Return: {item.return_id || item.auto_return_id || 'N/A'}</p>
                      </div>
                      <StatusBadge status={item.return_status || item.status || 'pending'} size="sm" />
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <p><span className="text-gray-500">Received At PDIC:</span> {item.received_date ? new Date(item.received_date).toLocaleDateString() : 'N/A'}</p>
                      <p><span className="text-gray-500">Due Amount:</span> <span className="font-semibold text-amber-700">{Number(item.return_amount || 0).toFixed(2)}</span></p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {item.payment_bill_url && (
                        <Button
                          variant="secondary"
                          loading={openingBillId === item.id}
                          onClick={async () => {
                            setOpeningBillId(item.id);
                            try {
                              const apiOrigin = import.meta.env.VITE_API_URL?.replace(/\/api\/?$/, '') || 'http://localhost:8080';
                              const url = /^https?:\/\//i.test(item.payment_bill_url) ? item.payment_bill_url : `${apiOrigin}${item.payment_bill_url}`;
                              window.open(url, '_blank', 'noopener,noreferrer');
                            } catch (error) {
                              showToast(error.message || 'Failed to open bill', 'error');
                            } finally {
                              setOpeningBillId(null);
                            }
                          }}
                        >
                          {openingBillId === item.id ? 'Loading...' : 'View Bill'}
                        </Button>
                      )}
                      {canConfirmPayment && (
                        <Button
                                                    onClick={async () => {
                            try {
                              await defectsAPI.confirmPayment(item.id, 'Confirmed from Pending Dues page');
                              showToast('Payment confirmed', 'success');
                              await fetchUsers();
                            } catch (error) {
                              showToast(error.message || 'Failed to confirm payment', 'error');
                            }
                          }}
                        >
                          Confirm Payment
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PendingDues;
