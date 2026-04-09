import { useEffect, useMemo, useRef, useState } from 'react';
import { jsPDF } from 'jspdf';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import DataTable from '../components/ui/DataTable';
import { dashboardAPI, externalInventoryAPI } from '../services/api';
import { useNotifications } from '../context/NotificationContext';
import { useAuth } from '../context/AuthContext';
import {
  Boxes,
  ClipboardCheck,
  Factory,
  Eye,
  PackagePlus,
  RefreshCw,
  Upload,
  Download,
} from 'lucide-react';

const initialItemForm = {
  item_id: '',
  name: '',
  serial_number: '',
  mac_id: '',
  device_type: '',
  custom_device_type: '',
  price: 0,
  unit: 'pcs',
  supplier_name: '',
  location: '',
  notes: '',
};

const ITEM_TYPE_OPTIONS = ['OTT Box', 'OLT', 'Remote', 'SB', 'Adapter', 'Others'];

const toTypeLabel = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  return ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalized) ? 'SB' : (value || '-');
};

const defaultPOLine = { item_inventory_id: '' };

const ExternalInventory = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const canManage = ['super_admin', 'manager', 'pdic_staff'].includes(user?.role);
  const canConfirmPO = canManage;

  const [dashboard, setDashboard] = useState(null);
  const [items, setItems] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [showCreatePOModal, setShowCreatePOModal] = useState(false);
  const [receivingPO, setReceivingPO] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemImageFile, setItemImageFile] = useState(null);
  const [itemImagePreview, setItemImagePreview] = useState('');
  const [importingItems, setImportingItems] = useState(false);
  const [downloadingReceiptPoId, setDownloadingReceiptPoId] = useState('');
  const importInputRef = useRef(null);

  const [itemForm, setItemForm] = useState(initialItemForm);
  const [editingInventoryId, setEditingInventoryId] = useState('');

  const normalizedItemType = String(itemForm.device_type || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  const isSetTopBoxType = ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedItemType);
  const isOtherType = normalizedItemType === 'others';
  const idFieldLabel = isSetTopBoxType ? 'NU ID' : 'MAC ID';
  const isIdRequired = !isOtherType;

  const [poForm, setPoForm] = useState({
    name: '',
    expected_date: '',
    notes: '',
    lines: [{ ...defaultPOLine }],
  });

  const [receiptForm, setReceiptForm] = useState({
    notes: '',
    lines: [],
  });

  const apiBaseUrl = useMemo(
    () => (import.meta.env.VITE_API_URL || 'http://localhost:8080/api').replace(/\/$/, ''),
    []
  );

  const toAssetUrl = (path) => {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    const backendBase = apiBaseUrl.replace(/\/api$/, '');
    return `${backendBase}${path.startsWith('/') ? path : `/${path}`}`;
  };

  const formatDateTime = (value) => {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const parts = new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).formatToParts(date);

    const get = (type) => parts.find((p) => p.type === type)?.value || '';
    return `${get('day')}/${get('month')}/${get('year')} ${get('hour')}:${get('minute')}:${get('second')} IST`;
  };

  const formatCurrency = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(Number(value || 0));

  const loadData = async () => {
    try {
      setLoading(true);
      if (canManage) {
        const [dashboardRes, itemsRes, poRes, movementRes] = await Promise.all([
          externalInventoryAPI.getDashboard(),
          externalInventoryAPI.getItems({ page_size: 100, status: 'active' }),
          externalInventoryAPI.getPurchaseOrders({ page_size: 100 }),
          externalInventoryAPI.getMovements({ page_size: 100 }),
        ]);

        setDashboard(dashboardRes.data || null);
        setItems(itemsRes.data || []);
        setPurchaseOrders(poRes.data || []);
        setMovements(movementRes.data || []);
      } else {
        const [itemsRes, poRes] = await Promise.all([
          externalInventoryAPI.getItems({ page_size: 100, status: 'active' }),
          externalInventoryAPI.getPurchaseOrders({ page_size: 100 }),
        ]);
        setDashboard(null);
        setItems(itemsRes.data || []);
        setPurchaseOrders(poRes.data || []);
        setMovements([]);
      }
    } catch (error) {
      showToast(error.message || 'Failed to load external inventory data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [canManage]);

  const resetPoForm = () => {
    setPoForm({
      name: '',
      expected_date: '',
      notes: '',
      lines: [{ ...defaultPOLine }],
    });
  };

  const handleCreateItem = async () => {
    const normalizedMacOrNuId = String(itemForm.mac_id || '').trim();
    if (
      !itemForm.item_id.trim() ||
      !itemForm.name.trim() ||
      !itemForm.serial_number.trim() ||
      !itemForm.device_type.trim()
    ) {
      showToast('Item ID, name, serial number and type are required', 'error');
      return;
    }

    if (isIdRequired && !normalizedMacOrNuId) {
      showToast(`${idFieldLabel} is required for the selected type`, 'error');
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        ...itemForm,
        mac_id: normalizedMacOrNuId,
        price: Number(itemForm.price),
      };

      const created = editingInventoryId
        ? await externalInventoryAPI.updateItem(editingInventoryId, payload)
        : await externalInventoryAPI.createItem(payload);

      const createdInventoryId = created?.data?.inventory_id || editingInventoryId;
      if (itemImageFile && createdInventoryId) {
        await externalInventoryAPI.uploadItemImage(createdInventoryId, itemImageFile);
      }

      showToast(editingInventoryId ? 'Inventory item updated' : 'Inventory device item created', 'success');
      setShowAddItemModal(false);
      setItemForm(initialItemForm);
      setEditingInventoryId('');
      setItemImageFile(null);
      setItemImagePreview('');
      await loadData();
    } catch (error) {
      showToast(error.message || 'Failed to create item', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const addPOLine = () => {
    setPoForm((prev) => ({
      ...prev,
      lines: [...prev.lines, { ...defaultPOLine }],
    }));
  };

  const updatePOLine = (index, key, value) => {
    setPoForm((prev) => {
      const next = [...prev.lines];
      next[index] = { ...next[index], [key]: value };
      return { ...prev, lines: next };
    });
  };

  const removePOLine = (index) => {
    setPoForm((prev) => {
      const next = prev.lines.filter((_, i) => i !== index);
      return { ...prev, lines: next.length ? next : [{ ...defaultPOLine }] };
    });
  };

  const handleCreatePO = async () => {
    if (!poForm.name.trim()) {
      showToast('Name is required', 'error');
      return;
    }

    if (poForm.lines.some((line) => !line.item_inventory_id)) {
      showToast('Each PO line needs a selected device item', 'error');
      return;
    }

    try {
      setSubmitting(true);
      await externalInventoryAPI.createPurchaseOrder({
        name: poForm.name,
        expected_date: poForm.expected_date || null,
        notes: poForm.notes || null,
        status: 'submitted',
        lines: poForm.lines.map((line) => ({
          item_inventory_id: line.item_inventory_id,
        })),
      });

      showToast('Purchase order created', 'success');
      setShowCreatePOModal(false);
      resetPoForm();
      await loadData();
    } catch (error) {
      showToast(error.message || 'Failed to create purchase order', 'error');
    } finally {
      setSubmitting(false);
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
      showToast(result.message || 'Import completed', 'success');
      await loadData();
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

  const handleDownloadModel = async () => {
    try {
      await dashboardAPI.trackActivity({
        action: 'export_model_download',
        description: 'Downloaded external inventory import model',
        context: 'external_inventory',
      });
    } catch {
      // Continue model download even if tracking fails.
    }

    const headers = [
      'item_id',
      'name',
      'serial_number',
      'mac_id',
      'device_type',
      'custom_device_type',
      'price',
      'unit',
      'supplier_name',
      'location',
      'notes',
    ];

    const sampleRows = [
      {
        item_id: 'ITEM-EX-1001',
        name: 'Sample OTT Device',
        serial_number: 'SN-EX-1001',
        mac_id: 'MAC-EX-1001',
        device_type: 'OTT Box',
        custom_device_type: '',
        price: '2799',
        unit: 'pcs',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse A',
        notes: 'Sample row',
      },
      {
        item_id: 'ITEM-EX-1002',
        name: 'Custom Device Sample',
        serial_number: 'SN-EX-1002',
        mac_id: '',
        device_type: 'Others',
        custom_device_type: 'Media Converter',
        price: '1599',
        unit: 'pcs',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse B',
        notes: 'MAC/NU ID optional for Others',
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

  const openReceiveModal = (po) => {
    setReceivingPO(po);
    setReceiptForm({
      notes: '',
      lines: (po.lines || []).map((line) => ({
        item_inventory_id: line.item_inventory_id,
      })),
    });
  };

  const handleReceivePO = async () => {
    if (!receivingPO) return;

    try {
      setSubmitting(true);
      const response = await externalInventoryAPI.receivePurchaseOrder(receivingPO.po_id, {
        notes: receiptForm.notes || null,
        lines: receiptForm.lines.map((line) => ({
          item_inventory_id: line.item_inventory_id,
        })),
      });

      const updatedPo = response?.data;
      const latestReceipt = updatedPo?.receipts?.[0] || null;
      if (updatedPo && latestReceipt) {
        downloadReceiptPdf(updatedPo, latestReceipt);
      }

      showToast('Purchase order submitted and stock updated', 'success');
      setReceivingPO(null);
      setReceiptForm({ notes: '', lines: [] });
      await loadData();
    } catch (error) {
      showToast(error.message || 'Failed to submit purchase order', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const downloadReceiptPdf = (po, receipt) => {
    const doc = new jsPDF();
    const lines = receipt?.lines || [];
    const total = lines.reduce((sum, line) => sum + Number(line.line_total || 0), 0);
    const orderPlacedBy = po?.ordered_by_name || po?.ordered_by || '-';

    let y = 16;
    doc.setFontSize(16);
    doc.text('External Inventory Receipt', 14, y);

    y += 10;
    doc.setFontSize(11);
    doc.text(`Receipt ID: ${receipt?.receipt_id || '-'}`, 14, y);
    y += 7;
    doc.text(`PO ID: ${po?.po_id || '-'}`, 14, y);
    y += 7;
    doc.text(`Name: ${po?.supplier_name || receipt?.supplier_name || '-'}`, 14, y);
    y += 7;
    doc.text(`Order Placed By: ${orderPlacedBy}`, 14, y);
    y += 7;
    doc.text(`Date: ${formatDateTime(receipt?.created_at)}`, 14, y);
    y += 7;
    doc.text(`Submitted By: ${receipt?.received_by_name || '-'}`, 14, y);
    y += 10;

    doc.setFontSize(12);
    doc.text('Items', 14, y);
    y += 7;

    doc.setFontSize(10);
    doc.text('Item', 14, y);
    doc.text('Amount', 196, y, { align: 'right' });
    y += 2;
    doc.line(14, y, 196, y);

    y += 6;
    lines.forEach((line) => {
      if (y > 276) {
        doc.addPage();
        y = 20;
      }
      const itemLabel = `${line.item_sku || '-'} ${line.item_name || ''}`.trim();
      doc.text(itemLabel.slice(0, 46), 14, y);
      doc.text(formatCurrency(line.line_total || 0).replace('₹', 'Rs '), 196, y, { align: 'right' });
      y += 7;
    });

    y += 4;
    doc.line(14, y, 196, y);
    y += 8;
    doc.setFontSize(12);
    doc.text(`Total: ${formatCurrency(total).replace('₹', 'Rs ')}`, 196, y, { align: 'right' });

    const fileName = `${receipt?.receipt_id || po?.po_id || 'receipt'}.pdf`;
    doc.save(fileName);
  };

  const handleDownloadLatestReceipt = async (po) => {
    try {
      setDownloadingReceiptPoId(po.po_id);
      const response = await externalInventoryAPI.getReceipts({ po_id: po.po_id, page_size: 1 });
      const latestReceipt = response?.data?.[0];

      if (!latestReceipt) {
        showToast('No receipt found for this purchase order', 'error');
        return;
      }

      downloadReceiptPdf(po, latestReceipt);
      showToast('Receipt downloaded', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to download receipt', 'error');
    } finally {
      setDownloadingReceiptPoId('');
    }
  };

  const managementItemColumns = [
    {
      key: 'image_url',
      label: 'Image',
      sortable: false,
      render: (value, row) => (
        value ? (
          <img
            src={toAssetUrl(value)}
            alt={row.name}
            className="h-10 w-10 rounded-lg border border-gray-200 object-cover"
          />
        ) : (
          <span className="text-xs text-gray-400">No image</span>
        )
      ),
    },
    { key: 'inventory_id', label: 'Inventory ID' },
    { key: 'item_id', label: 'Item ID' },
    { key: 'name', label: 'Name' },
    { key: 'serial_number', label: 'Serial Number' },
    {
      key: 'mac_id',
      label: 'Identifier',
      render: (value, row) => {
        const normalizedType = String(row?.device_type || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
        const isSetTop = ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedType);
        return `${isSetTop ? 'NU ID' : 'MAC ID'}: ${value || '-'}`;
      },
    },
    { key: 'device_type', label: 'Type', render: (value) => toTypeLabel(value) },
    {
      key: 'price',
      label: 'Price',
      render: (value) => formatCurrency(value),
    },
    {
      key: 'created_at',
      label: 'Added At',
      render: (value) => formatDateTime(value),
    },
  ];

  const viewerItemColumns = [
    {
      key: 'image_url',
      label: 'Image',
      sortable: false,
      render: (value, row) => (
        value ? (
          <img
            src={toAssetUrl(value)}
            alt={row.name}
            className="h-10 w-10 rounded-lg border border-gray-200 object-cover"
          />
        ) : (
          <span className="text-xs text-gray-400">No image</span>
        )
      ),
    },
    { key: 'name', label: 'Name' },
    { key: 'device_type', label: 'Type', render: (value) => toTypeLabel(value) },
    {
      key: 'price',
      label: 'Price',
      render: (value) => formatCurrency(value),
    },
  ];

  const itemColumns = canManage ? managementItemColumns : viewerItemColumns;

  const poColumns = [
    { key: 'po_id', label: 'PO ID' },
    { key: 'supplier_name', label: 'Name' },
    { key: 'ordered_by_name', label: 'Placed By' },
    { key: 'status', label: 'Status' },
    {
      key: 'total_amount',
      label: 'Total',
      render: (value) => formatCurrency(value),
    },
    {
      key: 'created_at',
      label: 'Created At',
      render: (value) => formatDateTime(value),
    },
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex flex-wrap gap-2">
          {canConfirmPO && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openReceiveModal(row)}
              disabled={['received', 'cancelled'].includes(row.status)}
            >
              Submit
            </Button>
          )}
          {['partially_received', 'received'].includes(row.status) && (
            <Button
              size="sm"
              variant="secondary"
              icon={Download}
              loading={downloadingReceiptPoId === row.po_id}
              onClick={() => handleDownloadLatestReceipt(row)}
            >
              Download Receipt
            </Button>
          )}
        </div>
      ),
    },
  ];

  const movementColumns = [
    { key: 'movement_id', label: 'Movement ID' },
    { key: 'item_sku', label: 'Item ID' },
    { key: 'item_name', label: 'Item' },
    { key: 'movement_type', label: 'Type' },
    { key: 'quantity', label: 'Qty' },
    { key: 'notes', label: 'Details' },
    { key: 'reference_type', label: 'Reference' },
    { key: 'reference_id', label: 'Ref ID' },
    {
      key: 'created_at',
      label: 'Timestamp',
      render: (value) => formatDateTime(value),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="external-inventory-hero relative overflow-hidden rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 via-amber-50 to-lime-50 p-6">
        <div className="absolute -top-8 -right-8 h-32 w-32 rounded-full bg-orange-200/40 blur-2xl" />
        <div className="absolute -bottom-10 left-20 h-28 w-28 rounded-full bg-lime-200/40 blur-2xl" />
        <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">External Inventory Hub</h1>
            <p className="mt-1 text-sm text-gray-600">
              {canManage
                ? 'Standalone external inventory for devices, purchasing, and stock movement.'
                : 'Browse available external inventory items.'}
            </p>
          </div>
          {canManage ? (
            <div className="flex gap-2">
              <Button variant="secondary" icon={RefreshCw} onClick={loadData}>
                Refresh
              </Button>
              <Button
                icon={PackagePlus}
                onClick={() => {
                  setEditingInventoryId('');
                  setItemForm(initialItemForm);
                  setItemImageFile(null);
                  setItemImagePreview('');
                  setShowAddItemModal(true);
                }}
              >
                Add Device Item
              </Button>
              <Button variant="secondary" icon={Factory} onClick={() => setShowCreatePOModal(true)}>
                New PO
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button variant="secondary" icon={RefreshCw} onClick={loadData}>
                Refresh
              </Button>
              <Button variant="secondary" icon={Factory} onClick={() => setShowCreatePOModal(true)}>
                New PO
              </Button>
            </div>
          )}
        </div>
      </div>

      {canManage && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card title="Items" icon={Boxes}>
          <p className="text-2xl font-bold text-gray-900">{dashboard?.total_skus ?? 0}</p>
        </Card>
        <Card title="Pending POs" icon={ClipboardCheck}>
          <p className="text-2xl font-bold text-amber-600">{dashboard?.pending_purchase_orders ?? 0}</p>
        </Card>
        </div>
      )}

      <Card title="Import Guide" subtitle="How to prepare the model sheet for upload">
        <div className="space-y-2 text-sm text-gray-700">
          <p>1. Click Download Model to get the CSV template (opens in Excel).</p>
          <p>2. Fill required columns: item_id, name, serial_number, device_type.</p>
          <p>3. For device_type = Others, custom_device_type is optional and MAC/NU ID can be blank.</p>
          <p>4. Keep the same header names and column order for smooth import.</p>
          <p>5. Save as CSV UTF-8 and upload using Import.</p>
        </div>
      </Card>

      <Card title="Inventory Items" subtitle="Standalone external device inventory" padding={false}>
        <DataTable
          columns={itemColumns}
          data={items}
          loading={loading}
          emptyMessage="No external inventory items yet"
          onRowClick={canManage ? (row) => setSelectedItem(row) : undefined}
          actions={canManage ? (
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
              <Button
                size="sm"
                variant="secondary"
                icon={Download}
                onClick={handleDownloadModel}
              >
                Download Model
              </Button>
            </>
          ) : null}
        />
      </Card>

      <Card title="Purchase Orders" subtitle="Order and receiving status" padding={false}>
          <DataTable columns={poColumns} data={purchaseOrders} loading={loading} emptyMessage="No purchase orders yet" />
      </Card>

      {canManage && (
        <Card title="Stock Movements" subtitle="Latest material flow" padding={false}>
          <DataTable columns={movementColumns} data={movements} loading={loading} emptyMessage="No stock movements yet" />
        </Card>
      )}

      {canManage && <Modal
        isOpen={showAddItemModal}
        onClose={() => {
          setShowAddItemModal(false);
          setEditingInventoryId('');
          setItemForm(initialItemForm);
          setItemImageFile(null);
          setItemImagePreview('');
        }}
        title={editingInventoryId ? 'Edit External Inventory Device Item' : 'Add External Inventory Device Item'}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setShowAddItemModal(false);
                setEditingInventoryId('');
                setItemForm(initialItemForm);
                setItemImageFile(null);
                setItemImagePreview('');
              }}
            >
              Cancel
            </Button>
            <Button loading={submitting} onClick={handleCreateItem}>
              {editingInventoryId ? 'Save Changes' : 'Create Item'}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm font-medium text-gray-700">Item ID</span>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              value={itemForm.item_id}
              onChange={(e) => setItemForm((p) => ({ ...p, item_id: e.target.value }))}
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium text-gray-700">Name</span>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              value={itemForm.name}
              onChange={(e) => setItemForm((p) => ({ ...p, name: e.target.value }))}
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium text-gray-700">Serial Number</span>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              value={itemForm.serial_number}
              onChange={(e) => setItemForm((p) => ({ ...p, serial_number: e.target.value }))}
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium text-gray-700">
              {idFieldLabel}
              {isIdRequired ? ' *' : ' (Optional)'}
            </span>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              value={itemForm.mac_id}
              onChange={(e) => setItemForm((p) => ({ ...p, mac_id: e.target.value }))}
              placeholder={isSetTopBoxType ? 'Enter NU ID' : 'Enter MAC ID'}
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
              {ITEM_TYPE_OPTIONS.map((typeOption) => (
                <option key={typeOption} value={typeOption}>
                  {typeOption}
                </option>
              ))}
            </select>
          </label>
          {isOtherType && (
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Custom Type (Optional)</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={itemForm.custom_device_type}
                onChange={(e) => setItemForm((p) => ({ ...p, custom_device_type: e.target.value }))}
                placeholder="Type custom device type"
              />
            </label>
          )}
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
          <label className="space-y-1 md:col-span-2">
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
          <label className="space-y-1 md:col-span-2">
            <span className="text-sm font-medium text-gray-700">Item Picture (Optional)</span>
            <input
              type="file"
              accept="image/*"
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setItemImageFile(file);
                setItemImagePreview(file ? URL.createObjectURL(file) : '');
              }}
            />
            {itemImagePreview && (
              <img
                src={itemImagePreview}
                alt="Item preview"
                className="mt-2 h-32 w-32 rounded-lg border border-gray-200 object-cover"
              />
            )}
          </label>
        </div>
      </Modal>}

      <Modal
        isOpen={!!selectedItem}
        onClose={() => setSelectedItem(null)}
        title={`Item Details ${selectedItem?.item_id ? `- ${selectedItem.item_id}` : ''}`}
        size="lg"
        footer={
          <div className="flex gap-2">
            {canManage && (
              <Button
                variant="secondary"
                onClick={() => {
                  if (!selectedItem) return;
                  setEditingInventoryId(selectedItem.inventory_id || '');
                  const selectedType = String(selectedItem.device_type || '').trim();
                  const normalizedSelectedType = selectedType.toLowerCase();
                  const isKnownType = ITEM_TYPE_OPTIONS.some((typeOption) => typeOption.toLowerCase() === normalizedSelectedType);
                  setItemForm({
                    item_id: selectedItem.item_id || '',
                    name: selectedItem.name || '',
                    serial_number: selectedItem.serial_number || '',
                    mac_id: selectedItem.mac_id || '',
                    device_type: isKnownType ? selectedType : 'Others',
                    custom_device_type: isKnownType ? '' : selectedType,
                    price: Number(selectedItem.price ?? 0),
                    unit: selectedItem.unit || 'pcs',
                    supplier_name: selectedItem.supplier_name || '',
                    location: selectedItem.location || '',
                    notes: selectedItem.notes || '',
                  });
                  setItemImageFile(null);
                  setItemImagePreview(selectedItem.image_url ? toAssetUrl(selectedItem.image_url) : '');
                  setSelectedItem(null);
                  setShowAddItemModal(true);
                }}
              >
                Edit Item
              </Button>
            )}
            <Button onClick={() => setSelectedItem(null)}>Close</Button>
          </div>
        }
      >
        {selectedItem && (
          <div className="space-y-4">
            <div className="flex flex-col gap-4 md:flex-row">
              <div className="md:w-1/3">
                {selectedItem.image_url ? (
                  <img
                    src={toAssetUrl(selectedItem.image_url)}
                    alt={selectedItem.name}
                    className="h-44 w-full rounded-lg border border-gray-200 object-cover"
                  />
                ) : (
                  <div className="flex h-44 w-full items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-gray-500">
                    <Eye className="mr-2 h-4 w-4" />
                    No picture
                  </div>
                )}
              </div>
              <div className="grid flex-1 grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p><span className="font-semibold text-gray-700">Inventory ID:</span> {selectedItem.inventory_id}</p>
                <p><span className="font-semibold text-gray-700">Item ID:</span> {selectedItem.item_id}</p>
                <p><span className="font-semibold text-gray-700">Name:</span> {selectedItem.name}</p>
                <p><span className="font-semibold text-gray-700">Type:</span> {toTypeLabel(selectedItem.device_type)}</p>
                <p><span className="font-semibold text-gray-700">Serial:</span> {selectedItem.serial_number || '-'}</p>
                <p>
                  <span className="font-semibold text-gray-700">
                    {(() => {
                      const normalizedType = String(selectedItem.device_type || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
                      return ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedType) ? 'NU ID' : 'MAC ID';
                    })()}:
                  </span>{' '}
                  {selectedItem.mac_id || '-'}
                </p>
                <p><span className="font-semibold text-gray-700">Price:</span> {formatCurrency(selectedItem.price || 0)}</p>
                <p><span className="font-semibold text-gray-700">Supplier:</span> {selectedItem.supplier_name || '-'}</p>
                <p><span className="font-semibold text-gray-700">Location:</span> {selectedItem.location || '-'}</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-700">Notes</p>
              <p className="mt-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {selectedItem.notes || 'No notes provided'}
              </p>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={showCreatePOModal}
        onClose={() => setShowCreatePOModal(false)}
        title="Create Purchase Order"
        size="xl"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowCreatePOModal(false)}>Cancel</Button>
            <Button loading={submitting} onClick={handleCreatePO}>Create PO</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Name</span>
              <input
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={poForm.name}
                onChange={(e) => setPoForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Netlink Procurement"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium text-gray-700">Expected Date</span>
              <input
                type="date"
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                value={poForm.expected_date}
                onChange={(e) => setPoForm((p) => ({ ...p, expected_date: e.target.value }))}
              />
              <p className="text-xs text-gray-500">Format shown as dd-mm-yyyy in UI locale.</p>
            </label>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-gray-800">PO Lines</h4>
              <Button size="sm" variant="outline" onClick={addPOLine}>Add Line</Button>
            </div>
            <p className="text-xs text-gray-500">
              Select one device item per line. Add multiple lines to purchase multiple devices in one order.
            </p>
            <div className="hidden rounded-lg border border-gray-200 bg-gray-50 p-2 text-xs font-semibold text-gray-600 md:grid md:grid-cols-12">
              <p className="md:col-span-10">Device Item</p>
              <p className="md:col-span-2">Action</p>
            </div>
            {poForm.lines.map((line, idx) => (
              <div key={idx} className="grid grid-cols-1 gap-2 rounded-lg border border-gray-200 p-3 md:grid-cols-12">
                <select
                  className="rounded-lg border border-gray-300 px-3 py-2 md:col-span-10"
                  value={line.item_inventory_id}
                  onChange={(e) => updatePOLine(idx, 'item_inventory_id', e.target.value)}
                >
                  <option value="">Select device item</option>
                  {items.map((item) => (
                    <option key={item.inventory_id} value={item.inventory_id}>
                      {item.item_id} | {item.name} | SN {item.serial_number} | {(() => {
                        const normalizedType = String(item.device_type || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
                        return ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedType) ? 'NU' : 'MAC';
                      })()} {item.mac_id}
                    </option>
                  ))}
                </select>
                <Button size="sm" variant="danger" className="md:col-span-2" onClick={() => removePOLine(idx)}>
                  Remove
                </Button>
              </div>
            ))}
          </div>
        </div>
      </Modal>

      {canConfirmPO && <Modal
        isOpen={!!receivingPO}
        onClose={() => setReceivingPO(null)}
        title={`Submit Purchase Order ${receivingPO?.po_id || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setReceivingPO(null)}>Cancel</Button>
            <Button loading={submitting} onClick={handleReceivePO}>Submit</Button>
          </>
        }
      >
        <div className="space-y-3">
          {receiptForm.lines.map((line, idx) => (
            <div key={idx} className="grid grid-cols-1 gap-2 rounded-lg border border-gray-200 p-3 md:grid-cols-1">
              <select
                className="rounded-lg border border-gray-300 px-3 py-2"
                value={line.item_inventory_id}
                onChange={(e) => {
                  const value = e.target.value;
                  setReceiptForm((prev) => {
                    const next = [...prev.lines];
                    next[idx] = { ...next[idx], item_inventory_id: value };
                    return { ...prev, lines: next };
                  });
                }}
              >
                {receivingPO?.lines?.map((poLine) => (
                  <option key={`${idx}-${poLine.item_inventory_id}`} value={poLine.item_inventory_id}>
                    {poLine.item_sku} - {poLine.item_name}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </Modal>}
    </div>
  );
};

export default ExternalInventory;

