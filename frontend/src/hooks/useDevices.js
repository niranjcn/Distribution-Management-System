import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { devicesAPI } from '../services/api';

export const deviceKeys = {
  all: ['devices'],
  overview: (params) => [...deviceKeys.all, 'overview', params],
  detail: (id) => [...deviceKeys.all, 'detail', id],
};

export function useMyDeviceOverview(params) {
  return useQuery({
    queryKey: deviceKeys.overview(params),
    queryFn: () => devicesAPI.getMyOverview(params),
    staleTime: params?.paginate ? 0 : 30 * 1000,
  });
}

export function useDeviceDetail(id) {
  return useQuery({
    queryKey: deviceKeys.detail(id),
    queryFn: () => devicesAPI.getDevice(id),
    enabled: !!id,
  });
}

export function useManagementHolderInsights() {
  return useQuery({
    queryKey: [...deviceKeys.all, 'holderInsights'],
    queryFn: () => devicesAPI.getManagementHolderInsights(),
    staleTime: 60 * 1000,
  });
}

export function useCreateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => devicesAPI.createDevice(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: deviceKeys.all }),
  });
}

export function useUpdateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => devicesAPI.updateDevice(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: deviceKeys.all }),
  });
}

export function useDeleteDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => devicesAPI.deleteDevice(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: deviceKeys.all }),
  });
}

export function useUpdateDeviceStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, notes }) => devicesAPI.updateDeviceStatus(id, status, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: deviceKeys.all }),
  });
}

export function useRequestDeviceEdit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, changes }) => devicesAPI.requestDeviceEdit(id, changes),
    onSuccess: () => qc.invalidateQueries({ queryKey: deviceKeys.all }),
  });
}
