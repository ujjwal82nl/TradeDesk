-- ============================================================
-- Trading Platform: Complete PostgreSQL Schema (15 tables)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ──────────────────────────────────────────────────────────
-- 1. USERS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(512) NOT NULL,
    full_name       VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE users IS 'Platform user accounts';

-- ──────────────────────────────────────────────────────────
-- 2. BROKER PROVIDERS (static registry)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broker_providers (
    id                    SERIAL PRIMARY KEY,
    name                  VARCHAR(50) UNIQUE NOT NULL,   -- DHAN | ZERODHA | INDMONEY | IBKR
    display_name          VARCHAR(100) NOT NULL,
    description           TEXT,
    logo_url              VARCHAR(500),
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    requires_request_token BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE broker_providers IS 'Supported broker integrations';

-- ──────────────────────────────────────────────────────────
-- 3. BROKER ACCOUNTS (user ↔ broker mapping)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broker_accounts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker_id       INTEGER NOT NULL REFERENCES broker_providers(id),
    account_id      VARCHAR(100) NOT NULL,
    account_name    VARCHAR(255),
    access_token    TEXT,                  -- Fernet-encrypted
    refresh_token   TEXT,                  -- Fernet-encrypted
    token_expiry    TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, broker_id, account_id)
);
CREATE INDEX idx_broker_accounts_user ON broker_accounts(user_id);
CREATE INDEX idx_broker_accounts_broker ON broker_accounts(broker_id);
COMMENT ON TABLE broker_accounts IS 'User-connected broker accounts';

