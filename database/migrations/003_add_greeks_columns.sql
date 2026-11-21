-- ============================================================
-- 003_add_greeks_columns.sql
-- Add Black-Scholes Greeks columns to positions table
-- ============================================================

ALTER TABLE positions ADD COLUMN IF NOT EXISTS delta NUMERIC(15, 6);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS gamma NUMERIC(15, 8);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS theta NUMERIC(15, 6);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS vega NUMERIC(15, 6);
