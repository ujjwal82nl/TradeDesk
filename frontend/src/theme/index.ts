import { createTheme, type ThemeOptions, type PaletteMode } from '@mui/material';
import { type Components } from '@mui/material/styles';
import type {} from '@mui/x-data-grid/themeAugmentation';

// ─── Palette constants ────────────────────────────────────────────────────────

const PRIMARY = '#1976d2';
const PRIMARY_DARK = '#42a5f5';
const SECONDARY = '#2e7d32';
const SECONDARY_DARK = '#66bb6a';
const ERROR = '#d32f2f';
const ERROR_DARK = '#ef5350';

// ─── Module augmentation for custom palette tokens ────────────────────────────

declare module '@mui/material/styles' {
  interface Palette {
    profit: Palette['primary'];
    loss: Palette['primary'];
  }
  interface PaletteOptions {
    profit?: PaletteOptions['primary'];
    loss?: PaletteOptions['primary'];
  }
}

declare module '@mui/material/Button' {
  interface ButtonPropsColorOverrides {
    profit: true;
    loss: true;
  }
}

// ─── Per-mode palette ─────────────────────────────────────────────────────────

function getPalette(mode: PaletteMode): ThemeOptions['palette'] {
  const isDark = mode === 'dark';
  return {
    mode,
    primary: { main: isDark ? PRIMARY_DARK : PRIMARY },
    secondary: { main: isDark ? SECONDARY_DARK : SECONDARY },
    error: { main: isDark ? ERROR_DARK : ERROR },
    profit: {
      main: isDark ? '#66bb6a' : '#2e7d32',
      light: isDark ? '#a5d6a7' : '#60ad5e',
      dark: isDark ? '#338a3e' : '#005005',
      contrastText: '#ffffff',
    },
    loss: {
      main: isDark ? '#ef5350' : '#d32f2f',
      light: isDark ? '#ff867c' : '#ff6659',
      dark: isDark ? '#b61827' : '#9a0007',
      contrastText: '#ffffff',
    },
    background: isDark
      ? { default: '#0d1117', paper: '#161b22' }
      : { default: '#f5f7fa', paper: '#ffffff' },
    text: isDark
      ? { primary: '#e6edf3', secondary: '#8b949e' }
      : { primary: '#1c2128', secondary: '#57606a' },
    divider: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
  };
}

// ─── Component overrides ──────────────────────────────────────────────────────

function getComponents(mode: PaletteMode): Components<any> {
  const isDark = mode === 'dark';
  return {
    MuiCssBaseline: {
      styleOverrides: `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${isDark ? '#30363d' : '#d0d7de'}; border-radius: 3px; }
      `,
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          ...(isDark && {
            border: '1px solid rgba(255,255,255,0.06)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
          }),
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          ...(isDark && {
            border: '1px solid rgba(255,255,255,0.06)',
          }),
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 8,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontWeight: 600,
            backgroundColor: isDark ? '#0d1117' : '#f6f8fa',
            color: isDark ? '#8b949e' : '#57606a',
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          },
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: 'none',
          fontFamily: "'Inter', sans-serif",
          '& .MuiDataGrid-columnHeaders': {
            backgroundColor: isDark ? '#0d1117' : '#f6f8fa',
            borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
          },
          '& .MuiDataGrid-columnHeaderTitle': {
            fontWeight: 600,
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: isDark ? '#8b949e' : '#57606a',
          },
          '& .MuiDataGrid-row:hover': {
            backgroundColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
          },
          '& .MuiDataGrid-cell': {
            borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}`,
          },
          '& .MuiDataGrid-footerContainer': {
            borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
          },
        },
      },
    },
    MuiTextField: {
      defaultProps: { variant: 'outlined', size: 'small' },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          fontSize: '0.75rem',
          backgroundColor: isDark ? '#30363d' : '#24292f',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          ...(isDark
            ? { backgroundColor: '#161b22', borderBottom: '1px solid rgba(255,255,255,0.06)' }
            : { backgroundColor: '#ffffff', borderBottom: '1px solid rgba(0,0,0,0.08)' }),
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundImage: 'none',
          ...(isDark
            ? { backgroundColor: '#161b22', borderRight: '1px solid rgba(255,255,255,0.06)' }
            : { backgroundColor: '#ffffff', borderRight: '1px solid rgba(0,0,0,0.08)' }),
        },
      },
    },
  };
}

// ─── Theme factory ────────────────────────────────────────────────────────────

export function createAppTheme(mode: PaletteMode) {
  return createTheme({
    palette: getPalette(mode),
    typography: {
      fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
      h1: { fontWeight: 700 },
      h2: { fontWeight: 700 },
      h3: { fontWeight: 700 },
      h4: { fontWeight: 600 },
      h5: { fontWeight: 600 },
      h6: { fontWeight: 600 },
      subtitle1: { fontWeight: 500 },
      subtitle2: { fontWeight: 500 },
      button: { fontWeight: 600 },
    },
    shape: { borderRadius: 10 },
    components: getComponents(mode),
  });
}
