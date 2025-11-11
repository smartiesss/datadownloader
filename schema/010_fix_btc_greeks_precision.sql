-- ============================================================================
-- Fix BTC Greeks Column Precision
-- Issue: "numeric field overflow - A field with precision 8, scale 6 must round to an absolute value less than 10^2"
-- Some Greeks values (theta, vega) can exceed 100, which doesn't fit in NUMERIC(8, 6)
-- Solution: Increase precision to NUMERIC(12, 6) to allow values up to 999,999
-- ============================================================================

-- Increase precision for Greeks columns
ALTER TABLE btc_option_quotes
    ALTER COLUMN delta TYPE NUMERIC(12, 6),
    ALTER COLUMN gamma TYPE NUMERIC(12, 6),
    ALTER COLUMN theta TYPE NUMERIC(12, 6),
    ALTER COLUMN vega TYPE NUMERIC(12, 6),
    ALTER COLUMN rho TYPE NUMERIC(12, 6);

-- Increase precision for IV columns (implied volatility can also be large)
ALTER TABLE btc_option_quotes
    ALTER COLUMN implied_volatility TYPE NUMERIC(12, 4),
    ALTER COLUMN bid_iv TYPE NUMERIC(12, 4),
    ALTER COLUMN ask_iv TYPE NUMERIC(12, 4),
    ALTER COLUMN mark_iv TYPE NUMERIC(12, 4);

-- Success message
DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'BTC Greeks precision increased:';
    RAISE NOTICE '  Greeks: NUMERIC(8,6) -> NUMERIC(12,6) (allows values up to 999,999)';
    RAISE NOTICE '  IVs: NUMERIC(8,4) -> NUMERIC(12,4)';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'BTC collectors should now handle all Greeks values';
    RAISE NOTICE '============================================================';
END $$;
