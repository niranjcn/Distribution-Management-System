import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { approvalsAPI } from '../services/api';

export const approvalKeys = {
  all: ['approvals'],
  list: (params) => [...approvalKeys.all, 'list', params],
  detail: (id) => [...approvalKeys.all, 'detail', id],
};

export function useApprovals(params) {
  return useQuery({
    queryKey: approvalKeys.list(params),
    queryFn: () => approvalsAPI.getApprovals(params),
  });
}

export function useApproveRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }) => approvalsAPI.approveRequest(id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: approvalKeys.all }),
  });
}

export function useRejectRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rejectionReason, notes }) => approvalsAPI.rejectRequest(id, rejectionReason, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: approvalKeys.all }),
  });
}
