import React, { useState } from 'react';
import { Box, Typography, Chip, LinearProgress, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, MenuItem, Select, FormControl, InputLabel } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import AddIcon from '@mui/icons-material/Add';
import { api } from '../../api/client';
import PnLCell from '../../components/common/PnLCell';
import { formatCurrency } from '../../utils/formatters';

const STRATEGY_TYPES = ['IRON_FLY','IRON_CONDOR','COVERED_CALL','SHORT_STRANGLE','SHORT_STRADDLE','WHEEL'];

const cols: GridColDef[] = [
  { field: 'name',          headerName: 'Name',          width: 150 },
  { field: 'strategy_type', headerName: 'Type',          width: 130, renderCell: p => <Chip label={p.value} size="small" variant="outlined" color="primary" /> },
  { field: 'underlying',    headerName: 'Underlying',    width: 100 },
  { field: 'expiry_date',   headerName: 'Expiry',        width: 100 },
  { field: 'status',        headerName: 'Status',        width: 90,  renderCell: p => <Chip label={p.value} size="small" color={p.value === 'OPEN' ? 'success' : 'default'} /> },
  { field: 'current_pnl',  headerName: 'Current P&L',   width: 150, renderCell: p => <PnLCell value={p.value} /> },
  { field: 'net_premium',   headerName: 'Net Premium',   width: 120, renderCell: p => formatCurrency(p.value) },
  { field: 'max_profit',    headerName: 'Max Profit',    width: 120, renderCell: p => p.value ? formatCurrency(p.value) : '∞' },
  { field: 'max_loss',      headerName: 'Max Loss',      width: 120, renderCell: p => p.value ? formatCurrency(p.value) : 'Unlimited' },
  { field: 'days_to_expiry',headerName: 'DTE',           width: 70,  renderCell: p => <Chip label={p.value} size="small" color={p.value < 7 ? 'error' : p.value < 30 ? 'warning' : 'default'} /> },
  { field: 'margin_used',   headerName: 'Margin',        width: 120, renderCell: p => formatCurrency(p.value, true) },
  { field: 'probability_of_profit', headerName: 'PoP',  width: 120, renderCell: p => p.value ? <LinearProgress variant="determinate" value={p.value * 100} sx={{ width: 80, height: 8, borderRadius: 4 }} /> : '—' },
];

export default function Strategies() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', strategy_type: 'IRON_FLY', underlying: '', expiry_date: '', broker_account_id: 1 });

  const { data, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.get('/strategies').then(r => r.data ?? []),
  });
  const createMutation = useMutation({
    mutationFn: (body: any) => api.post('/strategies', body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['strategies'] }); setOpen(false); },
  });

  const rows = (Array.isArray(data) ? data : []).map((s: any, i: number) => ({ ...s, id: s.id ?? i }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={700}>Option Strategies</Typography>
        <Button startIcon={<AddIcon />} variant="contained" size="small" onClick={() => setOpen(true)}>Add Strategy</Button>
      </Box>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
        <DataGrid rows={rows} columns={cols} loading={isLoading} autoHeight disableRowSelectionOnClick pageSizeOptions={[25]} />
      </Box>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Option Strategy</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label="Strategy Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Type</InputLabel>
            <Select value={form.strategy_type} label="Type" onChange={e => setForm(f => ({ ...f, strategy_type: e.target.value }))}>
              {STRATEGY_TYPES.map(t => <MenuItem key={t} value={t}>{t.replace(/_/g,' ')}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField label="Underlying (e.g. NIFTY)" value={form.underlying} onChange={e => setForm(f => ({ ...f, underlying: e.target.value }))} fullWidth />
          <TextField label="Expiry Date" type="date" value={form.expiry_date} onChange={e => setForm(f => ({ ...f, expiry_date: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createMutation.mutate(form)} disabled={createMutation.isPending}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
