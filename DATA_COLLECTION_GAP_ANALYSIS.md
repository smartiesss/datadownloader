# Data Collection Gap Analysis

## User's Expectation vs Current Reality

### What User Expects (Comprehensive Data Collection)

1. **Spot/Index Data**
   - ✅ Expected: Real-time index prices (every second)
   - ⚠️ Reality: Only periodic snapshots via REST API

2. **Perpetuals Data**
   - ✅ Expected: Real-time trades (every second)
   - ❌ Reality: Only OHLCV snapshots (1-minute candles)
   - ✅ Expected: Orderbook depth
   - ❌ Reality: Not collected for perpetuals

3. **Futures Data**
   - ✅ Expected: OHLCV data
   - ✅ Reality: Collecting via REST API

4. **Options Data**
   - ✅ Expected: Real-time quotes
   - ✅ Reality: Collecting via WebSocket
   - ✅ Expected: Real-time trades
   - ✅ Reality: Collecting via WebSocket (just infrequent)
   - ✅ Expected: Orderbook depth
   - ✅ Reality: Collecting via WebSocket
   - ✅ Expected: IV (Implied Volatility)
   - ✅ Reality: Collecting via REST API
   - ✅ Expected: Greeks
   - ✅ Reality: Collecting via REST API

## The Gap

### Missing: Real-Time Perpetual/Spot Data

**Current WebSocket Collector** (`ws_tick_collector_multi.py`):
- Only subscribes to **option instruments**
- Channels: `quote.{instrument}` and `trades.{instrument}` for OPTIONS only

**What's Missing:**
- Real-time perpetual trades
- Real-time perpetual quotes (bid/ask)
- Real-time perpetual orderbook depth
- Real-time index price updates

## Why This Happened

The original requirement stated:
> "spot OHLC, perp OHLC with orderbook depth"

This was interpreted as:
- Spot: OHLC (candles) - ✅ Collecting via REST
- Perp: OHLC (candles) + orderbook depth

But "OHLC" suggests **periodic snapshots** (candles), not real-time tick data.

However, the user clarified:
> "i am expecting trade is happening in every second for spot, perp at least"

This means the user wants **REAL-TIME TICK DATA** for perpetuals, not just OHLCV candles!

## Solution Options

### Option A: Add Perpetual WebSocket Channels (Quick Fix)

Modify `ws_tick_collector_multi.py` to also subscribe to perpetual instruments:

```python
# Subscribe to both options AND perpetuals
perpetual_instrument = f"{currency}-PERPETUAL"
channels = [
    # Options (existing)
    *[f"quote.{inst}" for inst in option_instruments],
    *[f"trades.{inst}" for inst in option_instruments],
    # Add perpetuals
    f"quote.{perpetual_instrument}",
    f"trades.{perpetual_instrument}",
    f"book.{perpetual_instrument}.100ms",  # orderbook updates
]
```

**Pros:**
- Quick to implement (one file change)
- Reuses existing infrastructure
- Same pattern as options

**Cons:**
- Mixes options and perpetuals in one collector
- Different data models (perpetuals don't have strikes/expirations)

### Option B: Separate Perpetual WebSocket Collector (Better Architecture)

Create `ws_perp_collector.py`:
- Dedicated collector for perpetuals only
- Separate database tables: `perpetuals_quotes`, `perpetuals_trades`, `perpetuals_orderbook_depth`
- Cleaner separation of concerns

**Pros:**
- Clean architecture
- Easy to manage separately
- Better for scaling

**Cons:**
- More code to maintain
- Another Docker container

### Option C: Unified Tick Collector (Most Flexible)

Create `ws_unified_collector.py`:
- Collects ALL real-time data (options, perpetuals, futures)
- Smart routing based on instrument type
- Single WebSocket connection

**Pros:**
- Comprehensive solution
- Single point of management
- Most efficient (one WebSocket connection)

**Cons:**
- Most complex implementation
- Requires careful routing logic

## Recommendation

**Option A (Quick Fix)** for immediate testing, then **Option B (Separate Collector)** for production.

This allows:
1. Quick validation that perpetual data collection works
2. Clean architecture for long-term maintenance
3. Easy to add more instrument types later

## Current Data Collection Summary

### What We HAVE (Working)

| Data Type | Frequency | Source | Table |
|-----------|-----------|--------|-------|
| Options Quotes | Real-time | WebSocket | `{currency}_option_quotes` |
| Options Trades | Real-time | WebSocket | `{currency}_option_trades` |
| Options Depth | 5 min | REST/WS | `{currency}_option_orderbook_depth` |
| Options OHLCV | 1 min | REST | `options_ohlcv` |
| Options IV | 1 min | REST | `options_ohlcv` |
| Options Greeks | 1 hour | REST | `options_greeks` |
| Perpetuals OHLCV | 1 min | REST | `perpetuals_ohlcv` |
| Futures OHLCV | 1 min | REST | `futures_ohlcv` |
| Funding Rates | 8 hours | REST | `funding_rates` |

### What We're MISSING

| Data Type | Expected Frequency | Why Missing |
|-----------|-------------------|-------------|
| Perpetuals Quotes | Real-time (100ms) | Not subscribed via WebSocket |
| Perpetuals Trades | Real-time (every trade) | Not subscribed via WebSocket |
| Perpetuals Depth | Real-time (100ms) | Not subscribed via WebSocket |
| Index Prices | Real-time (1s) | Could add via WebSocket |
| Spot Trades | N/A | Deribit doesn't have spot trading |

**Note:** Deribit is a derivatives exchange - there's no spot trading! "Spot price" = "Index price" (calculated from external exchanges).

## Action Items

1. ✅ Complete 15-minute test to see full picture of current data
2. ⚠️ Decide on perpetual collection strategy (Option A, B, or C)
3. ⚠️ Fix REST collector IV overflow error (schema change)
4. ⚠️ Implement perpetual WebSocket collector
5. ⚠️ Test comprehensive collection (options + perpetuals)
6. ⚠️ Deploy to NAS

## Expected Data Volumes with Perpetuals

### Current (Options Only)
- BTC options: ~60 quotes/minute
- ETH options: ~80 quotes/minute
- Total: ~140 quotes/minute = **8,400 quotes/hour**

### With Perpetuals Added
- BTC-PERPETUAL: ~1,000 trades/minute (estimated)
- ETH-PERPETUAL: ~800 trades/minute (estimated)
- Total perpetual trades: ~1,800/minute = **108,000 trades/hour**

### Storage Impact
- Current: ~4 GB/day
- With perpetuals: ~6-8 GB/day (50-100% increase)
- With compression: ~2.5-3.5 GB/day

**Still within NAS capacity!** (4TB = ~400 days of data)

## Next Steps After 15-Min Test

Based on the test results, we'll:
1. Show you exactly what data we collected
2. Confirm the gaps (perpetual trades)
3. Propose implementation plan for perpetual collection
4. Get your approval on approach (A, B, or C)
5. Implement and test
