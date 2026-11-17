import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, TextField, Button,
  Select, MenuItem, FormControl, InputLabel,
  Grid, Chip, Divider, Alert,
  ToggleButtonGroup, ToggleButton
} from '@mui/material';
import ShoppingCartCheckoutIcon from '@mui/icons-material/ShoppingCartCheckout';
import SendIcon from '@mui/icons-material/Send';
import BoltIcon from '@mui/icons-material/Bolt';

export default function OrderPad() {
  const [broker, setBroker] = useState('dhan');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [symbol, setSymbol] = useState('RELIANCE');
  const [exchange, setExchange] = useState('NSE');
  const [orderType, setOrderType] = useState('LIMIT');
  const [productType, setProductType] = useState('CNC');
  const [quantity, setQuantity] = useState('50');
  const [price, setPrice] = useState('1280.50');
  const [triggerPrice, setTriggerPrice] = useState('');

  const estMargin = (parseFloat(quantity || '0') * parseFloat(price || '0')).toLocaleString('en-IN', {
    maximumFractionDigits: 2,
  });

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={800} display="flex" alignItems="center" gap={1}>
          <ShoppingCartCheckoutIcon color="primary" /> Multi-Broker Order Pad
          <Chip label="Transactional" color="warning" size="small" sx={{ fontWeight: 700, ml: 1 }} />
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Execute direct equity, F&O and crypto orders across Dhan, Zerodha, CoinDCX, and INDmoney.
        </Typography>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Order Execution Engine:</strong> Place market, limit, and stop-loss orders directly routed to your connected broker accounts with margin checks and safety limits.
      </Alert>

      <Grid container spacing={3}>
        {/* Order Form */}
        <Grid item xs={12} md={7}>
          <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              {/* Buy / Sell Toggle */}
              <Box mb={2}>
                <ToggleButtonGroup
                  value={side}
                  exclusive
                  onChange={(_, val) => val && setSide(val)}
                  fullWidth
                  size="medium"
                >
                  <ToggleButton
                    value="BUY"
                    sx={{
                      fontWeight: 800,
                      color: side === 'BUY' ? '#fff' : 'success.main',
                      bgcolor: side === 'BUY' ? 'success.main !important' : 'transparent',
                    }}
                  >
                    BUY
                  </ToggleButton>
                  <ToggleButton
                    value="SELL"
                    sx={{
                      fontWeight: 800,
                      color: side === 'SELL' ? '#fff' : 'error.main',
                      bgcolor: side === 'SELL' ? 'error.main !important' : 'transparent',
                    }}
                  >
                    SELL
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              <Grid container spacing={2}>
                {/* Broker Select */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Broker Account</InputLabel>
                    <Select
                      value={broker}
                      label="Broker Account"
                      onChange={e => setBroker(e.target.value)}
                    >
                      <MenuItem value="dhan">Dhan (Account 1)</MenuItem>
                      <MenuItem value="zerodha">Zerodha Kite (Account 2)</MenuItem>
                      <MenuItem value="coindcx">CoinDCX (Crypto & Options)</MenuItem>
                      <MenuItem value="indmoney">INDmoney (US Stocks)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {/* Exchange Select */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Exchange</InputLabel>
                    <Select
                      value={exchange}
                      label="Exchange"
                      onChange={e => setExchange(e.target.value)}
                    >
                      <MenuItem value="NSE">NSE (National Stock Exchange)</MenuItem>
                      <MenuItem value="BSE">BSE (Bombay Stock Exchange)</MenuItem>
                      <MenuItem value="NFO">NSE F&O (Options / Futures)</MenuItem>
                      <MenuItem value="COINDCX">CoinDCX (Crypto / USDT)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {/* Symbol */}
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Trading Symbol / Contract"
                    value={symbol}
                    onChange={e => setSymbol(e.target.value.toUpperCase())}
                    helperText="e.g. RELIANCE, NIFTY 28NOV 24500 CE, BTC-USDT"
                  />
                </Grid>

                {/* Product Type */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Product Type</InputLabel>
                    <Select
                      value={productType}
                      label="Product Type"
                      onChange={e => setProductType(e.target.value)}
                    >
                      <MenuItem value="CNC">CNC (Delivery / Cash & Carry)</MenuItem>
                      <MenuItem value="MIS">MIS (Intraday)</MenuItem>
                      <MenuItem value="NRML">NRML (Normal F&O Position)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {/* Order Type */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Order Type</InputLabel>
                    <Select
                      value={orderType}
                      label="Order Type"
                      onChange={e => setOrderType(e.target.value)}
                    >
                      <MenuItem value="MARKET">Market Order</MenuItem>
                      <MenuItem value="LIMIT">Limit Order</MenuItem>
                      <MenuItem value="SL">Stop Loss (SL-Limit)</MenuItem>
                      <MenuItem value="SL-M">Stop Loss Market (SL-M)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {/* Quantity */}
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Quantity"
                    type="number"
                    value={quantity}
                    onChange={e => setQuantity(e.target.value)}
                  />
                </Grid>

                {/* Price */}
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Price (₹)"
                    type="number"
                    disabled={orderType === 'MARKET'}
                    value={price}
                    onChange={e => setPrice(e.target.value)}
                  />
                </Grid>

                {/* Trigger Price if SL */}
                {(orderType === 'SL' || orderType === 'SL-M') && (
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      size="small"
                      label="Trigger Price (₹)"
                      type="number"
                      value={triggerPrice}
                      onChange={e => setTriggerPrice(e.target.value)}
                    />
                  </Grid>
                )}
              </Grid>

              <Divider sx={{ my: 3 }} />

              <Button
                fullWidth
                variant="contained"
                size="large"
                color={side === 'BUY' ? 'success' : 'error'}
                startIcon={<SendIcon />}
                sx={{ py: 1.5, fontWeight: 800, fontSize: '1rem' }}
              >
                {side} {quantity} {symbol}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Order Summary & Validation */}
        <Grid item xs={12} md={5}>
          <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={800} gutterBottom display="flex" alignItems="center" gap={1}>
                <BoltIcon color="primary" /> Order Overview
              </Typography>
              <Divider sx={{ my: 1.5 }} />

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Action</Typography>
                <Chip
                  label={side}
                  color={side === 'BUY' ? 'success' : 'error'}
                  size="small"
                  sx={{ fontWeight: 800 }}
                />
              </Box>

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Selected Broker</Typography>
                <Typography variant="body2" fontWeight={700} sx={{ textTransform: 'capitalize' }}>
                  {broker}
                </Typography>
              </Box>

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Contract / Symbol</Typography>
                <Typography variant="body2" fontWeight={700}>
                  {symbol} ({exchange})
                </Typography>
              </Box>

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Type & Product</Typography>
                <Typography variant="body2" fontWeight={600}>
                  {orderType} • {productType}
                </Typography>
              </Box>

              <Divider sx={{ my: 1.5 }} />

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Est. Order Value</Typography>
                <Typography variant="subtitle1" fontWeight={800} color="primary.main">
                  ₹{estMargin}
                </Typography>
              </Box>

              <Box display="flex" justifyContent="space-between">
                <Typography variant="caption" color="text.secondary">Approx. Brokerage & Charges</Typography>
                <Typography variant="caption" color="text.secondary">₹23.60</Typography>
              </Box>
            </CardContent>
          </Card>

          <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
            <CardContent>
              <Typography variant="caption" color="text.secondary" display="block">
                ⚡ <strong>Safety Guardrails:</strong> Orders are verified against available cash margin and price bands before dispatching to broker API gateways.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

