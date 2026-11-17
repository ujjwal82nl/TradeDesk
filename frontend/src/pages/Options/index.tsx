import React from 'react';
import { Box, Typography, Grid, Chip } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import PnLCell    from '../../components/common/PnLCell';
import BrokerChip from '../../components/common/BrokerChip';
import StatCard   from '../../components/common/StatCard';
import { formatCurrency } from '../../utils/formatters';

const cols: GridColDef[] = [
  { field: 'symbol',      headerName: 'Symbol',   width: 100, renderCell: p => <strong>{p.value}</strong> },
  { field: 'broker_name', headerName: 'Broker',   width: 110, renderCell: p => <BrokerChip broker={p.value} /> },
  { field: 'strike_price',headerName: 'Strike',   width: 90  },
  { field: 'option_type', headerName: 'Type',     width: 60,  renderCell: p => <Typography fontWeight={700} color={p.value === 'CE' ? 'success.main' : 'error.main'}>{p.value}</Typography> },
  { field: 'expiry_date', headerName: 'Expiry',   width: 100 },
  { field: 'quantity',    headerName: 'Qty',      width: 70  },
  { field: 'average_price',headerName:'Avg',      width: 90, renderCell: p => formatCurrency(p.value) },
  { field: 'last_price',  headerName: 'LTP',      width: 90, renderCell: p => formatCurrency(p.value) },
  { field: 'pnl',         headerName: 'P&L',      width: 150, renderCell: p => <PnLCell value={p.value} /> },
  { field: 'delta',       headerName: 'Δ',        width: 70, type: 'number' },
  { field: 'theta',       headerName: 'Θ',        width: 70, type: 'number' },
  { field: 'vega',        headerName: 'V',        width: 70, type: 'number' },
  { field: 'gamma',       headerName: 'Γ',        width: 70, type: 'number' },
];

export default function Options() {
  const { data: options, isLoading } = useQuery({
    queryKey: ['option-positions'],
    queryFn: () => api.get('/positions/options').then(r => r.data ?? []),
  });
  const { data: greeks } = useQuery({
    queryKey: ['greeks-summary'],
    queryFn: () => api.get('/positions/greeks-summary').then(r => r.data),
  });

  const rows = (Array.isArray(options) ? options : []).map((o: any, i: number) => ({ ...o, id: o.id ?? i }));

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={2}>Options Dashboard</Typography>
      <Grid container spacing={2} mb={3}>
        {[
          { title: 'Net Delta', value: greeks?.net_delta?.toFixed(4) ?? '—' },
          { title: 'Net Theta', value: greeks?.net_theta?.toFixed(4) ?? '—' },
          { title: 'Net Vega',  value: greeks?.net_vega?.toFixed(4)  ?? '—' },
          { title: 'Net Gamma', value: greeks?.net_gamma?.toFixed(4) ?? '—' },
          { title: 'Positions', value: rows.length.toString() },
        ].map(c => <Grid item xs={6} sm={4} md={2} key={c.title}><StatCard title={c.title} value={c.value} /></Grid>)}
      </Grid>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
        <DataGrid rows={rows} columns={cols} loading={isLoading} autoHeight disableRowSelectionOnClick pageSizeOptions={[25, 50]} />
      </Box>
    </Box>
  );
}
