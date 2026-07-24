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
  Trash2,
  Upload,
  Download,
  Search,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { inventoryKeys } from '../hooks';

const initialItemForm = {
  item_id: '',
  name: '',
  serial_number: '',
  mac_id: '',
  identifier_type: '',
  identifier: '',
  device_type: '',
  custom_device_type: '',
  price: 0,
  unit: 'pcs',
  supplier_name: '',
  location: '',
  notes: '',
};

const ITEM_TYPE_OPTIONS = ['OTT Box', 'OLT', 'Remote', 'SB', 'Adapter', 'Others'];
const IDENTIFIER_TYPE_OPTIONS = ['NU ID', 'IMEI', 'Asset Tag', 'Serial Ref', 'Other'];

const normalizeType = (value) => String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
const isMacType = (value) => ['olt', 'adapter'].includes(normalizeType(value));

const toTypeLabel = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-_\s]+/g, '');
  return ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalized) ? 'SB' : (value || '-');
};

const defaultPOLine = { item_inventory_id: '' };

const TABLE_PAGE_SIZE = 10;
const TABLE_WINDOW_PAGES = 10;
const TABLE_WINDOW_SIZE = TABLE_PAGE_SIZE * TABLE_WINDOW_PAGES;
const EXPORT_PAGE_SIZE = 1000;

const ITEM_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'inventory_id', label: 'Inventory ID' },
  { value: 'item_id', label: 'Item ID' },
  { value: 'name', label: 'Name' },
  { value: 'serial_number', label: 'Serial Number' },
  { value: 'mac_id', label: 'MAC ID' },
  { value: 'identifier', label: 'Identifier' },
  { value: 'device_type', label: 'Type' },
  { value: 'supplier_name', label: 'Supplier' },
];

const PO_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'po_id', label: 'PO ID' },
  { value: 'supplier_name', label: 'Name' },
  { value: 'ordered_by_name', label: 'Placed By' },
  { value: 'status', label: 'Status' },
];

const MOVEMENT_SEARCH_BY_OPTIONS = [
  { value: 'all', label: 'All Fields' },
  { value: 'movement_id', label: 'Movement ID' },
  { value: 'item_sku', label: 'Item ID' },
  { value: 'item_name', label: 'Item' },
  { value: 'movement_type', label: 'Type' },
  { value: 'reference_type', label: 'Reference' },
  { value: 'reference_id', label: 'Ref ID' },
  { value: 'notes', label: 'Details' },
];

