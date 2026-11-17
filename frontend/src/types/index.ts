// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// ─── Brokers ──────────────────────────────────────────────────────────────────

export type BrokerProvider =
  | 'dhan'
  | 'zerodha'
  | 'upstox'
  | 'angel'
  | 'fyers'
  | 'iifl'
  | 'paper';

export interface BrokerAccount {
  id: number;
  user_id: number;
  provider: BrokerProvider;
  account_id: string;
  display_name: string | null;
  is_active: boolean;
  is_paper: boolean;
  created_at: string;
  updated_at: string;
}

export interface BrokerAccountCreate {
  provider: BrokerProvider;
  account_id: string;
  display_name?: string;
  credentials: Record<string, string>;
  is_paper?: boolean;
}

// ─── Portfolio ────────────────────────────────────────────────────────────────

export interface BrokerAllocation {
  broker_account_id: number;
  broker_name: string;
  provider: BrokerProvider;
  current_value: number;
  invested_value: number;
  pnl: number;
  pnl_percent: number;
  allocation_percent: number;
}

export interface AssetAllocation {
  asset_type: string;
  current_value: number;
  allocation_percent: number;
}

export interface PortfolioSummary {
  total_current_value: number;
  total_invested_value: number;
  total_pnl: number;
  total_pnl_percent: number;
  total_day_pnl: number;
  total_day_pnl_percent: number;
  broker_allocations: BrokerAllocation[];
  asset_allocations: AssetAllocation[];
  last_updated: string;
}

// ─── Holdings ─────────────────────────────────────────────────────────────────

export interface Holding {
  id: number;
  broker_account_id: number;
  symbol: string;
  exchange: string;
  isin: string | null;
  quantity: number;
  average_cost: number;
  last_price: number;
  current_value: number;
  invested_value: number;
  pnl: number;
  pnl_percent: number;
  day_change: number;
  day_change_percent: number;
  asset_type: string;
  last_updated: string;
}

export interface BrokerHoldingBreakdown {
  broker_account_id: number;
  broker_name: string;
  provider: BrokerProvider;
  quantity: number;
  average_cost: number;
  last_price: number;
  current_value: number;
  pnl: number;
  pnl_percent: number;
}

export interface MergedHolding {
  symbol: string;
  exchange: string;
  isin: string | null;
  asset_type: string;
  total_quantity: number;
  weighted_average_cost: number;
  last_price: number;
  total_current_value: number;
  total_invested_value: number;
  total_pnl: number;
  total_pnl_percent: number;
  day_change: number;
  day_change_percent: number;
  broker_breakdown: BrokerHoldingBreakdown[];
}

// ─── Positions ────────────────────────────────────────────────────────────────

export type PositionType = 'long' | 'short';
export type ProductType = 'intraday' | 'delivery' | 'margin' | 'co' | 'bo';

export interface Position {
  id: number;
  broker_account_id: number;
  symbol: string;
  exchange: string;
  product_type: ProductType;
  quantity: number;
  buy_quantity: number;
  sell_quantity: number;
  average_buy_price: number;
  average_sell_price: number;
  last_price: number;
  pnl: number;
  realised_pnl: number;
  unrealised_pnl: number;
  position_type: PositionType;
  multiplier: number;
  status?: string;
  is_open?: boolean;
  last_updated: string;
}

// ─── Options ──────────────────────────────────────────────────────────────────

export type OptionType = 'CE' | 'PE';

export interface OptionPosition {
  id: number;
  broker_account_id: number;
  underlying: string;
  symbol: string;
  expiry: string;
  strike: number;
  option_type: OptionType;
  quantity: number;
  average_price: number;
  last_price: number;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  pnl: number;
  last_updated: string;
}

export interface GreeksSummary {
  underlying: string;
  net_delta: number;
  net_gamma: number;
  net_theta: number;
  net_vega: number;
  total_pnl: number;
  positions: OptionPosition[];
}

// ─── Orders ───────────────────────────────────────────────────────────────────

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT' | 'SL' | 'SL-M';
export type OrderStatus =
  | 'PENDING'
  | 'OPEN'
  | 'COMPLETE'
  | 'CANCELLED'
  | 'REJECTED'
  | 'PARTIAL';
export type ValidityType = 'DAY' | 'IOC' | 'GTT';

export interface Order {
  id: number;
  broker_account_id: number;
  broker_order_id: string | null;
  symbol: string;
  exchange: string;
  order_type: OrderType;
  side: OrderSide;
  product_type: ProductType;
  quantity: number;
  filled_quantity: number;
  pending_quantity: number;
  price: number | null;
  trigger_price: number | null;
  average_price: number | null;
  status: OrderStatus;
  validity: ValidityType;
  tag: string | null;
  rejection_reason: string | null;
  placed_at: string;
  updated_at: string;
}

