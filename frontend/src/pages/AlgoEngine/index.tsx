import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Button,
  Chip,
  Grid,
  Card,
  CardContent,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import StopIcon from '@mui/icons-material/Stop';
import SaveIcon from '@mui/icons-material/Save';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AutoModeIcon from '@mui/icons-material/AutoMode';
import TuneIcon from '@mui/icons-material/Tune';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SecurityIcon from '@mui/icons-material/Security';
import LayersIcon from '@mui/icons-material/Layers';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';

import { api } from '../../api/client';
import { formatBrokerAccountLabel } from '../../utils/formatters';

// ---------------------------------------------------------------------------
// Constants & Types
// ---------------------------------------------------------------------------

const UNDERLYING_OPTIONS = [
  { value: 'NIFTY', label: 'NIFTY 50 (Index)', lotSize: 25 },
  { value: 'BANKNIFTY', label: 'BANK NIFTY (Index)', lotSize: 15 },
  { value: 'FINNIFTY', label: 'FIN NIFTY (Index)', lotSize: 25 },
  { value: 'MIDCPNIFTY', label: 'MIDCP NIFTY (Index)', lotSize: 50 },
  { value: 'SENSEX', label: 'SENSEX (BSE Index)', lotSize: 10 },
  { value: 'RELIANCE', label: 'RELIANCE (Equity)', lotSize: 250 },
  { value: 'HDFCBANK', label: 'HDFCBANK (Equity)', lotSize: 550 },
  { value: 'TATAPOWER', label: 'TATAPOWER (Equity)', lotSize: 1650 },
];

export interface StrategyLeg {
  leg_id: number;
  action: 'BUY' | 'SELL';
  instrument_type: 'CE' | 'PE' | 'EQ';
  strike_offset: number;
  lots: number;
  sl_pct?: number;
  sl_pts?: number;
  tp_pct?: number;
  tp_pts?: number;
}

export interface StrategyFormState {
  id?: number;
  name: string;
  description: string;
  template_type: string;
  underlying: string;
  broker_account_id: number | '';
  is_active: boolean;
  mode: 'LIVE' | 'PAPER';
  product_type: 'MIS' | 'NRML' | 'CNC';
  entry_params: {
    entry_time: string;
    no_entry_after: string;
    strike_type: 'ATM' | 'OTM' | 'ITM' | 'PREMIUM';
    strike_offset: number;
    spot_range_min?: number | '';
    spot_range_max?: number | '';
    indicator?: string;
    fast_ema?: number;
    slow_ema?: number;
    use_vwap?: boolean;
    candle_timeframe?: string;
  };
  exit_params: {
    sl_type: 'PERCENT' | 'POINTS' | 'MTM';
    sl_value: number;
    tp_type: 'PERCENT' | 'POINTS' | 'MTM';
    tp_value: number;
    trailing_sl: boolean;
    trail_trigger: number;
    trail_step: number;
    squareoff_time: string;
    max_daily_loss: number;
  };
  legs: StrategyLeg[];
}

const DEFAULT_STRATEGY: StrategyFormState = {
  name: '9:20 Intraday Straddle',
  description: 'Sells ATM Call and Put at 09:20 AM with 25% SL per leg and square-off at 15:15 PM.',
  template_type: 'TIME_BASED_STRADDLE',
  underlying: 'NIFTY',
  broker_account_id: '',
  is_active: false,
  mode: 'LIVE',
  product_type: 'MIS',
  entry_params: {
    entry_time: '09:20:00',
    no_entry_after: '14:30:00',
    strike_type: 'ATM',
    strike_offset: 0,
    indicator: 'NONE',
  },
  exit_params: {
    sl_type: 'PERCENT',
    sl_value: 25.0,
    tp_type: 'PERCENT',
    tp_value: 50.0,
    trailing_sl: true,
    trail_trigger: 10.0,
    trail_step: 5.0,
    squareoff_time: '15:15:00',
    max_daily_loss: 5000.0,
  },
  legs: [
    { leg_id: 1, action: 'SELL', instrument_type: 'CE', strike_offset: 0, lots: 1, sl_pct: 25, tp_pct: 50 },
    { leg_id: 2, action: 'SELL', instrument_type: 'PE', strike_offset: 0, lots: 1, sl_pct: 25, tp_pct: 50 },
  ],
};

