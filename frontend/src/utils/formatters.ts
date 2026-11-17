/** Shared formatting utilities. */

export const formatCurrency = (value: number | null | undefined, compact = false): string => {
  if (value == null) return '₹0';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (compact) {
    if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)}Cr`;
    if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(2)}L`;
    if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1)}K`;
  }
  return `${sign}₹${abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return '0.00%';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

export const formatQuantity = (value: number | null | undefined): string =>
  value == null ? '0' : value.toLocaleString('en-IN');

export const pnlColor = (value: number | null | undefined): 'success.main' | 'error.main' | 'text.secondary' => {
  if (value == null || value === 0) return 'text.secondary';
  return value > 0 ? 'success.main' : 'error.main';
};

/** Consistent broker account label formatter: BrokerName (ClientID) */
export const formatBrokerAccountLabel = (acc: {
  broker?: { display_name?: string };
  account_name?: string;
  account_id?: string;
} | null | undefined): string => {
  if (!acc) return '';
  const brokerName =
    acc.broker?.display_name ||
    acc.account_name?.split(' ')[0]?.replace(/\(.*\)/, '').trim() ||
    'Broker';
  return acc.account_id ? `${brokerName} (${acc.account_id})` : acc.account_name || brokerName;
};
