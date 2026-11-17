import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  CircularProgress,
  Typography,
  Box,
  Alert,
  Paper,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { formatBrokerAccountLabel } from '../../utils/formatters';

interface ImportDividendsDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (count: number) => void;
}

export default function ImportDividendsDialog({
  open,
  onClose,
  onSuccess,
}: ImportDividendsDialogProps) {
  const queryClient = useQueryClient();
  const [brokerAccountId, setBrokerAccountId] = useState<number | ''>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch broker accounts
  const { data: accounts = [] } = useQuery({
    queryKey: ['broker-accounts'],
    queryFn: () => api.get('/brokers/accounts').then((r) => r.data ?? []),
    enabled: open,
  });

  useEffect(() => {
    if (open && accounts.length > 0 && !brokerAccountId) {
      setBrokerAccountId(accounts[0].id);
    }
  }, [open, accounts, brokerAccountId]);

  const importMutation = useMutation({
    mutationFn: ({ file, accId }: { file: File; accId: number }) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post(`/dividends/import-csv?broker_account_id=${accId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    onSuccess: (res: any) => {
      const count = res.data?.imported_count ?? 0;
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['div-stock'] });
      queryClient.invalidateQueries({ queryKey: ['div-broker'] });
      onSuccess(count);
      onClose();
      setSelectedFile(null);
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || 'Failed to import dividend file.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brokerAccountId) {
      setErrorMsg('Please select a broker account.');
      return;
    }
    if (!selectedFile) {
      setErrorMsg('Please select a dividend file to import.');
      return;
    }
    setErrorMsg(null);
    importMutation.mutate({ file: selectedFile, accId: Number(brokerAccountId) });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>
          Import Dividend Statement
        </DialogTitle>
        <DialogContent dividers>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {errorMsg}
            </Alert>
          )}

          <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
            Upload dividend statements exported from any supported broker (Dhan, Zerodha, Upstox, Groww, Angel One, ICICI Direct, or generic CSV/Excel).
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            {/* Broker Account Selector */}
            <TextField
              select
              fullWidth
              size="small"
              label="Select Broker Account"
              value={brokerAccountId}
              onChange={(e) => setBrokerAccountId(Number(e.target.value))}
              required
              helperText="The imported dividend payouts will be linked to this broker account"
            >
              {accounts.map((acc: any) => (
                <MenuItem key={acc.id} value={acc.id}>
                  {formatBrokerAccountLabel(acc)}
                </MenuItem>
              ))}
            </TextField>

            {/* File Dropzone / Picker */}
            <Paper
              variant="outlined"
              sx={{
                p: 3,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: selectedFile ? 'rgba(0, 184, 148, 0.04)' : 'rgba(255, 255, 255, 0.02)',
                borderColor: selectedFile ? '#00b894' : 'divider',
                borderStyle: 'dashed',
                borderRadius: 3,
                transition: 'all 0.2s ease',
                '&:hover': {
                  borderColor: '#00b894',
                  bgcolor: 'rgba(0, 184, 148, 0.06)',
                },
              }}
              onClick={() => {
                const el = document.getElementById('dividend-file-input');
                el?.click();
              }}
            >
              <input
                id="dividend-file-input"
                type="file"
                accept=".csv,.xlsx,.xls,.txt"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    setSelectedFile(e.target.files[0]);
                    setErrorMsg(null);
                  }
                }}
              />
              <UploadFileIcon
                sx={{
                  fontSize: 40,
                  color: selectedFile ? '#00b894' : 'text.secondary',
                  mb: 1,
                }}
              />
              <Typography variant="subtitle2" fontWeight={600}>
                {selectedFile ? selectedFile.name : 'Click to select statement file'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {selectedFile
                  ? `${(selectedFile.size / 1024).toFixed(1)} KB — Ready to import`
                  : 'Supports .csv and .xlsx formats (Dhan, Zerodha, Groww, etc.)'}
              </Typography>
            </Paper>

            {/* Supported Formats Info */}
            <Box
              sx={{
                p: 1.5,
                bgcolor: 'rgba(255, 255, 255, 0.03)',
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography variant="caption" fontWeight={600} color="text.primary" display="block">
                Universal Format Auto-Detection:
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.3 }}>
                • <strong>Dhan</strong>: Money ➔ Dividend Payouts ➔ Export CSV/Excel<br />
                • <strong>Zerodha</strong>: Console ➔ Reports ➔ Dividends ➔ Download XLSX/CSV<br />
                • <strong>Groww / Upstox / Other</strong>: Any statement with Date, Stock Name, Qty, and Dividend Amount.
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={onClose} color="inherit" disabled={importMutation.isPending}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={importMutation.isPending || !selectedFile}
            startIcon={
              importMutation.isPending ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <UploadFileIcon />
              )
            }
            sx={{ fontWeight: 600 }}
          >
            {importMutation.isPending ? 'Importing...' : 'Import Statement'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
