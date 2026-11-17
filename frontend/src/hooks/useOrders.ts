import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useOrders = () =>
  useQuery({ queryKey: ['orders'], queryFn: () => api.get('/api/v1/orders').then(r => r.data) });

export const usePlaceOrder = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: any) => api.post('/api/v1/orders', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  });
};

export const useCancelOrder = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (orderId: number) => api.delete(`/api/v1/orders/${orderId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  });
};
