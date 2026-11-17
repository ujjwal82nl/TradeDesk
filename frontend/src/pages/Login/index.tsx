import React, { useState } from 'react';
import { Box, Card, CardContent, TextField, Button, Typography, Alert, InputAdornment, IconButton } from '@mui/material';
import Visibility    from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import { useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { setCredentials } from '../../store/slices/authSlice';
import { api } from '../../api/client';

export default function Login() {
  const dispatch  = useDispatch();
  const navigate  = useNavigate();
  const [form,    setForm]    = useState({ email: '', password: '' });
  const [error,   setError]   = useState('');
  const [loading, setLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);

  const handleLogin = async () => {
    setLoading(true); setError('');
    try {
      const { data } = await api.post('/auth/login', form);
      const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${data.access_token}` } });
      dispatch(setCredentials({ ...data, user: me.data }));
      navigate('/dashboard');
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Login failed. Check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'background.default' }}>
      <Card elevation={0} sx={{ width: 380, border: '1px solid', borderColor: 'divider' }}>
        <CardContent sx={{ p: 4 }}>
          <Box textAlign="center" mb={3}>
            <AccountBalanceIcon sx={{ fontSize: 48, color: 'primary.main' }} />
            <Typography variant="h5" fontWeight={800} mt={1}>TradeDesk</Typography>
            <Typography variant="body2" color="text.secondary">Multi-Broker Trading Platform</Typography>
          </Box>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <TextField
            label="Email" type="email" fullWidth sx={{ mb: 2 }}
            value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
          />
          <TextField
            label="Password" fullWidth sx={{ mb: 3 }}
            type={showPwd ? 'text' : 'password'}
            value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            InputProps={{ endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => setShowPwd(v => !v)} edge="end">
                  {showPwd ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            )}}
          />
          <Button variant="contained" fullWidth size="large" onClick={handleLogin} disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </Button>
          <Typography variant="caption" display="block" textAlign="center" mt={2} color="text.secondary">
            Default: admin@trading.local / Admin@123
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
