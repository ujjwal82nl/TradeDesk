import React, { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Chip, Stack, Grid, Button,
  Alert, Divider, Tooltip, TextField, Switch, FormControlLabel,
  Dialog, DialogTitle, DialogContent, DialogActions, Table, TableHead,
  TableRow, TableCell, TableBody, CircularProgress
} from '@mui/material';
import TelegramIcon from '@mui/icons-material/Telegram';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import SendIcon from '@mui/icons-material/Send';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';

import { api } from '../../api/client';

interface TelegramConfig {
  is_configured: boolean;
  has_token: boolean;
  has_chat_id: boolean;
  masked_token: string;
  chat_id: string;
  bot_info?: {
    username?: string;
    first_name?: string;
    bot_id?: number;
  };
}

interface AlertRule {
  id: number;
  name: string;
  symbol: string;
  exchange: string;
  timeframe: string;
  indicator: string;
  params: {
    period: number;
    multiplier: number;
  };
  current_signal: string | null;
  current_value: number | null;
  current_spot: number | null;
  last_flip_at: string | null;
  last_checked_at: string | null;
  is_active: boolean;
  notify_telegram: boolean;
  telegram_chat_id?: string | null;
}

interface AlertNotification {
  id: number;
  rule_id: number;
  symbol: string;
  event_type: string;
  old_signal: string | null;
  new_signal: string;
  spot_price: number | null;
  indicator_value: number | null;
  message_text: string;
  channel: string;
  status: string;
  error_message?: string | null;
  created_at: string;
}

