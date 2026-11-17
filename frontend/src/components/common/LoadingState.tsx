import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Skeleton,
  Stack,
} from '@mui/material';

type LoadingType = 'table' | 'cards' | 'chart';

interface LoadingStateProps {
  /** Number of skeleton rows / cards to render (default: 5) */
  rows?: number;
  /** Visual layout to simulate (default: "table") */
  type?: LoadingType;
}

// ── Table skeleton ──────────────────────────────────────────────────────────
const TableSkeleton: React.FC<{ rows: number }> = ({ rows }) => (
  <Box>
    {/* Simulated table header */}
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
        gap: 2,
        mb: 1,
        px: 2,
        py: 1,
        bgcolor: 'action.hover',
        borderRadius: 1,
      }}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} variant="text" height={20} />
      ))}
    </Box>

    {/* Rows */}
    {Array.from({ length: rows }).map((_, rowIdx) => (
      <Box
        key={rowIdx}
        sx={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
          gap: 2,
          px: 2,
          py: 0.75,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        {Array.from({ length: 5 }).map((_, colIdx) => (
          <Skeleton
            key={colIdx}
            variant="text"
            height={22}
            width={colIdx === 0 ? '80%' : '60%'}
          />
        ))}
      </Box>
    ))}
  </Box>
);

// ── Cards skeleton ───────────────────────────────────────────────────────────
const CardsSkeleton: React.FC<{ rows: number }> = ({ rows }) => (
  <Box
    sx={{
      display: 'grid',
      gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' },
      gap: 2,
    }}
  >
    {Array.from({ length: rows }).map((_, i) => (
      <Card key={i} variant="outlined">
        <CardContent>
          <Skeleton variant="text" width="55%" height={18} />
          <Skeleton variant="text" width="75%" height={36} sx={{ my: 0.5 }} />
          <Skeleton variant="text" width="40%" height={16} />
        </CardContent>
      </Card>
    ))}
  </Box>
);

// ── Chart skeleton ────────────────────────────────────────────────────────────
const ChartSkeleton: React.FC = () => (
  <Stack spacing={1}>
    {/* Y-axis labels + bars */}
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end', height: 200 }}>
      <Stack spacing={1} justifyContent="space-between" sx={{ height: '100%', width: 40 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="text" width="100%" height={14} />
        ))}
      </Stack>
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'flex-end',
          gap: 1,
          height: '100%',
        }}
      >
        {Array.from({ length: 10 }).map((_, i) => {
          const h = 30 + Math.sin(i * 0.8) * 20 + Math.random() * 40;
          return (
            <Skeleton
              key={i}
              variant="rectangular"
              width="100%"
              height={`${h}%`}
              sx={{ borderRadius: 1 }}
            />
          );
        })}
      </Box>
    </Box>
    {/* X-axis */}
    <Box sx={{ display: 'flex', gap: 1, ml: '48px' }}>
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={i} variant="text" width="100%" height={14} />
      ))}
    </Box>
  </Stack>
);

// ── Public component ─────────────────────────────────────────────────────────
export const LoadingState: React.FC<LoadingStateProps> = ({
  rows = 5,
  type = 'table',
}) => {
  if (type === 'cards') return <CardsSkeleton rows={rows} />;
  if (type === 'chart') return <ChartSkeleton />;
  return <TableSkeleton rows={rows} />;
};

export default LoadingState;
