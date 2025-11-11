-- ============================================================================
-- Fix BTC Option Trades Table Schema
-- Issue: Missing 'iv' and 'index_price' columns causing trade insertion failures
-- Reference: eth_option_trades table structure (001_init_timescaledb.sql)
-- Priority: CRITICAL - Blocking ALL BTC trade data collection
-- ============================================================================

-- Add missing columns
ALTER TABLE btc_option_trades ADD COLUMN IF NOT EXISTS iv NUMERIC(8, 4);
ALTER TABLE btc_option_trades ADD COLUMN IF NOT EXISTS index_price NUMERIC(18, 8);

-- Add comments for documentation
COMMENT ON COLUMN btc_option_trades.iv IS 'Implied volatility at trade time (optional)';
COMMENT ON COLUMN btc_option_trades.index_price IS 'Underlying index price at trade time';

-- ============================================================================
-- Verification Query (run after migration)
-- ============================================================================
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'btc_option_trades'
-- ORDER BY ordinal_position;
--
-- Expected output should include:
--   iv           | numeric    | YES
--   index_price  | numeric    | YES
-- ============================================================================
