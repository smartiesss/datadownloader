-- Migration 007: Create lifecycle_events table for audit trail
-- Purpose: Log all lifecycle events (subscriptions, expirations, new listings)
-- Author: Project Manager
-- Date: 2025-11-11

-- Drop existing table if recreating
DROP TABLE IF EXISTS lifecycle_events CASCADE;

-- Create lifecycle_events table
CREATE TABLE lifecycle_events (
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id SERIAL,
    event_type TEXT NOT NULL,  -- 'subscription_added', 'subscription_removed', 'instrument_expired', 'instrument_listed', 'rebalance_triggered'
    instrument_name TEXT,  -- NULL for system-wide events
    currency TEXT NOT NULL,  -- 'BTC' or 'ETH'
    collector_id TEXT,  -- e.g., 'btc-options-0', 'eth-options-2'
    details JSONB,  -- Additional event metadata
    success BOOLEAN DEFAULT TRUE,  -- Whether the action succeeded
    error_message TEXT,  -- Error details if success = FALSE
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_time, id)  -- TimescaleDB requires timestamp in PRIMARY KEY
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('lifecycle_events', 'event_time');

-- Create indexes for efficient queries
CREATE INDEX idx_lifecycle_events_event_type ON lifecycle_events(event_type);
CREATE INDEX idx_lifecycle_events_currency ON lifecycle_events(currency);
CREATE INDEX idx_lifecycle_events_instrument ON lifecycle_events(instrument_name);
CREATE INDEX idx_lifecycle_events_collector ON lifecycle_events(collector_id);
CREATE INDEX idx_lifecycle_events_success ON lifecycle_events(success) WHERE success = FALSE;
CREATE INDEX idx_lifecycle_events_time_type ON lifecycle_events(event_time DESC, event_type);

-- Add retention policy (keep 90 days of lifecycle events)
SELECT add_retention_policy('lifecycle_events', INTERVAL '90 days');

-- Add comments for documentation
COMMENT ON TABLE lifecycle_events IS 'Audit trail of all lifecycle management events';
COMMENT ON COLUMN lifecycle_events.event_type IS 'Type: subscription_added, subscription_removed, instrument_expired, instrument_listed, rebalance_triggered';
COMMENT ON COLUMN lifecycle_events.instrument_name IS 'Instrument affected by event (NULL for system-wide events)';
COMMENT ON COLUMN lifecycle_events.currency IS 'Currency affected: BTC or ETH';
COMMENT ON COLUMN lifecycle_events.collector_id IS 'Collector that processed the event (e.g., btc-options-0)';
COMMENT ON COLUMN lifecycle_events.details IS 'JSON metadata (e.g., {"old_partition": 0, "new_partition": 1, "reason": "load_balancing"})';
COMMENT ON COLUMN lifecycle_events.success IS 'TRUE if action succeeded, FALSE if failed';
COMMENT ON COLUMN lifecycle_events.error_message IS 'Error details if action failed';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration 007: lifecycle_events table created successfully';
END $$;
