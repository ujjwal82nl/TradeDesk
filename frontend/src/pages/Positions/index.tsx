import React, { useState, useMemo } from 'react';
import { Box, Typography, Tabs, Tab, Grid, Chip, Select, MenuItem, Button } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import SyncIcon from '@mui/icons-material/Sync';
import { api } from '../../api/client';
import PnLCell from '../../components/common/PnLCell';
import BrokerChip from '../../components/common/BrokerChip';
import StatCard from '../../components/common/StatCard';
import { formatCurrency, formatBrokerAccountLabel } from '../../utils/formatters';

const baseColumns: GridColDef[] = [
  {
    field: 'symbol',
    headerName: 'Symbol',
    width: 250,
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
        <Typography
          variant="body2"
          component="span"
          fontWeight={p.row.quantity !== 0 ? 700 : 500}
          color={p.row.quantity !== 0 ? 'text.primary' : 'text.secondary'}
        >
          {p.value}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'status',
    headerName: 'Status',
    width: 100,
    renderCell: (p) => {
      const isOpen = p.row.quantity !== 0 || p.value === 'OPEN';
      return (
        <Chip
          label={isOpen ? 'OPEN' : 'CLOSED'}
          size="small"
          sx={{
            fontWeight: 700,
            fontSize: '0.72rem',
            height: 22,
            px: 0.5,
            bgcolor: isOpen ? 'rgba(38, 166, 154, 0.16)' : 'rgba(255, 255, 255, 0.06)',
            color: isOpen ? '#26a69a' : 'text.secondary',
            border: isOpen ? '1px solid rgba(38, 166, 154, 0.4)' : '1px solid rgba(255, 255, 255, 0.12)',
          }}
        />
      );
    },
  },
  {
    field: 'broker_name',
    headerName: 'Broker',
    width: 110,
    renderCell: (p) => <BrokerChip broker={p.value} />,
  },
  { field: 'exchange', headerName: 'Exch', width: 70 },
  { field: 'product_type', headerName: 'Product', width: 90 },
  {
    field: 'quantity',
    headerName: 'Qty',
    width: 80,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <Typography
          variant="body2"
          component="span"
          fontWeight={p.value !== 0 ? 700 : 400}
          color={p.value !== 0 ? 'text.primary' : 'text.disabled'}
        >
          {p.value}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'average_price',
    headerName: 'Avg Price',
    width: 110,
    renderCell: (p) => formatCurrency(p.value),
  },
  {
    field: 'last_price',
    headerName: 'LTP',
    width: 110,
    renderCell: (p) => formatCurrency(p.value),
  },
  {
    field: 'pnl',
    headerName: 'P&L',
    width: 140,
    renderCell: (p) => <PnLCell value={p.row.pnl} percent={undefined} />,
  },
  {
    field: 'day_pnl',
    headerName: 'Day P&L',
    width: 130,
    renderCell: (p) => <PnLCell value={p.value} />,
  },
];

const optionCols: GridColDef[] = [
  ...baseColumns,
  {
    field: 'strike_price',
    headerName: 'Strike',
    width: 100,
    renderCell: (p) => (p.value ? formatCurrency(p.value) : '—'),
  },
  {
    field: 'option_type',
    headerName: 'Type',
    width: 70,
    renderCell: (p) =>
      p.value ? (
        <Typography
          variant="body2"
          fontWeight={700}
          color={p.value === 'CE' ? 'success.main' : 'error.main'}
        >
          {p.value}
        </Typography>
      ) : (
        '—'
      ),
  },
  {
    field: 'expiry_date',
    headerName: 'Expiry',
    width: 110,
    renderCell: (p) => (p.value ? String(p.value) : '—'),
  },
];

