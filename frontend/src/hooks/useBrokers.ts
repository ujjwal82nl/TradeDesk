import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useBrokerAccounts = () =>
  useQuery({ queryKey: ['broker-accounts'], queryFn: () => api.get('/api/v1/brokers/accounts').then(r => r.data) });

export const useBrokerProviders = () =>
  useQuery({ queryKey: ['broker-providers'], queryFn: () => api.get('/api/v1/brokers').then(r => r.data) });

export const useConnectBroker = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: any) => api.post('/api/v1/brokers/accounts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broker-accounts'] }),
  });
};

export const useDisconnectBroker = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/v1/brokers/accounts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broker-accounts'] }),
  });
};

export const useSyncBroker = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post(`/api/v1/brokers/accounts/${id}/sync`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broker-accounts'] }),
  });
};