const STATUS_COLOR: Record<string, any> = { RUNNING: 'success', STOPPED: 'default', ERROR: 'error', COMPLETED: 'primary' };
const MODE_COLOR: Record<string, any> = { PAPER: 'info', LIVE: 'error', BACKTEST: 'secondary' };

const runCols: GridColDef[] = [
  { field: 'name', headerName: 'Name', width: 200 },
  { field: 'mode', headerName: 'Mode', width: 100, renderCell: p => <Chip size="small" label={p.value} color={MODE_COLOR[p.value] ?? 'default'} /> },
  { field: 'status', headerName: 'Status', width: 110, renderCell: p => <Chip size="small" label={p.value} color={STATUS_COLOR[p.value] ?? 'default'} /> },
  { field: 'started_at', headerName: 'Started', width: 180, renderCell: p => p.value ? new Date(p.value).toLocaleString('en-IN') : '—' },
  { field: 'stopped_at', headerName: 'Stopped', width: 180, renderCell: p => p.value ? new Date(p.value).toLocaleString('en-IN') : '—' },
];

const signalCols: GridColDef[] = [
  { field: 'created_at', headerName: 'Time', width: 180, renderCell: p => new Date(p.value).toLocaleString('en-IN') },
  { field: 'symbol', headerName: 'Symbol', width: 140, renderCell: p => <strong>{p.value}</strong> },
  { field: 'signal_type', headerName: 'Signal', width: 100, renderCell: p => <Chip size="small" label={p.value} color={p.value === 'BUY' ? 'success' : p.value === 'SELL' ? 'error' : 'default'} /> },
  { field: 'price', headerName: 'Price', width: 110, renderCell: p => `₹${p.value}` },
  { field: 'quantity', headerName: 'Qty', width: 90 },
  { field: 'strategy_name', headerName: 'Strategy', width: 180 },
  { field: 'executed', headerName: 'Executed', width: 100, renderCell: p => <Chip size="small" label={p.value ? 'Executed' : 'Pending'} color={p.value ? 'success' : 'default'} /> },
];

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AlgoEngine() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState(0);

  // Queries
  const { data: templates } = useQuery({
    queryKey: ['algo-templates'],
    queryFn: () => api.get('/algo/templates').then(r => r.data ?? []),
  });

  const { data: strategies } = useQuery({
    queryKey: ['algo-strategies'],
    queryFn: () => api.get('/algo/strategies').then(r => r.data ?? []),
  });

  const { data: brokerAccounts } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then(r => r.data ?? []),
  });

  const { data: runs, isLoading: loadRuns } = useQuery({
    queryKey: ['algo-runs'],
    queryFn: () => api.get('/algo/runs').then(r => r.data ?? []),
    enabled: activeTab === 1,
  });

  const { data: signals, isLoading: loadSignals } = useQuery({
    queryKey: ['algo-signals'],
    queryFn: () => api.get('/algo/signals').then(r => r.data ?? []),
    enabled: activeTab === 2,
  });

  // Selected Strategy State
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | 'new'>('new');
  const [form, setForm] = useState<StrategyFormState>(DEFAULT_STRATEGY);

  // Snackbar notifications
  const [snack, setSnack] = useState<{ open: boolean; message: string; severity: 'success' | 'info' | 'error' | 'warning' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Delete & Kill Switch Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [killDialogOpen, setKillDialogOpen] = useState(false);

  // Auto-select broker if available
  useEffect(() => {
    if (brokerAccounts && brokerAccounts.length > 0 && form.broker_account_id === '') {
      setForm(f => ({ ...f, broker_account_id: brokerAccounts[0].id }));
    }
  }, [brokerAccounts, form.broker_account_id]);

  // When selected strategy dropdown changes
  const handleStrategyChange = (idOrNew: number | 'new') => {
    setSelectedStrategyId(idOrNew);
    if (idOrNew === 'new') {
      setForm({
        ...DEFAULT_STRATEGY,
        broker_account_id: brokerAccounts?.[0]?.id ?? '',
      });
    } else {
      const found = (strategies ?? []).find((s: any) => s.id === idOrNew);
      if (found) {
        setForm({
          id: found.id,
          name: found.name,
          description: found.description || '',
          template_type: found.template_type || 'CUSTOM',
          underlying: found.underlying || 'NIFTY',
          broker_account_id: found.broker_account_id || (brokerAccounts?.[0]?.id ?? ''),
          is_active: Boolean(found.is_active),
          mode: found.mode || 'LIVE',
          product_type: found.product_type || 'MIS',
          entry_params: { ...DEFAULT_STRATEGY.entry_params, ...(found.entry_params || {}) },
          exit_params: { ...DEFAULT_STRATEGY.exit_params, ...(found.exit_params || {}) },
          legs: found.legs && found.legs.length > 0 ? found.legs : DEFAULT_STRATEGY.legs,
        });
      }
    }
  };

  // Applying a preset template
  const handleApplyTemplate = (tmpl: any) => {
    setForm(prev => ({
      ...prev,
      name: tmpl.title,
      description: tmpl.description,
      template_type: tmpl.template_id,
      underlying: tmpl.default_underlying,
      product_type: tmpl.default_product || 'MIS',
      entry_params: { ...prev.entry_params, ...tmpl.entry_params },
      exit_params: { ...prev.exit_params, ...tmpl.exit_params },
      legs: tmpl.legs || prev.legs,
    }));
    setSnack({
      open: true,
      message: `Loaded template: ${tmpl.title}`,
      severity: 'info',
    });
  };

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (form.id) {
        return api.put(`/algo/strategies/${form.id}`, form);
      } else {
        return api.post('/algo/strategies', form);
      }
    },
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ['algo-strategies'] });
      const saved = resp.data;
      if (saved?.id) {
        setSelectedStrategyId(saved.id);
        setForm(f => ({ ...f, id: saved.id }));
      }
      setSnack({ open: true, message: 'Strategy configuration saved successfully!', severity: 'success' });
    },
    onError: (err: any) => {
      setSnack({ open: true, message: err.response?.data?.detail || 'Failed to save strategy.', severity: 'error' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => api.delete(`/algo/strategies/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['algo-strategies'] });
      setDeleteDialogOpen(false);
      handleStrategyChange('new');
      setSnack({ open: true, message: 'Strategy deleted.', severity: 'info' });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async (id: number) => api.post(`/algo/strategies/${id}/toggle-active`),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ['algo-strategies'] });
      const updated = resp.data;
      setForm(f => ({ ...f, is_active: updated.is_active }));
      setSnack({
        open: true,
        message: updated.is_active ? 'Strategy is now ACTIVE for live trading!' : 'Strategy deactivated.',
        severity: updated.is_active ? 'success' : 'info',
      });
    },
  });

  const killSwitchMutation = useMutation({
    mutationFn: async (id: number) => api.post(`/algo/strategies/${id}/kill-switch`),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ['algo-strategies'] });
      setKillDialogOpen(false);
      setForm(f => ({ ...f, is_active: false }));
      setSnack({
        open: true,
        message: resp.data.message || 'Kill switch activated! Strategy stopped.',
        severity: 'warning',
      });
    },
  });

  const stopRunMutation = useMutation({
    mutationFn: (id: number) => api.post(`/algo/runs/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['algo-runs'] }),
  });

  // Leg management helpers
  const handleAddLeg = () => {
    const newId = form.legs.length > 0 ? Math.max(...form.legs.map(l => l.leg_id)) + 1 : 1;
    setForm(f => ({
      ...f,
      legs: [
        ...f.legs,
        { leg_id: newId, action: 'BUY', instrument_type: 'CE', strike_offset: 0, lots: 1, sl_pct: 25, tp_pct: 50 },
      ],
    }));
  };

  const handleRemoveLeg = (legId: number) => {
    setForm(f => ({
      ...f,
      legs: f.legs.filter(l => l.leg_id !== legId),
    }));
  };

  const handleLegChange = (legId: number, field: keyof StrategyLeg, value: any) => {
    setForm(f => ({
      ...f,
      legs: f.legs.map(l => (l.leg_id === legId ? { ...l, [field]: value } : l)),
    }));
  };

  // Duplicate strategy
  const handleDuplicate = () => {
    setForm(f => ({
      ...f,
      id: undefined,
      name: `${f.name} (Copy)`,
      is_active: false,
    }));
    setSelectedStrategyId('new');
    setSnack({ open: true, message: 'Strategy cloned as a new draft. Click Save to persist.', severity: 'info' });
  };

  const runRows = (Array.isArray(runs) ? runs : []).map((r: any, i: number) => ({ ...r, id: r.id ?? i }));
  const signalRows = (Array.isArray(signals) ? signals : []).map((s: any, i: number) => ({ ...s, id: s.id ?? i }));

  return (
    <Box sx={{ pb: 6 }}>
      {/* Page Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h5" fontWeight={700}>Algo Engine</Typography>
          <Typography variant="body2" color="text.secondary">
            Configure multi-leg options & technical indicator trading strategies with direct live broker execution.
          </Typography>
        </Box>
      </Box>

      {/* Navigation Tabs */}
      <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3 }}>
        <Tab icon={<TuneIcon />} iconPosition="start" label="Strategy Configurator" />
        <Tab icon={<AutoModeIcon />} iconPosition="start" label="Execution Runs" />
        <Tab icon={<LayersIcon />} iconPosition="start" label="Trade Signals" />
        <Tab icon={<AccessTimeIcon />} iconPosition="start" label="Backtesting" />
      </Tabs>

      {/* TAB 0: STRATEGY CONFIGURATOR */}
      {activeTab === 0 && (
        <Box>
          {/* Top Control Toolbar */}
          <Paper
            elevation={0}
            sx={{
              p: 2.5,
              mb: 3,
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 2,
            }}
          >
            <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
              <FormControl size="small" sx={{ minWidth: 260 }}>
                <InputLabel>Select Strategy</InputLabel>
                <Select
                  value={selectedStrategyId}
                  label="Select Strategy"
                  onChange={e => handleStrategyChange(e.target.value as any)}
                >
                  <MenuItem value="new">
                    <em>➕ Create New Strategy</em>
                  </MenuItem>
                  {(strategies ?? []).map((s: any) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.name} {s.is_active ? '🟢 (Active)' : '⚪'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Chip
                label={form.is_active ? 'LIVE & ACTIVE' : 'INACTIVE / DRAFT'}
                color={form.is_active ? 'success' : 'default'}
                variant={form.is_active ? 'filled' : 'outlined'}
                sx={{ fontWeight: 700 }}
              />
            </Box>

            <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
              {form.id && (
                <FormControlLabel
                  control={
                    <Switch
                      checked={form.is_active}
                      onChange={() => toggleActiveMutation.mutate(form.id!)}
                      color="success"
                    />
                  }
                  label={form.is_active ? 'Active' : 'Paused'}
                  sx={{ mr: 1 }}
                />
              )}

              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => handleStrategyChange('new')}
              >
                New
              </Button>

              <Button
                variant="outlined"
                size="small"
                startIcon={<ContentCopyIcon />}
                onClick={handleDuplicate}
              >
                Duplicate
              </Button>

              {form.id && (
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<DeleteOutlineIcon />}
                  onClick={() => setDeleteDialogOpen(true)}
                >
                  Delete
                </Button>
              )}

              <Button
                variant="contained"
                size="small"
                startIcon={<SaveIcon />}
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
              >
                {saveMutation.isPending ? 'Saving...' : 'Save Strategy'}
              </Button>
            </Box>
          </Paper>

          {/* Quick Preset Templates Section */}
          <Box mb={3}>
            <Typography variant="subtitle2" color="text.secondary" fontWeight={600} mb={1.2}>
              PRESET TEMPLATES (1-CLICK LOAD & CUSTOMIZE)
            </Typography>
            <Grid container spacing={1.5}>
              {(templates ?? []).map((t: any) => (
                <Grid item xs={12} sm={6} md={2.4} key={t.template_id}>
                  <Card
                    variant="outlined"
                    sx={{
                      cursor: 'pointer',
                      borderRadius: 2.5,
                      transition: 'all 0.2s',
                      borderColor: form.template_type === t.template_id ? 'primary.main' : 'divider',
                      bgcolor: form.template_type === t.template_id ? 'action.selected' : 'background.paper',
                      '&:hover': { borderColor: 'primary.main', transform: 'translateY(-2px)' },
                      height: '100%',
                    }}
                    onClick={() => handleApplyTemplate(t)}
                  >
                    <CardContent sx={{ p: 1.8, '&:last-child': { pb: 1.8 } }}>
                      <Chip label={t.category} size="small" variant="outlined" color="primary" sx={{ mb: 1, fontSize: '0.7rem' }} />
                      <Typography variant="subtitle2" fontWeight={700} noWrap>
                        {t.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {t.description}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>

          <Grid container spacing={3}>
            {/* Card 1: Strategy Identity & Broker Route */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                <CardContent sx={{ p: 2.5 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2} display="flex" alignItems="center" gap={1}>
                    <TuneIcon color="primary" fontSize="small" /> Identity & Broker Execution
                  </Typography>

                  <Box display="flex" flexDirection="column" gap={2}>
                    <TextField
                      label="Strategy Name"
                      value={form.name}
                      onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                      fullWidth
                      size="small"
                      required
                    />

                    <TextField
                      label="Description"
                      value={form.description}
                      onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                      multiline
                      rows={2}
                      fullWidth
                      size="small"
                    />

                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <FormControl fullWidth size="small">
                          <InputLabel>Target Broker</InputLabel>
                          <Select
                            value={form.broker_account_id}
                            label="Target Broker"
                            onChange={e => setForm(f => ({ ...f, broker_account_id: e.target.value as any }))}
                          >
                            {(brokerAccounts ?? []).map((acc: any) => (
                              <MenuItem key={acc.id} value={acc.id}>
                                {formatBrokerAccountLabel(acc)}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Grid>

                      <Grid item xs={12} sm={3}>
                        <FormControl fullWidth size="small">
                          <InputLabel>Mode</InputLabel>
                          <Select
                            value={form.mode}
                            label="Mode"
                            onChange={e => setForm(f => ({ ...f, mode: e.target.value as any }))}
                          >
                            <MenuItem value="LIVE">LIVE</MenuItem>
                            <MenuItem value="PAPER">PAPER</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>

                      <Grid item xs={12} sm={3}>
                        <FormControl fullWidth size="small">
                          <InputLabel>Product</InputLabel>
                          <Select
                            value={form.product_type}
                            label="Product"
                            onChange={e => setForm(f => ({ ...f, product_type: e.target.value as any }))}
                          >
                            <MenuItem value="MIS">MIS (Intraday)</MenuItem>
                            <MenuItem value="NRML">NRML (Normal)</MenuItem>
                            <MenuItem value="CNC">CNC (Delivery)</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                    </Grid>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 2: Underlying & Contract Selection */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                <CardContent sx={{ p: 2.5 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2} display="flex" alignItems="center" gap={1}>
                    <LayersIcon color="primary" fontSize="small" /> Underlying & Contract
                  </Typography>

                  <Box display="flex" flexDirection="column" gap={2}>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={8}>
                        <FormControl fullWidth size="small">
                          <InputLabel>Underlying Asset</InputLabel>
                          <Select
                            value={form.underlying}
                            label="Underlying Asset"
                            onChange={e => setForm(f => ({ ...f, underlying: e.target.value }))}
                          >
                            {UNDERLYING_OPTIONS.map(opt => (
                              <MenuItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Grid>

                      <Grid item xs={12} sm={4}>
                        <TextField
                          label="Expiry Preference"
                          value="Current Weekly"
                          size="small"
                          fullWidth
                          disabled
                          helperText="Auto-selects current expiry"
                        />
                      </Grid>
                    </Grid>

                    <Alert severity="info" sx={{ py: 0.5, borderRadius: 2 }}>
                      Live underlying ticks & spot pricing will be queried in real-time from the connected broker account to select ATM strikes dynamically upon trigger.
                    </Alert>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 3: Entry Criteria */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ borderRadius: 3 }}>
                <CardContent sx={{ p: 2.5 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2} display="flex" alignItems="center" gap={1}>
                    <AccessTimeIcon color="primary" fontSize="small" /> Entry Criteria & Schedule
                  </Typography>

                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Entry Time (HH:MM:SS)"
                        value={form.entry_params.entry_time}
                        onChange={e => setForm(f => ({
                          ...f,
                          entry_params: { ...f.entry_params, entry_time: e.target.value },
                        }))}
                        size="small"
                        fullWidth
                        helperText="Strategy executes orders at this exact second"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="No Entry After"
                        value={form.entry_params.no_entry_after}
                        onChange={e => setForm(f => ({
                          ...f,
                          entry_params: { ...f.entry_params, no_entry_after: e.target.value },
                        }))}
                        size="small"
                        fullWidth
                        helperText="No orders triggered past this time"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <FormControl fullWidth size="small">
                        <InputLabel>Strike Selection</InputLabel>
                        <Select
                          value={form.entry_params.strike_type}
                          label="Strike Selection"
                          onChange={e => setForm(f => ({
                            ...f,
                            entry_params: { ...f.entry_params, strike_type: e.target.value as any },
                          }))}
                        >
                          <MenuItem value="ATM">ATM (At The Money)</MenuItem>
                          <MenuItem value="OTM">OTM (Out of The Money)</MenuItem>
                          <MenuItem value="ITM">ITM (In The Money)</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Strike Offset (Points)"
                        type="number"
                        value={form.entry_params.strike_offset}
                        onChange={e => setForm(f => ({
                          ...f,
                          entry_params: { ...f.entry_params, strike_offset: Number(e.target.value) },
                        }))}
                        size="small"
                        fullWidth
                        helperText="E.g. 0 for ATM, +100 for OTM, -100 for ITM"
                      />
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 4: Exit & Risk Criteria */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ borderRadius: 3 }}>
                <CardContent sx={{ p: 2.5 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2} display="flex" alignItems="center" gap={1}>
                    <SecurityIcon color="primary" fontSize="small" /> Exit & Risk Management
                  </Typography>

                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Stop Loss (SL % per leg)"
                        type="number"
                        value={form.exit_params.sl_value}
                        onChange={e => setForm(f => ({
                          ...f,
                          exit_params: { ...f.exit_params, sl_value: Number(e.target.value) },
                        }))}
                        size="small"
                        fullWidth
                        helperText="Triggers SL order when leg rises by X%"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Target Profit (TP % per leg)"
                        type="number"
                        value={form.exit_params.tp_value}
                        onChange={e => setForm(f => ({
                          ...f,
                          exit_params: { ...f.exit_params, tp_value: Number(e.target.value) },
                        }))}
                        size="small"
                        fullWidth
                        helperText="Triggers profit taking order at X% decay"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Square-off Time"
                        value={form.exit_params.squareoff_time}
                        onChange={e => setForm(f => ({
                          ...f,
                          exit_params: { ...f.exit_params, squareoff_time: e.target.value },
                        }))}
                        size="small"
                        fullWidth
                        helperText="Auto-exits all legs before broker cutoff"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Max Daily Loss (₹)"
                        type="number"
                        value={form.exit_params.max_daily_loss}
                        onChange={e => setForm(f => ({
                          ...f,
                          exit_params: { ...f.exit_params, max_daily_loss: Number(e.target.value) },
                        }))}
                        size="small"
                        fullWidth
                        helperText="Global emergency circuit breaker"
                      />
                    </Grid>

                    <Grid item xs={12}>
                      <Box display="flex" alignItems="center" justifyContent="space-between" p={1} bgcolor="action.hover" borderRadius={2}>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={form.exit_params.trailing_sl}
                              onChange={e => setForm(f => ({
                                ...f,
                                exit_params: { ...f.exit_params, trailing_sl: e.target.checked },
                              }))}
                              size="small"
                            />
                          }
                          label="Enable Trailing Stop Loss"
                        />
                        {form.exit_params.trailing_sl && (
                          <Typography variant="caption" color="text.secondary">
                            Trail SL by {form.exit_params.trail_step}% for every {form.exit_params.trail_trigger}% profit gain
                          </Typography>
                        )}
                      </Box>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 5: Multi-Leg Strategy Breakdown */}
            <Grid item xs={12}>
              <Card variant="outlined" sx={{ borderRadius: 3 }}>
                <CardContent sx={{ p: 2.5 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Box>
                      <Typography variant="subtitle1" fontWeight={700}>
                        Strategy Legs ({form.legs.length} Active Legs)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Orders are routed simultaneously to your broker account in an atomic multi-leg batch upon trigger.
                      </Typography>
                    </Box>
                    <Button size="small" variant="outlined" startIcon={<AddIcon />} onClick={handleAddLeg}>
                      Add Leg
                    </Button>
                  </Box>

                  <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: 'action.hover' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Leg #</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Action</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Option Type</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Strike Offset</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Lots</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Stop Loss (%)</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Target (%)</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {form.legs.map((leg, idx) => (
                          <TableRow key={leg.leg_id}>
                            <TableCell>#{idx + 1}</TableCell>
                            <TableCell>
                              <Select
                                size="small"
                                value={leg.action}
                                onChange={e => handleLegChange(leg.leg_id, 'action', e.target.value)}
                                sx={{ minWidth: 90 }}
                              >
                                <MenuItem value="SELL">SELL</MenuItem>
                                <MenuItem value="BUY">BUY</MenuItem>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <Select
                                size="small"
                                value={leg.instrument_type}
                                onChange={e => handleLegChange(leg.leg_id, 'instrument_type', e.target.value)}
                                sx={{ minWidth: 80 }}
                              >
                                <MenuItem value="CE">CE (Call)</MenuItem>
                                <MenuItem value="PE">PE (Put)</MenuItem>
                                <MenuItem value="EQ">EQ (Stock)</MenuItem>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <TextField
                                size="small"
                                type="number"
                                value={leg.strike_offset}
                                onChange={e => handleLegChange(leg.leg_id, 'strike_offset', Number(e.target.value))}
                                sx={{ width: 110 }}
                                helperText={leg.strike_offset === 0 ? 'ATM' : leg.strike_offset > 0 ? `+${leg.strike_offset}` : leg.strike_offset}
                              />
                            </TableCell>
                            <TableCell>
                              <TextField
                                size="small"
                                type="number"
                                value={leg.lots}
                                onChange={e => handleLegChange(leg.leg_id, 'lots', Math.max(1, Number(e.target.value)))}
                                sx={{ width: 80 }}
                              />
                            </TableCell>
                            <TableCell>
                              <TextField
                                size="small"
                                type="number"
                                value={leg.sl_pct ?? form.exit_params.sl_value}
                                onChange={e => handleLegChange(leg.leg_id, 'sl_pct', Number(e.target.value))}
                                sx={{ width: 90 }}
                              />
                            </TableCell>
                            <TableCell>
                              <TextField
                                size="small"
                                type="number"
                                value={leg.tp_pct ?? form.exit_params.tp_value}
                                onChange={e => handleLegChange(leg.leg_id, 'tp_pct', Number(e.target.value))}
                                sx={{ width: 90 }}
                              />
                            </TableCell>
                            <TableCell align="right">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleRemoveLeg(leg.leg_id)}
                                disabled={form.legs.length <= 1}
                              >
                                <DeleteOutlineIcon fontSize="small" />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>

            {/* Emergency Kill Switch Banner if Strategy is Active */}
            {form.id && (
              <Grid item xs={12}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 2.5,
                    borderRadius: 3,
                    border: '1px solid',
                    borderColor: 'error.main',
                    bgcolor: 'rgba(211, 47, 47, 0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 2,
                  }}
                >
                  <Box display="flex" alignItems="center" gap={1.5}>
                    <WarningAmberIcon color="error" fontSize="large" />
                    <Box>
                      <Typography variant="subtitle1" fontWeight={700} color="error.main">
                        Live Strategy Emergency Controls
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        If market conditions turn volatile, activate the Kill Switch to cancel all unfilled orders, square off all open legs, and immediately halt this algo.
                      </Typography>
                    </Box>
                  </Box>

                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<PowerSettingsNewIcon />}
                    onClick={() => setKillDialogOpen(true)}
                  >
                    Emergency Kill Switch
                  </Button>
                </Paper>
              </Grid>
            )}
          </Grid>
        </Box>
      )}

      {/* TAB 1: EXECUTION RUNS */}
      {activeTab === 1 && (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
          <DataGrid
            rows={runRows}
            columns={[
              ...runCols,
              {
                field: 'actions',
                headerName: 'Actions',
                width: 120,
                renderCell: p =>
                  p.row.status === 'RUNNING' ? (
                    <Button
                      size="small"
                      color="error"
                      startIcon={<StopIcon />}
                      onClick={() => stopRunMutation.mutate(p.row.id)}
                    >
                      Stop
                    </Button>
                  ) : null,
              },
            ]}
            loading={loadRuns}
            autoHeight
            disableRowSelectionOnClick
            pageSizeOptions={[25]}
          />
        </Box>
      )}

      {/* TAB 2: TRADE SIGNALS */}
      {activeTab === 2 && (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
          <DataGrid
            rows={signalRows}
            columns={signalCols}
            loading={loadSignals}
            autoHeight
            disableRowSelectionOnClick
            pageSizeOptions={[25, 50]}
          />
        </Box>
      )}

      {/* TAB 3: BACKTESTING */}
      {activeTab === 3 && (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 6, border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary">📈 Backtesting Simulation Module</Typography>
          <Typography variant="body2" color="text.secondary" mt={1}>
            Phase 4 historical simulation engine — run this exact strategy configuration against 1-minute historical tick data across past expiries.
          </Typography>
        </Box>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle sx={{ fontWeight: 700 }}>Delete Strategy?</DialogTitle>
        <DialogContent>
          Are you sure you want to delete <strong>{form.name}</strong>? This action cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => form.id && deleteMutation.mutate(form.id)}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Kill Switch Confirmation Dialog */}
      <Dialog open={killDialogOpen} onClose={() => setKillDialogOpen(false)}>
        <DialogTitle sx={{ fontWeight: 700, color: 'error.main' }}>
          🚨 Confirm Emergency Kill Switch
        </DialogTitle>
        <DialogContent>
          <Typography mb={1}>
            Are you sure you want to trigger the Kill Switch for <strong>{form.name}</strong>?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This will immediately mark this strategy as INACTIVE, cancel all pending entry/SL orders, and square off all open positions at market price.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setKillDialogOpen(false)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => form.id && killSwitchMutation.mutate(form.id)}
            disabled={killSwitchMutation.isPending}
          >
            {killSwitchMutation.isPending ? 'Executing Kill Switch...' : 'Execute Emergency Kill Switch'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Toast Snackbar */}
      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack(s => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snack.severity} sx={{ width: '100%', borderRadius: 2 }}>
          {snack.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
