import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useMargin = () =>
  useQuery({ queryKey: ['margin'], queryFn: () => api.get('/api/v1/margin').then(r => r.data) });

export const useMarginHistory = (days = 30) =>
  useQuery({
    queryKey: ['margin-history', days],
    queryFn: () => api.get(`/api/v1/margin/history?days=${days}`).then(r => r.data),
  });

export const useSyncMargin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/api/v1/margin/sync'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['margin'] }),
  });
};
