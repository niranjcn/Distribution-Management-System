import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import DataTable from '../components/ui/DataTable';
import { externalInventoryAPI, usersAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import { useQueryClient } from '@tanstack/react-query';
import { inventoryKeys } from '../hooks';
import {
  Boxes,
  Eye,
  PackagePlus,
  RefreshCw,
  Trash2,
  Upload,
  Search,
  Send,
  ClipboardList,
} from 'lucide-react';

const IDENTIFIER_TYPE_OPTIONS = ['NU ID', 'IMEI', 'Serial Ref', 'MAC ID', 'Asset Tag', 'Other'];
const ITEM_TYPE_OPTIONS = ['OTT Box', 'OLT', 'Remote', 'SB', 'Adapter', 'Others'];

const ROLE_LABELS = {
  sub_distributor: 'Sub Distributor',
  cluster: 'Cluster',
  operator: 'Operator',
};

const RECIPIENT_TYPE_OPTIONS = ['sub_distributor', 'cluster', 'operator'];

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;

const initialItemForm = {
  name: '',
  identifier_type: '',
  identifier: '',
  device_type: '',
  quantity: 1,
  price: 0,
  supplier_name: '',
  location: '',
  warranty_start_date: '',
  warranty_duration: '',
  notes: '',
};

const MANAGEMENT_ROLES = ['super_admin', 'manager', 'pdic_staff'];

const ExternalInventory = ({ tab }) => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const normalizedRole = String(user?.role || '').trim().toLowerCase();
  const canManage = MANAGEMENT_ROLES.includes(normalizedRole);
  const queryClient = useQueryClient();

  const tabs = useMemo(() => {
    if (!canManage) {
      return [{ key: 'items', label: 'Items' }];
    }
    return [
      { key: 'items', label: 'Items' },
      { key: 'distribution', label: 'Distribution' },
      { key: 'distributed', label: 'Distributed Items' },
    ];
  }, [canManage]);

  const validInitial = tabs.some((t) => t.key === tab) ? tab : 'items';
  const [activeTab, setActiveTab] = useState(validInitial);

  useEffect(() => {
    if (tabs.some((t) => t.key === tab)) {
      setActiveTab(tab);
    }
  }, [tab, tabs]);

  // ----- Items list state -----
  const [itemsPage, setItemsPage] = useState(1);
  const [itemsSearch, setItemsSearch] = useState('');
  const [appliedItemsSearch, setAppliedItemsSearch] = useState('');
  const [itemsWarranty, setItemsWarranty] = useState('');
  const [itemsIdentifierType, setItemsIdentifierType] = useState('');
  const [itemsDeviceType, setItemsDeviceType] = useState('');
  const [items, setItems] = useState([]);
  const [itemsTotal, setItemsTotal] = useState(0);
  const [itemsLoading, setItemsLoading] = useState(true);

  // ----- Management item editing state -----
  const [showItemModal, setShowItemModal] = useState(false);
  const [editingItemId, setEditingItemId] = useState('');
  const [itemForm, setItemForm] = useState(initialItemForm);
  const [submitting, setSubmitting] = useState(false);

  // ----- Recipients for distribution -----
  const [recipients, setRecipients] = useState([]);
  const [recipientsLoading, setRecipientsLoading] = useState(true);
  const [recipientType, setRecipientType] = useState('');

  // ----- Distribution form state -----
  const [distributionForm, setDistributionForm] = useState({
    item_id: '',
    to_user_id: '',
    quantity: 1,
    notes: '',
  });
  const [distributing, setDistributing] = useState(false);

  // ----- Distributed history state -----
  const [historyPage, setHistoryPage] = useState(1);
  const [historySearch, setHistorySearch] = useState('');
  const [appliedHistorySearch, setAppliedHistorySearch] = useState('');
  const [historyWarranty, setHistoryWarranty] = useState('');
  const [historyIdentifierType, setHistoryIdentifierType] = useState('');
  const [historyDeviceType, setHistoryDeviceType] = useState('');
  const [historyData, setHistoryData] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);

  const itemsQueryVersionRef = useRef(0);
  const itemsLoadingWindowsRef = useRef(new Set());
  const itemsLoadedWindowRef = useRef(0);
  const historyQueryVersionRef = useRef(0);
  const historyLoadingWindowsRef = useRef(new Set());
  const historyLoadedWindowRef = useRef(0);

  const buildItemsWindowParams = (windowPage) => {
    const params = { page: windowPage, page_size: TABLE_WINDOW_SIZE };
    if (appliedItemsSearch) {
      params.search = appliedItemsSearch;
    }
    if (itemsWarranty) {
      params.warranty = itemsWarranty;
    }
    if (itemsIdentifierType) {
      params.identifier_type = itemsIdentifierType;
    }
    if (itemsDeviceType) {
      params.type = itemsDeviceType;
    }
    return params;
  };

  const loadItemsWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (itemsLoadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = itemsQueryVersionRef.current;
    itemsLoadingWindowsRef.current.add(windowPage);
    if (withLoading) setItemsLoading(true);

    try {
      const response = await externalInventoryAPI.getItems(buildItemsWindowParams(windowPage));
      if (queryVersion !== itemsQueryVersionRef.current) {
        return;
      }

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setItems((prev) => {
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

      setItemsTotal(total);
      itemsLoadedWindowRef.current = Math.max(itemsLoadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load items', 'error');
    } finally {
      itemsLoadingWindowsRef.current.delete(windowPage);
      if (withLoading) setItemsLoading(false);
    }
  };

  const resetAndLoadItems = async () => {
    itemsQueryVersionRef.current += 1;
    itemsLoadedWindowRef.current = 0;
    itemsLoadingWindowsRef.current = new Set();
    setItems([]);
    setItemsTotal(0);
    setItemsPage(1);
    await loadItemsWindow(1, { reset: true, withLoading: true });
  };

  const handleItemsPageChange = (nextPage) => {
    setItemsPage(nextPage);

    const requiredWindow = Math.ceil(nextPage / TABLE_WINDOW_PAGES);
    const loadedPageCount = Math.max(1, Math.ceil((items.length || 0) / TABLE_PAGE_SIZE));
    const totalPageCount = Math.max(1, Math.ceil((itemsTotal || 0) / TABLE_PAGE_SIZE));
    const totalWindows = Math.ceil((itemsTotal || 0) / TABLE_WINDOW_SIZE);

    if (requiredWindow > itemsLoadedWindowRef.current) {
      loadItemsWindow(requiredWindow, { reset: false, withLoading: false });
    }

    if (nextPage >= loadedPageCount && loadedPageCount < totalPageCount) {
      const nextWindow = itemsLoadedWindowRef.current + 1;
      if (nextWindow <= totalWindows && nextWindow > itemsLoadedWindowRef.current) {
        loadItemsWindow(nextWindow, { reset: false, withLoading: false });
      }
    }
  };

  const loadRecipients = async () => {
    setRecipientsLoading(true);
    try {
      const [sdRes, clRes, opRes] = await Promise.all([
        usersAPI.getUsers({ role: 'sub_distributor', status: 'active', page_size: 10000 }).catch(() => ({ data: [] })),
        usersAPI.getUsers({ role: 'cluster', status: 'active', page_size: 10000 }).catch(() => ({ data: [] })),
        usersAPI.getUsers({ role: 'operator', status: 'active', page_size: 10000 }).catch(() => ({ data: [] })),
      ]);
      setRecipients([
        ...(Array.isArray(sdRes?.data) ? sdRes.data : []),
        ...(Array.isArray(clRes?.data) ? clRes.data : []),
        ...(Array.isArray(opRes?.data) ? opRes.data : []),
      ]);
    } catch (error) {
      showToast(error.message || 'Failed to load recipients', 'error');
      setRecipients([]);
    } finally {
      setRecipientsLoading(false);
    }
  };

  const buildHistoryWindowParams = (windowPage) => {
    const params = { page: windowPage, page_size: TABLE_WINDOW_SIZE };
    if (appliedHistorySearch) {
      params.search = appliedHistorySearch;
    }
    if (historyWarranty) {
      params.warranty = historyWarranty;
    }
    if (historyIdentifierType) {
      params.identifier_type = historyIdentifierType;
    }
    if (historyDeviceType) {
      params.type = historyDeviceType;
    }
    return params;
  };

  const loadHistoryWindow = async (windowPage, { reset = false, withLoading = false } = {}) => {
    if (!canManage) return;
    if (historyLoadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = historyQueryVersionRef.current;
    historyLoadingWindowsRef.current.add(windowPage);
    if (withLoading) setHistoryLoading(true);

    try {
      const response = await externalInventoryAPI.getDistributions(buildHistoryWindowParams(windowPage));
      if (queryVersion !== historyQueryVersionRef.current) {
        return;
      }

      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);

      setHistoryData((prev) => {
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

      setHistoryTotal(total);
      historyLoadedWindowRef.current = Math.max(historyLoadedWindowRef.current, windowPage);
    } catch (error) {
      showToast(error.message || 'Failed to load distribution history', 'error');
    } finally {
      historyLoadingWindowsRef.current.delete(windowPage);
      if (withLoading) setHistoryLoading(false);
    }
  };

  const resetAndLoadHistory = async () => {
    if (!canManage) return;
    historyQueryVersionRef.current += 1;
    historyLoadedWindowRef.current = 0;
    historyLoadingWindowsRef.current = new Set();
    setHistoryData([]);
    setHistoryTotal(0);
    setHistoryPage(1);
    await loadHistoryWindow(1, { reset: true, withLoading: true });
  };

  const handleHistoryPageChange = (nextPage) => {
    setHistoryPage(nextPage);

    const requiredWindow = Math.ceil(nextPage / TABLE_WINDOW_PAGES);
    const loadedPageCount = Math.max(1, Math.ceil((historyData.length || 0) / TABLE_PAGE_SIZE));
    const totalPageCount = Math.max(1, Math.ceil((historyTotal || 0) / TABLE_PAGE_SIZE));
    const totalWindows = Math.ceil((historyTotal || 0) / TABLE_WINDOW_SIZE);

    if (requiredWindow > historyLoadedWindowRef.current) {
      loadHistoryWindow(requiredWindow, { reset: false, withLoading: false });
    }

    if (nextPage >= loadedPageCount && loadedPageCount < totalPageCount) {
      const nextWindow = historyLoadedWindowRef.current + 1;
      if (nextWindow <= totalWindows && nextWindow > historyLoadedWindowRef.current) {
        loadHistoryWindow(nextWindow, { reset: false, withLoading: false });
      }
    }
  };

  const getItemsExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;
    while (true) {
      const response = await externalInventoryAPI.getItems({
        ...buildItemsWindowParams(page),
        page_size: 1000,
      });
      const rows = Array.isArray(response?.data) ? response.data : [];
      total = Number(response?.pagination?.total || rows.length);
      collected = collected.concat(rows);
      if (!rows.length || collected.length >= total) {
        break;
      }
      page += 1;
    }
    return collected;
  };

  const getHistoryExportRows = async () => {
    if (!canManage) return [];
    let page = 1;
    let collected = [];
    let total = 0;
    while (true) {
      const response = await externalInventoryAPI.getDistributions({
        ...buildHistoryWindowParams(page),
        page_size: 1000,
      });
      const rows = Array.isArray(response?.data) ? response.data : [];
      total = Number(response?.pagination?.total || rows.length);
      collected = collected.concat(rows);
      if (!rows.length || collected.length >= total) {
        break;
      }
      page += 1;
    }
    return collected;
  };

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    resetAndLoadItems();
    if (canManage) {
      resetAndLoadHistory();
    }
  };

  useEffect(() => {
    loadRecipients();
  }, []);

  useEffect(() => {
    const run = async () => {
      await resetAndLoadItems();
    };
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedItemsSearch, itemsWarranty, itemsIdentifierType, itemsDeviceType]);

  useEffect(() => {
    if (canManage) {
      const run = async () => {
        await resetAndLoadHistory();
      };
      run();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedHistorySearch, historyWarranty, historyIdentifierType, historyDeviceType, canManage]);

  useEffect(() => {
    const handler = () => refreshAll();
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formatCurrency = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(Number(value || 0));

  const itemLabel = (item) =>
    `${item?.name || '-'}${item?.device_type ? ` (${item.device_type})` : ''}${item?.quantity != null ? ` | Qty ${item.quantity}` : ''}`;

  const recipientLabel = (u) =>
    `${u?.name || u?.email || ''}${u?.email && u?.name ? ` (${u.email})` : ''}`;

  const handleRecipientTypeChange = (type) => {
    setRecipientType(type);
    setDistributionForm((p) => ({ ...p, to_user_id: '' }));
  };

  const visibleRecipients = useMemo(
    () => recipients.filter((u) => String(u.role) === recipientType),
    [recipients, recipientType]
  );

  const handleItemsSearchSubmit = () => {
    setAppliedItemsSearch(itemsSearch.trim());
    setItemsPage(1);
  };

  const handleItemsSearchReset = () => {
    setItemsSearch('');
    setAppliedItemsSearch('');
    setItemsWarranty('');
    setItemsIdentifierType('');
    setItemsDeviceType('');
    setItemsPage(1);
  };

  const handleHistorySearchSubmit = () => {
    setAppliedHistorySearch(historySearch.trim());
    setHistoryPage(1);
  };

  const handleHistorySearchReset = () => {
    setHistorySearch('');
    setAppliedHistorySearch('');
    setHistoryWarranty('');
    setHistoryIdentifierType('');
    setHistoryDeviceType('');
    setHistoryPage(1);
  };

  const openAddItem = () => {
    setEditingItemId('');
    setItemForm(initialItemForm);
    setShowItemModal(true);
  };

  const openEditItem = (item) => {
    setEditingItemId(String(item?.id || item?.item_id || ''));
    setItemForm({
      name: item?.name || '',
      identifier_type: item?.identifier_type || '',
      identifier: item?.identifier || '',
      device_type: item?.device_type || '',
      quantity: Number(item?.quantity ?? 1),
      price: Number(item?.price ?? 0),
      supplier_name: item?.supplier_name || '',
      location: item?.location || '',
      warranty_start_date: item?.warranty_start_date ? String(item.warranty_start_date).slice(0, 10) : '',
      warranty_duration:
        item?.warranty_duration != null ? Number(item.warranty_duration) : '',
      notes: item?.notes || '',
    });
    setShowItemModal(true);
  };

  const closeItemModal = () => {
    setShowItemModal(false);
    setEditingItemId('');
    setItemForm(initialItemForm);
  };

  const handleSaveItem = async () => {
    if (!itemForm.name.trim()) {
      showToast('Name is required', 'error');
      return;
    }
    const quantity = Number(itemForm.quantity || 1);
    if (quantity < 1) {
      showToast('Quantity must be at least 1', 'error');
      return;
    }
    const payload = {
      ...itemForm,
      price: Number(itemForm.price || 0),
      quantity,
      identifier_type: itemForm.identifier_type || null,
      identifier: itemForm.identifier || null,
      device_type: itemForm.device_type || null,
      supplier_name: itemForm.supplier_name || null,
      location: itemForm.location || null,
      warranty_start_date: itemForm.warranty_start_date || null,
      warranty_duration:
        itemForm.warranty_duration !== '' ? Number(itemForm.warranty_duration) : null,
      notes: itemForm.notes || null,
    };
    try {
      setSubmitting(true);
      if (editingItemId) {
        await externalInventoryAPI.updateItem(editingItemId, payload);
        showToast('External inventory item updated', 'success');
      } else {
        await externalInventoryAPI.createItem(payload);
        showToast('External inventory item created', 'success');
      }
      closeItemModal();
      refreshAll();
    } catch (error) {
      showToast(error.message || 'Failed to save item', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteItem = async (item) => {
    const itemId = String(item?.id || item?.item_id || '');
    const confirmed = window.confirm(`Delete external inventory item "${item?.name || itemId}"?`);
    if (!confirmed) return;
    try {
      await externalInventoryAPI.deleteItem(itemId);
      showToast('External inventory item deleted', 'success');
      refreshAll();
    } catch (error) {
      showToast(error.message || 'Failed to delete item', 'error');
    }
  };

  const handleDistribute = async () => {
    if (!distributionForm.item_id) {
      showToast('Select an item to distribute', 'error');
      return;
    }
    if (!distributionForm.to_user_id) {
      showToast('Select a recipient', 'error');
      return;
    }
    const quantity = Number(distributionForm.quantity || 1);
    if (quantity < 1) {
      showToast('Quantity must be at least 1', 'error');
      return;
    }
    try {
      setDistributing(true);
      await externalInventoryAPI.distributeItem({
        item_id: Number(distributionForm.item_id),
        to_user_id: Number(distributionForm.to_user_id),
        quantity,
        notes: distributionForm.notes || null,
      });
      showToast('Item distributed successfully', 'success');
      setDistributionForm({ item_id: '', to_user_id: '', quantity: 1, notes: '' });
      refreshAll();
    } catch (error) {
      showToast(error.message || 'Failed to distribute item', 'error');
    } finally {
      setDistributing(false);
    }
  };

  const mgmtItemColumns = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'identifier_type', label: 'Identifier Type' },
    { key: 'identifier', label: 'Identifier' },
    { key: 'device_type', label: 'Type' },
    { key: 'quantity', label: 'Available Qty' },
    { key: 'price', label: 'Price', render: (v) => formatCurrency(v) },
    { key: 'supplier_name', label: 'Supplier' },
    { key: 'location', label: 'Location' },
    {
      key: 'warranty_start_date',
      label: 'Warranty Start',
      render: (v) => (v ? String(v).slice(0, 10) : '-'),
    },
    { key: 'warranty_duration', label: 'Warranty (months)', render: (v) => (v != null ? v : '-') },
    { key: 'status', label: 'Status' },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => openEditItem(row)}>
            Edit
          </Button>
          <Button
            size="sm"
            variant="danger"
            icon={Trash2}
            onClick={() => handleDeleteItem(row)}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  const viewerItemColumns = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'price', label: 'Price', render: (v) => formatCurrency(v) },
  ];

  const itemColumns = canManage ? mgmtItemColumns : viewerItemColumns;

  const historyColumns = [
    { key: 'history_id', label: 'History ID' },
    { key: 'item_name', label: 'Item' },
    { key: 'recipient_name', label: 'Recipient' },
    { key: 'quantity', label: 'Qty' },
    { key: 'previous_quantity', label: 'Previous' },
    { key: 'remaining_quantity', label: 'Remaining' },
    {
      key: 'warranty_status',
      label: 'Warranty',
      render: (value) => (
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
          value === 'expired' ? 'bg-red-50 text-red-700'
          : value === 'active' ? 'bg-green-50 text-green-700'
          : 'bg-gray-100 text-gray-600'
        }`}>
          <span className={`h-1.5 w-1.5 rounded-full ${
            value === 'expired' ? 'bg-red-500'
            : value === 'active' ? 'bg-green-500'
            : 'bg-gray-400'
          }`} />
          {value === 'expired' ? 'Warranty Expired'
            : value === 'active' ? 'Warranty Active'
            : 'No Warranty'}
        </span>
      ),
    },
    { key: 'distributed_by_name', label: 'Distributed By' },
    {
      key: 'distributed_at',
      label: 'Distributed At',
      render: (value) => (value ? new Date(value).toLocaleString() : '-'),
    },
    { key: 'status', label: 'Status' },
  ];

  const renderTabButton = (t) => (
    <button
      key={t.key}
      type="button"
      onClick={() => setActiveTab(t.key)}
      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
        activeTab === t.key
          ? 'bg-blue-600 text-white'
          : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'
      }`}
    >
      {t.key === 'items' && <Boxes className="h-4 w-4" />}
      {t.key === 'distribution' && <Send className="h-4 w-4" />}
      {t.key === 'distributed' && <ClipboardList className="h-4 w-4" />}
      {t.label}
    </button>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 via-sky-50 to-indigo-50 p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 sm:text-2xl">External Inventory</h1>
            <p className="mt-1 text-sm text-gray-600">
              Manage distribution items, assign them to recipients, and review distribution history.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button variant="secondary" icon={RefreshCw} onClick={refreshAll}>
              Refresh
            </Button>
            {canManage && (
              <Button icon={PackagePlus} onClick={openAddItem}>
                Add Item
              </Button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">{tabs.map(renderTabButton)}</div>
      </div>

      {activeTab === 'items' && (
        <>
          <Card className="!p-4">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-800">Search Items</h3>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-12">
              <div className="md:col-span-4">
                <input
                  type="text"
                  value={itemsSearch}
                  onChange={(e) => setItemsSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleItemsSearchSubmit();
                    }
                  }}
                  placeholder="Search by name, identifier, type, supplier, or location..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="md:col-span-2">
                <select
                  value={itemsWarranty}
                  onChange={(e) => { setItemsWarranty(e.target.value); setItemsPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Warranty</option>
                  <option value="active">Warranty Active</option>
                  <option value="expired">Warranty Expired</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <select
                  value={itemsIdentifierType}
                  onChange={(e) => { setItemsIdentifierType(e.target.value); setItemsPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Identifier Types</option>
                  {IDENTIFIER_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <select
                  value={itemsDeviceType}
                  onChange={(e) => { setItemsDeviceType(e.target.value); setItemsPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Types</option>
                  {ITEM_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={handleItemsSearchSubmit} className="w-full">
                  Search
                </Button>
                <Button variant="secondary" onClick={handleItemsSearchReset}>
                  Reset
                </Button>
              </div>
            </div>
          </Card>

          <Card title="Inventory Items" subtitle="Individual distribution items" padding={false}>
            <DataTable
              columns={itemColumns}
              data={items}
              loading={itemsLoading}
              searchable={false}
              pageSize={TABLE_PAGE_SIZE}
              totalItems={itemsTotal || items.length}
              currentPage={itemsPage}
              onPageChange={handleItemsPageChange}
              getExportRows={getItemsExportRows}
              emptyMessage="No external inventory items available"
              onRowClick={canManage ? (row) => openEditItem(row) : undefined}
              actions={
                canManage ? (
                  <Button size="sm" variant="outline" icon={Upload} onClick={() => navigate('/external-inventory/bulk-import')}>
                    Bulk Import
                  </Button>
                ) : null
              }
            />
          </Card>
        </>
      )}

      {activeTab === 'distribution' && (
        <Card title="Distribute Item" subtitle="Assign an item to a recipient. Quantity is reduced immediately.">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Item *</span>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={distributionForm.item_id}
                onChange={(e) => setDistributionForm((p) => ({ ...p, item_id: e.target.value }))}
              >
                <option value="">Select item</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {itemLabel(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Select Recipient Type</span>
              <div className="flex flex-wrap gap-2">
                {RECIPIENT_TYPE_OPTIONS.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => handleRecipientTypeChange(type)}
                    className={`px-3 py-1.5 rounded-lg border-2 text-sm font-medium transition-colors ${
                      recipientType === type
                        ? type === 'sub_distributor' ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                        : type === 'cluster'         ? 'border-teal-500 bg-teal-50 text-teal-700'
                                                     : 'border-green-500 bg-green-50 text-green-700'
                        : 'border-gray-200 text-gray-600 hover:border-gray-400'
                    }`}
                  >
                    {ROLE_LABELS[type]}
                  </button>
                ))}
              </div>
            </label>
            {recipientType && (
              <label className="space-y-1">
                <span className="text-sm font-medium text-gray-700">
                  Recipient *
                  <span className="text-xs text-gray-400 ml-2">
                    ({visibleRecipients.length} available)
                  </span>
                </span>
                {visibleRecipients.length === 0 ? (
                  <p className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
                    No {ROLE_LABELS[recipientType].toLowerCase()}s found.
                  </p>
                ) : (
                  <select
                    className="w-full rounded-lg border border-gray-300 px-3 py-2"
                    value={distributionForm.to_user_id}
                    onChange={(e) => setDistributionForm((p) => ({ ...p, to_user_id: e.target.value }))}
                    disabled={recipientsLoading}
                  >
                    <option value="">Select {ROLE_LABELS[recipientType]}...</option>
                    {visibleRecipients.map((u) => (
                      <option key={u.id} value={u.id}>
                        {recipientLabel(u)}
                      </option>
                    ))}
                  </select>
                )}
              </label>
            )}
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Quantity</span>
              <input
                type="number"
                min="1"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={distributionForm.quantity}
                onChange={(e) => setDistributionForm((p) => ({ ...p, quantity: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Notes</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={distributionForm.notes}
                onChange={(e) => setDistributionForm((p) => ({ ...p, notes: e.target.value }))}
                placeholder="Optional note for the recipient"
              />
            </label>
          </div>
          <div className="mt-4 flex justify-end">
            <Button icon={Send} loading={distributing} onClick={handleDistribute}>
              Distribute
            </Button>
          </div>
        </Card>
      )}

      {activeTab === 'distributed' && canManage && (
        <>
          <Card className="!p-4">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-800">Search Distribution History</h3>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-12">
              <div className="md:col-span-4">
                <input
                  type="text"
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleHistorySearchSubmit();
                    }
                  }}
                  placeholder="Search by history ID, item, recipient, or distributor..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="md:col-span-2">
                <select
                  value={historyWarranty}
                  onChange={(e) => { setHistoryWarranty(e.target.value); setHistoryPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Warranty</option>
                  <option value="active">Warranty Active</option>
                  <option value="expired">Warranty Expired</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <select
                  value={historyIdentifierType}
                  onChange={(e) => { setHistoryIdentifierType(e.target.value); setHistoryPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Identifier Types</option>
                  {IDENTIFIER_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <select
                  value={historyDeviceType}
                  onChange={(e) => { setHistoryDeviceType(e.target.value); setHistoryPage(1); }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">All Types</option>
                  {ITEM_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={handleHistorySearchSubmit} className="w-full">
                  Search
                </Button>
                <Button variant="secondary" onClick={handleHistorySearchReset}>
                  Reset
                </Button>
              </div>
            </div>
          </Card>

          <Card title="Distributed Items" subtitle="Every completed external inventory distribution" padding={false}>
            <DataTable
              columns={historyColumns}
              data={historyData}
              loading={historyLoading}
              searchable={false}
              pageSize={TABLE_PAGE_SIZE}
              totalItems={historyTotal || historyData.length}
              currentPage={historyPage}
              onPageChange={handleHistoryPageChange}
              getExportRows={getHistoryExportRows}
              emptyMessage="No distributions recorded yet"
            />
          </Card>
        </>
      )}

      {canManage && (
        <Modal
          isOpen={showItemModal}
          onClose={closeItemModal}
          title={editingItemId ? 'Edit External Inventory Item' : 'Add External Inventory Item'}
          size="lg"
          footer={
            <>
              <Button variant="ghost" onClick={closeItemModal}>
                Cancel
              </Button>
              <Button loading={submitting} onClick={handleSaveItem}>
                {editingItemId ? 'Save Changes' : 'Create Item'}
              </Button>
            </>
          }
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-medium text-gray-700">Name *</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.name}
                onChange={(e) => setItemForm((p) => ({ ...p, name: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Identifier Type</span>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.identifier_type}
                onChange={(e) => setItemForm((p) => ({ ...p, identifier_type: e.target.value }))}
              >
                <option value="">Select identifier type</option>
                {IDENTIFIER_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Identifier</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.identifier}
                onChange={(e) => setItemForm((p) => ({ ...p, identifier: e.target.value }))}
                placeholder="Value of the selected identifier type"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Type</span>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.device_type}
                onChange={(e) => setItemForm((p) => ({ ...p, device_type: e.target.value }))}
              >
                <option value="">Select type</option>
                {ITEM_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Quantity</span>
              <input
                type="number"
                min="1"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.quantity}
                onChange={(e) => setItemForm((p) => ({ ...p, quantity: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Price</span>
              <input
                type="number"
                min="0"
                step="0.01"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.price}
                onChange={(e) => setItemForm((p) => ({ ...p, price: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Supplier</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.supplier_name}
                onChange={(e) => setItemForm((p) => ({ ...p, supplier_name: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Location</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.location}
                onChange={(e) => setItemForm((p) => ({ ...p, location: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Warranty Start Date</span>
              <input
                type="date"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.warranty_start_date}
                onChange={(e) => setItemForm((p) => ({ ...p, warranty_start_date: e.target.value }))}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Warranty Duration (months)</span>
              <input
                type="number"
                min="0"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.warranty_duration}
                onChange={(e) => setItemForm((p) => ({ ...p, warranty_duration: e.target.value }))}
                placeholder="e.g. 12"
              />
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-medium text-gray-700">Notes</span>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.notes}
                onChange={(e) => setItemForm((p) => ({ ...p, notes: e.target.value }))}
              />
            </label>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default ExternalInventory;