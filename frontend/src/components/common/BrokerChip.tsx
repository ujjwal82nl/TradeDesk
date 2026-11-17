import React from 'react';
import { Chip, SxProps, Theme } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import PublicIcon from '@mui/icons-material/Public';

type BrokerName = 'Dhan' | 'Zerodha' | 'INDMoney' | 'IBKR' | string;

interface BrokerConfig {
  color: string;
  bgColor: string;
  label: string;
}

const BROKER_CONFIG: Record<string, BrokerConfig> = {
  dhan: {
    color: '#1565c0',
    bgColor: '#e3f2fd',
    label: 'Dhan',
  },
  zerodha: {
    color: '#e65100',
    bgColor: '#fff3e0',
    label: 'Zerodha',
  },
  indmoney: {
    color: '#6a1b9a',
    bgColor: '#f3e5f5',
    label: 'INDMoney',
  },
  ind_money: {
    color: '#6a1b9a',
    bgColor: '#f3e5f5',
    label: 'INDMoney',
  },
  ibkr: {
    color: '#2e7d32',
    bgColor: '#e8f5e9',
    label: 'IBKR',
  },
  interactive_brokers: {
    color: '#2e7d32',
    bgColor: '#e8f5e9',
    label: 'IBKR',
  },
  coindcx: {
    color: '#0052fe',
    bgColor: '#eef4ff',
    label: 'CoinDCX',
  },
  coin_dcx: {
    color: '#0052fe',
    bgColor: '#eef4ff',
    label: 'CoinDCX',
  },
};

const fallbackConfig: BrokerConfig = {
  color: '#37474f',
  bgColor: '#eceff1',
  label: '',
};

interface BrokerChipProps {
  /** Broker identifier (case-insensitive). E.g. "Dhan", "zerodha", "IBKR" */
  broker: BrokerName;
  label?: string;
  sx?: SxProps<Theme>;
}

export const BrokerChip: React.FC<BrokerChipProps> = ({ broker, label, sx }) => {
  const raw = String(broker || '');
  const lower = raw.toLowerCase();
  let cfg = BROKER_CONFIG[lower.replace(/\s/g, '_')];
  if (!cfg) {
    if (lower.includes('dhan')) cfg = BROKER_CONFIG.dhan;
    else if (lower.includes('zerodha')) cfg = BROKER_CONFIG.zerodha;
    else if (lower.includes('indmoney') || lower.includes('ind_money')) cfg = BROKER_CONFIG.indmoney;
    else if (lower.includes('coindcx') || lower.includes('coin_dcx')) cfg = BROKER_CONFIG.coindcx;
    else if (lower.includes('ibkr') || lower.includes('interactive')) cfg = BROKER_CONFIG.ibkr;
    else cfg = { ...fallbackConfig, label: raw };
  }

  const isGlobal = lower.includes('ibkr') || lower.includes('interactive');
  const chipLabel = label !== undefined ? label : (cfg.label || raw);

  return (
    <Chip
      size="small"
      icon={
        isGlobal ? (
          <PublicIcon style={{ color: cfg.color, fontSize: 14 }} />
        ) : (
          <AccountBalanceIcon style={{ color: cfg.color, fontSize: 14 }} />
        )
      }
      label={chipLabel}
      sx={{
        bgcolor: cfg.bgColor,
        color: cfg.color,
        fontWeight: 600,
        fontSize: 11,
        height: 22,
        border: `1px solid ${cfg.color}40`,
        '& .MuiChip-icon': { ml: '4px' },
        ...sx,
      }}
    />
  );
};

export default BrokerChip;
