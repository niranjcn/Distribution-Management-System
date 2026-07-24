import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { defectsAPI } from '../services/api';

export const defectKeys = {
  all: ['defects'],
  list: (params) => [...defectKeys.all, 'list', params],
  detail: (id) => [...defectKeys.all, 'detail', id],
};

export function useDefects(params) {
  return useQuery({
    queryKey: defectKeys.list(params),
    queryFn: () => defectsAPI.getDefects(params),
  });
}

export function useDefectDetail(id) {
  return useQuery({
    queryKey: defectKeys.detail(id),
    queryFn: () => defectsAPI.getDefect(id),
    enabled: !!id,
  });
}

export function useCreateDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => defectsAPI.createDefect(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}

export function useUpdateDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => defectsAPI.updateDefect(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}

export function useUpdateDefectStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, notes, extra }) => defectsAPI.updateDefectStatus(id, status, notes, extra),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}

export function useReplaceDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => defectsAPI.replaceDevice(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}

export function useConfirmReplacementReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }) => defectsAPI.confirmReplacementReceipt(id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}

export function useGetReplacements(params) {
  return useQuery({
    queryKey: [...defectKeys.all, 'replacements', params],
    queryFn: () => defectsAPI.getReplacements(params),
  });
}

export function useGetPendingReplacements(params) {
  return useQuery({
    queryKey: [...defectKeys.all, 'pendingReplacements', params],
    queryFn: () => defectsAPI.getPendingReplacements(params),
  });
}

export function useDeleteDefect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => defectsAPI.deleteDefect(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: defectKeys.all }),
  });
}
