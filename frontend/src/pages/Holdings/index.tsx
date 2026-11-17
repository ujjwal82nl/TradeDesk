import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  TextField,
  Grid,
  Select,
  MenuItem,
  Chip,
  InputAdornment,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SyncIcon       from '@mui/icons-material/Sync';
import SearchIcon     from '@mui/icons-material/Search';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon  from '@mui/icons-material/ShowChart';
import InventoryIcon  from '@mui/icons-material/Inventory';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';
import PnLCell from '../../components/common/PnLCell';
import BrokerChip from '../../components/common/BrokerChip';
import StatCard from '../../components/common/StatCard';
import { formatCurrency, formatBrokerAccountLabel } from '../../utils/formatters';
import TradeLotsDialog from './TradeLotsDialog';

const getColumns = (onViewLots: (row: any) => void): GridColDef[] => [
  {
    field: 'symbol',
    headerName: 'Symbol',
    width: 170,
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', gap: 1 }}>
        <Typography variant="body2" component="span" fontWeight={700}>
          {p.value}
        </Typography>
        {p.row.instrument_type && p.row.instrument_type !== 'EQ' && (
          <Chip
            label={p.row.instrument_type}
            size="small"
            sx={{ height: 18, fontSize: '0.65rem', fontWeight: 600 }}
          />
        )}
      </Box>
    ),
  },
  {
    field: 'broker_name',
    headerName: 'Broker',
    width: 110,
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
        <BrokerChip broker={p.value} />
      </Box>
    ),
  },
  {
    field: 'exchange',
    headerName: 'Exch',
    width: 70,
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
        <Typography variant="body2" component="span" color="text.secondary">
          {p.value}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'quantity',
    headerName: 'Qty',
    width: 90,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <Typography variant="body2" component="span" fontWeight={600}>
          {p.value?.toLocaleString('en-IN') ?? 0}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'average_cost',
    headerName: 'Avg Cost',
    width: 110,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <Typography variant="body2" component="span">
          {formatCurrency(p.value)}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'current_price',
    headerName: 'LTP',
    width: 110,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <Typography variant="body2" component="span" fontWeight={600}>
          {formatCurrency(p.value)}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'current_value',
    headerName: 'Current Value',
    width: 130,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <Typography variant="body2" component="span" fontWeight={700}>
          {formatCurrency(p.value, true)}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'pnl',
    headerName: 'Total P&L',
    width: 160,
    type: 'number',
    renderCell: (p) => (
      <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
        <PnLCell value={p.row.pnl} percent={p.row.pnl_percent} />
      </Box>
    ),
  },
  {
    field: 'day_change',
    headerName: "Day's Change",
    width: 150,
    type: 'number',
    renderCell: (p) => {
      const dayVal = (p.row.day_change ?? 0) * (p.row.quantity ?? 1);
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
          <PnLCell value={dayVal} percent={p.row.day_change_percent} />
        </Box>
      );
    },
  },
  {
    field: 'actions',
    headerName: 'Breakdown',
    width: 120,
    sortable: false,
    renderCell: (p) => {
      const isDhan = p.row.broker_name?.toLowerCase().includes('dhan');
      const isSupported = p.row.supports_trade_lots ?? isDhan;
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          <Button
            size="small"
            variant="outlined"
            startIcon={<ReceiptLongIcon sx={{ fontSize: '0.85rem !important' }} />}
            onClick={() => onViewLots(p.row)}
            sx={{
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'none',
              py: 0.2,
              px: 1,
              height: 26,
              borderRadius: 1.5,
              borderColor: isSupported ? 'primary.main' : 'divider',
              color: isSupported ? 'primary.main' : 'text.secondary',
              '&:hover': {
                borderColor: isSupported ? 'primary.dark' : 'text.primary',
                bgcolor: isSupported ? 'primary.light' : 'action.hover',
              },
            }}
          >
            {isSupported ? 'Trade Lots' : 'Details'}
          </Button>
        </Box>
      );
    },
  },
];