export interface PlaceOrderRequest {
  broker_account_id: number;
  symbol: string;
  exchange: string;
  order_type: OrderType;
  side: OrderSide;
  product_type: ProductType;
  quantity: number;
  price?: number;
  trigger_price?: number;
  validity?: ValidityType;
  tag?: string;
}

export interface ModifyOrderRequest {
  order_id: number;
  quantity?: number;
  price?: number;
  trigger_price?: number;
  order_type?: OrderType;
}

// ─── Trades ───────────────────────────────────────────────────────────────────

export interface Trade {
  id: number;
  broker_account_id: number;
  order_id: number | null;
  broker_trade_id: string | null;
  symbol: string;
  exchange: string;
  side: OrderSide;
  product_type: ProductType;
  quantity: number;
  price: number;
  trade_value: number;
  charges: number | null;
  net_amount: number | null;
  trade_date: string;
  trade_time: string;
  asset_type: string;
  notes: string | null;
  tags: string[];
  setup_type: string | null;
  emotion_rating: number | null;
  mistake: string | null;
  lesson: string | null;
}

export interface JournalUpdate {
  notes?: string;
  tags?: string[];
  setup_type?: string;
  emotion_rating?: number;
  mistake?: string;
  lesson?: string;
}

// ─── Margin ───────────────────────────────────────────────────────────────────

export interface MarginData {
  broker_account_id: number;
  broker_name: string;
  provider: BrokerProvider;
  available_cash: number;
  used_margin: number;
  total_margin: number;
  collateral: number;
  span_margin: number;
  exposure_margin: number;
  option_premium: number;
  utilization_percent: number;
  last_updated: string;
}

export interface MarginSummary {
  total_available_cash: number;
  total_used_margin: number;
  total_collateral: number;
  overall_utilization_percent: number;
  broker_margins: MarginData[];
}

// ─── Dividends ────────────────────────────────────────────────────────────────

export interface Dividend {
  id: number;
  symbol: string;
  isin: string | null;
  record_date: string;
  ex_date: string | null;
  payment_date: string | null;
  dividend_per_share: number;
  quantity: number;
  total_dividend: number;
  status: 'upcoming' | 'paid' | 'announced';
  broker_account_id: number | null;
}

export interface MonthlyIncome {
  year: number;
  month: number;
  month_label: string;
  total_dividend: number;
  dividend_count: number;
}

// ─── Option Strategies ────────────────────────────────────────────────────────

export type StrategyLegAction = 'BUY' | 'SELL';

export interface StrategyLeg {
  id?: number;
  action: StrategyLegAction;
  option_type: OptionType;
  strike: number;
  expiry: string;
  quantity: number;
  premium: number | null;
  current_premium: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
}

export interface OptionStrategy {
  id: number;
  name: string;
  underlying: string;
  strategy_type: string;
  broker_account_id: number | null;
  legs: StrategyLeg[];
  max_profit: number | null;
  max_loss: number | null;
  breakeven_points: number[];
  net_premium: number | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface OptionStrategyCreate {
  name: string;
  underlying: string;
  strategy_type: string;
  broker_account_id?: number;
  legs: StrategyLeg[];
}

// ─── Algo ─────────────────────────────────────────────────────────────────────

export type AlgoStatus = 'running' | 'stopped' | 'error' | 'completed';
export type SignalAction = 'BUY' | 'SELL' | 'HOLD' | 'EXIT';

export interface TradeSignal {
  id: number;
  algo_run_id: number;
  symbol: string;
  exchange: string;
  action: SignalAction;
  quantity: number;
  price: number | null;
  confidence: number | null;
  metadata: Record<string, unknown>;
  executed: boolean;
  order_id: number | null;
  created_at: string;
}

export interface AlgoRun {
  id: number;
  algo_name: string;
  broker_account_id: number;
  status: AlgoStatus;
  config: Record<string, unknown>;
  start_time: string;
  end_time: string | null;
  signals_count: number;
  trades_count: number;
  pnl: number | null;
  error_message: string | null;
  signals: TradeSignal[];
}

export interface AlgoRunCreate {
  algo_name: string;
  broker_account_id: number;
  config?: Record<string, unknown>;
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export interface PnlDataPoint {
  date: string;
  pnl: number;
  cumulative_pnl: number;
}

export interface WinRateStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  sharpe_ratio: number | null;
}

export interface SymbolPerformance {
  symbol: string;
  total_trades: number;
  total_pnl: number;
  win_rate: number;
}

export interface AnalyticsSummary {
  pnl_series: PnlDataPoint[];
  win_rate_stats: WinRateStats;
  top_performers: SymbolPerformance[];
  worst_performers: SymbolPerformance[];
  period_days: number;
}

// ─── Pagination ───────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
}
