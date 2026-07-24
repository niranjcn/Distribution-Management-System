import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dashboardAPI } from '../services/api';

export const activityKeys = {
  all: ['activities'],
  list: (params) => [...activityKeys.all, 'list', params],
};

export function useActivities(params) {
  return useQuery({
    queryKey: activityKeys.list(params),
    queryFn: () => dashboardAPI.getActivities(params),
  });
}

export function invalidateActivities() {
  const qc = useQueryClient();
  return qc.invalidateQueries({ queryKey: activityKeys.all });
}
