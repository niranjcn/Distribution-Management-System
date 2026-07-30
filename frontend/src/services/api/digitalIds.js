import { apiRequest } from './client';

export const digitalIdsAPI = {
  create: async (data) => {
    const res = await apiRequest('/digital-ids', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res;
  },
  update: async (id, data) => {
    const res = await apiRequest(`/digital-ids/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return res;
  },
  delete: async (id) => {
    const res = await apiRequest(`/digital-ids/${id}`, {
      method: 'DELETE',
    });
    return res;
  },
};
