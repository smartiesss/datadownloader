-- ============================================================================
-- Add Greeks and IV columns to BTC option quotes table
-- Issue: btc_option_quotes missing delta, gamma, theta, vega, rho, and IV columns
-- This makes it match eth_option_quotes structure
-- ============================================================================

-- Add Greeks columns
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS delta NUMERIC(8, 6);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS gamma NUMERIC(8, 6);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS theta NUMERIC(8, 6);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS vega NUMERIC(8, 6);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS rho NUMERIC(8, 6);

-- Add IV columns
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS implied_volatility NUMERIC(8, 4);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS bid_iv NUMERIC(8, 4);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS ask_iv NUMERIC(8, 4);
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS mark_iv NUMERIC(8, 4);

-- Add last_price column (for consistency with ETH)
ALTER TABLE btc_option_quotes ADD COLUMN IF NOT EXISTS last_price NUMERIC(18, 8);

-- Add comments
COMMENT ON COLUMN btc_option_quotes.delta IS 'Option delta (sensitivity to underlying price)';
COMMENT ON COLUMN btc_option_quotes.gamma IS 'Option gamma (rate of change of delta)';
COMMENT ON COLUMN btc_option_quotes.theta IS 'Option theta (time decay)';
COMMENT ON COLUMN btc_option_quotes.vega IS 'Option vega (sensitivity to volatility)';
COMMENT ON COLUMN btc_option_quotes.rho IS 'Option rho (sensitivity to interest rate)';
COMMENT ON COLUMN btc_option_quotes.implied_volatility IS 'Mark IV (implied volatility)';
COMMENT ON COLUMN btc_option_quotes.bid_iv IS 'Bid IV';
COMMENT ON COLUMN btc_option_quotes.ask_iv IS 'Ask IV';
COMMENT ON COLUMN btc_option_quotes.mark_iv IS 'Mark IV';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Greeks and IV columns added to btc_option_quotes';
    RAISE NOTICE 'btc_option_quotes now matches eth_option_quotes structure';
END $$;
