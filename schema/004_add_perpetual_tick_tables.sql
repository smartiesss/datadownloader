-- Perpetual Futures Tick Data Tables
-- Real-time quotes, trades, and orderbook depth for BTC-PERPETUAL and ETH-PERPETUAL

-- ============================================================================
-- PERPETUALS QUOTES (Real-time bid/ask prices)
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetuals_quotes (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,  -- e.g., 'BTC-PERPETUAL', 'ETH-PERPETUAL'
    best_bid_price NUMERIC(20, 10),
    best_bid_amount NUMERIC(20, 8),
    best_ask_price NUMERIC(20, 10),
    best_ask_amount NUMERIC(20, 8),
    mark_price NUMERIC(20, 10),
    index_price NUMERIC(20, 10),
    funding_rate NUMERIC(10, 8),
    open_interest NUMERIC(20, 8),
    PRIMARY KEY (timestamp, instrument)
);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_perpetuals_quotes_time ON perpetuals_quotes (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_quotes_instrument ON perpetuals_quotes (instrument, timestamp DESC);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('perpetuals_quotes', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

-- Enable compression (after 7 days)
ALTER TABLE perpetuals_quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Compression policy (compress data older than 7 days)
SELECT add_compression_policy('perpetuals_quotes', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy (keep 90 days)
SELECT add_retention_policy('perpetuals_quotes', INTERVAL '90 days', if_not_exists => TRUE);


-- ============================================================================
-- PERPETUALS TRADES (Real-time executed trades)
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetuals_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    trade_id VARCHAR(50) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    price NUMERIC(20, 10) NOT NULL,
    amount NUMERIC(20, 8) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    tick_direction INTEGER,  -- 0, 1, 2, 3 (price movement)
    liquidation BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (trade_id, instrument)
);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_perpetuals_trades_time ON perpetuals_trades (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_trades_instrument ON perpetuals_trades (instrument, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_trades_direction ON perpetuals_trades (direction, timestamp DESC);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('perpetuals_trades', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

-- Enable compression (after 7 days)
ALTER TABLE perpetuals_trades SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Compression policy
SELECT add_compression_policy('perpetuals_trades', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy (keep 90 days)
SELECT add_retention_policy('perpetuals_trades', INTERVAL '90 days', if_not_exists => TRUE);


-- ============================================================================
-- PERPETUALS ORDERBOOK DEPTH (Periodic snapshots)
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetuals_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,  -- Array of [price, amount] arrays
    asks JSONB,  -- Array of [price, amount] arrays
    mark_price NUMERIC(20, 10),
    index_price NUMERIC(20, 10),
    funding_rate NUMERIC(10, 8),
    open_interest NUMERIC(20, 8),
    volume_24h NUMERIC(20, 8),
    PRIMARY KEY (timestamp, instrument)
);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_perpetuals_depth_time ON perpetuals_orderbook_depth (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_depth_instrument ON perpetuals_orderbook_depth (instrument, timestamp DESC);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('perpetuals_orderbook_depth', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

-- Enable compression (after 7 days)
ALTER TABLE perpetuals_orderbook_depth SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Compression policy
SELECT add_compression_policy('perpetuals_orderbook_depth', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy (keep 90 days)
SELECT add_retention_policy('perpetuals_orderbook_depth', INTERVAL '90 days', if_not_exists => TRUE);


-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE perpetuals_quotes IS 'Real-time bid/ask quotes for perpetual futures (BTC-PERPETUAL, ETH-PERPETUAL)';
COMMENT ON TABLE perpetuals_trades IS 'Real-time executed trades for perpetual futures';
COMMENT ON TABLE perpetuals_orderbook_depth IS 'Periodic orderbook depth snapshots for perpetual futures';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Perpetual tick data tables created successfully!';
    RAISE NOTICE 'Tables: perpetuals_quotes, perpetuals_trades, perpetuals_orderbook_depth';
    RAISE NOTICE 'Features: TimescaleDB hypertables, compression (7d), retention (90d)';
END $$;
