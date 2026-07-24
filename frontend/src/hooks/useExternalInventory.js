import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { externalInventoryAPI } from '../services/api';

export const inventoryKeys = {
  all: ['externalInventory'],
  items: (params) => [...inventoryKeys.all, 'items', params],
  dashboard: () => [...inventoryKeys.all, 'dashboard'],
  purchaseOrders: (params) => [...inventoryKeys.all, 'purchaseOrders', params],
  receipts: (params) => [...inventoryKeys.all, 'receipts', params],
  movements: (params) => [...inventoryKeys.all, 'movements', params],
};

export function useInventoryItems(params) {
  return useQuery({
    queryKey: inventoryKeys.items(params),
    queryFn: () => externalInventoryAPI.getItems(params),
  });
}

export function useInventoryDashboard() {
  return useQuery({
    queryKey: inventoryKeys.dashboard(),
    queryFn: () => externalInventoryAPI.getDashboard(),
    staleTime: 30 * 1000,
  });
}

export function useCreateInventoryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => externalInventoryAPI.createItem(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useUpdateInventoryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => externalInventoryAPI.updateItem(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useDeleteInventoryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => externalInventoryAPI.deleteItem(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useCreateAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => externalInventoryAPI.createAdjustment(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function usePurchaseOrders(params) {
  return useQuery({
    queryKey: inventoryKeys.purchaseOrders(params),
    queryFn: () => externalInventoryAPI.getPurchaseOrders(params),
  });
}

export function useCreatePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => externalInventoryAPI.createPurchaseOrder(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useReceivePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => externalInventoryAPI.receivePurchaseOrder(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useReceipts(params) {
  return useQuery({
    queryKey: inventoryKeys.receipts(params),
    queryFn: () => externalInventoryAPI.getReceipts(params),
  });
}

export function useMovements(params) {
  return useQuery({
    queryKey: inventoryKeys.movements(params),
    queryFn: () => externalInventoryAPI.getMovements(params),
  });
}
