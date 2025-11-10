-- ============================================================================
-- Crypto Data Infrastructure - Database Schema
-- Task: T-002
-- Acceptance Criteria: AC-002
--
-- Creates 6 TimescaleDB hypertables for crypto derivatives data:
-- 1. perpetuals_ohlcv
-- 2. futures_ohlcv
-- 3. options_ohlcv
-- 4. options_greeks
-- 5. funding_rates
-- 6. index_prices
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- Table 1: Perpetuals OHLCV
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetuals_ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume NUMERIC(18, 8) NOT NULL,
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('perpetuals_ohlcv', 'timestamp', if_not_exists => TRUE);

-- Create index on instrument for faster filtering
CREATE INDEX IF NOT EXISTS idx_perpetuals_instrument ON perpetuals_ohlcv (instrument);

-- ============================================================================
-- Table 2: Futures OHLCV
-- ============================================================================
CREATE TABLE IF NOT EXISTS futures_ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    expiry_date DATE NOT NULL,
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume NUMERIC(18, 8) NOT NULL,
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('futures_ohlcv', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_futures_instrument ON futures_ohlcv (instrument);
CREATE INDEX IF NOT EXISTS idx_futures_expiry ON futures_ohlcv (expiry_date);

-- ============================================================================
-- Table 3: Options OHLCV
-- ============================================================================
CREATE TABLE IF NOT EXISTS options_ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    strike NUMERIC(18, 8) NOT NULL,
    expiry_date DATE NOT NULL,
    option_type TEXT NOT NULL,  -- 'call' or 'put'
    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume NUMERIC(18, 8) NOT NULL,
    implied_volatility NUMERIC(8, 6),  -- Computed later
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('options_ohlcv', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_options_instrument ON options_ohlcv (instrument);
CREATE INDEX IF NOT EXISTS idx_options_expiry ON options_ohlcv (expiry_date);
CREATE INDEX IF NOT EXISTS idx_options_type ON options_ohlcv (option_type);
CREATE INDEX IF NOT EXISTS idx_options_strike ON options_ohlcv (strike);

-- ============================================================================
-- Table 4: Options Greeks
-- ============================================================================
CREATE TABLE IF NOT EXISTS options_greeks (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    delta NUMERIC(8, 6) NOT NULL,
    gamma NUMERIC(8, 6) NOT NULL,
    vega NUMERIC(8, 6) NOT NULL,
    theta NUMERIC(8, 6) NOT NULL,
    rho NUMERIC(8, 6),
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('options_greeks', 'timestamp', if_not_exists => TRUE);

-- Create index on instrument
CREATE INDEX IF NOT EXISTS idx_greeks_instrument ON options_greeks (instrument);

-- ============================================================================
-- Table 5: Funding Rates
-- ============================================================================
CREATE TABLE IF NOT EXISTS funding_rates (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    funding_rate NUMERIC(12, 10) NOT NULL,
    PRIMARY KEY (timestamp, instrument)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('funding_rates', 'timestamp', if_not_exists => TRUE);

-- Create index on instrument
CREATE INDEX IF NOT EXISTS idx_funding_instrument ON funding_rates (instrument);

-- ============================================================================
-- Table 6: Index Prices
-- ============================================================================
CREATE TABLE IF NOT EXISTS index_prices (
    timestamp TIMESTAMPTZ NOT NULL,
    currency TEXT NOT NULL,  -- 'BTC' or 'ETH'
    price NUMERIC(18, 8) NOT NULL,
    PRIMARY KEY (timestamp, currency)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('index_prices', 'timestamp', if_not_exists => TRUE);

-- Create index on currency
CREATE INDEX IF NOT EXISTS idx_index_currency ON index_prices (currency);

-- ============================================================================
-- Verification
-- ============================================================================
-- Query to verify all hypertables were created successfully
-- Expected output: 6 rows (one for each hypertable)
-- SELECT hypertable_name FROM timescaledb_information.hypertables;

-- ============================================================================
-- Schema Creation Complete
-- ============================================================================
-- AC-002: Database schema created with indexes ✓
-- - 6 tables created as TimescaleDB hypertables
-- - Primary keys defined on (timestamp, instrument) or (timestamp, currency)
-- - Indexes created on frequently filtered columns
-- - NUMERIC precision set to (18, 8) for prices/volumes
-- ============================================================================
