import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Skeleton,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat';

interface StatCardProps {
  /** Card header label */
  title: string;
  /** Primary display value */
  value: string | number;
  /** Optional secondary line below value */
  subtitle?: string;
  /**
   * Trend as a decimal percent change (e.g. 2.34 → +2.34%).
   * Positive = green, negative = red, zero / undefined = neutral.
   */
  trend?: number;
  /** Leading icon rendered in a coloured circle */
  icon?: React.ReactNode;
  /** Show skeleton placeholders instead of real data */
  isLoading?: boolean;
  /** Symbol prepended to the value (default: '') */
  prefix?: string;
  /** Symbol appended to the value (default: '') */
  suffix?: string;
  /** Format display value as currency (₹) */
  isCurrency?: boolean;
  /** Compact card height – less padding */
  compact?: boolean;
}

/** Formats a trend number as "+2.34 %" / "-1.23 %" */
const formatTrend = (trend: number): string =>
  `${trend >= 0 ? '+' : ''}${trend.toFixed(2)}%`;

const TrendIcon: React.FC<{ trend: number }> = ({ trend }) => {
  if (trend > 0) return <TrendingUpIcon fontSize="small" />;
  if (trend < 0) return <TrendingDownIcon fontSize="small" />;
  return <TrendingFlatIcon fontSize="small" />;
};

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  icon,
  isLoading = false,
  prefix = '',
  suffix = '',
  isCurrency = false,
  compact = false,
}) => {
  const displayPrefix = isCurrency && !prefix ? '₹' : prefix;
  const theme = useTheme();

  const trendColor =
    trend === undefined
      ? theme.palette.text.secondary
      : trend > 0
      ? theme.palette.success.main
      : trend < 0
      ? theme.palette.error.main
      : theme.palette.text.secondary;

  if (isLoading) {
    return (
      <Card variant="outlined" sx={{ height: '100%' }}>
        <CardContent sx={{ p: compact ? 1.5 : 2, '&:last-child': { pb: compact ? 1.5 : 2 } }}>
          <Skeleton variant="text" width="60%" height={20} />
          <Skeleton variant="text" width="80%" height={36} sx={{ my: 0.5 }} />
          <Skeleton variant="text" width="40%" height={18} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        transition: 'box-shadow 0.2s',
        '&:hover': { boxShadow: theme.shadows[4] },
      }}
    >
      <CardContent
        sx={{
          p: compact ? 1.5 : 2.5,
          '&:last-child': { pb: compact ? 1.5 : 2.5 },
          display: 'flex',
          flexDirection: 'column',
          gap: compact ? 0.5 : 1,
        }}
      >
        {/* Title row */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="caption" color="text.secondary" fontWeight={500} letterSpacing={0.5}>
            {title.toUpperCase()}
          </Typography>
          {icon && (
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {icon}
            </Box>
          )}
        </Box>

        {/* Value */}
        <Typography
          variant={compact ? 'h6' : 'h5'}
          fontWeight={700}
          sx={{ lineHeight: 1.2, wordBreak: 'break-all' }}
        >
          {displayPrefix}
          {typeof value === 'number' ? value.toLocaleString('en-IN') : value}
          {suffix}
        </Typography>

        {/* Trend + subtitle row */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {trend !== undefined && (
            <Tooltip title={`${formatTrend(trend)} change`}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.25,
                  color: trendColor,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                <TrendIcon trend={trend} />
                {formatTrend(trend)}
              </Box>
            </Tooltip>
          )}
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default StatCard;
