import React, { useState } from 'react';
import { Box, Typography, Chip, Drawer, TextField, Button, Select, MenuItem } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import DownloadIcon from '@mui/icons-material/Download';
import { api } from '../../api/client';
import BrokerChip from '../../components/common/BrokerChip';
import PnLCell from '../../components/common/PnLCell';
import { formatCurrency, formatBrokerAccountLabel } from '../../utils/formatters';

const cols: GridColDef[] = [
  { field: 'trade_timestamp', headerName: 'Date/Time',  width: 160, renderCell: p => new Date(p.value).toLocaleString('en-IN') },
  { field: 'symbol',          headerName: 'Symbol',     width: 120, renderCell: p => <strong>{p.value}</strong> },
  { field: 'broker_name',     headerName: 'Broker',     width: 110, renderCell: p => <BrokerChip broker={p.value} /> },
  { field: 'transaction_type',headerName: 'Side',       width: 70,  renderCell: p => <Chip size="small" label={p.value} color={p.value === 'BUY' ? 'success' : 'error'} /> },
  { field: 'quantity',        headerName: 'Qty',        width: 80, type: 'number' },
  { field: 'price',           headerName: 'Price',      width: 100, renderCell: p => formatCurrency(p.value) },
  { field: 'trade_value',     headerName: 'Value',      width: 120, renderCell: p => formatCurrency(p.value, true) },
  { field: 'journal_entry',   headerName: 'Journal',    width: 200, renderCell: p => <Typography variant="caption" noWrap>{p.value || '—'}</Typography> },
];

export default function Trades() {
  const qc = useQueryClient();
  const [brokerFilter, setBrokerFilter] = useState('all');
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [journal, setJournal] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['trades'],
    queryFn: () => api.get('/trades').then(r => r.data?.items ?? r.data ?? []),
  });
  const { data: brokerAccounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then(r => r.data ?? []),
  });
  const updateJournal = useMutation({
    mutationFn: ({ id, entry }: { id: number; entry: string }) =>
      api.put(`/trades/${id}/journal`, { journal_entry: entry }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['trades'] }); setSelectedTrade(null); },
  });

  const rows = (Array.isArray(data) ? data : [])
    .filter((t: any) => brokerFilter === 'all' || String(t.broker_account_id) === String(brokerFilter))
    .map((t: any, i: number) => ({ ...t, id: t.id ?? i }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={700}>Trade History</Typography>
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
          <Button startIcon={<DownloadIcon />} variant="outlined" size="small" onClick={() => window.open('/api/v1/trades/export')}>
            Export CSV
          </Button>
        </Box>
      </Box>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
        <DataGrid
          rows={rows} columns={cols} loading={isLoading} autoHeight disableRowSelectionOnClick
          pageSizeOptions={[25, 50, 100]}
          onRowClick={p => { setSelectedTrade(p.row); setJournal(p.row.journal_entry || ''); }}
        />
      </Box>

      <Drawer anchor="right" open={Boolean(selectedTrade)} onClose={() => setSelectedTrade(null)} PaperProps={{ sx: { width: 400, p: 3 } }}>
        {selectedTrade && (
          <Box>
            <Typography variant="h6" fontWeight={700} mb={1}>{selectedTrade.symbol}</Typography>
            <Typography variant="body2" color="text.secondary" mb={0.5}>
              {selectedTrade.transaction_type} · {selectedTrade.quantity} @ {formatCurrency(selectedTrade.price)}
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              {new Date(selectedTrade.trade_timestamp).toLocaleString('en-IN')}
            </Typography>
            <TextField label="Journal Entry" multiline rows={6} fullWidth value={journal} onChange={e => setJournal(e.target.value)} sx={{ mb: 2 }} />
            <Button variant="contained" fullWidth onClick={() => updateJournal.mutate({ id: selectedTrade.id, entry: journal })} disabled={updateJournal.isPending}>
              Save Journal
            </Button>
          </Box>
        )}
      </Drawer>
    </Box>
  );
}
