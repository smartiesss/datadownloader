-- ============================================================================
-- ETH Options Tick Data Archive - Database Initialization
-- Task: T-000, T-002
-- Acceptance Criteria: AC-026 (Docker deployment)
--
-- This script initializes the TimescaleDB database with:
-- 1. TimescaleDB extension
-- 2. Tick data tables (quotes + trades) from master plan
-- 3. Gap detection table
-- 4. Indexes and compression policies
--
-- Executed automatically on first Docker container startup
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- Table 1: ETH Option Quote Ticks (bid/ask changes)
-- Storage: ~15M quotes/day, ~1.8 GB/day uncompressed
-- ============================================================================
CREATE TABLE IF NOT EXISTS eth_option_quotes (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    best_bid_price NUMERIC(18, 8),
    best_bid_amount NUMERIC(18, 8),
    best_ask_price NUMERIC(18, 8),
    best_ask_amount NUMERIC(18, 8),
    underlying_price NUMERIC(18, 8),
    mark_price NUMERIC(18, 8),
    -- Greeks columns
    delta NUMERIC(8, 6),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 6),
    vega NUMERIC(8, 6),
    rho NUMERIC(8, 6),
    -- IV columns
    implied_volatility NUMERIC(8, 4),
    bid_iv NUMERIC(8, 4),
    ask_iv NUMERIC(8, 4),
    mark_iv NUMERIC(8, 4),
    -- Additional market data
    open_interest NUMERIC(18, 8),
    last_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable with 1-day chunks
SELECT create_hypertable(
    'eth_option_quotes',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create index for faster queries by instrument
CREATE INDEX IF NOT EXISTS idx_quotes_instrument_timestamp
    ON eth_option_quotes (instrument, timestamp DESC);

-- Enable compression after 7 days (50-70% size reduction)
ALTER TABLE eth_option_quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Auto-compress data older than 7 days
SELECT add_compression_policy(
    'eth_option_quotes',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- Table 2: ETH Option Trade Ticks (executed trades)
-- Storage: ~2M trades/day, ~200 MB/day uncompressed
-- ============================================================================
CREATE TABLE IF NOT EXISTS eth_option_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC(18, 8) NOT NULL,
    amount NUMERIC(18, 8) NOT NULL,
    direction TEXT NOT NULL,  -- 'buy' or 'sell' (taker side)
    iv NUMERIC(8, 4),  -- Implied volatility at trade time (optional)
    index_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument, trade_id)
);

-- Convert to hypertable with 1-day chunks
SELECT create_hypertable(
    'eth_option_trades',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trades_instrument_timestamp
    ON eth_option_trades (instrument, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trades_trade_id
    ON eth_option_trades (trade_id);

-- Enable compression after 7 days
ALTER TABLE eth_option_trades SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Auto-compress data older than 7 days
SELECT add_compression_policy(
    'eth_option_trades',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- Table 3: Data Gaps (for monitoring and alerting)
-- Tracks periods when no ticks were received
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_gaps (
    gap_id SERIAL PRIMARY KEY,
    instrument TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,  -- NULL if gap is ongoing
    duration_sec INTEGER,  -- Calculated when gap closes
    cause TEXT,  -- 'websocket_disconnect', 'api_error', 'unknown', etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for gap analysis
CREATE INDEX IF NOT EXISTS idx_gaps_instrument
    ON data_gaps (instrument);

CREATE INDEX IF NOT EXISTS idx_gaps_start_time
    ON data_gaps (start_time DESC);

CREATE INDEX IF NOT EXISTS idx_gaps_ongoing
    ON data_gaps (end_time) WHERE end_time IS NULL;

-- ============================================================================
-- Table 4: Collector Status (heartbeat and metrics)
-- Tracks collector uptime, tick rates, errors
-- ============================================================================
CREATE TABLE IF NOT EXISTS collector_status (
    timestamp TIMESTAMPTZ NOT NULL,
    collector_id TEXT NOT NULL,  -- 'collector-1', 'collector-2', etc.
    status TEXT NOT NULL,  -- 'running', 'stopped', 'error'
    ticks_per_sec NUMERIC(8, 2),
    active_subscriptions INTEGER,
    buffer_usage_pct NUMERIC(5, 2),
    last_error TEXT,
    PRIMARY KEY (timestamp, collector_id)
);

-- Convert to hypertable
SELECT create_hypertable(
    'collector_status',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Retention policy: keep only last 90 days of status
SELECT add_retention_policy(
    'collector_status',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- Verification Query
-- Run this after container startup to verify schema creation:
--
--   docker exec -it eth-timescaledb psql -U postgres -d crypto_data \
--     -c "SELECT hypertable_name, num_dimensions FROM timescaledb_information.hypertables;"
--
-- Expected output:
--   hypertable_name      | num_dimensions
--   ---------------------+----------------
--   eth_option_quotes    | 1
--   eth_option_trades    | 1
--   collector_status     | 1
-- ============================================================================

-- ============================================================================
-- Grant Permissions (if using non-postgres user)
-- ============================================================================
-- Uncomment if you create a dedicated collector user:
--
-- CREATE USER collector WITH PASSWORD 'your_password_here';
-- GRANT ALL PRIVILEGES ON DATABASE crypto_data TO collector;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO collector;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO collector;
-- ============================================================================

-- ============================================================================
-- Schema Initialization Complete
-- ============================================================================
-- AC-026: Database schema created for Docker deployment ✓
-- - 3 hypertables created (quotes, trades, status)
-- - 1 regular table (data_gaps)
-- - Compression policies configured (50-70% reduction after 7 days)
-- - Retention policy configured (90 days for status)
-- - Indexes created for common query patterns
-- ============================================================================
