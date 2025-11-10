# Full Orderbook Depth Collection - Architecture Documentation

## Overview

The ETH options data collector now captures **full orderbook depth** (multiple price levels beyond best bid/ask) to support accurate backtesting and market analysis.

## Architecture

### Two-Tier Data Collection Strategy

The system uses a hybrid approach combining WebSocket and REST API:

#### 1. WebSocket Stream (Real-Time, Level 1)
- **Channel**: `book.{instrument}.100ms`
- **Frequency**: ~10 updates/second per instrument
- **Data**: Best bid/ask prices only (Level 1)
- **Purpose**: High-frequency price updates
- **Note**: Deribit WebSocket does NOT send full depth arrays (`bids`/`asks`) to reduce bandwidth

#### 2. REST API Snapshots (Periodic, Full Depth)
- **Endpoint**: `GET /public/get_order_book?instrument_name={instrument}&depth=20`
- **Frequency**: Every 5 minutes (configurable via `SNAPSHOT_INTERVAL_SEC` env var)
- **Data**: Full orderbook with 20 price levels (bids and asks arrays)
- **Purpose**: Complete orderbook snapshots for backtesting
- **Implementation**: `scripts/ws_tick_collector.py::_periodic_snapshot_loop()`

### Why This Design?

**Problem**: WebSocket `book.{instrument}.100ms` channel only sends:
- `best_bid_price`, `best_bid_amount`
- `best_ask_price`, `best_ask_amount`
- Mark price, underlying price

It does NOT send full `bids[]` and `asks[]` arrays like the REST API.

**Solution**: Periodic REST API snapshots (every 5 minutes) capture full depth while WebSocket provides real-time Level 1 updates.

**Benefits**:
- Real-time price updates (WebSocket)
- Complete depth data for backtesting (REST snapshots)
- Bandwidth efficient
- Data completeness guaranteed

## Database Schema

### Table: `eth_option_orderbook_depth`

```sql
CREATE TABLE eth_option_orderbook_depth (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    bids JSONB,              -- Array of {"price": float, "amount": float}
    asks JSONB,              -- Array of {"price": float, "amount": float}
    mark_price DECIMAL(20, 10),
    underlying_price DECIMAL(20, 10),
    open_interest DECIMAL(20, 8),
    volume_24h DECIMAL(20, 8)
);

-- Index for efficient querying
CREATE INDEX idx_orderbook_depth_instrument_time
    ON eth_option_orderbook_depth (instrument, timestamp DESC);

-- GIN index for JSONB querying
CREATE INDEX idx_orderbook_depth_bids
    ON eth_option_orderbook_depth USING GIN (bids);
CREATE INDEX idx_orderbook_depth_asks
    ON eth_option_orderbook_depth USING GIN (asks);
```

### JSONB Format

Deribit API format:
```json
{
  "bids": [[2950.5, 10.5], [2950.0, 5.2], ...],
  "asks": [[2951.0, 8.3], [2951.5, 12.1], ...]
}
```

Stored format (converted for efficient querying):
```json
{
  "bids": [
    {"price": 2950.5, "amount": 10.5},
    {"price": 2950.0, "amount": 5.2}
  ],
  "asks": [
    {"price": 2951.0, "amount": 8.3},
    {"price": 2951.5, "amount": 12.1}
  ]
}
```

## Storage Requirements

Based on actual measurements with 50 instruments and 20 depth levels:

### Per Snapshot
- **Average row size**: 1,802 bytes (1.76 KB)
- **Instruments tracked**: 50 (top 50 by open interest)
- **Depth levels**: 20 bid levels + 20 ask levels

### Daily Storage (5-minute snapshots)
- **Snapshots per day**: 50 instruments × 288 snapshots/day = 14,400 snapshots
- **Daily storage**: ~25 MB/day

### Long-Term Projections (Uncompressed)
- **1 month**: ~750 MB
- **1 year**: ~9 GB
- **5 years**: ~44 GB

### With TimescaleDB Compression (80-90% reduction)
- **1 year**: ~900 MB - 1.8 GB
- **5 years**: ~4 - 9 GB

## Implementation Details

### Modified Files

1. **`schema/002_add_orderbook_depth.sql`** - Database schema
2. **`scripts/tick_buffer.py`** - Added depth buffering (`add_depth()`, `get_and_clear()`)
3. **`scripts/tick_writer.py`** - Added `write_depth_snapshots()` method
4. **`scripts/orderbook_snapshot.py`** - Enhanced to fetch and save full depth
5. **`scripts/ws_tick_collector.py`** - Added periodic snapshot loop

### Key Code Sections

#### Periodic Snapshot Loop (ws_tick_collector.py:174-215)
```python
async def _periodic_snapshot_loop(self):
    """Fetch periodic REST API snapshots every 5 minutes"""
    snapshot_interval_sec = int(os.getenv('SNAPSHOT_INTERVAL_SEC', 300))

    while self.running:
        await asyncio.sleep(snapshot_interval_sec)

        snapshot_fetcher = OrderbookSnapshotFetcher(
            database_url=self.database_url,
            rest_api_url="https://www.deribit.com/api/v2"
        )

        # Fetch with full depth enabled
        await snapshot_fetcher.fetch_and_populate(
            self.instruments,
            save_full_depth=True
        )
```

