import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { externalInventoryAPI } from '../services/api';

export const inventoryKeys = {
  all: ['externalInventory'],
  items: (params) => [...inventoryKeys.all, 'items', params],
  distributions: (params) => [...inventoryKeys.all, 'distributions', params],
};

export function useInventoryItems(params) {
  return useQuery({
    queryKey: inventoryKeys.items(params),
    queryFn: () => externalInventoryAPI.getItems(params),
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

export function useDistributeInventoryItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => externalInventoryAPI.distributeItem(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useBulkDistributeInventoryItems() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => externalInventoryAPI.bulkDistributeItems(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
}

export function useExternalDistributions(params) {
  return useQuery({
    queryKey: inventoryKeys.distributions(params),
    queryFn: () => externalInventoryAPI.getDistributions(params),
  });
}