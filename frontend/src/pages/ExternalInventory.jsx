import { useEffect, useMemo, useRef, useState } from 'react';
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
  Download,
  Search,
  Send,
  ClipboardList,
} from 'lucide-react';

const IDENTIFIER_TYPE_OPTIONS = ['NU ID', 'IMEI', 'Serial Ref', 'MAC ID', 'Asset Tag', 'Other'];
const ITEM_TYPE_OPTIONS = ['OTT Box', 'OLT', 'Remote', 'SB', 'Adapter', 'Others'];

const TABLE_PAGE_SIZE = 10;

const initialItemForm = {
  name: '',
  identifier_type: '',
  identifier: '',
  device_type: '',
  quantity: 1,
  price: 0,
  supplier_name: '',
  location: '',
  notes: '',
};

const MANAGEMENT_ROLES = ['super_admin', 'manager', 'pdic_staff'];

const ExternalInventory = ({ tab }) => {
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
  const [items, setItems] = useState([]);
  const [itemsTotal, setItemsTotal] = useState(0);
  const [itemsLoading, setItemsLoading] = useState(true);

  // ----- Management item editing state -----
  const [showItemModal, setShowItemModal] = useState(false);
  const [editingItemId, setEditingItemId] = useState('');
  const [itemForm, setItemForm] = useState(initialItemForm);
  const [submitting, setSubmitting] = useState(false);
  const [importingItems, setImportingItems] = useState(false);
const [importResult, setImportResult] = useState(null);
  const importInputRef = useRef(null);

  // ----- Recipients for distribution -----
  const [recipients, setRecipients] = useState([]);
  const [recipientsLoading, setRecipientsLoading] = useState(true);

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
  const [historyData, setHistoryData] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);

  const buildItemsParams = (page) => {
    const params = { page, page_size: TABLE_PAGE_SIZE };
    if (appliedItemsSearch) {
      params.search = appliedItemsSearch;
    }
    return params;
  };

  const loadItems = async (page = itemsPage) => {
    setItemsLoading(true);
    try {
      const response = await externalInventoryAPI.getItems(buildItemsParams(page));
      const rows = Array.isArray(response?.data) ? response.data : [];
      setItems(rows);
      setItemsTotal(Number(response?.pagination?.total || rows.length));
    } catch (error) {
      showToast(error.message || 'Failed to load items', 'error');
    } finally {
      setItemsLoading(false);
    }
  };

  const loadRecipients = async () => {
    setRecipientsLoading(true);
    try {
      const response = await usersAPI.getUsers({ status: 'active', page_size: 10000 });
      const rows = Array.isArray(response?.data) ? response.data : [];
      setRecipients(rows);
    } catch (error) {
      showToast(error.message || 'Failed to load recipients', 'error');
      setRecipients([]);
    } finally {
      setRecipientsLoading(false);
    }
  };

  const loadHistory = async (page = historyPage) => {
    if (!canManage) return;
    setHistoryLoading(true);
    try {
      const params = { page, page_size: TABLE_PAGE_SIZE };
      if (appliedHistorySearch) {
        params.search = appliedHistorySearch;
      }
      const response = await externalInventoryAPI.getDistributions(params);
      const rows = Array.isArray(response?.data) ? response.data : [];
      setHistoryData(rows);
      setHistoryTotal(Number(response?.pagination?.total || rows.length));
    } catch (error) {
      showToast(error.message || 'Failed to load distribution history', 'error');
    } finally {
      setHistoryLoading(false);
    }
  };

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    loadItems(itemsPage);
    if (canManage) {
      loadHistory(historyPage);
    }
  };

  useEffect(() => {
    loadItems(itemsPage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsPage, appliedItemsSearch]);

  useEffect(() => {
    loadRecipients();
  }, []);

  useEffect(() => {
    if (canManage) {
      loadHistory(historyPage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyPage, appliedHistorySearch, canManage]);

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

  const handleItemsSearchSubmit = () => {
    setAppliedItemsSearch(itemsSearch.trim());
    setItemsPage(1);
  };

  const handleItemsSearchReset = () => {
    setItemsSearch('');
    setAppliedItemsSearch('');
    setItemsPage(1);
  };

  const handleHistorySearchSubmit = () => {
    setAppliedHistorySearch(historySearch.trim());
    setHistoryPage(1);
  };

  const handleHistorySearchReset = () => {
    setHistorySearch('');
    setAppliedHistorySearch('');
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

  const handleImportItems = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      showToast('Please upload a CSV file (.csv)', 'error');
      return;
    }
    try {
      setImportingItems(true);
      const result = await externalInventoryAPI.bulkUploadItems(file);
      setImportResult(result.data || {});
      showToast(result.message || 'Import completed', 'success');
      refreshAll();
    } catch (error) {
      showToast(error.message || 'Failed to import items', 'error');
    } finally {
      setImportingItems(false);
    }
  };

  const escapeCsvCell = (value) => {
    const text = String(value ?? '');
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };

  const handleDownloadModel = () => {
    const headers = [
      'name',
      'identifier_type',
      'identifier',
      'device_type',
      'price',
      'quantity',
      'supplier_name',
      'location',
      'notes',
    ];
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
        notes: 'OLT example',
      },
      {
        name: 'Sample Remote Device',
        identifier_type: 'MAC ID',
        identifier: 'AA:BB:CC:DD:EE:FF',
        device_type: 'Remote',
        price: '1599',
        quantity: '5',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse B',
        notes: 'Remote example',
      },
    ];
    const csvLines = [
      headers.join(','),
      ...sampleRows.map((row) => headers.map((key) => escapeCsvCell(row[key])).join(',')),
    ];
    const csvContent = `\uFEFF${csvLines.join('\n')}`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'external-inventory-import-model.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
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
              <div className="md:col-span-8">
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
              <div className="flex gap-2 md:col-span-4">
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
            {importResult && (importResult.error_count > 0 || importResult.skipped_count > 0) && (
              <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-sm text-slate-600">
                  Import finished: {importResult.created_count} created, {importResult.skipped_count} skipped,{' '}
                  {importResult.error_count} errors.
                  {importResult.errors_truncated || importResult.skipped_truncated
                    ? ' Only the first 500 failed rows are shown.'
                    : ''}
                </p>
              </div>
            )}
            <DataTable
              columns={itemColumns}
              data={items}
              loading={itemsLoading}
              searchable={false}
              pageSize={TABLE_PAGE_SIZE}
              totalItems={itemsTotal || items.length}
              currentPage={itemsPage}
              onPageChange={setItemsPage}
              emptyMessage="No external inventory items available"
              onRowClick={canManage ? (row) => openEditItem(row) : undefined}
              actions={
                canManage ? (
                  <>
                    <input
                      ref={importInputRef}
                      type="file"
                      accept=".csv,text/csv"
                      className="hidden"
                      onChange={handleImportItems}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      icon={Upload}
                      loading={importingItems}
                      onClick={() => importInputRef.current?.click()}
                    >
                      Import
                    </Button>
                    <Button size="sm" variant="secondary" icon={Download} onClick={handleDownloadModel}>
                      Download Model
                    </Button>
                  </>
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
              <span className="text-sm font-medium text-gray-700">Recipient *</span>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={distributionForm.to_user_id}
                onChange={(e) => setDistributionForm((p) => ({ ...p, to_user_id: e.target.value }))}
                disabled={recipientsLoading}
              >
                <option value="">Select recipient</option>
                {recipients.map((u) => (
                  <option key={u.id} value={u.id}>
                    {recipientLabel(u)}
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
              <div className="md:col-span-8">
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
              <div className="flex gap-2 md:col-span-4">
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
              onPageChange={setHistoryPage}
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