export default function Positions() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'CLOSED'>('ALL');
  const [brokerFilter, setBrokerFilter] = useState<string>('all');

  const { data: positions, isLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.get('/positions').then((r) => r.data?.items ?? r.data ?? []),
  });

  const { data: brokerAccounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then((r) => r.data ?? []),
  });

  const syncMutation = useMutation({
    mutationFn: () => api.post('/positions/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['greeks-summary'] });
    },
  });

  const { data: greeks } = useQuery({
    queryKey: ['greeks-summary'],
    queryFn: () => api.get('/positions/greeks-summary').then((r) => r.data),
    enabled: tab === 2,
  });

  const all: any[] = Array.isArray(positions) ? positions : [];

  // Filter positions by selected broker account
  const brokerFiltered = useMemo(() => {
    if (brokerFilter === 'all') return all;
    return all.filter((p: any) => String(p.broker_account_id) === String(brokerFilter));
  }, [all, brokerFilter]);

  // Categorize positions
  const options = brokerFiltered.filter(
    (p: any) => ['CE', 'PE'].includes(p.option_type) || p.instrument_type === 'OPT'
  );
  const futures = brokerFiltered.filter(
    (p: any) => p.instrument_type === 'FUT' || p.instrument_type === 'FUTURES'
  );
  const stocks = brokerFiltered.filter(
    (p: any) =>
      p.instrument_type === 'EQ' ||
      p.instrument_type === 'EQUITY' ||
      (!options.includes(p) && !futures.includes(p))
  );

  // Filter by category tab: All (0), Stocks (1), Options (2), Futures (3)
  const categoryRows =
    tab === 0 ? brokerFiltered : tab === 1 ? stocks : tab === 2 ? options : futures;

  // Filter by status dropdown
  const filteredRows = categoryRows.filter((p: any) => {
    const isOpen = p.quantity !== 0 || p.is_open === true;
    return (
      statusFilter === 'ALL' ||
      (statusFilter === 'OPEN' && isOpen) ||
      (statusFilter === 'CLOSED' && !isOpen)
    );
  });

  // KPI Metrics across the selected broker view
  const openCount = brokerFiltered.filter((p: any) => p.quantity !== 0 || p.is_open === true).length;
  const closedCount = brokerFiltered.filter((p: any) => p.quantity === 0 && p.is_open !== true).length;
  const unrealizedPnL = brokerFiltered
    .filter((p: any) => p.quantity !== 0 || p.is_open === true)
    .reduce((acc: number, p: any) => acc + (Number(p.pnl) || 0), 0);
  const realizedPnL = brokerFiltered
    .filter((p: any) => p.quantity === 0 && p.is_open !== true)
    .reduce((acc: number, p: any) => acc + (Number(p.pnl) || 0), 0);

  const rowsWithId = filteredRows.map((p: any, i: number) => ({ ...p, id: p.id ?? i }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          Positions
        </Typography>
        <Button
          startIcon={<SyncIcon className={syncMutation.isPending ? 'spin' : ''} />}
          variant="contained"
          size="medium"
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          sx={{ textTransform: 'none', px: 2.5, fontWeight: 600 }}
        >
          {syncMutation.isPending ? 'Syncing...' : 'Sync Positions'}
        </Button>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={2} mb={2.5}>
        <Grid item xs={6} sm={3}>
          <StatCard
            title="Open Positions"
            value={openCount}
            subtitle={openCount > 0 ? `${openCount} active contract${openCount > 1 ? 's' : ''}` : 'No open positions'}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard
            title="Closed Positions"
            value={closedCount}
            subtitle="Squared off"
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard
            title="Unrealized P&L"
            value={formatCurrency(unrealizedPnL)}
            subtitle="Open positions"
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard
            title="Realized P&L"
            value={formatCurrency(realizedPnL)}
            subtitle="Today's closed P&L"
          />
        </Grid>
      </Grid>

      {/* Requested Category Tabs: All, Stocks, Options, Futures */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{
          mb: 2,
          '& .MuiTab-root': { fontWeight: 600, textTransform: 'none', minWidth: 100 },
        }}
      >
        <Tab label={`All (${all.length})`} />
        <Tab label={`Stocks (${stocks.length})`} />
        <Tab label={`Options (${options.length})`} />
        <Tab label={`Futures (${futures.length})`} />
      </Tabs>

      {/* Greeks bar for options tab */}
      {tab === 2 && greeks && (
        <Grid container spacing={2} mb={2}>
          {[
            { title: 'Net Delta', value: greeks.net_delta?.toFixed(4) ?? '—' },
            { title: 'Net Theta', value: greeks.net_theta?.toFixed(4) ?? '—' },
            { title: 'Net Vega', value: greeks.net_vega?.toFixed(4) ?? '—' },
            { title: 'Net Gamma', value: greeks.net_gamma?.toFixed(4) ?? '—' },
          ].map((c) => (
            <Grid item xs={6} sm={3} key={c.title}>
              <StatCard title={c.title} value={c.value} />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Data Grid with Table Header Toolbar */}
      <Box
        sx={{
          bgcolor: 'background.paper',
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
          overflow: 'hidden',
        }}
      >
        {/* Table Header with Title & Status Selection */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            px: 2.5,
            py: 1.5,
            borderBottom: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle1" fontWeight={700}>
              {tab === 0
                ? 'All Positions'
                : tab === 1
                ? 'Stocks'
                : tab === 2
                ? 'Option Contracts'
                : 'Futures Contracts'}
            </Typography>
            <Chip
              label={`${filteredRows.length} ${filteredRows.length === 1 ? 'record' : 'records'}`}
              size="small"
              sx={{ height: 22, fontSize: '0.75rem', fontWeight: 600 }}
            />
          </Box>

          {/* Filters: Broker & Status */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {brokerAccounts.length > 1 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary" fontWeight={500}>
                  Broker:
                </Typography>
                <Select
                  size="small"
                  value={brokerFilter}
                  onChange={(e) => setBrokerFilter(e.target.value)}
                  sx={{
                    height: 32,
                    minWidth: 175,
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    borderRadius: 1.5,
                  }}
                >
                  <MenuItem value="all">All Brokers</MenuItem>
                  {brokerAccounts.map((acc: any) => (
                    <MenuItem key={acc.id} value={String(acc.id)}>
                      {formatBrokerAccountLabel(acc)}
                    </MenuItem>
                  ))}
                </Select>
              </Box>
            )}

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" color="text.secondary" fontWeight={500}>
                Status:
              </Typography>
              <Select
                size="small"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'ALL' | 'OPEN' | 'CLOSED')}
                sx={{
                  height: 32,
                  minWidth: 155,
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  borderRadius: 1.5,
                }}
              >
                <MenuItem value="ALL">All ({categoryRows.length})</MenuItem>
                <MenuItem value="OPEN">
                  Open Only ({categoryRows.filter((p: any) => p.quantity !== 0 || p.is_open === true).length})
                </MenuItem>
                <MenuItem value="CLOSED">
                  Closed Only ({categoryRows.filter((p: any) => p.quantity === 0 && p.is_open !== true).length})
                </MenuItem>
              </Select>
            </Box>
          </Box>
        </Box>

        <DataGrid
          rows={rowsWithId}
          columns={tab === 2 ? optionCols : baseColumns}
          loading={isLoading}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          getRowClassName={(params) =>
            params.row.quantity === 0 ? 'position-closed-row' : 'position-open-row'
          }
          sx={{
            border: 'none',
            '& .MuiDataGrid-cell': {
              display: 'flex',
              alignItems: 'center',
            },
            '& .position-closed-row': {
              opacity: 0.65,
              '&:hover': { opacity: 0.95 },
            },
            '& .position-open-row': {
              bgcolor: 'rgba(38, 166, 154, 0.05)',
              '&:hover': { bgcolor: 'rgba(38, 166, 154, 0.09)' },
            },
          }}
        />
      </Box>
    </Box>
  );
}