#### Depth Buffering (tick_buffer.py:140-156)
```python
def add_depth(self, depth: Dict):
    """Add full orderbook depth snapshot to buffer"""
    with self._lock:
        self._depth.append(depth)
        self.depth_stats.ticks_received += 1

        utilization = self.get_depth_utilization()
        if utilization >= self.flush_threshold_pct:
            self._warn_buffer_full('depth', utilization)
```

#### Database Write (tick_writer.py:190-228)
```python
async def write_depth_snapshots(self, depth_snapshots: List[Dict]) -> int:
    """Write depth snapshots in batches with retry logic"""
    for i in range(0, len(depth_snapshots), self.batch_size):
        batch = depth_snapshots[i:i + self.batch_size]
        written = await self._write_depth_batch(batch)
        total_written += written

    return total_written
```

## Configuration

### Environment Variables

```bash
# Periodic snapshot interval (default: 300 seconds = 5 minutes)
SNAPSHOT_INTERVAL_SEC=300

# Buffer sizes
BUFFER_SIZE_QUOTES=200000
BUFFER_SIZE_TRADES=100000
# Depth buffer is hardcoded to 50,000 snapshots

# Database connection
DATABASE_URL=postgresql://postgres:password@localhost:5432/crypto_data
```

### Recommended Settings

**For Production**:
- `SNAPSHOT_INTERVAL_SEC=300` (5 minutes) - Balances data completeness and API rate limits
- Enable TimescaleDB compression for 80-90% storage reduction

**For Testing**:
- `SNAPSHOT_INTERVAL_SEC=60` (1 minute) - More frequent snapshots for validation

## Data Verification

### Check Depth Snapshots
```sql
-- Count total snapshots
SELECT
    COUNT(*) as total_snapshots,
    COUNT(DISTINCT instrument) as unique_instruments,
    MIN(timestamp) as first_snapshot,
    MAX(timestamp) as latest_snapshot
FROM eth_option_orderbook_depth;

-- Sample depth data
SELECT
    instrument,
    timestamp,
    jsonb_array_length(bids) as num_bids,
    jsonb_array_length(asks) as num_asks,
    mark_price,
    underlying_price
FROM eth_option_orderbook_depth
ORDER BY timestamp DESC
LIMIT 10;
```

### Query Specific Price Levels
```sql
-- Get top 5 bid levels for an instrument
SELECT
    instrument,
    timestamp,
    jsonb_array_elements(bids) as bid_level
FROM eth_option_orderbook_depth
WHERE instrument = 'ETH-10NOV25-3000-P'
ORDER BY timestamp DESC
LIMIT 5;
```

## Use Cases

### 1. Backtesting with Realistic Slippage
- Access full depth to simulate order execution
- Calculate slippage for different order sizes
- Model market impact accurately

### 2. Liquidity Analysis
- Measure bid-ask spread across depth levels
- Identify liquidity dry-ups
- Track order book imbalance

### 3. Market Microstructure Research
- Study order book dynamics
- Analyze quote fading
- Detect spoofing patterns

## Monitoring

### Check Collector Status
```bash
# View logs
tail -f logs/ws_tick_collector.log | grep -E "Periodic snapshot|STATS"

# Expected log entries every 5 minutes:
# 2025-11-09 15:53:57 - Fetching periodic REST API snapshot...
# 2025-11-09 15:53:59 - Periodic snapshot complete: 50 quotes, 50 instruments with data
```

### Verify Data Freshness
```sql
-- Check latest snapshot timestamp
SELECT
    MAX(timestamp) as latest_snapshot,
    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as minutes_ago
FROM eth_option_orderbook_depth;

-- Should be within 5-10 minutes if collector is running
```

## Troubleshooting

### No Depth Data Collected

**Problem**: `depth_received` counter stays at 0

**Cause**: Deribit WebSocket `book.{instrument}.100ms` does not send `bids`/`asks` arrays

**Solution**: This is expected! Depth data comes from periodic REST API snapshots, not WebSocket.

**Verify**: Check `eth_option_orderbook_depth` table for snapshots every 5 minutes:
```sql
SELECT COUNT(*) FROM eth_option_orderbook_depth
WHERE timestamp >= NOW() - INTERVAL '10 minutes';
```

### High Storage Usage

**Solution**: Enable TimescaleDB compression:
```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert to hypertable
SELECT create_hypertable(
    'eth_option_orderbook_depth',
    'timestamp',
    migrate_data => true
);

-- Enable compression (80-90% reduction)
ALTER TABLE eth_option_orderbook_depth
SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument');

SELECT add_compression_policy(
    'eth_option_orderbook_depth',
    INTERVAL '7 days'
);
```

## Future Enhancements

1. **WebSocket Depth Reconstruction**
   - Maintain local orderbook state
   - Apply delta updates from WebSocket
   - Would require full snapshot on reconnect

2. **Adaptive Snapshot Frequency**
   - Increase frequency during high volatility
   - Reduce frequency during quiet periods

3. **Compression Optimization**
   - Custom compression for JSONB arrays
   - Differential encoding for price levels

## Summary

The depth collection system successfully captures:
- ✅ Full orderbook snapshots (20 levels) every 5 minutes via REST API
- ✅ Real-time best bid/ask updates via WebSocket
- ✅ Efficient JSONB storage in PostgreSQL
- ✅ ~25 MB/day storage requirement (50 instruments)
- ✅ Compatible with TimescaleDB for 80-90% compression

**Status**: Production ready ✅
