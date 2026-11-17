-- ============================================================
-- Seed Data: Broker Providers + Default Admin User
-- ============================================================

-- Broker providers
INSERT INTO broker_providers (name, display_name, description, is_active, requires_request_token)
VALUES
  ('DHAN',      'Dhan',            'Dhan HQ – Indian discount broker with dhanhq SDK.',       TRUE, FALSE),
  ('ZERODHA',   'Zerodha',         'Zerodha – India''s largest discount broker (KiteConnect).', TRUE, TRUE),
  ('INDMONEY',  'INDMoney',        'INDMoney – No official API; CSV import available.',        TRUE, FALSE),
  ('IBKR',      'Interactive Brokers', 'IBKR – Global broker via TWS Gateway (planned).',     TRUE, FALSE)
ON CONFLICT (name) DO NOTHING;

-- Default admin user (password: Admin@123  – bcrypt hash)
-- In production, change via /api/v1/auth/change-password immediately after first login.
INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser)
VALUES (
  'admin@trading.com',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.s5uOeK',
  'Admin',
  TRUE,
  TRUE
)
ON CONFLICT (email) DO NOTHING;
