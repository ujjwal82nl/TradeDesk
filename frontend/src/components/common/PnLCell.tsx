import React from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import RemoveIcon from '@mui/icons-material/Remove';

/**
 * Formats a raw rupee value into a compact Indian-style string:
 *   - < 1 L  → ₹12,345.67
 *   - ≥ 1 L  → ₹1.23L
 *   - ≥ 1 Cr → ₹1.23Cr
 */
export const formatIndianCompact = (value: number): string => {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';

  if (abs >= 1_00_00_000) {
    return `${sign}₹${(abs / 1_00_00_000).toFixed(2)}Cr`;
  }
  if (abs >= 1_00_000) {
    return `${sign}₹${(abs / 1_00_000).toFixed(2)}L`;
  }
  if (abs >= 1_000) {
    return `${sign}₹${(abs / 1_000).toFixed(1)}K`;
  }
  return `${sign}₹${abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

interface PnLCellProps {
  /** Absolute rupee value of profit / loss */
  value: number;
  /** Optional percentage change to display alongside the value */
  percent?: number;
  /** Whether to render an up/down arrow icon */
  showArrow?: boolean;
  /** Font size override (defaults to "inherit") */
  fontSize?: number | string;
  /** Whether to render compact format */
  compact?: boolean;
}

export const PnLCell: React.FC<PnLCellProps> = ({
  value,
  percent,
  showArrow = true,
  fontSize = 'inherit',
  compact = false,
}) => {
  const isPositive = value > 0;
  const isNegative = value < 0;
  const isNeutral = value === 0;

  const color = isPositive
    ? 'success.main'
    : isNegative
    ? 'error.main'
    : 'text.secondary';

  const Arrow = isPositive
    ? ArrowDropUpIcon
    : isNegative
    ? ArrowDropDownIcon
    : RemoveIcon;

  const formatted = formatIndianCompact(value);
  const percentStr =
    percent !== undefined
      ? ` (${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%)`
      : '';

  return (
    <Tooltip title={`₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}${percentStr}`}>
      <Box
        component="span"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          color,
          fontSize,
          fontWeight: 600,
          whiteSpace: 'nowrap',
          gap: 0.25,
        }}
      >
        {showArrow && !isNeutral && (
          <Arrow fontSize="small" sx={{ color, mb: '1px' }} />
        )}

        <Typography
          component="span"
          fontSize="inherit"
          fontWeight="inherit"
          color={color}
        >
          {formatted}
        </Typography>

        {percent !== undefined && (
          <Typography
            component="span"
            fontSize="0.8em"
            fontWeight={500}
            color={color}
            sx={{ ml: 0.5 }}
          >
            ({percent >= 0 ? '+' : ''}
            {percent.toFixed(2)}%)
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
};

export default PnLCell;
