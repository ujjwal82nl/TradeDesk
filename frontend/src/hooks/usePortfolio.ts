import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const usePortfolioSummary = () =>
  useQuery({ queryKey: ['portfolio-summary'], queryFn: () => api.get('/api/v1/portfolio/summary').then(r => r.data) });

export const useBrokerAllocation = () =>
  useQuery({ queryKey: ['broker-allocation'], queryFn: () => api.get('/api/v1/portfolio/broker-allocation').then(r => r.data) });

export const useAssetAllocation = () =>
  useQuery({ queryKey: ['asset-allocation'], queryFn: () => api.get('/api/v1/portfolio/asset-allocation').then(r => r.data) });

export const usePortfolioSnapshots = (dateRange?: { from?: string; to?: string }) =>
  useQuery({
    queryKey: ['portfolio-snapshots', dateRange],
    queryFn: () => {
      const params = new URLSearchParams();
      if (dateRange?.from) params.set('date_from', dateRange.from);
      if (dateRange?.to)   params.set('date_to',   dateRange.to);
      return api.get(`/api/v1/portfolio/snapshots?${params}`).then(r => r.data);
    },
  });
