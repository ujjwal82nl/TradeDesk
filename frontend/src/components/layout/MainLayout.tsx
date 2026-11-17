import React from 'react';
import {
  Box, Drawer, AppBar, Toolbar, Typography, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, IconButton, Avatar,
  Menu, MenuItem, Tooltip, useMediaQuery, useTheme, Divider, Chip
} from '@mui/material';
import { NavLink, useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';

import DashboardIcon       from '@mui/icons-material/Dashboard';
import AccountBalanceIcon  from '@mui/icons-material/AccountBalance';
import InventoryIcon       from '@mui/icons-material/Inventory';
import TrendingUpIcon      from '@mui/icons-material/TrendingUp';
import FunctionsIcon       from '@mui/icons-material/Functions';
import SchemaIcon          from '@mui/icons-material/Schema';
import ListAltIcon         from '@mui/icons-material/ListAlt';
import SwapHorizIcon       from '@mui/icons-material/SwapHoriz';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import CurrencyRupeeIcon   from '@mui/icons-material/CurrencyRupee';
import BarChartIcon        from '@mui/icons-material/BarChart';
import MemoryIcon          from '@mui/icons-material/Memory';
import SettingsIcon        from '@mui/icons-material/Settings';
import Brightness4Icon     from '@mui/icons-material/Brightness4';
import Brightness7Icon     from '@mui/icons-material/Brightness7';
import RefreshIcon         from '@mui/icons-material/Refresh';
import MenuIcon            from '@mui/icons-material/Menu';
import ChevronLeftIcon     from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon    from '@mui/icons-material/ChevronRight';
import LogoutIcon          from '@mui/icons-material/Logout';
import AutoGraphIcon       from '@mui/icons-material/AutoGraph';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import ShoppingCartCheckoutIcon from '@mui/icons-material/ShoppingCartCheckout';

import { logout } from '../../store/slices/authSlice';

const DRAWER_EXPANDED_W = 230;
const DRAWER_COLLAPSED_W = 68;

type NavEntry =
  | { header: string }
  | { divider: true }
  | { label: string; path: string; icon: React.ReactElement; badge?: string; exact?: boolean };

const NAV: NavEntry[] = [
  // 1. Reporting & Analytics Section
  { header: 'REPORTING & ANALYSIS' },
  { label: 'Dashboard',   path: '/dashboard',            icon: <DashboardIcon fontSize="small" />, exact: true },
  { label: 'Holdings',    path: '/dashboard/holdings',   icon: <InventoryIcon fontSize="small" /> },
  { label: 'Positions',   path: '/dashboard/positions',  icon: <TrendingUpIcon fontSize="small" /> },
  { label: 'Options',     path: '/dashboard/options',    icon: <FunctionsIcon fontSize="small" /> },
  { label: 'Strategies',  path: '/dashboard/strategies', icon: <SchemaIcon fontSize="small" /> },
  { divider: true },
  { label: 'Orders',      path: '/dashboard/orders',     icon: <ListAltIcon fontSize="small" /> },
  { label: 'Trades',      path: '/dashboard/trades',     icon: <SwapHorizIcon fontSize="small" /> },
  { divider: true },
  { label: 'Margin',      path: '/dashboard/margin',     icon: <AccountBalanceWalletIcon fontSize="small" /> },
  { label: 'Dividends',   path: '/dashboard/dividends',  icon: <CurrencyRupeeIcon fontSize="small" /> },
  { label: 'Analytics',   path: '/dashboard/analytics',  icon: <BarChartIcon fontSize="small" /> },
  { divider: true },
  { label: 'Algo Engine', path: '/dashboard/algo',       icon: <MemoryIcon fontSize="small" /> },
  { label: 'Brokers',     path: '/dashboard/brokers',    icon: <SettingsIcon fontSize="small" /> },

  // 2. Transactional & Trading Section
  { divider: true },
  { header: 'TRADING & EXECUTION' },
  { label: 'Screener',    path: '/trading/screener',     icon: <AutoGraphIcon fontSize="small" /> },
  { label: 'Signals',     path: '/trading/signals',      icon: <NotificationsActiveIcon fontSize="small" /> },
  { label: 'Order Pad',   path: '/trading/order-pad',    icon: <ShoppingCartCheckoutIcon fontSize="small" /> },
];

interface Props {
  children:       React.ReactNode;
  themeMode:      'light' | 'dark';
  onToggleTheme:  () => void;
}

export default function MainLayout({ children, themeMode, onToggleTheme }: Props) {
  const theme    = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [anchorEl,   setAnchorEl]   = React.useState<null | HTMLElement>(null);
  const [collapsed,  setCollapsed]  = React.useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try {
        localStorage.setItem('sidebar_collapsed', String(next));
      } catch {}
      return next;
    });
  };

  const currentWidth = isMobile
    ? DRAWER_EXPANDED_W
    : collapsed
    ? DRAWER_COLLAPSED_W
    : DRAWER_EXPANDED_W;

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflowX: 'hidden' }}>
      <Toolbar
        sx={{
          minHeight: 64,
          px: collapsed && !isMobile ? 1 : 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed && !isMobile ? 'center' : 'space-between',
        }}
      >
        <Tooltip title={collapsed && !isMobile ? 'Click to expand' : ''} placement="right">
          <Box
            component={collapsed && !isMobile ? IconButton : 'div'}
            onClick={collapsed && !isMobile ? toggleCollapsed : undefined}
            sx={{
              display: 'flex',
              alignItems: 'center',
              overflow: 'hidden',
              cursor: collapsed && !isMobile ? 'pointer' : 'default',
              p: collapsed && !isMobile ? 0.5 : 0,
            }}
          >
            <AccountBalanceIcon sx={{ mr: collapsed && !isMobile ? 0 : 1, color: 'primary.main', fontSize: 28 }} />
            {(!collapsed || isMobile) && (
              <Typography variant="subtitle1" fontWeight={800} color="primary.main" noWrap>
                TradeDesk
              </Typography>
            )}
          </Box>
        </Tooltip>

        {!collapsed && !isMobile && (
          <Tooltip title="Collapse sidebar">
            <IconButton size="small" onClick={toggleCollapsed} sx={{ color: 'text.secondary' }}>
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Toolbar>
      <Divider />
      <List dense sx={{ flex: 1, pt: 1, px: 0.5, overflowY: 'auto' }}>
        {NAV.map((item, i) => {
          if ('header' in item) {
            if (collapsed && !isMobile) {
              return <Divider key={i} sx={{ my: 0.8 }} />;
            }
            return (
              <Typography
                key={i}
                variant="caption"
                sx={{
                  px: 2,
                  pt: 1.5,
                  pb: 0.5,
                  display: 'block',
                  color: 'text.secondary',
                  fontWeight: 700,
                  fontSize: '0.68rem',
                  letterSpacing: '0.08em',
                }}
              >
                {item.header}
              </Typography>
            );
          }

          if ('divider' in item) {
            return <Divider key={i} sx={{ my: 0.5 }} />;
          }

          return (
            <ListItem key={item.path} disablePadding sx={{ display: 'block' }}>
              <Tooltip title={collapsed && !isMobile ? item.label : ''} placement="right" arrow>
                <ListItemButton
                  component={NavLink}
                  to={item.path}
                  end={item.exact}
                  onClick={() => isMobile && setMobileOpen(false)}
                  sx={{
                    minHeight: 40,
                    borderRadius: 2,
                    mx: collapsed && !isMobile ? 0.5 : 1,
                    mb: 0.3,
                    px: collapsed && !isMobile ? 1.5 : 1.8,
                    justifyContent: collapsed && !isMobile ? 'center' : 'initial',
                    '&.active': {
                      bgcolor: 'primary.main',
                      color: '#fff',
                      '& .MuiListItemIcon-root': { color: '#fff' },
                      '& .MuiChip-root': { bgcolor: '#fff', color: 'primary.main' },
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: collapsed && !isMobile ? 0 : 1.8,
                      justifyContent: 'center',
                      color: 'inherit',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  {(!collapsed || isMobile) && (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', overflow: 'hidden' }}>
                      <ListItemText
                        primary={item.label}
                        primaryTypographyProps={{
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          noWrap: true,
                        }}
                      />
                      {item.badge && (
                        <Chip
                          label={item.badge}
                          size="small"
                          sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700, ml: 1 }}
                        />
                      )}
                    </Box>
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          );
        })}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {!isMobile && (
        <Drawer
          variant="permanent"
          sx={{
            width: currentWidth,
            flexShrink: 0,
            whiteSpace: 'nowrap',
            boxSizing: 'border-box',
            '& .MuiDrawer-paper': {
              width: currentWidth,
              boxSizing: 'border-box',
              overflowX: 'hidden',
              transition: theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
            },
          }}
        >
          {drawer}
        </Drawer>
      )}
      {isMobile && (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{ '& .MuiDrawer-paper': { width: DRAWER_EXPANDED_W } }}
        >
          {drawer}
        </Drawer>
      )}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <AppBar position="static" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper', color: 'text.primary' }}>
          <Toolbar sx={{ gap: 1 }}>
            {isMobile ? (
              <IconButton edge="start" onClick={() => setMobileOpen(true)}>
                <MenuIcon />
              </IconButton>
            ) : (
              <Tooltip title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
                <IconButton edge="start" onClick={toggleCollapsed} sx={{ mr: 1 }}>
                  {collapsed ? <ChevronRightIcon /> : <MenuIcon />}
                </IconButton>
              </Tooltip>
            )}
            <Typography variant="h6" fontWeight={700} sx={{ flexGrow: 1 }}>TradeDesk Portfolio & Terminal</Typography>
            <Tooltip title="Refresh all"><IconButton size="small"><RefreshIcon /></IconButton></Tooltip>
            <Tooltip title={`Switch to ${themeMode === 'dark' ? 'light' : 'dark'} mode`}>
              <IconButton size="small" onClick={onToggleTheme}>
                {themeMode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
              </IconButton>
            </Tooltip>
            <IconButton onClick={e => setAnchorEl(e.currentTarget)} size="small">
              <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '0.8rem' }}>T</Avatar>
            </IconButton>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
              <MenuItem onClick={() => { dispatch(logout()); navigate('/login'); setAnchorEl(null); }}>
                <LogoutIcon fontSize="small" sx={{ mr: 1 }} /> Logout
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ flex: 1, overflow: 'auto', p: 3, bgcolor: 'background.default' }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
