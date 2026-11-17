import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  MenuItem,
  InputAdornment,
  IconButton,
  Tooltip as MuiTooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Snackbar,
  Alert,
  Chip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import SyncIcon from '@mui/icons-material/Sync';
import AddIcon from '@mui/icons-material/Add';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';

import { api } from '../../api/client';
import BrokerChip from '../../components/common/BrokerChip';
import { formatCurrency, formatBrokerAccountLabel } from '../../utils/formatters';
import RecordDividendDialog from './RecordDividendDialog';
import ImportDividendsDialog from './ImportDividendsDialog';

const formatDate = (val: string | null | undefined): string => {
  if (!val) return '—';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return String(val);
    return d.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return String(val);
  }
};

export default function Dividends() {
  const queryClient = useQueryClient();

  // Tabs: 'byStock' | 'byPayouts' | 'byYear'
  const [selectedTab, setSelectedTab] = useState<'byStock' | 'byPayouts' | 'byYear'>('byStock');
  const [search, setSearch] = useState('');
  const [selectedBroker, setSelectedBroker] = useState<string>('all');
  const [selectedFy, setSelectedFy] = useState<string>('all');

  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [recordDialogOpen, setRecordDialogOpen] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'info' | 'warning' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'info',
  });

  // Queries
  const { data: dividendsData, isLoading } = useQuery({
    queryKey: ['dividends'],
    queryFn: () =>
      api.get('/dividends', { params: { page_size: 500 } }).then((r) => r.data ?? { items: [] }),
  });

  const { data: byStock = [] } = useQuery({
    queryKey: ['div-stock'],
    queryFn: () => api.get('/dividends/by-stock').then((r) => r.data ?? []),
  });

  const { data: brokerAccounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then((r) => r.data ?? []),
  });

  // Mutations
  const syncMutation = useMutation({
    mutationFn: () => api.post('/dividends/sync'),
    onSuccess: (res: any) => {
      const count = res.data?.synced_count ?? 0;
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['div-stock'] });
      setNotification({
        open: true,
        message:
          count > 0
            ? `Successfully synced ${count} new dividend credit(s) from broker ledger!`
            : 'Broker ledger scan complete. All records are up to date.',
        severity: 'success',
      });
    },
    onError: (err: any) => {
      setNotification({
        open: true,
        message: err.response?.data?.detail || 'Failed to sync dividends from broker.',
        severity: 'error',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/dividends/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['div-stock'] });
      setDeleteConfirmId(null);
      setNotification({
        open: true,
        message: 'Dividend payout record deleted.',
        severity: 'success',
      });
    },
    onError: (err: any) => {
      setNotification({
        open: true,
        message: err.response?.data?.detail || 'Failed to delete record.',
        severity: 'error',
      });
    },
  });

  const allDividends: any[] = useMemo(() => {
    return dividendsData?.items ?? [];
  }, [dividendsData]);

  // Filtered by selected broker
  const brokerFilteredDividends = useMemo(() => {
    if (selectedBroker === 'all') return allDividends;
    return allDividends.filter((d) => String(d.broker_account_id) === selectedBroker);
  }, [allDividends, selectedBroker]);

  // Overall KPIs (matching Dhan layout, responsive to broker filter)
  const totalDividendEarned = useMemo(() => {
    return brokerFilteredDividends.reduce((sum, d) => sum + (parseFloat(d.net_dividend) || 0), 0);
  }, [brokerFilteredDividends]);

  const numberOfStocks = useMemo(() => {
    return new Set(brokerFilteredDividends.map((d) => d.company_name || d.symbol)).size;
  }, [brokerFilteredDividends]);

  // Financial Years list (e.g. 2026-2027, 2025-2026)
  const financialYears = useMemo(() => {
    const fySet = new Set<string>();
    brokerFilteredDividends.forEach((d) => {
      const dateStr = d.payment_date || d.ex_date;
      if (dateStr) {
        const dt = new Date(dateStr);
        if (!isNaN(dt.getTime())) {
          const year = dt.getFullYear();
          const month = dt.getMonth() + 1; // 1-12
          const startYear = month >= 4 ? year : year - 1;
          fySet.add(`${startYear}-${startYear + 1}`);
        }
      }
    });
    return Array.from(fySet).sort().reverse();
  }, [brokerFilteredDividends]);

  // Filtered by Stock data
  const filteredByStock = useMemo(() => {
    let list = byStock;
    if (selectedBroker !== 'all') {
      const brokerSymbols = new Set(brokerFilteredDividends.map((d) => d.symbol));
      list = byStock.filter((s: any) => brokerSymbols.has(s.symbol));
    }
    if (search) {
      const term = search.toLowerCase();
      list = list.filter(
        (s: any) =>
          (s.company_name || '').toLowerCase().includes(term) ||
          (s.symbol || '').toLowerCase().includes(term)
      );
    }
    return list;
  }, [byStock, search, selectedBroker, brokerFilteredDividends]);

  // Filtered individual payouts
  const filteredPayouts = useMemo(() => {
    return brokerFilteredDividends.filter((d) => {
      if (search) {
        const term = search.toLowerCase();
        const sym = (d.symbol || '').toLowerCase();
        const comp = (d.company_name || '').toLowerCase();
        if (!sym.includes(term) && !comp.includes(term)) return false;
      }
      return true;
    });
  }, [brokerFilteredDividends, search]);

  // Filtered by year data
  const yearFilteredPayouts = useMemo(() => {
    let list = brokerFilteredDividends;
    if (selectedFy !== 'all') {
      const [startYearStr, endYearStr] = selectedFy.split('-');
      const startYear = parseInt(startYearStr, 10);
      const endYear = parseInt(endYearStr, 10);
      const startDate = new Date(startYear, 3, 1); // 1st Apr
      const endDate = new Date(endYear, 2, 31, 23, 59, 59); // 31st Mar

      list = brokerFilteredDividends.filter((d) => {
        const dateStr = d.payment_date || d.ex_date;
        if (!dateStr) return false;
        const dt = new Date(dateStr);
        return dt >= startDate && dt <= endDate;
      });
    }
    return list;
  }, [brokerFilteredDividends, selectedFy]);

  const yearTotalEarned = useMemo(() => {
    return yearFilteredPayouts.reduce((sum, d) => sum + (parseFloat(d.net_dividend) || 0), 0);
  }, [yearFilteredPayouts]);

  return (
    <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 1280, mx: 'auto' }}>
      {/* Top Header matching Dhan */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 2,
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h5" fontWeight={700} sx={{ letterSpacing: -0.5 }}>
            Dividend Payouts
          </Typography>

          {/* Metrics side-by-side matching Dhan */}
          <Box sx={{ display: 'flex', gap: 6, mt: 2.5, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.82rem' }}>
                Total Dividend Earned
              </Typography>
              <Typography
                variant="h4"
                fontWeight={700}
                sx={{ mt: 0.5, color: 'text.primary', fontSize: { xs: '1.5rem', sm: '1.85rem' } }}
              >
                ₹ {totalDividendEarned.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.82rem' }}>
                on Number of Stocks
              </Typography>
              <Typography
                variant="h4"
                fontWeight={700}
                sx={{ mt: 0.5, color: 'text.primary', fontSize: { xs: '1.5rem', sm: '1.85rem' } }}
              >
                {numberOfStocks}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Right Actions */}
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mt: 1 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<UploadFileIcon />}
            onClick={() => setImportDialogOpen(true)}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            Import Statement
          </Button>

          <Button
            variant="outlined"
            size="small"
            startIcon={
              syncMutation.isPending ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <SyncIcon />
              )
            }
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            {syncMutation.isPending ? 'Syncing...' : 'Sync from Broker'}
          </Button>

          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setRecordDialogOpen(true)}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            Record Dividend
          </Button>
        </Box>
      </Box>

      {/* Tabs as Dhan style pills + Broker & Search Filter */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3, mt: 3, flexWrap: 'wrap' }}>
        <Button
          onClick={() => setSelectedTab('byStock')}
          variant={selectedTab === 'byStock' ? 'outlined' : 'text'}
          sx={{
            borderRadius: 6,
            px: 2,
            py: 0.6,
            textTransform: 'none',
            fontSize: '0.9rem',
            fontWeight: 600,
            borderColor: selectedTab === 'byStock' ? '#00b894' : 'transparent',
            color: selectedTab === 'byStock' ? '#00b894' : 'text.secondary',
            bgcolor: selectedTab === 'byStock' ? 'rgba(0, 184, 148, 0.08)' : 'transparent',
            '&:hover': {
              borderColor: '#00b894',
              bgcolor: 'rgba(0, 184, 148, 0.12)',
            },
          }}
        >
          By Stock
        </Button>

        <Button
          onClick={() => setSelectedTab('byPayouts')}
          variant={selectedTab === 'byPayouts' ? 'outlined' : 'text'}
          sx={{
            borderRadius: 6,
            px: 2,
            py: 0.6,
            textTransform: 'none',
            fontSize: '0.9rem',
            fontWeight: 600,
            borderColor: selectedTab === 'byPayouts' ? '#00b894' : 'transparent',
            color: selectedTab === 'byPayouts' ? '#00b894' : 'text.secondary',
            bgcolor: selectedTab === 'byPayouts' ? 'rgba(0, 184, 148, 0.08)' : 'transparent',
            '&:hover': {
              borderColor: '#00b894',
              bgcolor: 'rgba(0, 184, 148, 0.12)',
            },
          }}
        >
          By Payouts
        </Button>

        <Button
          onClick={() => setSelectedTab('byYear')}
          variant={selectedTab === 'byYear' ? 'outlined' : 'text'}
          sx={{
            borderRadius: 6,
            px: 2,
            py: 0.6,
            textTransform: 'none',
            fontSize: '0.9rem',
            fontWeight: 600,
            borderColor: selectedTab === 'byYear' ? '#00b894' : 'transparent',
            color: selectedTab === 'byYear' ? '#00b894' : 'text.secondary',
            bgcolor: selectedTab === 'byYear' ? 'rgba(0, 184, 148, 0.08)' : 'transparent',
            '&:hover': {
              borderColor: '#00b894',
              bgcolor: 'rgba(0, 184, 148, 0.12)',
            },
          }}
        >
          By year
        </Button>

        {/* Broker Account Filter & Search Input */}
        <Box sx={{ ml: 'auto', display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
          {brokerAccounts.length > 1 && (
            <TextField
              select
              size="small"
              value={selectedBroker}
              onChange={(e) => setSelectedBroker(e.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="all">All Brokers</MenuItem>
              {brokerAccounts.map((acc: any) => (
                <MenuItem key={acc.id} value={String(acc.id)}>
                  {formatBrokerAccountLabel(acc)}
                </MenuItem>
              ))}
            </TextField>
          )}

          <TextField
            size="small"
            placeholder="Search stock..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
            sx={{
              minWidth: 200,
              '& .MuiOutlinedInput-root': {
                borderRadius: 4,
                bgcolor: 'background.paper',
                fontSize: '0.85rem',
              },
            }}
          />
        </Box>
      </Box>

      {/* TAB 1: BY STOCK */}
      {selectedTab === 'byStock' && (
        <Paper
          elevation={0}
          sx={{
            borderRadius: 3,
            border: '1px solid',
            borderColor: 'divider',
            overflow: 'hidden',
          }}
        >
          <TableContainer>
            <Table sx={{ minWidth: 650 }}>
              <TableHead>
                <TableRow sx={{ bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Name
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Last Dividend Paid
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}
                  >
                    Quantity held currently
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}
                  >
                    Dividend Paid Till Date
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={4} align="center" sx={{ py: 6 }}>
                      <CircularProgress size={28} />
                    </TableCell>
                  </TableRow>
                ) : filteredByStock.length > 0 ? (
                  filteredByStock.map((row: any, idx: number) => (
                    <TableRow
                      key={idx}
                      hover
                      sx={{
                        '&:last-child td, &:last-child th': { border: 0 },
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <TableCell sx={{ fontWeight: 500, py: 1.6 }}>
                        <Typography variant="body2" fontWeight={500} color="text.primary">
                          {row.company_name || row.symbol}
                        </Typography>
                        {row.symbol && row.symbol !== row.company_name && (
                          <Typography variant="caption" color="text.secondary">
                            {row.symbol}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ py: 1.6, color: 'text.secondary' }}>
                        {formatDate(row.last_dividend_date)}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.6, fontWeight: 500 }}>
                        {row.quantity > 0 ? row.quantity.toLocaleString('en-IN') : '—'}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.6, fontWeight: 600 }}>
                        {parseFloat(row.total_received).toLocaleString('en-IN', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                      No dividend records found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* TAB 2: BY PAYOUTS */}
      {selectedTab === 'byPayouts' && (
        <Paper
          elevation={0}
          sx={{
            borderRadius: 3,
            border: '1px solid',
            borderColor: 'divider',
            overflow: 'hidden',
          }}
        >
          <TableContainer>
            <Table sx={{ minWidth: 750 }}>
              <TableHead>
                <TableRow sx={{ bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Date
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Name
                  </TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Dividend / Share
                  </TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Quantity
                  </TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Dividend Paid
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>
                    Broker
                  </TableCell>
                  <TableCell width={40} sx={{ py: 1.8 }} />
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredPayouts.length > 0 ? (
                  filteredPayouts.map((row: any) => (
                    <TableRow key={row.id} hover sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                      <TableCell sx={{ py: 1.6, color: 'text.secondary' }}>
                        {formatDate(row.payment_date || row.ex_date)}
                      </TableCell>
                      <TableCell sx={{ py: 1.6 }}>
                        <Typography variant="body2" fontWeight={500}>
                          {row.company_name || row.symbol}
                        </Typography>
                        {row.symbol?.includes('SLB') && (
                          <Chip label="SLB" size="small" color="info" sx={{ height: 18, fontSize: '0.65rem', mt: 0.2 }} />
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.6 }}>
                        {row.dividend_per_share > 0 ? `₹${parseFloat(row.dividend_per_share).toFixed(2)}` : '—'}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.6 }}>
                        {row.quantity > 0 ? row.quantity.toLocaleString('en-IN') : '—'}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.6, fontWeight: 600, color: '#00b894' }}>
                        {formatCurrency(row.net_dividend || row.total_dividend)}
                      </TableCell>
                      <TableCell sx={{ py: 1.6 }}>
                        <BrokerChip broker={row.broker_name || 'Broker'} />
                      </TableCell>
                      <TableCell sx={{ py: 1.6 }}>
                        <MuiTooltip title="Delete payout record">
                          <IconButton
                            size="small"
                            onClick={() => setDeleteConfirmId(row.id)}
                            sx={{ '&:hover': { color: 'error.main' } }}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </MuiTooltip>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                      No dividend payouts recorded.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* TAB 3: BY YEAR */}
      {selectedTab === 'byYear' && (
        <Box>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              bgcolor: 'background.paper',
              p: 2,
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
              mb: 3,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" fontWeight={600} color="text.secondary">
                Financial Year:
              </Typography>
              <TextField
                select
                size="small"
                value={selectedFy}
                onChange={(e) => setSelectedFy(e.target.value)}
                sx={{ minWidth: 160 }}
              >
                <MenuItem value="all">All Years</MenuItem>
                {financialYears.map((fy) => (
                  <MenuItem key={fy} value={fy}>
                    FY {fy}
                  </MenuItem>
                ))}
              </TextField>
            </Box>

            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" color="text.secondary">
                Total Dividend in FY
              </Typography>
              <Typography variant="h6" fontWeight={700} color="#00b894">
                ₹ {yearTotalEarned.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
          </Box>

          <Paper
            elevation={0}
            sx={{
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
              overflow: 'hidden',
            }}
          >
            <TableContainer>
              <Table sx={{ minWidth: 650 }}>
                <TableHead>
                  <TableRow sx={{ bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
                    <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>Date</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>Name</TableCell>
                    <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>Dividend / Share</TableCell>
                    <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>Quantity</TableCell>
                    <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 600, py: 1.8 }}>Dividend Paid</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {yearFilteredPayouts.length > 0 ? (
                    yearFilteredPayouts.map((row: any) => (
                      <TableRow key={row.id} hover sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                        <TableCell sx={{ py: 1.6, color: 'text.secondary' }}>
                          {formatDate(row.payment_date || row.ex_date)}
                        </TableCell>
                        <TableCell sx={{ py: 1.6, fontWeight: 500 }}>
                          {row.company_name || row.symbol}
                        </TableCell>
                        <TableCell align="right" sx={{ py: 1.6 }}>
                          {row.dividend_per_share > 0 ? `₹${parseFloat(row.dividend_per_share).toFixed(2)}` : '—'}
                        </TableCell>
                        <TableCell align="right" sx={{ py: 1.6 }}>
                          {row.quantity > 0 ? row.quantity.toLocaleString('en-IN') : '—'}
                        </TableCell>
                        <TableCell align="right" sx={{ py: 1.6, fontWeight: 600, color: '#00b894' }}>
                          {formatCurrency(row.net_dividend || row.total_dividend)}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                        No dividends recorded for this financial year.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Box>
      )}

      {/* Universal Import Statement Dialog */}
      <ImportDividendsDialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onSuccess={(count) => {
          setNotification({
            open: true,
            message: `Successfully imported ${count} dividend records!`,
            severity: 'success',
          });
        }}
      />

      {/* Manual Record Dividend Dialog */}
      <RecordDividendDialog open={recordDialogOpen} onClose={() => setRecordDialogOpen(false)} />

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmId !== null} onClose={() => setDeleteConfirmId(null)}>
        <DialogTitle sx={{ fontWeight: 700 }}>Delete Dividend Record?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to remove this dividend record? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteConfirmId(null)} color="inherit" disabled={deleteMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (deleteConfirmId !== null) deleteMutation.mutate(deleteConfirmId);
            }}
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Notifications */}
      <Snackbar
        open={notification.open}
        autoHideDuration={5000}
        onClose={() => setNotification((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={notification.severity} onClose={() => setNotification((prev) => ({ ...prev, open: false }))}>
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
