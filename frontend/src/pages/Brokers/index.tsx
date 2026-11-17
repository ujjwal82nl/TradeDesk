import React, { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Snackbar,
  Alert,
} from '@mui/material';
import AddIcon    from '@mui/icons-material/Add';
import SyncIcon   from '@mui/icons-material/Sync';
import DeleteIcon from '@mui/icons-material/Delete';
import KeyIcon    from '@mui/icons-material/Key';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

const BROKER_EMOJIS: Record<string, string> = { DHAN: '🔵', ZERODHA: '🟠', INDMONEY: '🟣', IBKR: '🟢', COINDCX: '🪙' };

export default function Brokers() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<any>(null);
  const [newToken, setNewToken] = useState('');
  const [form, setForm] = useState({ broker_id: '', account_id: '', account_name: '', access_token: '' });
  const [notification, setNotification] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
    open: false,
    message: '',
    severity: 'info',
  });

  const { data: providers } = useQuery({ queryKey: ['broker-providers'], queryFn: () => api.get('/brokers').then(r => r.data ?? []) });
  const { data: accounts, isLoading } = useQuery({ queryKey: ['broker-accounts'], queryFn: () => api.get('/brokers/accounts').then(r => r.data ?? []) });

  const connectMutation = useMutation({
    mutationFn: (body: any) => api.post('/brokers/accounts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-accounts'] });
      setOpen(false);
      setNotification({ open: true, message: 'Broker account connected successfully!', severity: 'success' });
    },
    onError: (err: any) => {
      setNotification({ open: true, message: err.response?.data?.detail || 'Failed to connect broker account.', severity: 'error' });
    },
  });

  const updateTokenMutation = useMutation({
    mutationFn: ({ id, access_token }: { id: number; access_token: string }) =>
      api.put(`/brokers/accounts/${id}`, { access_token }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-accounts'] });
      setUpdateOpen(false);
      setNewToken('');
      setNotification({ open: true, message: 'Broker access token updated successfully!', severity: 'success' });
    },
    onError: (err: any) => {
      setNotification({ open: true, message: err.response?.data?.detail || 'Failed to update access token.', severity: 'error' });
    },
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => api.post(`/brokers/accounts/${id}/sync`),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ['broker-accounts'] });
      const errors = res.data?.errors || [];
      if (errors.length > 0) {
        setNotification({ open: true, message: errors.join('; '), severity: 'warning' });
      } else {
        setNotification({ open: true, message: 'Account synced successfully!', severity: 'success' });
      }
    },
    onError: (err: any) => {
      setNotification({ open: true, message: err.response?.data?.detail || 'Failed to sync broker account.', severity: 'error' });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/brokers/accounts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-accounts'] });
      setNotification({ open: true, message: 'Broker account disconnected.', severity: 'info' });
    },
  });

  const provList = Array.isArray(providers) ? providers : [];
  const acctList = Array.isArray(accounts)  ? accounts  : [];

  const getBrokerName = (brokerId: number) => provList.find((p: any) => p.id === brokerId)?.name ?? '';

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>Connected Brokers</Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => setOpen(true)}>Connect Broker</Button>
      </Box>

      <Grid container spacing={3}>
        {acctList.map((acct: any) => {
          const brokerName = getBrokerName(acct.broker_id);
          const isExpired = acct.is_token_expired || acct.token_status === 'EXPIRED';
          return (
            <Grid item xs={12} sm={6} md={4} key={acct.id}>
              <Card elevation={0} sx={{ border: '1px solid', borderColor: isExpired ? 'rgba(211, 47, 47, 0.4)' : 'divider', height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box display="flex" alignItems="center" gap={1} mb={1}>
                    <Typography variant="h4">{BROKER_EMOJIS[brokerName] ?? '📈'}</Typography>
                    <Box>
                      <Typography variant="subtitle1" fontWeight={700}>{acct.account_name}</Typography>
                      <Typography variant="caption" color="text.secondary">ID: {acct.account_id}</Typography>
                    </Box>
                  </Box>
                  <Box sx={{ my: 1 }}>
                    {isExpired ? (
                      <Chip label="Token Expired" size="small" color="error" sx={{ mr: 1, fontWeight: 700 }} />
                    ) : acct.token_status === 'ACTIVE' || acct.is_active ? (
                      <Chip label="Active" size="small" color="success" sx={{ mr: 1, fontWeight: 700 }} />
                    ) : (
                      <Chip label="Inactive" size="small" color="default" sx={{ mr: 1 }} />
                    )}
                    {acct.is_default && <Chip label="Default" size="small" color="primary" />}
                  </Box>

                  {acct.token_expiry && (
                    <Typography
                      variant="caption"
                      display="block"
                      color={isExpired ? "error.main" : "text.secondary"}
                      mt={1}
                      fontWeight={isExpired ? 700 : 500}
                    >
                      {isExpired ? 'Expired on:' : 'Valid until:'}{' '}
                      {new Date(acct.token_expiry).toLocaleString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </Typography>
                  )}

                  {acct.status_message && !acct.token_expiry && (
                    <Typography variant="caption" display="block" color="text.secondary" mt={0.5}>
                      {acct.status_message}
                    </Typography>
                  )}

                  {isExpired && (
                    <Box sx={{ mt: 1.5, p: 1, bgcolor: 'rgba(211, 47, 47, 0.08)', borderRadius: 1.5, border: '1px solid rgba(211, 47, 47, 0.2)' }}>
                      <Typography variant="caption" color="error.main" fontWeight={600} display="block">
                        Access token expired. Update token to restore live connection.
                      </Typography>
                    </Box>
                  )}

                  {acct.last_synced_at && (
                    <Typography variant="caption" display="block" color="text.secondary" mt={1}>
                      Last sync: {new Date(acct.last_synced_at).toLocaleString('en-IN')}
                    </Typography>
                  )}
                </CardContent>
                <CardActions sx={{ display: 'flex', justifyContent: 'space-between', px: 2, pb: 2, pt: 0 }}>
                  <Box display="flex" gap={1}>
                    <Button size="small" startIcon={<SyncIcon />} onClick={() => syncMutation.mutate(acct.id)} disabled={syncMutation.isPending}>
                      Sync
                    </Button>
                    <Button
                      size="small"
                      color={isExpired ? "warning" : "primary"}
                      startIcon={<KeyIcon />}
                      onClick={() => {
                        setSelectedAccount(acct);
                        setNewToken('');
                        setUpdateOpen(true);
                      }}
                    >
                      Update Token
                    </Button>
                  </Box>
                  <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => disconnectMutation.mutate(acct.id)}>
                    Disconnect
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          );
        })}
        {acctList.length === 0 && !isLoading && (
          <Grid item xs={12}>
            <Box textAlign="center" py={6} color="text.secondary">
              <Typography variant="h6">No brokers connected yet</Typography>
              <Typography variant="body2">Click "Connect Broker" to add your first broker account.</Typography>
            </Box>
          </Grid>
        )}
      </Grid>

      {/* Connect Broker Modal */}
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Connect Broker Account</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <FormControl fullWidth>
            <InputLabel>Broker</InputLabel>
            <Select
              value={form.broker_id}
              label="Broker"
              onChange={(e) => {
                const val = e.target.value as string;
                const prov = provList.find((p: any) => p.id === Number(val));
                setForm((f) => ({
                  ...f,
                  broker_id: val,
                  account_name: f.account_name || (prov ? `${prov.display_name} Primary` : ''),
                }));
              }}
            >
              {provList.map((p: any) => (
                <MenuItem key={p.id} value={p.id}>
                  {BROKER_EMOJIS[p.name] ?? ''} {p.display_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Account ID / Client ID"
            placeholder={
              provList.find((p: any) => p.id === Number(form.broker_id))?.name === 'ZERODHA'
                ? 'e.g. AB1234'
                : 'Account ID / Client ID'
            }
            value={form.account_id}
            onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}
            fullWidth
          />
          <TextField
            label="Account Name (display)"
            value={form.account_name}
            onChange={(e) => setForm((f) => ({ ...f, account_name: e.target.value }))}
            fullWidth
          />
          <TextField
            label="Access Token (Optional if using .env auto-login)"
            type="password"
            value={form.access_token}
            onChange={(e) => setForm((f) => ({ ...f, access_token: e.target.value }))}
            fullWidth
            helperText={
              provList.find((p: any) => p.id === Number(form.broker_id))?.name === 'ZERODHA'
                ? 'Automated daily login via Password + TOTP is supported via .env, or paste an active daily Kite access token.'
                : 'Stored encrypted in the database'
            }
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => connectMutation.mutate({ ...form, broker_id: Number(form.broker_id) })} disabled={connectMutation.isPending}>Connect</Button>
        </DialogActions>
      </Dialog>

      {/* Update Token Modal */}
      <Dialog open={updateOpen} onClose={() => setUpdateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Update Access Token — {selectedAccount?.account_name}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Paste your refreshed access token for <strong>{selectedAccount?.account_name}</strong> (Client ID: {selectedAccount?.account_id}).
          </Typography>
          <TextField
            label="New Access Token"
            type="password"
            value={newToken}
            onChange={(e) => setNewToken(e.target.value)}
            fullWidth
            multiline
            rows={3}
            placeholder="Paste access token here..."
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUpdateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="primary"
            onClick={() => updateTokenMutation.mutate({ id: selectedAccount.id, access_token: newToken.trim() })}
            disabled={!newToken.trim() || updateTokenMutation.isPending}
          >
            {updateTokenMutation.isPending ? 'Updating...' : 'Save Token'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Notification Toast */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={() => setNotification((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setNotification((prev) => ({ ...prev, open: false }))}
          severity={notification.severity}
          sx={{ width: '100%', fontWeight: 600 }}
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
