import React, { useState } from 'react';
import { Box, Typography, Chip, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, ToggleButton, ToggleButtonGroup, MenuItem, Select, FormControl, InputLabel } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import AddIcon from '@mui/icons-material/Add';
import { api } from '../../api/client';
import BrokerChip from '../../components/common/BrokerChip';
import { formatCurrency, formatBrokerAccountLabel } from '../../utils/formatters';

const STATUS_COLORS: Record<string, any> = {
  COMPLETE: 'success', REJECTED: 'error', CANCELLED: 'default',
  PENDING: 'warning', OPEN: 'primary', TRIGGER_PENDING: 'warning',
};

const cols: GridColDef[] = [
  { field: 'order_timestamp', headerName: 'Time',       width: 160, renderCell: p => new Date(p.value).toLocaleString('en-IN') },
  { field: 'symbol',          headerName: 'Symbol',     width: 120, renderCell: p => <strong>{p.value}</strong> },
  { field: 'broker_name',     headerName: 'Broker',     width: 110, renderCell: p => <BrokerChip broker={p.value} /> },
  { field: 'transaction_type',headerName: 'Side',       width: 70,  renderCell: p => <Chip size="small" label={p.value} color={p.value === 'BUY' ? 'success' : 'error'} /> },
  { field: 'order_type',      headerName: 'Type',       width: 90  },
  { field: 'product_type',    headerName: 'Product',    width: 80  },
  { field: 'quantity',        headerName: 'Qty',        width: 70, type: 'number' },
  { field: 'filled_quantity', headerName: 'Filled',     width: 70, type: 'number' },
  { field: 'price',           headerName: 'Price',      width: 90, renderCell: p => p.value ? formatCurrency(p.value) : 'MARKET' },
  { field: 'average_price',   headerName: 'Avg Price',  width: 100, renderCell: p => p.value ? formatCurrency(p.value) : '—' },
  { field: 'status',          headerName: 'Status',     width: 130, renderCell: p => <Chip size="small" label={p.value} color={STATUS_COLORS[p.value] ?? 'default'} /> },
];

export default function Orders() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [brokerFilter, setBrokerFilter] = useState('all');
  const [form, setForm] = useState({ symbol: '', exchange: 'NSE', transaction_type: 'BUY', order_type: 'MARKET', product_type: 'CNC', quantity: '', price: '', broker_account_id: 1 });

  const { data, isLoading } = useQuery({
    queryKey: ['orders'],
    queryFn: () => api.get('/orders').then(r => r.data?.items ?? r.data ?? []),
  });
  const { data: brokerAccounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then(r => r.data ?? []),
  });
  const placeMutation = useMutation({
    mutationFn: (body: any) => api.post('/orders', body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['orders'] }); setOpen(false); },
  });

  const rows = (Array.isArray(data) ? data : [])
    .filter((o: any) => brokerFilter === 'all' || String(o.broker_account_id) === String(brokerFilter))
    .map((o: any, i: number) => ({ ...o, id: o.id ?? i }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={700}>Orders</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {brokerAccounts.length > 1 && (
            <Select
              size="small"
              value={brokerFilter}
              onChange={(e) => setBrokerFilter(e.target.value)}
              sx={{ minWidth: 175, height: 36, fontSize: '0.85rem' }}
            >
              <MenuItem value="all">All Brokers</MenuItem>
              {brokerAccounts.map((acc: any) => (
                <MenuItem key={acc.id} value={String(acc.id)}>
                  {formatBrokerAccountLabel(acc)}
                </MenuItem>
              ))}
            </Select>
          )}
          <Button startIcon={<AddIcon />} variant="contained" size="small" onClick={() => setOpen(true)}>
            Place Order
          </Button>
        </Box>
      </Box>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
        <DataGrid rows={rows} columns={cols} loading={isLoading} autoHeight disableRowSelectionOnClick pageSizeOptions={[25, 50]} />
      </Box>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Place Order</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          {brokerAccounts.length > 0 && (
            <FormControl fullWidth size="small">
              <InputLabel>Target Broker</InputLabel>
              <Select
                value={form.broker_account_id}
                label="Target Broker"
                onChange={e => setForm(f => ({ ...f, broker_account_id: Number(e.target.value) }))}
              >
                {brokerAccounts.map((acc: any) => (
                  <MenuItem key={acc.id} value={acc.id}>
                    {formatBrokerAccountLabel(acc)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          <TextField label="Symbol" value={form.symbol} onChange={e => setForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))} fullWidth />
          <FormControl fullWidth><InputLabel>Exchange</InputLabel>
            <Select value={form.exchange} label="Exchange" onChange={e => setForm(f => ({ ...f, exchange: e.target.value }))}>
              {['NSE','BSE','NFO','MCX'].map(x => <MenuItem key={x} value={x}>{x}</MenuItem>)}
            </Select>
          </FormControl>
          <ToggleButtonGroup exclusive value={form.transaction_type} onChange={(_, v) => v && setForm(f => ({ ...f, transaction_type: v }))} fullWidth>
            <ToggleButton value="BUY" color="success" sx={{ flex: 1 }}>BUY</ToggleButton>
            <ToggleButton value="SELL" color="error" sx={{ flex: 1 }}>SELL</ToggleButton>
          </ToggleButtonGroup>
          <FormControl fullWidth><InputLabel>Order Type</InputLabel>
            <Select value={form.order_type} label="Order Type" onChange={e => setForm(f => ({ ...f, order_type: e.target.value }))}>
              {['MARKET','LIMIT','SL','SL-M'].map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth><InputLabel>Product</InputLabel>
            <Select value={form.product_type} label="Product" onChange={e => setForm(f => ({ ...f, product_type: e.target.value }))}>
              {['CNC','MIS','NRML'].map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField label="Quantity" type="number" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} fullWidth />
          {form.order_type !== 'MARKET' && (
            <TextField label="Price" type="number" value={form.price} onChange={e => setForm(f => ({ ...f, price: e.target.value }))} fullWidth />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" color={form.transaction_type === 'BUY' ? 'success' : 'error'} onClick={() => placeMutation.mutate({ ...form, quantity: Number(form.quantity), price: form.price ? Number(form.price) : undefined })} disabled={placeMutation.isPending}>
            {form.transaction_type}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
