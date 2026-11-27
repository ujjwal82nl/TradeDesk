import React, { useState, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { useSelector } from 'react-redux';
import { createAppTheme } from './theme';
import { RootState } from './store';
import MainLayout from './components/layout/MainLayout';
import AlgoEngine from './pages/AlgoEngine';

// Helper to auto-recover from stale chunks on new deployments
function lazyWithRetry<T extends React.ComponentType<any>>(
  componentImport: () => Promise<{ default: T }>
) {
  return React.lazy(async () => {
    const refreshed = window.sessionStorage.getItem('retry-chunk-refresh') === 'true';
    try {
      const component = await componentImport();
      window.sessionStorage.setItem('retry-chunk-refresh', 'false');
      return component;
    } catch (error) {
      if (!refreshed) {
        window.sessionStorage.setItem('retry-chunk-refresh', 'true');
        window.location.reload();
        return new Promise<{ default: T }>(() => {});
      }
      throw error;
    }
  });
}

// Lazy-loaded read-only / reporting pages
const Portfolio    = lazyWithRetry(() => import('./pages/Portfolio'));
const Holdings     = lazyWithRetry(() => import('./pages/Holdings'));
const Positions    = lazyWithRetry(() => import('./pages/Positions'));
const Options      = lazyWithRetry(() => import('./pages/Options'));
const Strategies   = lazyWithRetry(() => import('./pages/Strategies'));
const Orders       = lazyWithRetry(() => import('./pages/Orders'));
const Trades       = lazyWithRetry(() => import('./pages/Trades'));
const Margin       = lazyWithRetry(() => import('./pages/Margin'));
const Dividends    = lazyWithRetry(() => import('./pages/Dividends'));
const Analytics    = lazyWithRetry(() => import('./pages/Analytics'));
const Brokers      = lazyWithRetry(() => import('./pages/Brokers'));
const Login        = lazyWithRetry(() => import('./pages/Login'));

// Lazy-loaded transactional / trading pages
const Screener     = lazyWithRetry(() => import('./pages/Trading/Screener'));
const Signals      = lazyWithRetry(() => import('./pages/Trading/Signals'));
const OrderPad     = lazyWithRetry(() => import('./pages/Trading/OrderPad'));

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

  const basename =
    typeof window !== 'undefined' && window.location.pathname.startsWith('/opt')
      ? '/opt'
      : '';

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter basename={basename}>
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
