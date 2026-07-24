import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersAPI, adminUpdateCredentials } from '../services/api';

export const userKeys = {
  all: ['users'],
  list: (params) => [...userKeys.all, 'list', params],
  detail: (id) => [...userKeys.all, 'detail', id],
};

export function useUsers(params) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => usersAPI.getUsers(params),
  });
}

export function useUserDetail(id) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => usersAPI.getUser(id),
    enabled: !!id,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => usersAPI.createUser(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => usersAPI.updateUser(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => usersAPI.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useUpdateUserStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) => usersAPI.updateUserStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}
