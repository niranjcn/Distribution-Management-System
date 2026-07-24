import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { distributionsAPI } from '../services/api';

export const distributionKeys = {
  all: ['distributions'],
  list: (params) => [...distributionKeys.all, 'list', params],
  detail: (id) => [...distributionKeys.all, 'detail', id],
};

export function useDistributions(params) {
  return useQuery({
    queryKey: distributionKeys.list(params),
    queryFn: () => distributionsAPI.getDistributions(params),
  });
}

export function useDistributionDetail(id) {
  return useQuery({
    queryKey: distributionKeys.detail(id),
    queryFn: () => distributionsAPI.getDistribution(id),
    enabled: !!id,
  });
}

export function useCreateDistribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => distributionsAPI.createDistribution(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: distributionKeys.all }),
  });
}

export function useUpdateDistributionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, notes }) => distributionsAPI.updateDistributionStatus(id, status, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: distributionKeys.all }),
  });
}

export function useCancelDistribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => distributionsAPI.cancelDistribution(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: distributionKeys.all }),
  });
}

export function useConfirmReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, received, notes }) => distributionsAPI.confirmReceipt(id, received, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: distributionKeys.all }),
  });
}

export function useConfirmDisputedReturn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }) => distributionsAPI.confirmDisputedReturn(id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: distributionKeys.all }),
  });
}
