import React, { useState, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { useSelector } from 'react-redux';
import { createAppTheme } from './theme';
import { RootState } from './store';
import MainLayout from './components/layout/MainLayout';

// Lazy-loaded read-only / reporting pages
const Portfolio    = React.lazy(() => import('./pages/Portfolio'));
const Holdings     = React.lazy(() => import('./pages/Holdings'));
const Positions    = React.lazy(() => import('./pages/Positions'));
const Options      = React.lazy(() => import('./pages/Options'));
const Strategies   = React.lazy(() => import('./pages/Strategies'));
const Orders       = React.lazy(() => import('./pages/Orders'));
const Trades       = React.lazy(() => import('./pages/Trades'));
const Margin       = React.lazy(() => import('./pages/Margin'));
const Dividends    = React.lazy(() => import('./pages/Dividends'));
const Analytics    = React.lazy(() => import('./pages/Analytics'));
const AlgoEngine   = React.lazy(() => import('./pages/AlgoEngine'));
const Brokers      = React.lazy(() => import('./pages/Brokers'));
const Login        = React.lazy(() => import('./pages/Login'));

// Lazy-loaded transactional / trading pages
const Screener     = React.lazy(() => import('./pages/Trading/Screener'));
const Signals      = React.lazy(() => import('./pages/Trading/Signals'));
const OrderPad     = React.lazy(() => import('./pages/Trading/OrderPad'));

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useSelector((s: RootState) => s.auth.accessToken);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const [mode, setMode] = useState<'light' | 'dark'>(
    () => (localStorage.getItem('themeMode') as 'light' | 'dark') || 'dark'
  );
  const theme = useMemo(() => createAppTheme(mode), [mode]);
  const toggleMode = () =>
    setMode(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('themeMode', next);
      return next;
    });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <React.Suspense fallback={null}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <MainLayout themeMode={mode} onToggleTheme={toggleMode}>
                    <Routes>
                      {/* Root redirect to /dashboard */}
                      <Route path="/"                      element={<Navigate to="/dashboard" replace />} />

                      {/* Primary reporting & dashboard hierarchy */}
                      <Route path="/dashboard"             element={<Portfolio />} />
                      <Route path="/dashboard/portfolio"   element={<Portfolio />} />
                      <Route path="/dashboard/holdings"    element={<Holdings />} />
                      <Route path="/dashboard/positions"   element={<Positions />} />
                      <Route path="/dashboard/options"     element={<Options />} />
                      <Route path="/dashboard/strategies"  element={<Strategies />} />
                      <Route path="/dashboard/orders"      element={<Orders />} />
                      <Route path="/dashboard/trades"      element={<Trades />} />
                      <Route path="/dashboard/margin"      element={<Margin />} />
                      <Route path="/dashboard/dividends"   element={<Dividends />} />
                      <Route path="/dashboard/analytics"   element={<Analytics />} />
                      <Route path="/dashboard/algo"        element={<AlgoEngine />} />
                      <Route path="/dashboard/brokers"     element={<Brokers />} />

                      {/* Transactional / Trading execution routes */}
                      <Route path="/trading/screener"      element={<Screener />} />
                      <Route path="/trading/signals"       element={<Signals />} />
                      <Route path="/trading/order-pad"     element={<OrderPad />} />
                      <Route path="/screener"              element={<Navigate to="/trading/screener" replace />} />
                      <Route path="/signals"               element={<Navigate to="/trading/signals" replace />} />
                      <Route path="/order-pad"             element={<Navigate to="/trading/order-pad" replace />} />

                      {/* Backwards compatibility redirects */}
                      <Route path="/portfolio"             element={<Navigate to="/dashboard/portfolio" replace />} />
                      <Route path="/holdings"              element={<Navigate to="/dashboard/holdings" replace />} />
                      <Route path="/positions"             element={<Navigate to="/dashboard/positions" replace />} />
                      <Route path="/options"               element={<Navigate to="/dashboard/options" replace />} />
                      <Route path="/strategies"            element={<Navigate to="/dashboard/strategies" replace />} />
                      <Route path="/orders"                element={<Navigate to="/dashboard/orders" replace />} />
                      <Route path="/trades"                element={<Navigate to="/dashboard/trades" replace />} />
                      <Route path="/margin"                element={<Navigate to="/dashboard/margin" replace />} />
                      <Route path="/dividends"             element={<Navigate to="/dashboard/dividends" replace />} />
                      <Route path="/analytics"             element={<Navigate to="/dashboard/analytics" replace />} />
                      <Route path="/algo"                  element={<Navigate to="/dashboard/algo" replace />} />
                      <Route path="/brokers"               element={<Navigate to="/dashboard/brokers" replace />} />

                      {/* Catch-all redirect */}
                      <Route path="*"                      element={<Navigate to="/dashboard" replace />} />
                    </Routes>
                  </MainLayout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </React.Suspense>
      </BrowserRouter>
    </ThemeProvider>
  );
}
