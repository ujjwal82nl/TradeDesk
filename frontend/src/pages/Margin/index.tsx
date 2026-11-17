import React from 'react';
import { Box, Typography, Grid, LinearProgress, Button } from '@mui/material';
import SyncIcon from '@mui/icons-material/Sync';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import StatCard   from '../../components/common/StatCard';
import BrokerChip from '../../components/common/BrokerChip';
import { formatCurrency } from '../../utils/formatters';

const cols: GridColDef[] = [
  { field: 'broker_name',      headerName: 'Broker',        width: 200, renderCell: p => <BrokerChip broker={p.value} label={p.value} /> },
  { field: 'available_margin', headerName: 'Available',     width: 140, renderCell: p => formatCurrency(p.value, true) },
  { field: 'used_margin',      headerName: 'Used',          width: 130, renderCell: p => formatCurrency(p.value, true) },
  { field: 'span_margin',      headerName: 'SPAN',          width: 120, renderCell: p => formatCurrency(p.value, true) },
  { field: 'exposure_margin',  headerName: 'Exposure',      width: 120, renderCell: p => formatCurrency(p.value, true) },
  { field: 'collateral',       headerName: 'Collateral',    width: 140, renderCell: p => formatCurrency(p.value, true) },
  { field: 'cash_balance',     headerName: 'Cash',          width: 140, renderCell: p => formatCurrency(p.value, true) },
  { field: 'utilization',      headerName: 'Utilization %', width: 160,
    renderCell: p => (
      <Box sx={{ width: '100%', px: 1 }}>
        <LinearProgress variant="determinate" value={Math.min(p.value ?? 0, 100)} color={p.value > 80 ? 'error' : p.value > 60 ? 'warning' : 'success'} sx={{ height: 8, borderRadius: 4 }} />
        <Typography variant="caption">{(p.value ?? 0).toFixed(1)}%</Typography>
      </Box>
    ),
  },
];

export default function Margin() {
  const queryClient = useQueryClient();

  const { data: summary, isLoading, refetch } = useQuery({
    queryKey: ['margin'],
    queryFn: () => api.get('/margin').then(r => r.data),
  });

  const { data: history } = useQuery({
    queryKey: ['margin-history'],
    queryFn: () => api.get('/margin/history?days=30').then(r => r.data ?? []),
  });

  const syncMutation = useMutation({
    mutationFn: () => api.post('/margin/sync').then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['margin'] });
      queryClient.invalidateQueries({ queryKey: ['margin-history'] });
    },
  });

  const brokers = summary?.brokers ?? [];
  const rows = brokers.map((b: any, i: number) => ({
    ...b, id: i,
    utilization: b.used_margin && b.total_balance ? (b.used_margin / b.total_balance * 100) : 0,
  }));

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>Margin Dashboard</Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<SyncIcon />}
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending || isLoading}
          sx={{ borderRadius: 2, textTransform: 'none' }}
        >
          {syncMutation.isPending ? 'Syncing...' : 'Sync from Brokers'}
        </Button>
      </Box>

      <Grid container spacing={2} mb={3}>
        {[
          { title: 'Total Available',  value: summary?.total_available  ?? 0 },
          { title: 'Total Used',       value: summary?.total_used       ?? 0 },
          { title: 'Total Collateral', value: summary?.total_collateral ?? 0 },
          { title: 'Total Cash',       value: summary?.total_cash       ?? 0 },
        ].map(c => <Grid item xs={6} sm={3} key={c.title}><StatCard title={c.title} value={c.value} isCurrency compact isLoading={isLoading} /></Grid>)}
      </Grid>

      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider', mb: 3 }}>
        <DataGrid rows={rows} columns={cols} loading={isLoading || syncMutation.isPending} autoHeight disableRowSelectionOnClick pageSizeOptions={[10]} />
      </Box>

      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle1" fontWeight={700} mb={2}>30-Day Margin Usage</Typography>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={Array.isArray(history) ? history : []}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} tickFormatter={v => new Date(v).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} />
            <YAxis tickFormatter={v => formatCurrency(v, true)} tick={{ fontSize: 10 }} width={70} />
            <Tooltip formatter={(v: any) => formatCurrency(v)} />
            <Line type="monotone" dataKey="used_margin" stroke="#f44336" dot={false} name="Used" />
            <Line type="monotone" dataKey="available_margin" stroke="#4caf50" dot={false} name="Available" />
          </LineChart>
        </ResponsiveContainer>
      </Box>
    </Box>
  );
}
