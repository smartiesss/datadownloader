-- Migration 006: Create instrument_metadata table for lifecycle management
-- Purpose: Track all instruments (active and expired) with metadata
-- Author: Project Manager
-- Date: 2025-11-11

-- Drop existing table if recreating
DROP TABLE IF EXISTS instrument_metadata CASCADE;

-- Create instrument_metadata table
CREATE TABLE instrument_metadata (
    instrument_name TEXT PRIMARY KEY,
    currency TEXT NOT NULL,  -- 'BTC' or 'ETH'
    instrument_type TEXT NOT NULL,  -- 'option', 'future', 'perpetual'
    strike_price NUMERIC(18, 8),  -- NULL for perpetuals
    expiry_date TIMESTAMPTZ,  -- NULL for perpetuals
    option_type TEXT,  -- 'call', 'put', NULL for perpetuals
    is_active BOOLEAN DEFAULT TRUE,  -- FALSE when expired or delisted
    listed_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TIMESTAMPTZ,  -- Set when option expires
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),  -- Updated by lifecycle manager
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX idx_instrument_metadata_currency ON instrument_metadata(currency);
CREATE INDEX idx_instrument_metadata_is_active ON instrument_metadata(is_active);
CREATE INDEX idx_instrument_metadata_expiry_date ON instrument_metadata(expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_instrument_metadata_active_by_currency ON instrument_metadata(currency, is_active);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_instrument_metadata_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_instrument_metadata_timestamp
    BEFORE UPDATE ON instrument_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_instrument_metadata_timestamp();

-- Add comments for documentation
COMMENT ON TABLE instrument_metadata IS 'Tracks all instruments (options, futures, perpetuals) with lifecycle status';
COMMENT ON COLUMN instrument_metadata.instrument_name IS 'Unique instrument identifier (e.g., BTC-15NOV25-100000-C)';
COMMENT ON COLUMN instrument_metadata.currency IS 'Base currency: BTC or ETH';
COMMENT ON COLUMN instrument_metadata.instrument_type IS 'Type: option, future, or perpetual';
COMMENT ON COLUMN instrument_metadata.strike_price IS 'Strike price for options (NULL for perpetuals)';
COMMENT ON COLUMN instrument_metadata.expiry_date IS 'Expiry timestamp for options/futures (NULL for perpetuals)';
COMMENT ON COLUMN instrument_metadata.option_type IS 'Option type: call or put (NULL for non-options)';
COMMENT ON COLUMN instrument_metadata.is_active IS 'TRUE if currently trading, FALSE if expired/delisted';
COMMENT ON COLUMN instrument_metadata.listed_at IS 'When instrument was first listed on exchange';
COMMENT ON COLUMN instrument_metadata.expired_at IS 'When instrument expired (NULL if still active)';
COMMENT ON COLUMN instrument_metadata.last_seen_at IS 'Last time lifecycle manager saw this instrument active';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration 006: instrument_metadata table created successfully';
END $$;
