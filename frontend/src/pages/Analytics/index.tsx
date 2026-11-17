import React from 'react';
import { Box, Typography, Grid, Card, CardContent } from '@mui/material';
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import StatCard from '../../components/common/StatCard';
import { formatCurrency } from '../../utils/formatters';

const COLORS = ['#2196f3','#4caf50','#ff9800','#e91e63','#9c27b0','#00bcd4','#ff5722'];

export default function Analytics() {
  const { data: portValue } = useQuery({ queryKey: ['portfolio-value'], queryFn: () => api.get('/analytics/portfolio-value').then(r => r.data ?? []) });
  const { data: xirr }      = useQuery({ queryKey: ['xirr'],            queryFn: () => api.get('/analytics/xirr').then(r => r.data) });
  const { data: brokerPerf }= useQuery({ queryKey: ['broker-perf'],     queryFn: () => api.get('/analytics/broker-performance').then(r => r.data ?? []) });
  const { data: sector }    = useQuery({ queryKey: ['sector-alloc'],    queryFn: () => api.get('/analytics/sector-allocation').then(r => r.data ?? []) });

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>Analytics</Typography>
      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6} md={3}><StatCard title="XIRR / Return" value={xirr?.xirr != null ? `${xirr.xirr}%` : '—'} subtitle="vs invested cost" /></Grid>
        <Grid item xs={12} sm={6} md={3}><StatCard title="Total Invested" value={xirr?.total_invested ?? 0} isCurrency compact /></Grid>
        <Grid item xs={12} sm={6} md={3}><StatCard title="Current Value" value={xirr?.current_value ?? 0} isCurrency compact /></Grid>
        <Grid item xs={12} sm={6} md={3}><StatCard title="Absolute Return" value={xirr?.absolute_return ?? 0} isCurrency compact /></Grid>
      </Grid>

      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={8}>
          <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="subtitle1" fontWeight={700} mb={2}>Portfolio Value Over Time</Typography>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={Array.isArray(portValue) ? portValue : []}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2196f3" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#2196f3" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={v => formatCurrency(v, true)} tick={{ fontSize: 10 }} width={70} />
                <Tooltip formatter={(v: any) => formatCurrency(v)} />
                <Area type="monotone" dataKey="total_net_worth" stroke="#2196f3" fill="url(#grad)" name="Net Worth" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </Box>
        </Grid>
        <Grid item xs={12} md={4}>
          <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Typography variant="subtitle1" fontWeight={700} mb={2}>Broker Performance</Typography>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={Array.isArray(brokerPerf) ? brokerPerf : []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis type="number" tickFormatter={v => formatCurrency(v, true)} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="broker" width={80} tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: any) => formatCurrency(v)} />
                <Bar dataKey="pnl" fill="#4caf50" name="P&L" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Box>
        </Grid>
      </Grid>

      <Box sx={{ bgcolor: 'background.paper', borderRadius: 3, p: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle1" fontWeight={700} mb={2}>Top Holdings by Value</Typography>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={(Array.isArray(sector) ? sector : []).slice(0, 10)} dataKey="value" nameKey="symbol" cx="50%" cy="50%" outerRadius={90}>
              {(Array.isArray(sector) ? sector : []).slice(0, 10).map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip formatter={(v: any) => formatCurrency(v, true)} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </Box>
    </Box>
  );
}
