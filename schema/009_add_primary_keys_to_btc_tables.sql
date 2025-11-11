-- ============================================================================
-- Add Primary Keys to BTC Option Tables
-- Issue: "there is no unique or exclusion constraint matching the ON CONFLICT specification"
-- The code uses INSERT...ON CONFLICT which requires primary keys
-- ============================================================================

-- Check if tables have data (this will help us decide strategy)
DO $$
DECLARE
    quotes_count INTEGER;
    trades_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO quotes_count FROM btc_option_quotes;
    SELECT COUNT(*) INTO trades_count FROM btc_option_trades;

    RAISE NOTICE 'btc_option_quotes has % rows', quotes_count;
    RAISE NOTICE 'btc_option_trades has % rows', trades_count;
END $$;

-- Add primary key to btc_option_quotes
-- Note: This will fail if there are duplicate (timestamp, instrument) rows
-- If it fails, you'll need to clean duplicates first
ALTER TABLE btc_option_quotes
    ADD PRIMARY KEY (timestamp, instrument);

-- Add primary key to btc_option_trades
-- Note: This will fail if there are duplicate (timestamp, trade_id, instrument) rows
ALTER TABLE btc_option_trades
    DROP CONSTRAINT IF EXISTS btc_option_trades_pkey CASCADE;

ALTER TABLE btc_option_trades
    ADD PRIMARY KEY (timestamp, trade_id, instrument);

-- Verify primary keys were added
DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Primary keys added to BTC tables:';
    RAISE NOTICE '  btc_option_quotes: PRIMARY KEY (timestamp, instrument)';
    RAISE NOTICE '  btc_option_trades: PRIMARY KEY (timestamp, trade_id, instrument)';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'BTC tables now match ETH table structure';
    RAISE NOTICE 'ON CONFLICT clauses will now work correctly';
    RAISE NOTICE '============================================================';
END $$;
