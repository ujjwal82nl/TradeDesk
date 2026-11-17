import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import RefreshIcon from '@mui/icons-material/Refresh';
import StorageIcon from '@mui/icons-material/Storage';
import { useQuery } from '@tanstack/react-query';

import { api } from '../../api/client';
import BrokerChip from '../../components/common/BrokerChip';
import PnLCell from '../../components/common/PnLCell';
import { formatCurrency } from '../../utils/formatters';

interface TradeLotsDialogProps {
  open: boolean;
  onClose: () => void;
  holdingId?: number | null;
  symbol?: string | null;
  brokerName?: string | null;
}

export default function TradeLotsDialog({
  open,
  onClose,
  holdingId,
  symbol,
  brokerName,
}: TradeLotsDialogProps) {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const fetchLots = async (force: boolean = false) => {
    if (holdingId) {
      const res = await api.get(`/holdings/${holdingId}/lots${force ? '?force_refresh=true' : ''}`);
      return res.data;
    }
    if (symbol) {
      const res = await api.get(`/holdings/lots/by-symbol/${symbol}${force ? '?force_refresh=true' : ''}`);
      return Array.isArray(res.data) && res.data.length > 0 ? res.data[0] : null;
    }
    return null;
  };

  // Fetch lots: reads directly from PostgreSQL for zero-latency instant display
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['holding-lots', holdingId, symbol],
    queryFn: () => fetchLots(false),
    enabled: open && Boolean(holdingId || symbol),
    staleTime: Infinity,
  });

  const handleForceRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchLots(true);
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Date only: "28 Oct 2026"
  const formatDateOnly = (dateStr: string) => {
    if (!dateStr || dateStr === 'Opening Balance') return dateStr;
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  // Full timestamp for hover tooltip: "28 Oct 2026, 03:00 pm"
  const formatFullTimestamp = (dateStr: string) => {
    if (!dateStr || dateStr === 'Opening Balance') return dateStr;
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const datePart = d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
      const timePart = d.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      });
      return `${datePart}, ${timePart.toLowerCase()}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          p: 0.5,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 40,
              height: 40,
              borderRadius: 2,
              bgcolor: 'primary.light',
              color: 'primary.main',
              opacity: 0.9,
            }}
          >
            <ReceiptLongIcon />
          </Box>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="h6" fontWeight={700}>
                {data?.symbol || symbol || 'Holding Trade Lots'}
              </Typography>
              {(data?.broker_name || brokerName) && (
                <BrokerChip broker={data?.broker_name || brokerName || ''} />
              )}
              {data?.supports_historical_trades && (
                <Chip
                  icon={<StorageIcon sx={{ fontSize: '0.75rem !important' }} />}
                  label="Local DB"
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary' }}
                />
              )}
            </Box>
            {data?.isin && (
              <Typography variant="caption" color="text.secondary">
                ISIN: {data.isin}
              </Typography>
            )}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title="Force re-sync trades from broker">
            <span>
              <IconButton onClick={handleForceRefresh} disabled={isLoading || isRefreshing} size="small">
                <RefreshIcon className={isRefreshing ? 'spin' : ''} fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ py: 2.5 }}>
        {isLoading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6, gap: 2 }}>
            <CircularProgress size={36} />
            <Typography variant="body2" color="text.secondary">
              Reconstructing open trade lots using FIFO execution history...
            </Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Failed to load trade lots: {(error as any)?.message || 'Unknown error'}
          </Alert>
        )}

        {!isLoading && data && (
          <>
            {/* Quick Metrics Header */}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
                gap: 2,
                p: 2,
                mb: 2.5,
                bgcolor: 'action.hover',
                borderRadius: 2,
              }}
            >
              <Box>
                <Typography variant="caption" color="text.secondary">
                  HELD QUANTITY
                </Typography>
                <Typography variant="subtitle1" fontWeight={700}>
                  {data.total_quantity?.toLocaleString('en-IN')} shares
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  AVERAGE COST
                </Typography>
                <Typography variant="subtitle1" fontWeight={700}>
                  {formatCurrency(data.average_cost)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  CURRENT LTP
                </Typography>
                <Typography variant="subtitle1" fontWeight={700}>
                  {formatCurrency(data.current_price)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  UNREALIZED P&L
                </Typography>
                <PnLCell value={data.total_pnl} percent={data.total_pnl_percent} />
              </Box>
            </Box>

            {!data.supports_historical_trades ? (
              <Alert severity="info" icon={<InfoOutlinedIcon />} sx={{ borderRadius: 2 }}>
                {data.message ||
                  `Historical trade history is not supported via API by ${data.broker_name}. Only consolidated holding summary is available.`}
              </Alert>
            ) : data.lots?.length === 0 ? (
              <Alert severity="info" sx={{ borderRadius: 2 }}>
                No active open buy lots found for this holding in available trade history.
              </Alert>
            ) : (
              <>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                  <Typography variant="subtitle2" fontWeight={700}>
                    Open Buy Executions ({data.lots.length} {data.lots.length === 1 ? 'Lot' : 'Lots'})
                  </Typography>
                  <Chip
                    label="FIFO Matched"
                    size="small"
                    color="success"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
                  />
                </Box>

                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                  These are the exact unsettled/unsold buy orders that formed your current holding quantity.
                  Past sell orders have already been matched and cleared against earlier buys.
                </Typography>

                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, overflowX: 'auto' }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: 'action.hover' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem' }}>TRADE DATE</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          OPEN QTY
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          BUY PRICE
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          INVESTED
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          CURRENT VALUE
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          LOT P&L
                        </TableCell>
                        <TableCell align="center" sx={{ fontWeight: 700, fontSize: '0.75rem' }}>
                          ORDER ID
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.lots.map((lot: any, idx: number) => {
                        const isSell = lot.transaction_type?.toUpperCase() === 'SELL';
                        return (
                          <TableRow
                            key={lot.trade_id || idx}
                            sx={{
                              '&:last-child td, &:last-child th': { border: 0 },
                              bgcolor: lot.is_opening_lot ? 'action.hover' : 'inherit',
                            }}
                          >
                            <TableCell>
                              <Tooltip
                                title={
                                  lot.trade_date === 'Opening Balance'
                                    ? 'Opening balance lot'
                                    : formatFullTimestamp(lot.trade_date)
                                }
                                arrow
                                placement="top"
                              >
                                <Box sx={{ cursor: 'pointer', display: 'inline-block' }}>
                                  <Typography variant="body2" fontWeight={600} fontSize="0.82rem">
                                    {formatDateOnly(lot.trade_date)}
                                  </Typography>
                                  {lot.holding_days !== undefined && lot.trade_date !== 'Opening Balance' && (
                                    <Typography variant="caption" color="text.secondary" display="block">
                                      {lot.holding_days === 0
                                        ? 'Today'
                                        : `${lot.holding_days} ${lot.holding_days === 1 ? 'day' : 'days'} ago`}
                                    </Typography>
                                  )}
                                  {lot.notes && (
                                    <Typography variant="caption" color="info.main" display="block">
                                      {lot.notes}
                                    </Typography>
                                  )}
                                </Box>
                              </Tooltip>
                            </TableCell>
                            <TableCell align="right">
                              <Typography
                                variant="body2"
                                fontWeight={700}
                                sx={{
                                  color: isSell ? 'error.main' : 'success.main',
                                }}
                              >
                                {isSell ? '-' : '+'}
                                {lot.quantity?.toLocaleString('en-IN')}
                              </Typography>
                              {lot.original_quantity && lot.original_quantity > lot.quantity && (
                                <Typography variant="caption" color="text.secondary" display="block">
                                  (of {lot.original_quantity})
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" fontWeight={600}>
                                {formatCurrency(lot.price)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" color="text.secondary">
                                {formatCurrency(lot.amount)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" fontWeight={600}>
                                {formatCurrency(lot.current_value)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <PnLCell value={lot.pnl} percent={lot.pnl_percent} />
                            </TableCell>
                            <TableCell align="center">
                              {lot.order_id && lot.order_id !== 'PRE_API_HISTORY' ? (
                                <Tooltip title={copiedId === lot.order_id ? 'Copied!' : 'Click to copy Order ID'}>
                                  <Chip
                                    label={lot.order_id}
                                    size="small"
                                    onClick={() => handleCopy(lot.order_id)}
                                    icon={
                                      copiedId === lot.order_id ? (
                                        <CheckCircleOutlineIcon sx={{ fontSize: '0.9rem !important' }} />
                                      ) : (
                                        <ContentCopyIcon sx={{ fontSize: '0.8rem !important' }} />
                                      )
                                    }
                                    variant="outlined"
                                    sx={{
                                      height: 22,
                                      fontSize: '0.65rem',
                                      fontFamily: 'monospace',
                                      cursor: 'pointer',
                                    }}
                                  />
                                </Tooltip>
                              ) : (
                                <Typography variant="caption" color="text.secondary">
                                  —
                                </Typography>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 1.5 }}>
        <Button onClick={onClose} variant="outlined" sx={{ textTransform: 'none' }}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

