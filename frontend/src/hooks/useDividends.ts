import { useQuery } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useDividends = () =>
  useQuery({ queryKey: ['dividends'], queryFn: () => api.get('/api/v1/dividends').then(r => r.data) });