-- ──────────────────────────────────────────────────────────
-- 4. HOLDINGS (long-term equity positions)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS holdings (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    symbol              VARCHAR(50)  NOT NULL,
    exchange            VARCHAR(20)  NOT NULL DEFAULT 'NSE',
    isin                VARCHAR(20),
    quantity            NUMERIC(15, 4) NOT NULL DEFAULT 0,
    average_cost        NUMERIC(15, 4) NOT NULL DEFAULT 0,
    current_price       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    current_value       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    pnl                 NUMERIC(15, 4) NOT NULL DEFAULT 0,
    pnl_percent         NUMERIC(10, 4) NOT NULL DEFAULT 0,
    day_change          NUMERIC(15, 4) NOT NULL DEFAULT 0,
    day_change_percent  NUMERIC(10, 4) NOT NULL DEFAULT 0,
    product_type        VARCHAR(20)  NOT NULL DEFAULT 'CNC',
    instrument_type     VARCHAR(20)  NOT NULL DEFAULT 'EQUITY',
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_holdings_account  ON holdings(broker_account_id);
CREATE INDEX idx_holdings_symbol   ON holdings(symbol);
CREATE INDEX idx_holdings_isin     ON holdings(isin);
COMMENT ON TABLE holdings IS 'Long-term holdings synced from brokers';

-- ──────────────────────────────────────────────────────────
-- 5. POSITIONS (open intraday / F&O positions)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    symbol              VARCHAR(50)  NOT NULL,
    exchange            VARCHAR(20)  NOT NULL,
    product_type        VARCHAR(20)  NOT NULL,
    quantity            NUMERIC(15, 4) NOT NULL DEFAULT 0,
    buy_quantity        NUMERIC(15, 4) NOT NULL DEFAULT 0,
    sell_quantity       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    average_price       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    last_price          NUMERIC(15, 4) NOT NULL DEFAULT 0,
    pnl                 NUMERIC(15, 4) NOT NULL DEFAULT 0,
    day_pnl             NUMERIC(15, 4) NOT NULL DEFAULT 0,
    multiplier          NUMERIC(10, 2) NOT NULL DEFAULT 1,
    instrument_type     VARCHAR(20)  NOT NULL DEFAULT 'EQUITY',
    expiry_date         DATE,
    strike_price        NUMERIC(15, 4),
    option_type         VARCHAR(5),               -- CE | PE
    lot_size            INTEGER NOT NULL DEFAULT 1,
    delta               NUMERIC(15, 6),
    gamma               NUMERIC(15, 8),
    theta               NUMERIC(15, 6),
    vega                NUMERIC(15, 6),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_positions_account    ON positions(broker_account_id);
CREATE INDEX idx_positions_symbol     ON positions(symbol);
CREATE INDEX idx_positions_instrument ON positions(instrument_type);
COMMENT ON TABLE positions IS 'Open intraday and derivative positions';

-- ──────────────────────────────────────────────────────────
-- 6. ORDERS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    broker_order_id     VARCHAR(100),
    symbol              VARCHAR(50)  NOT NULL,
    exchange            VARCHAR(20)  NOT NULL,
    transaction_type    VARCHAR(10)  NOT NULL CHECK (transaction_type IN ('BUY','SELL')),
    order_type          VARCHAR(10)  NOT NULL CHECK (order_type IN ('MARKET','LIMIT','SL','SL-M')),
    product_type        VARCHAR(20)  NOT NULL,
    quantity            INTEGER NOT NULL,
    filled_quantity     INTEGER NOT NULL DEFAULT 0,
    pending_quantity    INTEGER NOT NULL DEFAULT 0,
    price               NUMERIC(15, 4),
    trigger_price       NUMERIC(15, 4),
    average_price       NUMERIC(15, 4),
    status              VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    tag                 VARCHAR(100),
    order_timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exchange_timestamp  TIMESTAMPTZ,
    remarks             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_orders_account   ON orders(broker_account_id);
CREATE INDEX idx_orders_symbol    ON orders(symbol);
CREATE INDEX idx_orders_status    ON orders(status);
CREATE INDEX idx_orders_timestamp ON orders(order_timestamp DESC);
COMMENT ON TABLE orders IS 'All placed orders across brokers';

-- ──────────────────────────────────────────────────────────
-- 7. TRADES (executed fills)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    order_id            INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    broker_trade_id     VARCHAR(100),
    symbol              VARCHAR(50)  NOT NULL,
    exchange            VARCHAR(20)  NOT NULL,
    transaction_type    VARCHAR(10)  NOT NULL CHECK (transaction_type IN ('BUY','SELL')),
    quantity            NUMERIC(15, 4) NOT NULL,
    price               NUMERIC(15, 4) NOT NULL,
    trade_value         NUMERIC(18, 4) NOT NULL,
    product_type        VARCHAR(20)  NOT NULL,
    trade_timestamp     TIMESTAMPTZ NOT NULL,
    journal_entry       TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_trades_account   ON trades(broker_account_id);
CREATE INDEX idx_trades_symbol    ON trades(symbol);
CREATE INDEX idx_trades_timestamp ON trades(trade_timestamp DESC);
COMMENT ON TABLE trades IS 'Executed trade fills — every trade auto-creates a journal entry';

-- ──────────────────────────────────────────────────────────
-- 8. DIVIDENDS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dividends (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    symbol              VARCHAR(50)  NOT NULL,
    isin                VARCHAR(20),
    company_name        VARCHAR(255),
    ex_date             DATE NOT NULL,
    payment_date        DATE,
    dividend_per_share  NUMERIC(12, 4) NOT NULL DEFAULT 0,
    quantity            NUMERIC(15, 4) NOT NULL DEFAULT 0,
    total_dividend      NUMERIC(15, 4) NOT NULL DEFAULT 0,
    tax_deducted        NUMERIC(15, 4) NOT NULL DEFAULT 0,
    net_dividend        NUMERIC(15, 4) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dividends_account  ON dividends(broker_account_id);
CREATE INDEX idx_dividends_symbol   ON dividends(symbol);
CREATE INDEX idx_dividends_ex_date  ON dividends(ex_date DESC);
COMMENT ON TABLE dividends IS 'Dividend income records per broker account';

-- ──────────────────────────────────────────────────────────
-- 9. OPTION STRATEGIES
-- ──────────────────────────────────────────────────────────
CREATE TYPE strategy_type_enum AS ENUM (
    'IRON_FLY','IRON_CONDOR','COVERED_CALL','SHORT_STRANGLE','SHORT_STRADDLE','WHEEL'
);
CREATE TYPE strategy_status_enum AS ENUM ('OPEN','CLOSED');

CREATE TABLE IF NOT EXISTS option_strategies (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    strategy_type       strategy_type_enum NOT NULL,
    underlying          VARCHAR(50)  NOT NULL,
    expiry_date         DATE NOT NULL,
    status              strategy_status_enum NOT NULL DEFAULT 'OPEN',
    max_profit          NUMERIC(15, 4),
    max_loss            NUMERIC(15, 4),
    breakeven_lower     NUMERIC(15, 4),
    breakeven_upper     NUMERIC(15, 4),
    net_premium         NUMERIC(15, 4) NOT NULL DEFAULT 0,
    margin_used         NUMERIC(15, 4) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ
);
CREATE INDEX idx_strategies_account ON option_strategies(broker_account_id);
CREATE INDEX idx_strategies_status  ON option_strategies(status);
COMMENT ON TABLE option_strategies IS 'Named multi-leg option strategies';

-- ──────────────────────────────────────────────────────────
-- 10. STRATEGY LEGS (positions within a strategy)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_positions (
    id                  SERIAL PRIMARY KEY,
    strategy_id         INTEGER NOT NULL REFERENCES option_strategies(id) ON DELETE CASCADE,
    symbol              VARCHAR(100) NOT NULL,
    transaction_type    VARCHAR(10)  NOT NULL CHECK (transaction_type IN ('BUY','SELL')),
    quantity            INTEGER NOT NULL,
    strike_price        NUMERIC(12, 2) NOT NULL,
    option_type         VARCHAR(5)   NOT NULL CHECK (option_type IN ('CE','PE')),
    expiry_date         DATE NOT NULL,
    entry_price         NUMERIC(12, 4) NOT NULL DEFAULT 0,
    current_price       NUMERIC(12, 4) NOT NULL DEFAULT 0
);
CREATE INDEX idx_strategy_legs_strategy ON strategy_positions(strategy_id);
COMMENT ON TABLE strategy_positions IS 'Individual legs of option strategies';

-- ──────────────────────────────────────────────────────────
-- 11. MARGIN SNAPSHOTS (time-series)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS margin_snapshots (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    available_margin    NUMERIC(18, 4) NOT NULL DEFAULT 0,
    used_margin         NUMERIC(18, 4) NOT NULL DEFAULT 0,
    span_margin         NUMERIC(18, 4) NOT NULL DEFAULT 0,
    exposure_margin     NUMERIC(18, 4) NOT NULL DEFAULT 0,
    collateral          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    cash_balance        NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_balance       NUMERIC(18, 4) NOT NULL DEFAULT 0,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_margin_account   ON margin_snapshots(broker_account_id);
CREATE INDEX idx_margin_timestamp ON margin_snapshots(timestamp DESC);
COMMENT ON TABLE margin_snapshots IS 'Point-in-time margin snapshots for trend charting';

-- ──────────────────────────────────────────────────────────
-- 12. CASH BALANCES
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cash_balances (
    id                  SERIAL PRIMARY KEY,
    broker_account_id   INTEGER NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    balance             NUMERIC(18, 4) NOT NULL DEFAULT 0,
    currency            VARCHAR(10)  NOT NULL DEFAULT 'INR',
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_cash_account   ON cash_balances(broker_account_id);
CREATE INDEX idx_cash_timestamp ON cash_balances(timestamp DESC);
COMMENT ON TABLE cash_balances IS 'Cash balance snapshots per broker account';

-- ──────────────────────────────────────────────────────────
-- 13. PORTFOLIO SNAPSHOTS (daily NAV)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_net_worth         NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_portfolio_value   NUMERIC(18, 4) NOT NULL DEFAULT 0,
    today_pnl               NUMERIC(18, 4) NOT NULL DEFAULT 0,
    unrealized_pnl          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    realized_pnl            NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_cash              NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_margin_used       NUMERIC(18, 4) NOT NULL DEFAULT 0,
    snapshot_date           DATE NOT NULL,
    UNIQUE(user_id, snapshot_date)
);
CREATE INDEX idx_snapshots_user ON portfolio_snapshots(user_id);
CREATE INDEX idx_snapshots_date ON portfolio_snapshots(snapshot_date DESC);
COMMENT ON TABLE portfolio_snapshots IS 'Daily aggregated portfolio value for charting';

-- ──────────────────────────────────────────────────────────
-- 14. ALGO RUNS
-- ──────────────────────────────────────────────────────────
CREATE TYPE algo_status_enum AS ENUM ('RUNNING','STOPPED','ERROR','COMPLETED');
CREATE TYPE algo_mode_enum   AS ENUM ('PAPER','LIVE','BACKTEST');

CREATE TABLE IF NOT EXISTS algo_runs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    strategy_code   TEXT NOT NULL,
    status          algo_status_enum NOT NULL DEFAULT 'RUNNING',
    mode            algo_mode_enum   NOT NULL DEFAULT 'PAPER',
    started_at      TIMESTAMPTZ,
    stopped_at      TIMESTAMPTZ,
    config          JSONB NOT NULL DEFAULT '{}',
    logs            TEXT
);
CREATE INDEX idx_algo_runs_user   ON algo_runs(user_id);
CREATE INDEX idx_algo_runs_status ON algo_runs(status);
COMMENT ON TABLE algo_runs IS 'Algo engine execution runs';

-- ──────────────────────────────────────────────────────────
-- 15. TRADE SIGNALS
-- ──────────────────────────────────────────────────────────
CREATE TYPE signal_type_enum AS ENUM ('BUY','SELL','EXIT','HOLD');

CREATE TABLE IF NOT EXISTS trade_signals (
    id                  SERIAL PRIMARY KEY,
    algo_run_id         INTEGER NOT NULL REFERENCES algo_runs(id) ON DELETE CASCADE,
    symbol              VARCHAR(50)  NOT NULL,
    exchange            VARCHAR(20)  NOT NULL DEFAULT 'NSE',
    signal_type         signal_type_enum NOT NULL,
    price               NUMERIC(15, 4) NOT NULL,
    quantity            INTEGER NOT NULL,
    strategy_name       VARCHAR(255),
    confidence_score    NUMERIC(5, 4) CHECK (confidence_score BETWEEN 0 AND 1),
    executed            BOOLEAN NOT NULL DEFAULT FALSE,
    executed_at         TIMESTAMPTZ,
    order_id            INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_signals_run      ON trade_signals(algo_run_id);
CREATE INDEX idx_signals_symbol   ON trade_signals(symbol);
CREATE INDEX idx_signals_executed ON trade_signals(executed);
COMMENT ON TABLE trade_signals IS 'Trade signals generated by algo engine';

-- ──────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at TRIGGER
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_users
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_broker_accounts
  BEFORE UPDATE ON broker_accounts
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
