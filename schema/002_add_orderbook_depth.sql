-- Add Full Orderbook Depth Storage
-- This stores complete bid/ask orderbook (all price levels) for backtesting

-- Create orderbook depth table
CREATE TABLE IF NOT EXISTS eth_option_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,  -- Array of {"price": 0.05, "amount": 10.5}
    asks JSONB,  -- Array of {"price": 0.06, "amount": 5.2}
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_orderbook_depth_instrument_time
    ON eth_option_orderbook_depth (instrument, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_orderbook_depth_time
    ON eth_option_orderbook_depth (timestamp DESC);

-- Add GIN index for JSONB querying (optional, useful for depth analysis)
CREATE INDEX IF NOT EXISTS idx_orderbook_depth_bids
    ON eth_option_orderbook_depth USING GIN (bids);

CREATE INDEX IF NOT EXISTS idx_orderbook_depth_asks
    ON eth_option_orderbook_depth USING GIN (asks);

-- NOTE: TimescaleDB features (hypertable, compression) can be enabled later
-- when deploying to production NAS for 80-90% storage savings
--
-- To enable TimescaleDB later:
-- 1. CREATE EXTENSION IF NOT EXISTS timescaledb;
-- 2. SELECT create_hypertable('eth_option_orderbook_depth', 'timestamp', migrate_data => true);
-- 3. ALTER TABLE eth_option_orderbook_depth SET (timescaledb.compress, ...);
-- 4. SELECT add_compression_policy('eth_option_orderbook_depth', INTERVAL '7 days');

-- Create materialized view for latest orderbook (fast lookups)
CREATE MATERIALIZED VIEW IF NOT EXISTS latest_orderbook AS
SELECT DISTINCT ON (instrument)
    instrument,
    timestamp,
    bids,
    asks,
    mark_price,
    underlying_price,
    open_interest,
    volume_24h
FROM eth_option_orderbook_depth
ORDER BY instrument, timestamp DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_latest_orderbook_instrument
    ON latest_orderbook (instrument);

COMMENT ON TABLE eth_option_orderbook_depth IS
'Full orderbook depth for ETH options - stores all bid/ask levels for market impact analysis and backtesting';

COMMENT ON COLUMN eth_option_orderbook_depth.bids IS
'JSONB array of bid levels: [{"price": 0.05, "amount": 10}, ...] ordered by price DESC (best first)';

COMMENT ON COLUMN eth_option_orderbook_depth.asks IS
'JSONB array of ask levels: [{"price": 0.06, "amount": 5}, ...] ordered by price ASC (best first)';