export default function Signals() {
  const [tgConfig, setTgConfig] = useState<TelegramConfig | null>(null);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [notifications, setNotifications] = useState<AlertNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [testSending, setTestSending] = useState(false);
  const [detectingChat, setDetectingChat] = useState(false);

  // Dialogs
  const [openConfigDialog, setOpenConfigDialog] = useState(false);
  const [botTokenInput, setBotTokenInput] = useState('');
  const [chatIdInput, setChatIdInput] = useState('');
  const [bannerAlert, setBannerAlert] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  // Load all data
  const fetchData = async () => {
    setLoading(true);
    try {
      const [configRes, rulesRes, notifsRes] = await Promise.all([
        api.get('/alerts/config'),
        api.get('/alerts/rules'),
        api.get('/alerts/notifications'),
      ]);
      setTgConfig(configRes.data);
      setRules(rulesRes.data);
      setNotifications(notifsRes.data);
    } catch (err: any) {
      console.error('Failed to load alert data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Save Telegram Config
  const handleSaveConfig = async () => {
    try {
      const res = await api.post('/alerts/config', {
        bot_token: botTokenInput || undefined,
        chat_id: chatIdInput || undefined,
      });
      setBannerAlert({ type: 'success', message: 'Telegram credentials saved successfully.' });
      setOpenConfigDialog(false);
      fetchData();
    } catch (err: any) {
      setBannerAlert({ type: 'error', message: err?.response?.data?.detail || 'Failed to update Telegram settings' });
    }
  };

  // Test Telegram Connection
  const handleTestTelegram = async () => {
    setTestSending(true);
    try {
      const res = await api.post('/alerts/telegram/test');
      if (res.data?.success) {
        setBannerAlert({ type: 'success', message: 'Test message delivered to Telegram successfully! Check your Telegram chat.' });
      } else {
        setBannerAlert({ type: 'error', message: res.data?.error || 'Failed to send test message' });
      }
      fetchData();
    } catch (err: any) {
      setBannerAlert({ type: 'error', message: err?.response?.data?.detail || 'Error testing Telegram connection' });
    } finally {
      setTestSending(false);
    }
  };

  // Auto-detect chat ID
  const handleAutoDetectChatId = async () => {
    setDetectingChat(true);
    try {
      const res = await api.get('/alerts/telegram/detect-chat-id');
      if (res.data?.success && res.data?.chat_id) {
        setChatIdInput(res.data.chat_id);
        setBannerAlert({
          type: 'success',
          message: `Detected Chat ID: ${res.data.chat_id} (${res.data.first_name || res.data.username || 'User'}). Saved!`
        });
        fetchData();
      } else {
        setBannerAlert({
          type: 'error',
          message: res.data?.error || 'No recent messages found. Open your Telegram bot and click /start, then click Auto-detect again.'
        });
      }
    } catch (err: any) {
      setBannerAlert({ type: 'error', message: 'Failed to auto-detect chat ID' });
    } finally {
      setDetectingChat(false);
    }
  };

  // Evaluate Rule
  const handleEvaluateRule = async (ruleId: number, forceNotify: boolean = false) => {
    setEvaluating(true);
    try {
      const res = await api.post(`/alerts/rules/${ruleId}/evaluate?notify=${forceNotify}`);
      const data = res.data;
      if (forceNotify) {
        if (data.telegram_sent) {
          setBannerAlert({
            type: 'success',
            message: `Alert dispatched to Telegram! Spot: $${data.current_spot.toLocaleString()}, SuperTrend: $${data.supertrend.toFixed(2)}, Signal: ${data.signal}`
          });
        } else {
          setBannerAlert({
            type: 'error',
            message: `Indicator evaluated (${data.signal}), but Telegram delivery failed: ${data.notification?.error || 'Check Bot Token/Chat ID'}`
          });
        }
      } else {
        setBannerAlert({
          type: 'info',
          message: `Evaluation completed: ${data.symbol} is currently ${data.signal} at $${data.current_spot.toLocaleString()} (SuperTrend: $${data.supertrend.toFixed(2)}). Flip: ${data.did_flip ? 'YES' : 'NO'}`
        });
      }
      fetchData();
    } catch (err: any) {
      setBannerAlert({ type: 'error', message: err?.response?.data?.detail || 'Evaluation failed' });
    } finally {
      setEvaluating(false);
    }
  };

  // Toggle Rule active
  const handleToggleRuleActive = async (rule: AlertRule) => {
    try {
      await api.put(`/alerts/rules/${rule.id}`, { is_active: !rule.is_active });
      fetchData();
    } catch (err: any) {
      console.error(err);
    }
  };

  const primaryRule = rules.find(r => r.symbol === 'BTCUSD') || rules[0];

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto' }}>
      {/* Page Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={800} display="flex" alignItems="center" gap={1}>
            <NotificationsActiveIcon color="primary" /> Real-Time Indicator Signals & Telegram Bot
            <Chip label="Automated" color="success" size="small" sx={{ fontWeight: 700, ml: 1 }} />
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Continuous technical indicator monitoring (SuperTrend, breakouts, reversals) with instant Telegram notifications.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            size="small"
            onClick={fetchData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<TelegramIcon />}
            size="small"
            color="primary"
            onClick={() => {
              setBotTokenInput(tgConfig?.masked_token || '');
              setChatIdInput(tgConfig?.chat_id || '');
              setOpenConfigDialog(true);
            }}
          >
            Configure Telegram Bot
          </Button>
        </Stack>
      </Box>

      {/* Banner Alert Feedback */}
      {bannerAlert && (
        <Alert
          severity={bannerAlert.type}
          onClose={() => setBannerAlert(null)}
          sx={{ mb: 3 }}
        >
          {bannerAlert.message}
        </Alert>
      )}

      {/* Telegram Status & Setup Card */}
      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <Box display="flex" alignItems="center" gap={1.5}>
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: 2,
                    bgcolor: tgConfig?.is_configured ? 'rgba(0, 136, 204, 0.15)' : 'action.hover',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#0088cc',
                  }}
                >
                  <TelegramIcon sx={{ fontSize: 28 }} />
                </Box>
                <Box>
                  <Typography variant="subtitle1" fontWeight={800} display="flex" alignItems="center" gap={1}>
                    Telegram Bot Integration
                    {tgConfig?.is_configured ? (
                      <Chip label="Connected" size="small" color="success" icon={<CheckCircleIcon />} sx={{ fontWeight: 700 }} />
                    ) : (
                      <Chip label="Pending Setup" size="small" color="warning" icon={<ErrorOutlineIcon />} sx={{ fontWeight: 700 }} />
                    )}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {tgConfig?.bot_info?.username ? (
                      <>Bot: <strong>@{tgConfig.bot_info.username}</strong> ({tgConfig.bot_info.first_name}) • Chat ID: <code>{tgConfig.chat_id}</code></>
                    ) : (
                      'Configure your Bot Token from @BotFather and your Chat ID to receive instant alerts.'
                    )}
                  </Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} md={6} sx={{ display: 'flex', justifyContent: { xs: 'flex-start', md: 'flex-end' }, gap: 1 }}>
              <Button
                variant="outlined"
                color="info"
                size="small"
                startIcon={<AutoAwesomeIcon />}
                onClick={handleAutoDetectChatId}
                disabled={detectingChat}
              >
                {detectingChat ? <CircularProgress size={16} /> : 'Auto-Detect Chat ID'}
              </Button>
              <Button
                variant="contained"
                color="success"
                size="small"
                startIcon={<SendIcon />}
                onClick={handleTestTelegram}
                disabled={testSending || !tgConfig?.is_configured}
              >
                {testSending ? <CircularProgress size={16} color="inherit" /> : 'Send Test Alert'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Primary Setup & Trigger Card (BTCUSD SuperTrend 16, 1.5, 90 mins) */}
      {primaryRule && (
        <Card elevation={0} sx={{ border: '2px solid', borderColor: 'primary.main', mb: 3, position: 'relative' }}>
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              right: 0,
              bgcolor: 'primary.main',
              color: '#fff',
              px: 2,
              py: 0.3,
              borderBottomLeftRadius: 8,
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '0.05em',
            }}
          >
            ACTIVE MONITORING RULE
          </Box>
          <CardContent sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2} mb={2}>
              <Box>
                <Typography variant="h6" fontWeight={800} display="flex" alignItems="center" gap={1}>
                  {primaryRule.symbol} SuperTrend Indicator
                  <Chip label={primaryRule.timeframe} size="small" variant="outlined" sx={{ fontWeight: 700 }} />
                  <Chip
                    label={primaryRule.current_signal === 'GREEN' ? 'BULLISH (GREEN)' : 'BEARISH (RED)'}
                    size="small"
                    color={primaryRule.current_signal === 'GREEN' ? 'success' : 'error'}
                    sx={{ fontWeight: 800 }}
                  />
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <strong>Trigger Condition:</strong> When SuperTrend signal flips between 🔴 <strong>RED</strong> and 🟢 <strong>GREEN</strong>.
                </Typography>
              </Box>

              <Stack direction="row" spacing={1} alignItems="center">
                <FormControlLabel
                  control={
                    <Switch
                      checked={primaryRule.is_active}
                      onChange={() => handleToggleRuleActive(primaryRule)}
                      color="primary"
                    />
                  }
                  label={primaryRule.is_active ? 'Active' : 'Paused'}
                  sx={{ mr: 1 }}
                />
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={() => handleEvaluateRule(primaryRule.id, false)}
                  disabled={evaluating}
                >
                  Evaluate Live
                </Button>
                <Button
                  variant="contained"
                  color="warning"
                  size="small"
                  startIcon={<SendIcon />}
                  onClick={() => handleEvaluateRule(primaryRule.id, true)}
                  disabled={evaluating || !tgConfig?.is_configured}
                >
                  Simulate Flip & Send Telegram Alert
                </Button>
              </Stack>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Metrics Grid */}
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>
                  SETUP / STRIKE
                </Typography>
                <Typography variant="h6" fontWeight={800} color="primary.main">
                  {primaryRule.symbol}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Exchange: {primaryRule.exchange}
                </Typography>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>
                  PARAMETERS & TIMEFRAME
                </Typography>
                <Typography variant="body1" fontWeight={700}>
                  Period: {primaryRule.params?.period ?? 16}, Mult: {primaryRule.params?.multiplier ?? 1.5}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Interval: <strong>{primaryRule.timeframe} (90 mins)</strong>
                </Typography>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>
                  CURRENT SPOT PRICE
                </Typography>
                <Typography variant="h6" fontWeight={800}>
                  ${primaryRule.current_spot ? primaryRule.current_spot.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Loading...'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Live BTCUSD Candle
                </Typography>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>
                  SUPERTREND BAND VALUE
                </Typography>
                <Typography
                  variant="h6"
                  fontWeight={800}
                  color={primaryRule.current_signal === 'GREEN' ? 'success.main' : 'error.main'}
                  display="flex"
                  alignItems="center"
                  gap={0.5}
                >
                  {primaryRule.current_signal === 'GREEN' ? <TrendingUpIcon fontSize="small" /> : <TrendingDownIcon fontSize="small" />}
                  ${primaryRule.current_value ? primaryRule.current_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Loading...'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  State: <strong>{primaryRule.current_signal ?? 'Calculating'}</strong>
                </Typography>
              </Grid>
            </Grid>

            {/* Telegram Message Preview Box */}
            <Box sx={{ mt: 3, p: 2, bgcolor: 'action.hover', borderRadius: 2, border: '1px dashed', borderColor: 'divider' }}>
              <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={0.5}>
                TELEGRAM ALERT PREVIEW (EXACT MESSAGE DISPATCHED):
              </Typography>
              <Typography variant="body2" component="pre" sx={{ fontFamily: 'monospace', m: 0, fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
{`🚀 SUPERTREND SIGNAL FLIP: ${primaryRule.symbol} 🚀
📊 Instrument: ${primaryRule.symbol}
⏱ Time Interval: ${primaryRule.timeframe} (90 mins)
📐 Parameters: Period=${primaryRule.params?.period ?? 16}, Multiplier=${primaryRule.params?.multiplier ?? 1.5}
⚡ Signal Changed: 🔴 RED ➔ 🟢 BULLISH (BUY / GREEN)
💰 Current Spot Price: $${primaryRule.current_spot ? primaryRule.current_spot.toLocaleString() : '64,050.00'}
🎯 SuperTrend Value: $${primaryRule.current_value ? primaryRule.current_value.toFixed(2) : '63,820.25'}
🕒 Trigger Time: UTC Real-Time
🔔 TradeDesk Automated Indicator Alert Engine`}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Dispatched Telegram Notifications History */}
      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
        <CardContent sx={{ p: 0 }}>
          <Box sx={{ p: 2, pb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="subtitle1" fontWeight={800} display="flex" alignItems="center" gap={1}>
              <TelegramIcon color="primary" fontSize="small" /> Telegram Alert Notification Log
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Showing last {notifications.length} alerts
            </Typography>
          </Box>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'action.hover' }}>
                <TableCell sx={{ fontWeight: 700 }}>Time (UTC)</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Instrument</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Event</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Signal Flip</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Spot Price</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">SuperTrend</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Channel</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Delivery Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {notifications.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                    No alerts triggered yet. Click "Simulate Flip & Send Telegram Alert" or wait for market candle flips.
                  </TableCell>
                </TableRow>
              ) : (
                notifications.map(n => (
                  <TableRow key={n.id} hover>
                    <TableCell sx={{ fontSize: '0.78rem' }}>
                      {new Date(n.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>{n.symbol}</TableCell>
                    <TableCell>
                      <Chip label={n.event_type} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={0.5}>
                        <Chip
                          label={n.old_signal || 'START'}
                          size="small"
                          color={n.old_signal === 'GREEN' ? 'success' : 'default'}
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                        ➔
                        <Chip
                          label={n.new_signal}
                          size="small"
                          color={n.new_signal === 'GREEN' ? 'success' : 'error'}
                          sx={{ height: 20, fontSize: '0.7rem', fontWeight: 800 }}
                        />
                      </Box>
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      ${n.spot_price?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      ${n.indicator_value?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell>
                      <Chip
                        icon={<TelegramIcon />}
                        label={n.channel}
                        size="small"
                        sx={{ bgcolor: 'rgba(0, 136, 204, 0.1)', color: '#0088cc', fontWeight: 700 }}
                      />
                    </TableCell>
                    <TableCell>
                      {n.status === 'SENT' ? (
                        <Chip label="Delivered" size="small" color="success" icon={<CheckCircleIcon />} sx={{ height: 22 }} />
                      ) : (
                        <Tooltip title={n.error_message || 'Delivery failed'}>
                          <Chip label="Failed" size="small" color="error" icon={<ErrorOutlineIcon />} sx={{ height: 22 }} />
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Configure Telegram Modal */}
      <Dialog open={openConfigDialog} onClose={() => setOpenConfigDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: 1 }}>
          <TelegramIcon color="primary" /> Configure Telegram Alert Bot
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" paragraph>
            Enter your Telegram Bot Token from <strong>@BotFather</strong> and your personal or channel <strong>Chat ID</strong>.
          </Typography>

          <TextField
            label="Telegram Bot Token"
            fullWidth
            size="small"
            placeholder="e.g. 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
            value={botTokenInput}
            onChange={e => setBotTokenInput(e.target.value)}
            helperText="Obtained from https://t.me/BotFather"
            sx={{ mb: 3 }}
          />

          <Box display="flex" gap={1} alignItems="flex-start">
            <TextField
              label="Telegram Chat ID"
              fullWidth
              size="small"
              placeholder="e.g. 987654321 or -1001234567890"
              value={chatIdInput}
              onChange={e => setChatIdInput(e.target.value)}
              helperText="Your personal Chat ID or Group/Channel ID"
            />
            <Button
              variant="outlined"
              size="medium"
              sx={{ minWidth: 140, height: 40 }}
              onClick={handleAutoDetectChatId}
              disabled={detectingChat}
            >
              {detectingChat ? <CircularProgress size={16} /> : 'Auto-Detect'}
            </Button>
          </Box>

          <Alert severity="info" sx={{ mt: 2 }}>
            <strong>How to find your Chat ID easily:</strong><br />
            1. Open Telegram and search for your bot username.<br />
            2. Send <code>/start</code> to your bot.<br />
            3. Click the <strong>Auto-Detect</strong> button above, and TradeDesk will detect your Chat ID!
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setOpenConfigDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveConfig} color="primary">
            Save & Connect
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
