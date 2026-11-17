import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

interface ErrorStateProps {
  /** Human-readable error description */
  message: string;
  /** Optional callback to trigger a retry / refetch */
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ message, onRetry }) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 2,
      py: 6,
      px: 3,
      textAlign: 'center',
    }}
  >
    <ErrorOutlineIcon sx={{ fontSize: 56, color: 'error.main', opacity: 0.8 }} />

    <Typography variant="h6" color="error" fontWeight={600}>
      Something went wrong
    </Typography>

    <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
      {message}
    </Typography>

    {onRetry && (
      <Button
        variant="outlined"
        color="error"
        size="small"
        onClick={onRetry}
        sx={{ mt: 1 }}
      >
        Try Again
      </Button>
    )}
  </Box>
);

export default ErrorState;
