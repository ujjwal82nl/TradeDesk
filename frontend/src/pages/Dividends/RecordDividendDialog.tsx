import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  MenuItem,
  CircularProgress,
  Autocomplete,
  Typography,
  Alert,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { formatBrokerAccountLabel } from '../../utils/formatters';

interface RecordDividendDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function RecordDividendDialog({ open, onClose }: RecordDividendDialogProps) {
  const queryClient = useQueryClient();

  const [brokerAccountId, setBrokerAccountId] = useState<number | ''>('');
  const [symbol, setSymbol] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [isin, setIsin] = useState('');
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [exDate, setExDate] = useState('');
  const [quantity, setQuantity] = useState<string>('1');
  const [dps, setDps] = useState<string>('0');
  const [grossDividend, setGrossDividend] = useState<string>('0');
  const [taxDeducted, setTaxDeducted] = useState<string>('0');
  const [netDividend, setNetDividend] = useState<string>('0');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch broker accounts
  const { data: accounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then((r) => r.data ?? []),
    enabled: open,
  });

  // Fetch current holdings for quick symbol autocompletion
  const { data: holdings = [] } = useQuery({
    queryKey: ['holdings'],
    queryFn: () => api.get('/holdings').then((r) => r.data ?? []),
    enabled: open,
  });

  // Auto-select first broker account if none selected
  useEffect(() => {
    if (open && accounts.length > 0 && !brokerAccountId) {
      setBrokerAccountId(accounts[0].id);
    }
  }, [open, accounts, brokerAccountId]);

  // Recalculate gross and net dividend when qty or dps changes
  const handleQtyChange = (val: string) => {
    setQuantity(val);
    const q = parseFloat(val) || 0;
    const d = parseFloat(dps) || 0;
    const gross = (q * d).toFixed(2);
    setGrossDividend(gross);
    const tax = parseFloat(taxDeducted) || 0;
    setNetDividend((parseFloat(gross) - tax).toFixed(2));
  };

  const handleDpsChange = (val: string) => {
    setDps(val);
    const q = parseFloat(quantity) || 0;
    const d = parseFloat(val) || 0;
    const gross = (q * d).toFixed(2);
    setGrossDividend(gross);
    const tax = parseFloat(taxDeducted) || 0;
    setNetDividend((parseFloat(gross) - tax).toFixed(2));
  };

  const handleGrossChange = (val: string) => {
    setGrossDividend(val);
    const gross = parseFloat(val) || 0;
    const tax = parseFloat(taxDeducted) || 0;
    setNetDividend((gross - tax).toFixed(2));
  };

  const handleTaxChange = (val: string) => {
    setTaxDeducted(val);
    const gross = parseFloat(grossDividend) || 0;
    const tax = parseFloat(val) || 0;
    setNetDividend((gross - tax).toFixed(2));
  };

  const createMutation = useMutation({
    mutationFn: (payload: any) => api.post('/dividends', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['div-monthly'] });
      queryClient.invalidateQueries({ queryKey: ['div-stock'] });
      queryClient.invalidateQueries({ queryKey: ['div-broker'] });
      queryClient.invalidateQueries({ queryKey: ['div-calendar'] });
      onClose();
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || 'Failed to record dividend.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brokerAccountId) {
      setErrorMsg('Please select a broker account.');
      return;
    }
    if (!symbol.trim()) {
      setErrorMsg('Please enter a stock symbol.');
      return;
    }
    setErrorMsg(null);

    createMutation.mutate({
      broker_account_id: Number(brokerAccountId),
      symbol: symbol.trim().toUpperCase(),
      company_name: companyName.trim() || undefined,
      isin: isin.trim() || undefined,
      payment_date: paymentDate || undefined,
      ex_date: exDate || undefined,
      quantity: parseFloat(quantity) || 1,
      dividend_per_share: parseFloat(dps) || 0,
      total_dividend: parseFloat(grossDividend) || 0,
      tax_deducted: parseFloat(taxDeducted) || 0,
      net_dividend: parseFloat(netDividend) || parseFloat(grossDividend) || 0,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>Record Dividend</DialogTitle>
        <DialogContent dividers>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {errorMsg}
            </Alert>
          )}

          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Record dividends received directly into your linked bank account or credited via corporate actions.
          </Typography>

          <Grid container spacing={2}>
            {/* Broker Account */}
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                label="Broker Account"
                size="small"
                value={brokerAccountId}
                onChange={(e) => setBrokerAccountId(Number(e.target.value))}
                required
              >
                {accounts.map((acc: any) => (
                  <MenuItem key={acc.id} value={acc.id}>
                    {formatBrokerAccountLabel(acc)}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>

            {/* Stock Symbol with holding autocompletion */}
            <Grid item xs={12} sm={6}>
              <Autocomplete
                freeSolo
                options={holdings.map((h: any) => h.symbol)}
                value={symbol}
                onInputChange={(_, newVal) => {
                  setSymbol(newVal);
                  const match = holdings.find(
                    (h: any) => h.symbol.toUpperCase() === newVal.trim().toUpperCase()
                  );
                  if (match) {
                    if (match.company_name) setCompanyName(match.company_name);
                    if (match.isin) setIsin(match.isin);
                    if (match.quantity) setQuantity(String(match.quantity));
                  }
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Stock Symbol"
                    size="small"
                    required
                    placeholder="e.g. TCS, INFY, TATAGOLD"
                  />
                )}
              />
            </Grid>

            {/* Company Name */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Company Name"
                size="small"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Tata Consultancy Services"
              />
            </Grid>

            {/* Payment Date */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Payment Date"
                type="date"
                size="small"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                required
              />
            </Grid>

            {/* Ex-Dividend Date */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Ex-Dividend Date"
                type="date"
                size="small"
                value={exDate}
                onChange={(e) => setExDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            {/* Quantity */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Eligible Quantity"
                type="number"
                size="small"
                value={quantity}
                onChange={(e) => handleQtyChange(e.target.value)}
                inputProps={{ step: 'any', min: '0' }}
              />
            </Grid>

            {/* Dividend Per Share */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Dividend Per Share (₹)"
                type="number"
                size="small"
                value={dps}
                onChange={(e) => handleDpsChange(e.target.value)}
                inputProps={{ step: 'any', min: '0' }}
              />
            </Grid>

            {/* Gross Dividend */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Gross Dividend (₹)"
                type="number"
                size="small"
                value={grossDividend}
                onChange={(e) => handleGrossChange(e.target.value)}
                inputProps={{ step: 'any', min: '0' }}
                required
              />
            </Grid>

            {/* TDS / Tax */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="TDS / Tax (₹)"
                type="number"
                size="small"
                value={taxDeducted}
                onChange={(e) => handleTaxChange(e.target.value)}
                inputProps={{ step: 'any', min: '0' }}
              />
            </Grid>

            {/* Net Received */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Net Received (₹)"
                type="number"
                size="small"
                value={netDividend}
                onChange={(e) => setNetDividend(e.target.value)}
                inputProps={{ step: 'any', min: '0' }}
                required
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={onClose} color="inherit" disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={createMutation.isPending}
            startIcon={createMutation.isPending ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {createMutation.isPending ? 'Saving...' : 'Save Dividend'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
