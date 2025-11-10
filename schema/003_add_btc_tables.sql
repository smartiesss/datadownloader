-- BTC Options Data Tables
-- Same structure as ETH tables, but for BTC options

-- BTC Option Quotes (Level 1: Best Bid/Ask)
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

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_btc_quotes_instrument_time
    ON btc_option_quotes (instrument, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_btc_quotes_time
    ON btc_option_quotes (timestamp DESC);

-- BTC Option Trades
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
CREATE INDEX IF NOT EXISTS idx_btc_trades_time
    ON btc_option_trades (timestamp DESC);

-- BTC Option Orderbook Depth (Full orderbook snapshots)
CREATE TABLE IF NOT EXISTS btc_option_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,  -- Array of {"price": 0.05, "amount": 10.5}
    asks JSONB,  -- Array of {"price": 0.06, "amount": 5.2}
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

CREATE INDEX IF NOT EXISTS idx_btc_orderbook_depth_instrument_time
    ON btc_option_orderbook_depth (instrument, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_btc_orderbook_depth_bids
    ON btc_option_orderbook_depth USING GIN (bids);
CREATE INDEX IF NOT EXISTS idx_btc_orderbook_depth_asks
    ON btc_option_orderbook_depth USING GIN (asks);

-- Comments for documentation
COMMENT ON TABLE btc_option_quotes IS 'BTC options Level 1 quotes (best bid/ask) from WebSocket';
COMMENT ON TABLE btc_option_trades IS 'BTC options trades from WebSocket';
COMMENT ON TABLE btc_option_orderbook_depth IS 'BTC options full orderbook depth snapshots (periodic, from REST API)';
