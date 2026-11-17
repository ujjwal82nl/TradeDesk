import React from 'react';
import { Box, Grid, Typography, Divider } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon     from '@mui/icons-material/TrendingUp';
import CurrencyRupeeIcon from '@mui/icons-material/CurrencyRupee';
import { api } from '../../api/client';
import StatCard from '../../components/common/StatCard';
import { formatCurrency } from '../../utils/formatters';

const COLORS = ['#2196f3', '#4caf50', '#ff9800', '#e91e63', '#9c27b0', '#00bcd4'];

export default function Portfolio() {
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['portfolio-summary'],
    queryFn: () => api.get('/portfolio/summary').then(r => r.data),
  });
  const { data: brokerAlloc } = useQuery({
    queryKey: ['broker-allocation'],
    queryFn: () => api.get('/portfolio/broker-allocation').then(r => r.data),
  });
  const { data: snapshots } = useQuery({
    queryKey: ['portfolio-snapshots'],
    queryFn: () => api.get('/portfolio/snapshots').then(r => r.data),
  });

  const allocData = (Array.isArray(brokerAlloc) ? brokerAlloc : []).filter((b: any) => (b.value || 0) > 0);
  const snapData  = Array.isArray(snapshots)   ? snapshots.slice(-30) : [];

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>Portfolio Overview</Typography>

      {/* Top KPI row */}
      <Grid container spacing={2} mb={3}>
        {[
          { title: 'Total Net Worth',   value: summary?.total_net_worth,   trend: summary?.today_pnl_percent, icon: <AccountBalanceIcon /> },
          { title: "Today's P&L",       value: summary?.today_pnl,         trend: summary?.today_pnl_percent, icon: <TrendingUpIcon /> },
          { title: 'Unrealized P&L',    value: summary?.unrealized_pnl,    icon: <TrendingUpIcon /> },
          { title: 'Realized P&L',      value: summary?.realized_pnl,      icon: <TrendingUpIcon /> },
          { title: 'Total Cash',         value: summary?.total_cash,        icon: <CurrencyRupeeIcon /> },
          { title: 'Margin Used',        value: summary?.total_margin_used, icon: <AccountBalanceIcon /> },
        ].map(card => (
          <Grid item xs={12} sm={6} md={4} lg={2} key={card.title}>
            <StatCard {...card} isCurrency compact isLoading={loadingSummary} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        {/* Broker Allocation */}
        <Grid item xs={12} md={4}>
          <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="subtitle1" fontWeight={700} mb={2}>Broker Allocation</Typography>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={allocData} dataKey="value" nameKey="broker_name" cx="50%" cy="50%" outerRadius={80}>
                  {allocData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: any) => formatCurrency(v, true)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Box>
        </Grid>

        {/* Portfolio Value Chart */}
        <Grid item xs={12} md={8}>
          <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="subtitle1" fontWeight={700} mb={2}>Portfolio Value – Last 30 Days</Typography>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={snapData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={(v: number) => formatCurrency(v, true)} tick={{ fontSize: 10 }} width={70} />
                <Tooltip formatter={(v: any) => formatCurrency(v)} />
                <Bar dataKey="total_net_worth" fill="#2196f3" radius={[4, 4, 0, 0]} name="Net Worth" />
              </BarChart>
            </ResponsiveContainer>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
