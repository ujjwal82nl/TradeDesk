import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, TextField, InputAdornment,
  Chip, Stack, Table, TableHead, TableRow, TableCell, TableBody,
  Button, Grid, Alert
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

const PRESET_FILTERS = [
  'All Equities',
  'F&O Stocks',
  'Nifty 50',
  'High Volume Breakouts',
  'RSI < 30 (Oversold)',
  'RSI > 70 (Overbought)',
  '52-Week High',
  'Crypto / CoinDCX'
];

export default function Screener() {
  const [selectedFilter, setSelectedFilter] = useState('All Equities');
  const [search, setSearch] = useState('');

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto' }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={800} display="flex" alignItems="center" gap={1}>
            <AutoGraphIcon color="primary" /> Market Screener & Scanner
            <Chip label="Transactional" color="warning" size="small" sx={{ fontWeight: 700, ml: 1 }} />
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Scan NSE, BSE, F&O contracts and CoinDCX crypto pairs with technical indicators and custom criteria.
          </Typography>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Screener & Scanner Engine:</strong> This is part of the new <strong>Trading & Execution</strong> workspace. You will be able to filter stocks, scan technical patterns, and one-click execute orders directly from here.
      </Alert>

      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search symbol, company, or contract..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={8}>
              <Stack direction="row" spacing={1} overflow="auto" sx={{ pb: 0.5 }}>
                {PRESET_FILTERS.map(f => (
                  <Chip
                    key={f}
                    label={f}
                    clickable
                    color={selectedFilter === f ? 'primary' : 'default'}
                    variant={selectedFilter === f ? 'filled' : 'outlined'}
                    onClick={() => setSelectedFilter(f)}
                    size="small"
                  />
                ))}
              </Stack>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
        <CardContent sx={{ p: 0 }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'action.hover' }}>
                <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Market / Exchange</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">LTP (₹)</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">24h Change</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="right">Volume</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>RSI (14)</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Signal / Pattern</TableCell>
                <TableCell sx={{ fontWeight: 700 }} align="center">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {[
                { sym: 'RELIANCE', exch: 'NSE EQ', ltp: '1,280.50', chg: '+1.85%', vol: '8.4M', rsi: '58.4', sig: 'Bullish EMA Cross', bull: true },
                { sym: 'HDFCBANK', exch: 'NSE EQ', ltp: '1,745.20', chg: '+0.45%', vol: '12.1M', rsi: '49.1', sig: 'Consolidation', bull: true },
                { sym: 'NIFTY 28NOV 24500 CE', exch: 'NSE F&O', ltp: '142.00', chg: '+18.2%', vol: '1.2M', rsi: '62.0', sig: 'High IV Breakout', bull: true },
                { sym: 'BTC-USDT', exch: 'CoinDCX', ltp: '8,020,000.00', chg: '+2.40%', vol: '$1.4B', rsi: '66.5', sig: 'Bullish Momentum', bull: true },
                { sym: 'INFY', exch: 'NSE EQ', ltp: '1,860.00', chg: '-0.90%', vol: '4.2M', rsi: '38.2', sig: 'Near Support', bull: false },
              ].map((row, idx) => (
                <TableRow key={idx} hover>
                  <TableCell sx={{ fontWeight: 700 }}>{row.sym}</TableCell>
                  <TableCell>
                    <Chip label={row.exch} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>₹{row.ltp}</TableCell>
                  <TableCell align="right" sx={{ color: row.chg.startsWith('+') ? 'success.main' : 'error.main', fontWeight: 700 }}>
                    {row.chg}
                  </TableCell>
                  <TableCell align="right">{row.vol}</TableCell>
                  <TableCell>{row.rsi}</TableCell>
                  <TableCell>
                    <Chip
                      label={row.sig}
                      size="small"
                      color={row.bull ? 'success' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Button size="small" variant="contained" color="primary" startIcon={<PlayArrowIcon />}>
                      Trade
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Box>
  );
}

