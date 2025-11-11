-- ============================================================================
-- COMPLETE DATABASE SCHEMA FOR NAS DEPLOYMENT
-- This script creates ALL tables needed for the lifecycle management system
-- Run this ONCE on fresh TimescaleDB database
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- ETH OPTIONS TABLES (from 001_init_timescaledb.sql)
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
    delta NUMERIC(8, 6),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 6),
    vega NUMERIC(8, 6),
    rho NUMERIC(8, 6),
    implied_volatility NUMERIC(8, 4),
    bid_iv NUMERIC(8, 4),
    ask_iv NUMERIC(8, 4),
    mark_iv NUMERIC(8, 4),
    open_interest NUMERIC(18, 8),
    last_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument)
);

SELECT create_hypertable(
    'eth_option_quotes',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_eth_quotes_instrument_timestamp
    ON eth_option_quotes (instrument, timestamp DESC);

ALTER TABLE eth_option_quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy(
    'eth_option_quotes',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ETH Trades
CREATE TABLE IF NOT EXISTS eth_option_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC(18, 8) NOT NULL,
    amount NUMERIC(18, 8) NOT NULL,
    direction TEXT NOT NULL,
    iv NUMERIC(8, 4),
    index_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument, trade_id)
);

SELECT create_hypertable(
    'eth_option_trades',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_eth_trades_instrument_timestamp
    ON eth_option_trades (instrument, timestamp DESC);

ALTER TABLE eth_option_trades SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy(
    'eth_option_trades',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- ETH ORDERBOOK DEPTH (from 002_add_orderbook_depth.sql)
-- ============================================================================

CREATE TABLE IF NOT EXISTS eth_option_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,
    asks JSONB,
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

CREATE INDEX IF NOT EXISTS idx_eth_orderbook_depth_instrument_time
    ON eth_option_orderbook_depth (instrument, timestamp DESC);

-- ============================================================================
-- BTC OPTIONS TABLES (from 003_add_btc_tables.sql)
-- ============================================================================

CREATE TABLE IF NOT EXISTS btc_option_quotes (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    best_bid_price DECIMAL(20, 10),
    best_bid_amount DECIMAL(20, 8),
    best_ask_price DECIMAL(20, 10),
    best_ask_amount DECIMAL(20, 8),
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

CREATE INDEX IF NOT EXISTS idx_btc_quotes_instrument_time
    ON btc_option_quotes (instrument, timestamp DESC);

CREATE TABLE IF NOT EXISTS btc_option_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    trade_id VARCHAR(50) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    price DECIMAL(20, 10) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    PRIMARY KEY (trade_id, instrument)
);

CREATE INDEX IF NOT EXISTS idx_btc_trades_instrument_time
    ON btc_option_trades (instrument, timestamp DESC);

CREATE TABLE IF NOT EXISTS btc_option_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,
    asks JSONB,
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

CREATE INDEX IF NOT EXISTS idx_btc_orderbook_depth_instrument_time
    ON btc_option_orderbook_depth (instrument, timestamp DESC);

-- ============================================================================
-- PERPETUALS TABLES (from 004_add_perpetual_tick_tables.sql)
-- ============================================================================

CREATE TABLE IF NOT EXISTS perpetuals_quotes (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_perpetuals_quotes_time ON perpetuals_quotes (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_quotes_instrument ON perpetuals_quotes (instrument, timestamp DESC);

SELECT create_hypertable('perpetuals_quotes', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

ALTER TABLE perpetuals_quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('perpetuals_quotes', INTERVAL '7 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS perpetuals_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    trade_id VARCHAR(50) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    price NUMERIC(20, 10) NOT NULL,
    amount NUMERIC(20, 8) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    tick_direction INTEGER,
    liquidation BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (trade_id, instrument)
);

CREATE INDEX IF NOT EXISTS idx_perpetuals_trades_time ON perpetuals_trades (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_trades_instrument ON perpetuals_trades (instrument, timestamp DESC);

SELECT create_hypertable('perpetuals_trades', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

ALTER TABLE perpetuals_trades SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('perpetuals_trades', INTERVAL '7 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS perpetuals_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,
    asks JSONB,
    mark_price NUMERIC(20, 10),
    index_price NUMERIC(20, 10),
    funding_rate NUMERIC(10, 8),
    open_interest NUMERIC(20, 8),
    volume_24h NUMERIC(20, 8),
    PRIMARY KEY (timestamp, instrument)
);

CREATE INDEX IF NOT EXISTS idx_perpetuals_depth_time ON perpetuals_orderbook_depth (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_perpetuals_depth_instrument ON perpetuals_orderbook_depth (instrument, timestamp DESC);

SELECT create_hypertable('perpetuals_orderbook_depth', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

ALTER TABLE perpetuals_orderbook_depth SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('perpetuals_orderbook_depth', INTERVAL '7 days', if_not_exists => TRUE);

-- ============================================================================
-- LIFECYCLE MANAGEMENT TABLES (from 006 & 007)
-- ============================================================================

CREATE TABLE IF NOT EXISTS instrument_metadata (
    instrument_name TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    strike_price NUMERIC(18, 8),
    expiry_date TIMESTAMPTZ,
    option_type TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    listed_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_instrument_metadata_currency ON instrument_metadata(currency);
CREATE INDEX idx_instrument_metadata_is_active ON instrument_metadata(is_active);
CREATE INDEX idx_instrument_metadata_expiry_date ON instrument_metadata(expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_instrument_metadata_active_by_currency ON instrument_metadata(currency, is_active);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id SERIAL,
    event_type TEXT NOT NULL,
    instrument_name TEXT,
    currency TEXT NOT NULL,
    collector_id TEXT,
    details JSONB,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_time, id)
);

SELECT create_hypertable('lifecycle_events', 'event_time');

CREATE INDEX idx_lifecycle_events_event_type ON lifecycle_events(event_type);
CREATE INDEX idx_lifecycle_events_currency ON lifecycle_events(currency);
CREATE INDEX idx_lifecycle_events_instrument ON lifecycle_events(instrument_name);
CREATE INDEX idx_lifecycle_events_collector ON lifecycle_events(collector_id);
CREATE INDEX idx_lifecycle_events_success ON lifecycle_events(success) WHERE success = FALSE;

SELECT add_retention_policy('lifecycle_events', INTERVAL '90 days');

-- ============================================================================
-- UTILITY TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_gaps (
    gap_id SERIAL PRIMARY KEY,
    instrument TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_sec INTEGER,
    cause TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gaps_instrument ON data_gaps (instrument);
CREATE INDEX IF NOT EXISTS idx_gaps_start_time ON data_gaps (start_time DESC);

CREATE TABLE IF NOT EXISTS collector_status (
    timestamp TIMESTAMPTZ NOT NULL,
    collector_id TEXT NOT NULL,
    status TEXT NOT NULL,
    ticks_per_sec NUMERIC(8, 2),
    active_subscriptions INTEGER,
    buffer_usage_pct NUMERIC(5, 2),
    last_error TEXT,
    PRIMARY KEY (timestamp, collector_id)
);

SELECT create_hypertable(
    'collector_status',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

SELECT add_retention_policy(
    'collector_status',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'NAS SCHEMA INITIALIZATION COMPLETE';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Created tables:';
    RAISE NOTICE '  ETH: eth_option_quotes, eth_option_trades, eth_option_orderbook_depth';
    RAISE NOTICE '  BTC: btc_option_quotes, btc_option_trades, btc_option_orderbook_depth';
    RAISE NOTICE '  PERP: perpetuals_quotes, perpetuals_trades, perpetuals_orderbook_depth';
    RAISE NOTICE '  LIFECYCLE: instrument_metadata, lifecycle_events';
    RAISE NOTICE '  UTILITY: data_gaps, collector_status';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Ready for lifecycle management deployment!';
    RAISE NOTICE '============================================================';
END $$;
