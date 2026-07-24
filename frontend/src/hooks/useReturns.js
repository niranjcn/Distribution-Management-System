import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { returnsAPI } from '../services/api';

export const returnKeys = {
  all: ['returns'],
  list: (params) => [...returnKeys.all, 'list', params],
  detail: (id) => [...returnKeys.all, 'detail', id],
};

export function useReturns(params) {
  return useQuery({
    queryKey: returnKeys.list(params),
    queryFn: () => returnsAPI.getReturns(params),
  });
}

export function useReturnDetail(id) {
  return useQuery({
    queryKey: returnKeys.detail(id),
    queryFn: () => returnsAPI.getReturn(id),
    enabled: !!id,
  });
}

export function useCreateReturn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => returnsAPI.createReturn(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: returnKeys.all }),
  });
}

export function useUpdateReturnStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, notes, extra }) => returnsAPI.updateReturnStatus(id, status, notes, extra),
    onSuccess: () => qc.invalidateQueries({ queryKey: returnKeys.all }),
  });
}

export function useCancelReturn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => returnsAPI.cancelReturn(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: returnKeys.all }),
  });
}