export default function Holdings() {
  const [tab, setTab] = useState(0);
  const [search, setSearch] = useState('');
  const [brokerFilter, setBrokerFilter] = useState('all');
  const [selectedHolding, setSelectedHolding] = useState<{
    id?: number | null;
    symbol?: string | null;
    brokerName?: string | null;
  } | null>(null);

  const queryClient = useQueryClient();

  const { data: brokerAccounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then((r) => r.data ?? []),
  });

  const columns = useMemo(
    () =>
      getColumns((row) =>
        setSelectedHolding({
          id: row.id,
          symbol: row.symbol,
          brokerName: row.broker_name,
        })
      ),
    []
  );

  // Fetch holdings
  const { data: allData, isLoading } = useQuery({
    queryKey: ['holdings'],
    queryFn: () =>
      api.get('/holdings').then((r) => (Array.isArray(r.data) ? r.data : r.data?.items ?? [])),
  });

  // Fetch merged holdings
  const { data: mergedData, isLoading: isMergedLoading } = useQuery({
    queryKey: ['holdings-merged'],
    queryFn: () => api.get('/holdings/merged').then((r) => r.data ?? []),
  });

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: () => api.post('/holdings/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
      queryClient.invalidateQueries({ queryKey: ['holdings-merged'] });
    },
  });

  const holdingsList: any[] = useMemo(() => (Array.isArray(allData) ? allData : []), [allData]);

  // Aggregate stats
  const stats = useMemo(() => {
    let totalInvested = 0;
    let totalCurrent = 0;
    let totalPnl = 0;
    let totalDayChange = 0;

    holdingsList.forEach((h) => {
      const qty = Number(h.quantity) || 0;
      const cost = Number(h.average_cost) || 0;
      const ltp = Number(h.current_price) || 0;
      const dayChg = Number(h.day_change) || 0;

      const invested = qty * cost;
      const current = Number(h.current_value) || qty * ltp;
      const pnl = Number(h.pnl) || (current - invested);

      totalInvested += invested;
      totalCurrent += current;
      totalPnl += pnl;
      totalDayChange += dayChg * qty;
    });

    const totalPnlPercent = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;
    const dayPnlPercent = totalInvested > 0 ? (totalDayChange / totalInvested) * 100 : 0;

    return {
      totalInvested,
      totalCurrent,
      totalPnl,
      totalPnlPercent,
      totalDayChange,
      dayPnlPercent,
      count: holdingsList.length,
    };
  }, [holdingsList]);

  // Filtered rows for DataGrid
  const rows = useMemo(() => {
    return holdingsList
      .filter((h: any) => {
        const matchesSearch =
          !search ||
          h.symbol?.toLowerCase().includes(search.toLowerCase()) ||
          h.isin?.toLowerCase().includes(search.toLowerCase());

        const matchesBroker =
          brokerFilter === 'all' ||
          String(h.broker_account_id) === String(brokerFilter);

        return matchesSearch && matchesBroker;
      })
      .map((h: any, i: number) => ({ ...h, id: h.id ?? i }));
  }, [holdingsList, search, brokerFilter]);

  return (
    <Box>
      {/* Page Title & Action Bar */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2.5}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Holdings
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Cross-broker demat portfolio and long-term equity holdings
          </Typography>
        </Box>
        <Button
          startIcon={<SyncIcon className={syncMutation.isPending ? 'spin' : ''} />}
          variant="contained"
          size="medium"
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          sx={{ textTransform: 'none', px: 2.5, fontWeight: 600 }}
        >
          {syncMutation.isPending ? 'Syncing...' : 'Sync Holdings'}
        </Button>
      </Box>

      {/* Summary KPI Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="PORTFOLIO VALUE"
            value={formatCurrency(stats.totalCurrent, true)}
            subtitle={`Invested: ${formatCurrency(stats.totalInvested, true)}`}
            icon={<AccountBalanceWalletIcon />}
            isLoading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="TOTAL RETURN (P&L)"
            value={formatCurrency(stats.totalPnl, true)}
            trend={stats.totalPnlPercent}
            icon={<TrendingUpIcon />}
            isLoading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="TODAY'S P&L"
            value={formatCurrency(stats.totalDayChange, true)}
            trend={stats.dayPnlPercent}
            icon={<ShowChartIcon />}
            isLoading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="TOTAL SCRIPS"
            value={stats.count}
            subtitle={brokerAccounts.length > 0 ? `Across ${brokerAccounts.length} broker account${brokerAccounts.length > 1 ? 's' : ''}` : 'Holdings portfolio'}
            icon={<InventoryIcon />}
            isLoading={isLoading}
          />
        </Grid>
      </Grid>

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{
          mb: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
          '& .MuiTab-root': { fontWeight: 600, textTransform: 'none', minWidth: 120 },
        }}
      >
        <Tab label={`All Holdings (${holdingsList.length})`} />
        <Tab label={`Merged View (${(mergedData ?? []).length})`} />
      </Tabs>

      {/* Tab 0: All Holdings (DataGrid) */}
      {tab === 0 && (
        <>
          {/* Filter Bar */}
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              mb: 2,
              alignItems: 'center',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
            }}
          >
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <TextField
                size="small"
                placeholder="Search symbol or ISIN..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                    </InputAdornment>
                  ),
                }}
                sx={{ width: 280 }}
              />

              {brokerAccounts.length > 1 && (
                <Select
                  size="small"
                  value={brokerFilter}
                  onChange={(e) => setBrokerFilter(e.target.value)}
                  sx={{ minWidth: 175, height: 40 }}
                >
                  <MenuItem value="all">All Brokers</MenuItem>
                  {brokerAccounts.map((acc: any) => (
                    <MenuItem key={acc.id} value={String(acc.id)}>
                      {formatBrokerAccountLabel(acc)}
                    </MenuItem>
                  ))}
                </Select>
              )}
            </Box>

            <Typography variant="body2" color="text.secondary">
              Showing <strong>{rows.length}</strong> of {holdingsList.length} holdings
            </Typography>
          </Box>

          {/* Holdings Table */}
          <Box
            sx={{
              bgcolor: 'background.paper',
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
              overflow: 'hidden',
              '& .MuiDataGrid-cell': {
                display: 'flex',
                alignItems: 'center',
              },
            }}
          >
            <DataGrid
              rows={rows}
              columns={columns}
              loading={isLoading}
              autoHeight
              disableRowSelectionOnClick
              pageSizeOptions={[25, 50, 100]}
              initialState={{ pagination: { paginationModel: { pageSize: 50 } } }}
            />
          </Box>
        </>
      )}

      {/* Tab 1: Merged View */}
      {tab === 1 && (
        <Box>
          {isMergedLoading && (
            <Typography variant="body2" color="text.secondary" py={4} textAlign="center">
              Loading merged holdings across brokers...
            </Typography>
          )}

          {!isMergedLoading && (mergedData ?? []).length === 0 && (
            <Typography variant="body2" color="text.secondary" py={4} textAlign="center">
              No holdings to display in merged view.
            </Typography>
          )}

          {(Array.isArray(mergedData) ? mergedData : []).map((h: any) => (
            <Accordion
              key={h.symbol}
              disableGutters
              elevation={0}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                mb: 1.5,
                borderRadius: 2,
                overflow: 'hidden',
                '&:before': { display: 'none' },
                bgcolor: 'background.paper',
              }}
            >
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box
                  display="flex"
                  gap={{ xs: 2, md: 4 }}
                  alignItems="center"
                  flex={1}
                  flexWrap="wrap"
                >
                  <Box sx={{ minWidth: 140 }}>
                    <Typography fontWeight={700} variant="subtitle1">
                      {h.symbol}
                    </Typography>
                    {h.isin && (
                      <Typography variant="caption" color="text.secondary">
                        {h.isin}
                      </Typography>
                    )}
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      TOTAL QTY
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {h.total_quantity?.toLocaleString('en-IN')}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      WEIGHTED AVG
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {formatCurrency(h.weighted_avg_cost)}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      LTP
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {formatCurrency(h.current_price)}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      CURRENT VALUE
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {formatCurrency(h.total_value, true)}
                    </Typography>
                  </Box>

                  <Box sx={{ ml: 'auto', pr: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block" textAlign="right">
                      OVERALL P&L
                    </Typography>
                    <PnLCell value={h.total_pnl} percent={h.total_pnl_percent} />
                  </Box>
                </Box>
              </AccordionSummary>

              <AccordionDetails sx={{ pt: 1, pb: 2, px: 3, bgcolor: 'action.hover' }}>
                <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', mb: 1, display: 'block' }}>
                  Broker Breakdown:
                </Typography>
                {(h.brokers ?? []).map((b: any) => (
                  <Box
                    key={b.broker_name}
                    display="flex"
                    gap={{ xs: 2, md: 4 }}
                    py={1.2}
                    borderTop="1px solid"
                    borderColor="divider"
                    alignItems="center"
                    flexWrap="wrap"
                  >
                    <Box sx={{ minWidth: 120 }}>
                      <BrokerChip broker={b.broker_name} />
                    </Box>
                    <Typography variant="body2">
                      Qty: <strong>{b.quantity?.toLocaleString('en-IN')}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Avg: <strong>{formatCurrency(b.average_cost)}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Value: <strong>{formatCurrency(b.value, true)}</strong>
                    </Typography>
                    <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 2 }}>
                      <PnLCell value={b.pnl} />
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<ReceiptLongIcon sx={{ fontSize: '0.85rem !important' }} />}
                        onClick={() =>
                          setSelectedHolding({
                            id: b.holding_id,
                            symbol: h.symbol,
                            brokerName: b.broker_name,
                          })
                        }
                        sx={{
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          textTransform: 'none',
                          py: 0.2,
                          px: 1,
                          height: 26,
                          borderRadius: 1.5,
                        }}
                      >
                        Trade Lots
                      </Button>
                    </Box>
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )}

      {/* Trade Lots Detail Dialog */}
      <TradeLotsDialog
        open={Boolean(selectedHolding)}
        onClose={() => setSelectedHolding(null)}
        holdingId={selectedHolding?.id}
        symbol={selectedHolding?.symbol}
        brokerName={selectedHolding?.brokerName}
      />
    </Box>
  );
}
