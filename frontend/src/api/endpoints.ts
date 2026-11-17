import { apiClient } from './client';
import type {
  AlgoRun,
  AlgoRunCreate,
  AnalyticsSummary,
  BrokerAccount,
  BrokerAccountCreate,
  Dividend,
  GreeksSummary,
  Holding,
  JournalUpdate,
  LoginRequest,
  MarginSummary,
  MergedHolding,
  ModifyOrderRequest,
  MonthlyIncome,
  OptionPosition,
  OptionStrategy,
  OptionStrategyCreate,
  Order,
  PaginatedResponse,
  PaginationParams,
  PlaceOrderRequest,
  PortfolioSummary,
  Position,
  TokenResponse,
  Trade,
  TradeSignal,
  User,
} from '../types';

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/api/v1/auth/login', data).then((r) => r.data),

  refresh: (refreshToken: string) =>
    apiClient
      .post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken })
      .then((r) => r.data),

  me: () => apiClient.get<User>('/api/v1/auth/me').then((r) => r.data),

  logout: () => apiClient.post('/api/v1/auth/logout').then((r) => r.data),
};

// ─── Brokers ──────────────────────────────────────────────────────────────────

export const brokersApi = {
  list: () => apiClient.get<BrokerAccount[]>('/api/v1/brokers').then((r) => r.data),

  create: (data: BrokerAccountCreate) =>
    apiClient.post<BrokerAccount>('/api/v1/brokers', data).then((r) => r.data),

  get: (id: number) =>
    apiClient.get<BrokerAccount>(`/api/v1/brokers/${id}`).then((r) => r.data),

  update: (id: number, data: Partial<BrokerAccountCreate>) =>
    apiClient.put<BrokerAccount>(`/api/v1/brokers/${id}`, data).then((r) => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/v1/brokers/${id}`).then((r) => r.data),

  sync: (id: number) =>
    apiClient.post(`/api/v1/brokers/${id}/sync`).then((r) => r.data),
};

// ─── Portfolio ────────────────────────────────────────────────────────────────

export const portfolioApi = {
  summary: (brokerAccountIds?: number[]) => {
    const params = brokerAccountIds?.length
      ? { broker_account_ids: brokerAccountIds.join(',') }
      : undefined;
    return apiClient
      .get<PortfolioSummary>('/api/v1/portfolio/summary', { params })
      .then((r) => r.data);
  },
};

// ─── Holdings ─────────────────────────────────────────────────────────────────

export const holdingsApi = {
  list: (params?: { broker_account_id?: number } & PaginationParams) =>
    apiClient
      .get<PaginatedResponse<Holding>>('/api/v1/holdings', { params })
      .then((r) => r.data),

  merged: () =>
    apiClient.get<MergedHolding[]>('/api/v1/holdings/merged').then((r) => r.data),

  sync: (brokerAccountId: number) =>
    apiClient
      .post('/api/v1/holdings/sync', { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Positions ────────────────────────────────────────────────────────────────

export const positionsApi = {
  list: (params?: { broker_account_id?: number }) =>
    apiClient
      .get<Position[]>('/api/v1/positions', { params })
      .then((r) => r.data),

  sync: (brokerAccountId: number) =>
    apiClient
      .post('/api/v1/positions/sync', { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Options ──────────────────────────────────────────────────────────────────

export const optionsApi = {
  positions: (params?: { broker_account_id?: number; underlying?: string }) =>
    apiClient
      .get<OptionPosition[]>('/api/v1/options/positions', { params })
      .then((r) => r.data),

  greeksSummary: (params?: { broker_account_id?: number }) =>
    apiClient
      .get<GreeksSummary[]>('/api/v1/options/greeks-summary', { params })
      .then((r) => r.data),
};

// ─── Orders ───────────────────────────────────────────────────────────────────

export const ordersApi = {
  list: (params?: { broker_account_id?: number; status?: string } & PaginationParams) =>
    apiClient
      .get<PaginatedResponse<Order>>('/api/v1/orders', { params })
      .then((r) => r.data),

  get: (id: number) =>
    apiClient.get<Order>(`/api/v1/orders/${id}`).then((r) => r.data),

  place: (data: PlaceOrderRequest) =>
    apiClient.post<Order>('/api/v1/orders', data).then((r) => r.data),

  modify: (id: number, data: ModifyOrderRequest) =>
    apiClient.put<Order>(`/api/v1/orders/${id}`, data).then((r) => r.data),

  cancel: (id: number) =>
    apiClient.delete(`/api/v1/orders/${id}`).then((r) => r.data),

  sync: (brokerAccountId: number) =>
    apiClient
      .post('/api/v1/orders/sync', { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Trades ───────────────────────────────────────────────────────────────────

export const tradesApi = {
  list: (
    params?: {
      broker_account_id?: number;
      symbol?: string;
      from_date?: string;
      to_date?: string;
    } & PaginationParams,
  ) =>
    apiClient
      .get<PaginatedResponse<Trade>>('/api/v1/trades', { params })
      .then((r) => r.data),

  get: (id: number) =>
    apiClient.get<Trade>(`/api/v1/trades/${id}`).then((r) => r.data),

  updateJournal: (id: number, data: JournalUpdate) =>
    apiClient.patch<Trade>(`/api/v1/trades/${id}/journal`, data).then((r) => r.data),

  sync: (brokerAccountId: number) =>
    apiClient
      .post('/api/v1/trades/sync', { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Margin ───────────────────────────────────────────────────────────────────

export const marginApi = {
  summary: (params?: { broker_account_id?: number }) =>
    apiClient
      .get<MarginSummary>('/api/v1/margin/summary', { params })
      .then((r) => r.data),

  sync: (brokerAccountId: number) =>
    apiClient
      .post('/api/v1/margin/sync', { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Dividends ────────────────────────────────────────────────────────────────

export const dividendsApi = {
  list: (params?: { status?: string; from_date?: string; to_date?: string } & PaginationParams) =>
    apiClient
      .get<PaginatedResponse<Dividend>>('/api/v1/dividends', { params })
      .then((r) => r.data),

  monthlyIncome: (params?: { year?: number }) =>
    apiClient
      .get<MonthlyIncome[]>('/api/v1/dividends/monthly-income', { params })
      .then((r) => r.data),

  sync: () => apiClient.post('/api/v1/dividends/sync').then((r) => r.data),
};

// ─── Option Strategies ────────────────────────────────────────────────────────

export const strategiesApi = {
  list: (params?: { broker_account_id?: number; is_active?: boolean }) =>
    apiClient
      .get<OptionStrategy[]>('/api/v1/strategies', { params })
      .then((r) => r.data),

  get: (id: number) =>
    apiClient.get<OptionStrategy>(`/api/v1/strategies/${id}`).then((r) => r.data),

  create: (data: OptionStrategyCreate) =>
    apiClient.post<OptionStrategy>('/api/v1/strategies', data).then((r) => r.data),

  update: (id: number, data: Partial<OptionStrategyCreate>) =>
    apiClient.put<OptionStrategy>(`/api/v1/strategies/${id}`, data).then((r) => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/v1/strategies/${id}`).then((r) => r.data),

  execute: (id: number, brokerAccountId: number) =>
    apiClient
      .post(`/api/v1/strategies/${id}/execute`, { broker_account_id: brokerAccountId })
      .then((r) => r.data),
};

// ─── Analytics ────────────────────────────────────────────────────────────────

export const analyticsApi = {
  summary: (params?: {
    broker_account_id?: number;
    period_days?: number;
    from_date?: string;
    to_date?: string;
  }) =>
    apiClient
      .get<AnalyticsSummary>('/api/v1/analytics/summary', { params })
      .then((r) => r.data),
};

// ─── Algo ─────────────────────────────────────────────────────────────────────

export const algoApi = {
  runs: (params?: { broker_account_id?: number; status?: string } & PaginationParams) =>
    apiClient
      .get<PaginatedResponse<AlgoRun>>('/api/v1/algo/runs', { params })
      .then((r) => r.data),

  getRun: (id: number) =>
    apiClient.get<AlgoRun>(`/api/v1/algo/runs/${id}`).then((r) => r.data),

  start: (data: AlgoRunCreate) =>
    apiClient.post<AlgoRun>('/api/v1/algo/runs', data).then((r) => r.data),

  stop: (id: number) =>
    apiClient.post<AlgoRun>(`/api/v1/algo/runs/${id}/stop`).then((r) => r.data),

  signals: (runId: number) =>
    apiClient.get<TradeSignal[]>(`/api/v1/algo/runs/${runId}/signals`).then((r) => r.data),
};