const ExternalInventory = () => {
  const { user } = useAuth();
  const { showToast } = useNotifications();
  const normalizedRole = String(user?.role || '').trim().toLowerCase();
  const canManage = ['super_admin', 'manager', 'pdic_staff', 'staff'].includes(normalizedRole);
  const canConfirmPO = canManage;

  const [dashboard, setDashboard] = useState(null);
  const [items, setItems] = useState([]);
  const [itemsTotalCount, setItemsTotalCount] = useState(0);
  const [itemsPage, setItemsPage] = useState(1);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [purchaseOrdersTotalCount, setPurchaseOrdersTotalCount] = useState(0);
  const [purchaseOrdersPage, setPurchaseOrdersPage] = useState(1);
  const [movements, setMovements] = useState([]);
  const [movementsTotalCount, setMovementsTotalCount] = useState(0);
  const [movementsPage, setMovementsPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [showCreatePOModal, setShowCreatePOModal] = useState(false);
  const [receivingPO, setReceivingPO] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [importingItems, setImportingItems] = useState(false);
  const [deletingInventoryId, setDeletingInventoryId] = useState('');
  const [downloadingReceiptPoId, setDownloadingReceiptPoId] = useState('');
  const importInputRef = useRef(null);

  const [itemForm, setItemForm] = useState(initialItemForm);
  const [editingInventoryId, setEditingInventoryId] = useState('');
  const [itemSearchBy, setItemSearchBy] = useState('all');
  const [itemSearchInput, setItemSearchInput] = useState('');
  const [appliedItemSearch, setAppliedItemSearch] = useState({ by: 'all', query: '' });
  const [poSearchBy, setPoSearchBy] = useState('all');
  const [poSearchInput, setPoSearchInput] = useState('');
  const [appliedPOSearch, setAppliedPOSearch] = useState({ by: 'all', query: '' });
  const [movementSearchBy, setMovementSearchBy] = useState('all');
  const [movementSearchInput, setMovementSearchInput] = useState('');
  const [appliedMovementSearch, setAppliedMovementSearch] = useState({ by: 'all', query: '' });
  const itemsLoadedWindowRef = useRef(0);
  const itemsLoadingWindowsRef = useRef(new Set());
  const itemsQueryVersionRef = useRef(0);
  const poLoadedWindowRef = useRef(0);
  const poLoadingWindowsRef = useRef(new Set());
  const poQueryVersionRef = useRef(0);
  const movementsLoadedWindowRef = useRef(0);
  const movementsLoadingWindowsRef = useRef(new Set());
  const movementsQueryVersionRef = useRef(0);

  const normalizedItemType = normalizeType(itemForm.device_type);
  const isSetTopBoxType = ['settopbox', 'setupbox', 'sb', 'stb'].includes(normalizedItemType);
  const isMacIdType = isMacType(itemForm.device_type);
  const isOtherType = normalizedItemType === 'others';
  const idFieldLabel = isSetTopBoxType ? 'NU ID' : 'MAC ID';
  const identifierRequired = !isMacIdType;

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

  const buildItemsParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      page: windowPage,
      page_size: pageSize,
      status: 'active',
    };
    if (appliedItemSearch.query) {
      params.search = appliedItemSearch.query;
      if (appliedItemSearch.by && appliedItemSearch.by !== 'all') {
        params.search_by = appliedItemSearch.by;
      }
    }
    return params;
  };

  const buildPOParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      page: windowPage,
      page_size: pageSize,
    };
    if (appliedPOSearch.query) {
      params.search = appliedPOSearch.query;
      if (appliedPOSearch.by && appliedPOSearch.by !== 'all') {
        params.search_by = appliedPOSearch.by;
      }
    }
    return params;
  };

  const buildMovementParams = (windowPage, pageSize = TABLE_WINDOW_SIZE) => {
    const params = {
      page: windowPage,
      page_size: pageSize,
    };
    if (appliedMovementSearch.query) {
      params.search = appliedMovementSearch.query;
      if (appliedMovementSearch.by && appliedMovementSearch.by !== 'all') {
        params.search_by = appliedMovementSearch.by;
      }
    }
    return params;
  };

  const getItemsExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await externalInventoryAPI.getItems(buildItemsParams(page, EXPORT_PAGE_SIZE));
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

  const getPOExportRows = async () => {
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await externalInventoryAPI.getPurchaseOrders(buildPOParams(page, EXPORT_PAGE_SIZE));
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

  const getMovementsExportRows = async () => {
    if (!canManage) return [];
    let page = 1;
    let collected = [];
    let total = 0;

    while (true) {
      const response = await externalInventoryAPI.getMovements(buildMovementParams(page, EXPORT_PAGE_SIZE));
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

  const loadItemsWindow = async (windowPage, { reset = false } = {}) => {
    if (itemsLoadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = itemsQueryVersionRef.current;
    itemsLoadingWindowsRef.current.add(windowPage);
    try {
      const response = await externalInventoryAPI.getItems(buildItemsParams(windowPage));
      if (queryVersion !== itemsQueryVersionRef.current) return;
      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);
      setItems((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.inventory_id || row?.id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setItemsTotalCount(total);
      itemsLoadedWindowRef.current = Math.max(itemsLoadedWindowRef.current, windowPage);
    } finally {
      itemsLoadingWindowsRef.current.delete(windowPage);
    }
  };

  const loadPOWindow = async (windowPage, { reset = false } = {}) => {
    if (poLoadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = poQueryVersionRef.current;
    poLoadingWindowsRef.current.add(windowPage);
    try {
      const response = await externalInventoryAPI.getPurchaseOrders(buildPOParams(windowPage));
      if (queryVersion !== poQueryVersionRef.current) return;
      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);
      setPurchaseOrders((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.po_id || row?.id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setPurchaseOrdersTotalCount(total);
      poLoadedWindowRef.current = Math.max(poLoadedWindowRef.current, windowPage);
    } finally {
      poLoadingWindowsRef.current.delete(windowPage);
    }
  };

  const loadMovementWindow = async (windowPage, { reset = false } = {}) => {
    if (!canManage) return;
    if (movementsLoadingWindowsRef.current.has(windowPage)) return;
    const queryVersion = movementsQueryVersionRef.current;
    movementsLoadingWindowsRef.current.add(windowPage);
    try {
      const response = await externalInventoryAPI.getMovements(buildMovementParams(windowPage));
      if (queryVersion !== movementsQueryVersionRef.current) return;
      const rows = Array.isArray(response?.data) ? response.data : [];
      const total = Number(response?.pagination?.total || rows.length);
      setMovements((prev) => {
        const merged = reset ? rows : [...prev, ...rows];
        const unique = [];
        const seen = new Set();
        for (const row of merged) {
          const rowId = String(row?.movement_id || row?.id || '');
          if (!rowId || seen.has(rowId)) continue;
          seen.add(rowId);
          unique.push(row);
        }
        return unique;
      });
      setMovementsTotalCount(total);
      movementsLoadedWindowRef.current = Math.max(movementsLoadedWindowRef.current, windowPage);
    } finally {
      movementsLoadingWindowsRef.current.delete(windowPage);
    }
  };

  const resetAndLoadItems = async () => {
    itemsQueryVersionRef.current += 1;
    itemsLoadedWindowRef.current = 0;
    itemsLoadingWindowsRef.current = new Set();
    setItems([]);
    setItemsTotalCount(0);
    setItemsPage(1);
    await loadItemsWindow(1, { reset: true });
  };

  const resetAndLoadPOs = async () => {
    poQueryVersionRef.current += 1;
    poLoadedWindowRef.current = 0;
    poLoadingWindowsRef.current = new Set();
    setPurchaseOrders([]);
    setPurchaseOrdersTotalCount(0);
    setPurchaseOrdersPage(1);
    await loadPOWindow(1, { reset: true });
  };

  const resetAndLoadMovements = async () => {
    if (!canManage) {
      setMovements([]);
      setMovementsTotalCount(0);
      setMovementsPage(1);
      return;
    }
    movementsQueryVersionRef.current += 1;
    movementsLoadedWindowRef.current = 0;
    movementsLoadingWindowsRef.current = new Set();
    setMovements([]);
    setMovementsTotalCount(0);
    setMovementsPage(1);
    await loadMovementWindow(1, { reset: true });
  };

  const loadData = async () => {
    try {
      setLoading(true);
      if (canManage) {
        const [dashboardRes] = await Promise.all([
          externalInventoryAPI.getDashboard(),
        ]);
        setDashboard(dashboardRes.data || null);
      } else {
        setDashboard(null);
      }
      await Promise.all([resetAndLoadItems(), resetAndLoadPOs(), resetAndLoadMovements()]);
    } catch (error) {
      showToast(error.message || 'Failed to load external inventory data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [canManage, appliedItemSearch, appliedPOSearch, appliedMovementSearch]);

  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      loadData();
    };
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);

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
    const normalizedIdentifierType = String(itemForm.identifier_type || '').trim();
    const normalizedIdentifier = String(itemForm.identifier || '').trim();
    if (
      !itemForm.item_id.trim() ||
      !itemForm.name.trim() ||
      !itemForm.serial_number.trim() ||
      !itemForm.device_type.trim()
    ) {
      showToast('Item ID, name, serial number and type are required', 'error');
      return;
    }

    if (isMacIdType && !normalizedMacOrNuId) {
      showToast(`${idFieldLabel} is required for OLT and Adapter`, 'error');
      return;
    }

    if (identifierRequired && (!normalizedIdentifierType || !normalizedIdentifier)) {
      showToast('Identifier Type and Identifier are required for non-OLT/Adapter types', 'error');
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        ...itemForm,
        mac_id: isMacIdType ? normalizedMacOrNuId : '',
        identifier_type: isMacIdType ? '' : normalizedIdentifierType,
        identifier: isMacIdType ? '' : normalizedIdentifier,
        price: Number(itemForm.price),
      };

      const created = editingInventoryId
        ? await externalInventoryAPI.updateItem(editingInventoryId, payload)
        : await externalInventoryAPI.createItem(payload);

      showToast(editingInventoryId ? 'Inventory item updated' : 'Inventory device item created', 'success');
      setShowAddItemModal(false);
      setItemForm(initialItemForm);
      setEditingInventoryId('');
      // Data refetch is handled automatically by appDataMutation event
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
      // Data refetch is handled automatically by appDataMutation event
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
      'identifier_type',
      'identifier',
      'device_type',
      'custom_device_type',
      'price',
      'supplier_name',
      'location',
      'notes',
    ];

    const sampleRows = [
      {
        item_id: 'ITEM-EX-1001',
        name: 'Sample OLT Device',
        serial_number: 'SN-EX-1001',
        mac_id: 'MAC-EX-1001',
        identifier_type: '',
        identifier: '',
        device_type: 'OLT',
        custom_device_type: '',
        price: '2799',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse A',
        notes: 'For OLT/Adapter, fill mac_id',
      },
      {
        item_id: 'ITEM-EX-1002',
        name: 'Sample Remote Device',
        serial_number: 'SN-EX-1002',
        mac_id: '',
        identifier_type: 'NU ID',
        identifier: 'NU-EX-1002',
        device_type: 'Remote',
        custom_device_type: '',
        price: '1599',
        supplier_name: 'Sample Supplier',
        location: 'Warehouse B',
        notes: 'For non-OLT/Adapter, fill identifier_type and identifier',
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
      // Data refetch is handled automatically by appDataMutation event
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

  const startEditItem = (item) => {
    if (!item) return;
    setEditingInventoryId(item.inventory_id || '');
    const selectedType = String(item.device_type || '').trim();
    const normalizedSelectedType = selectedType.toLowerCase();
    const isKnownType = ITEM_TYPE_OPTIONS.some((typeOption) => typeOption.toLowerCase() === normalizedSelectedType);
    const rowUsesMac = isMacType(selectedType);
    setItemForm({
      item_id: item.item_id || '',
      name: item.name || '',
      serial_number: item.serial_number || '',
      mac_id: rowUsesMac ? (item.mac_id || '') : '',
      identifier_type: rowUsesMac ? '' : (item.identifier_type || ''),
      identifier: rowUsesMac ? '' : (item.identifier || ''),
      device_type: isKnownType ? selectedType : 'Others',
      custom_device_type: isKnownType ? '' : selectedType,
      price: Number(item.price ?? 0),
      unit: item.unit || 'pcs',
      supplier_name: item.supplier_name || '',
      location: item.location || '',
      notes: item.notes || '',
    });
    setSelectedItem(null);
    setShowAddItemModal(true);
  };

  const handleDeleteItem = async (item) => {
    if (!item?.inventory_id) {
      showToast('Item reference is missing', 'error');
      return;
    }

    const serialRef = item.serial_number || item.inventory_id;
    const confirmed = window.confirm(`Delete external inventory item ${serialRef}?`);
    if (!confirmed) return;

    try {
      setDeletingInventoryId(item.inventory_id);
      await externalInventoryAPI.deleteItem(item.inventory_id);
      showToast('External inventory item deleted', 'success');

      if (selectedItem?.inventory_id === item.inventory_id) {
        setSelectedItem(null);
      }

      // Data refetch is handled automatically by appDataMutation event
    } catch (error) {
      showToast(error.message || 'Failed to delete item', 'error');
    } finally {
      setDeletingInventoryId('');
    }
  };

  const managementItemColumns = [
    { key: 'inventory_id', label: 'Inventory ID' },
    { key: 'item_id', label: 'Item ID' },
    { key: 'name', label: 'Name' },
    { key: 'serial_number', label: 'Serial Number' },
    {
      key: 'mac_id',
      label: 'MAC ID',
      render: (value, row) => (isMacType(row?.device_type) ? (value || '-') : '-'),
    },
    {
      key: 'identifier_type',
      label: 'Identifier Type',
      render: (value, row) => (!isMacType(row?.device_type) ? (value || '-') : '-'),
    },
    {
      key: 'identifier',
      label: 'Identifier',
      render: (value, row) => (!isMacType(row?.device_type) ? (value || '-') : '-'),
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
    {
      key: 'actions',
      label: 'Actions',
      sortable: false,
      render: (_, row) => (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={(event) => {
              event.stopPropagation();
              startEditItem(row);
            }}
          >
            Edit
          </Button>
          <Button
            size="sm"
            variant="danger"
            icon={Trash2}
            loading={deletingInventoryId === row.inventory_id}
            onClick={(event) => {
              event.stopPropagation();
              handleDeleteItem(row);
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  const viewerItemColumns = [
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

  const handleItemSearchSubmit = () => {
    setAppliedItemSearch({ by: itemSearchBy, query: itemSearchInput.trim() });
  };

  const handleItemSearchReset = () => {
    setItemSearchBy('all');
    setItemSearchInput('');
    setAppliedItemSearch({ by: 'all', query: '' });
  };

  const handlePOSearchSubmit = () => {
    setAppliedPOSearch({ by: poSearchBy, query: poSearchInput.trim() });
  };

  const handlePOSearchReset = () => {
    setPOSearchBy('all');
    setPOSearchInput('');
    setAppliedPOSearch({ by: 'all', query: '' });
  };

  const handleMovementSearchSubmit = () => {
    setAppliedMovementSearch({ by: movementSearchBy, query: movementSearchInput.trim() });
  };

  const handleMovementSearchReset = () => {
    setMovementSearchBy('all');
    setMovementSearchInput('');
    setAppliedMovementSearch({ by: 'all', query: '' });
  };

  const handleItemsPageChange = async (nextPage) => {
    setItemsPage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(items.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && items.length < itemsTotalCount;
    if (needsNextWindow) {
      await loadItemsWindow(itemsLoadedWindowRef.current + 1);
    }
  };

  const handlePOPageChange = async (nextPage) => {
    setPurchaseOrdersPage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(purchaseOrders.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && purchaseOrders.length < purchaseOrdersTotalCount;
    if (needsNextWindow) {
      await loadPOWindow(poLoadedWindowRef.current + 1);
    }
  };

  const handleMovementsPageChange = async (nextPage) => {
    setMovementsPage(nextPage);
    const loadedPages = Math.max(1, Math.ceil(movements.length / TABLE_PAGE_SIZE));
    const needsNextWindow = nextPage >= loadedPages && movements.length < movementsTotalCount;
    if (needsNextWindow) {
      await loadMovementWindow(movementsLoadedWindowRef.current + 1);
    }
  };

  return (
    <div className="space-y-6">
      <div className="external-inventory-hero relative overflow-hidden rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 via-amber-50 to-lime-50 p-6">
        <div className="absolute -top-8 -right-8 h-32 w-32 rounded-full bg-orange-200/40 blur-2xl" />
        <div className="absolute -bottom-10 left-20 h-28 w-28 rounded-full bg-lime-200/40 blur-2xl" />
        <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">External Inventory Hub</h1>
            <p className="mt-1 text-sm text-gray-600">
              {canManage
                ? 'Standalone external inventory for devices, purchasing, and stock movement.'
                : 'Browse available external inventory items.'}
            </p>
          </div>
          {canManage ? (
            <div className="flex flex-col sm:flex-row gap-2">
              <Button variant="secondary" icon={RefreshCw} onClick={loadData} className="w-full sm:w-auto justify-center">
                Refresh
              </Button>
              <Button
                icon={PackagePlus}
                onClick={() => {
                  setEditingInventoryId('');
                  setItemForm(initialItemForm);
                  setShowAddItemModal(true);
                }}
                className="w-full sm:w-auto justify-center"
              >
                Add Device Item
              </Button>
              <Button variant="secondary" icon={Factory} onClick={() => setShowCreatePOModal(true)} className="w-full sm:w-auto justify-center">
                New PO
              </Button>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row gap-2">
              <Button variant="secondary" icon={RefreshCw} onClick={loadData} className="w-full sm:w-auto justify-center">
                Refresh
              </Button>
              <Button variant="secondary" icon={Factory} onClick={() => setShowCreatePOModal(true)} className="w-full sm:w-auto justify-center">
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

      {canManage && (
        <Card title="Import Guide" subtitle="How to prepare the model sheet for upload">
          <div className="space-y-2 text-sm text-gray-700">
            <p>1. Click Download Model to get the CSV template (opens in Excel).</p>
            <p>2. Fill required columns: item_id, name, serial_number, device_type.</p>
            <p>3. For OLT and Adapter, MAC ID is required.</p>
            <p>4. For all other types, identifier_type and identifier are required.</p>
            <p>5. Keep the same header names and column order for smooth import.</p>
            <p>6. Save as CSV UTF-8 and upload using Import.</p>
          </div>
        </Card>
      )}

      <Card className="!p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Search Inventory Items</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-3">
            <select
              value={itemSearchBy}
              onChange={(e) => setItemSearchBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {ITEM_SEARCH_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-6">
            <input
              type="text"
              value={itemSearchInput}
              onChange={(e) => setItemSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleItemSearchSubmit();
                }
              }}
              placeholder="Enter pattern to search..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
          <div className="md:col-span-3 flex gap-2">
            <Button onClick={handleItemSearchSubmit} className="w-full">Search</Button>
            <Button variant="secondary" onClick={handleItemSearchReset}>Reset</Button>
          </div>
        </div>
      </Card>

      <Card title="Inventory Items" subtitle="Standalone external device inventory" padding={false}>
        <DataTable
          columns={itemColumns}
          data={items}
          loading={loading}
          searchable={false}
          pageSize={TABLE_PAGE_SIZE}
          totalItems={itemsTotalCount || items.length}
          currentPage={itemsPage}
          onPageChange={handleItemsPageChange}
          getExportRows={getItemsExportRows}
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

      <Card className="!p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Search Purchase Orders</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-3">
            <select
              value={poSearchBy}
              onChange={(e) => setPOSearchBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {PO_SEARCH_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-6">
            <input
              type="text"
              value={poSearchInput}
              onChange={(e) => setPOSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handlePOSearchSubmit();
                }
              }}
              placeholder="Enter pattern to search..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
          <div className="md:col-span-3 flex gap-2">
            <Button onClick={handlePOSearchSubmit} className="w-full">Search</Button>
            <Button variant="secondary" onClick={handlePOSearchReset}>Reset</Button>
          </div>
        </div>
      </Card>

      <Card title="Purchase Orders" subtitle="Order and receiving status" padding={false}>
          <DataTable
            columns={poColumns}
            data={purchaseOrders}
            loading={loading}
            searchable={false}
            pageSize={TABLE_PAGE_SIZE}
            totalItems={purchaseOrdersTotalCount || purchaseOrders.length}
            currentPage={purchaseOrdersPage}
            onPageChange={handlePOPageChange}
            getExportRows={getPOExportRows}
            emptyMessage="No purchase orders yet"
          />
      </Card>

      {canManage && (
        <>
          <Card className="!p-4">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-800">Search Stock Movements</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
              <div className="md:col-span-3">
                <select
                  value={movementSearchBy}
                  onChange={(e) => setMovementSearchBy(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  {MOVEMENT_SEARCH_BY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-6">
                <input
                  type="text"
                  value={movementSearchInput}
                  onChange={(e) => setMovementSearchInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleMovementSearchSubmit();
                    }
                  }}
                  placeholder="Enter pattern to search..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div className="md:col-span-3 flex gap-2">
                <Button onClick={handleMovementSearchSubmit} className="w-full">Search</Button>
                <Button variant="secondary" onClick={handleMovementSearchReset}>Reset</Button>
              </div>
            </div>
          </Card>

          <Card title="Stock Movements" subtitle="Latest material flow" padding={false}>
            <DataTable
              columns={movementColumns}
              data={movements}
              loading={loading}
              searchable={false}
              pageSize={TABLE_PAGE_SIZE}
              totalItems={movementsTotalCount || movements.length}
              currentPage={movementsPage}
              onPageChange={handleMovementsPageChange}
              getExportRows={getMovementsExportRows}
              emptyMessage="No stock movements yet"
            />
          </Card>
        </>
      )}

      {canManage && <Modal
        isOpen={showAddItemModal}
        onClose={() => {
          setShowAddItemModal(false);
          setEditingInventoryId('');
          setItemForm(initialItemForm);
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
              {isMacIdType ? ' *' : ' (Not used)'}
            </span>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              value={itemForm.mac_id}
              onChange={(e) => setItemForm((p) => ({ ...p, mac_id: e.target.value }))}
              placeholder={isSetTopBoxType ? 'Enter NU ID' : 'Enter MAC ID'}
              disabled={!isMacIdType}
            />
          </label>
          {!isMacIdType && (
            <>
              <label className="space-y-1">
                <span className="text-sm font-medium text-gray-700">Identifier Type *</span>
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                  value={itemForm.identifier_type}
                  onChange={(e) => setItemForm((p) => ({ ...p, identifier_type: e.target.value }))}
                >
                  <option value="">Select identifier type</option>
                  {IDENTIFIER_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-sm font-medium text-gray-700">Identifier *</span>
                <input
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                  value={itemForm.identifier}
                  onChange={(e) => setItemForm((p) => ({ ...p, identifier: e.target.value }))}
                  placeholder="Enter identifier"
                />
              </label>
            </>
          )}
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
                  startEditItem(selectedItem);
                }}
              >
                Edit Item
              </Button>
            )}
            {canManage && (
              <Button
                variant="danger"
                icon={Trash2}
                loading={deletingInventoryId === selectedItem?.inventory_id}
                onClick={() => handleDeleteItem(selectedItem)}
              >
                Delete Item
              </Button>
            )}
            <Button onClick={() => setSelectedItem(null)}>Close</Button>
          </div>
        }
      >
        {selectedItem && (
          <div className="space-y-4">
            <div className="flex flex-col gap-4">
              <div className="grid flex-1 grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p><span className="font-semibold text-gray-700">Inventory ID:</span> {selectedItem.inventory_id}</p>
                <p><span className="font-semibold text-gray-700">Item ID:</span> {selectedItem.item_id}</p>
                <p><span className="font-semibold text-gray-700">Name:</span> {selectedItem.name}</p>
                <p><span className="font-semibold text-gray-700">Type:</span> {toTypeLabel(selectedItem.device_type)}</p>
                <p><span className="font-semibold text-gray-700">Serial:</span> {selectedItem.serial_number || '-'}</p>
                <p><span className="font-semibold text-gray-700">MAC ID:</span> {isMacType(selectedItem.device_type) ? (selectedItem.mac_id || '-') : '-'}</p>
                <p><span className="font-semibold text-gray-700">Identifier Type:</span> {!isMacType(selectedItem.device_type) ? (selectedItem.identifier_type || '-') : '-'}</p>
                <p><span className="font-semibold text-gray-700">Identifier:</span> {!isMacType(selectedItem.device_type) ? (selectedItem.identifier || '-') : '-'}</p>
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
                      {item.item_id} | {item.name} | SN {item.serial_number} | {isMacType(item.device_type)
                        ? `MAC ${item.mac_id || '-'}`
                        : `${item.identifier_type || 'Identifier'} ${item.identifier || '-'}`}
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

