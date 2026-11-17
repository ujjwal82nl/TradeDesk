import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const usePositions = () =>
  useQuery({ queryKey: ['positions'], queryFn: () => api.get('/api/v1/positions').then(r => r.data) });

export const useOptionPositions = () =>
  useQuery({ queryKey: ['positions-options'], queryFn: () => api.get('/api/v1/positions/options').then(r => r.data) });

export const useGreeks = () =>
  useQuery({ queryKey: ['positions-greeks'], queryFn: () => api.get('/api/v1/positions/greeks').then(r => r.data) });

export const useSyncPositions = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/api/v1/positions/sync'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
};
