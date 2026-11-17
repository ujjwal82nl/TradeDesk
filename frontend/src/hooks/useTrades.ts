import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient as api } from '../api/client';

export const useTrades = (page = 1, pageSize = 50) =>
  useQuery({
    queryKey: ['trades', page, pageSize],
    queryFn: () => api.get(`/api/v1/trades?page=${page}&page_size=${pageSize}`).then(r => r.data),
  });

export const useUpdateTradeJournal = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: any }) => api.put(`/api/v1/trades/${id}/journal`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['trades'] }),
  });
};
