import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useHoldings = () =>
  useQuery({ queryKey: ['holdings'], queryFn: () => api.get('/api/v1/holdings').then(r => r.data) });

export const useMergedHoldings = () =>
  useQuery({ queryKey: ['holdings-merged'], queryFn: () => api.get('/api/v1/holdings/merged').then(r => r.data) });

export const useSyncHoldings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/api/v1/holdings/sync'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['holdings'] }),
  });
};
