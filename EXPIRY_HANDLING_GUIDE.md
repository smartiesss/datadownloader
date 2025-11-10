# Automatic Instrument Expiry Handling

## Problem

Options expire at 08:00 UTC on their expiry date. The collector was continuing to subscribe to expired instruments, resulting in:
- No ticks received for 30+ minutes
- Wasted WebSocket subscriptions
- No data collection

Example log showing the issue:
```
eth-collector | 2025-11-10 08:32:24,916 - __main__ - WARNING - No ticks received for 1938s (timeout: 10s)
eth-collector | 2025-11-10 08:33:24,932 - __main__ - WARNING - No ticks received for 1998s (timeout: 10s)
```

## Solution

Implemented automatic expiry detection and instrument refresh:

### 1. Expiry Checker Module (`scripts/instrument_expiry_checker.py`)

Parses instrument names to extract expiry dates:

```python
# Example: ETH-10NOV25-3100-C
#   Expiry: 10th November 2025, 08:00 UTC

parse_expiry_from_instrument("ETH-10NOV25-3100-C")
# Returns: 2025-11-10 08:00:00+00:00

is_instrument_expired("ETH-10NOV25-3100-C")
# Returns: True (if current time > 08:05 UTC on 2025-11-10)
```

Functions:
- `parse_expiry_from_instrument()` - Extract expiry datetime
- `is_instrument_expired()` - Check if expired (with 5-min buffer)
- `filter_expired_instruments()` - Remove expired from list
- `get_next_expiry_time()` - Find next expiry in list

### 2. Automatic Refresh Triggers

The collector now automatically refreshes instruments when:

**A. Periodic Check (every hour)**
```python
# Runs every hour or before next expiry (whichever is sooner)
async def _instrument_refresh_loop(self):
    # Check if instruments expired
    # Fetch new active instruments
    # Resubscribe to WebSocket
```

**B. No Ticks Detected (5 minutes)**
```python
# If no ticks for 300 seconds, assume instruments expired
async def _heartbeat_monitor(self):
    if time_since_last_tick > 300:  # 5 minutes
        logger.error("No ticks - instruments may have expired!")
        await self._refresh_instruments()
```

**C. Smart Scheduling**
- Calculates next expiry time from subscribed instruments
- Schedules refresh 1 minute after expiry
- Falls back to hourly if no expiry info available

### 3. Refresh Process

When triggered, the collector:

1. **Fetches new instruments** from Deribit API
2. **Filters expired ones** using expiry checker
3. **Compares with current subscriptions**:
   - Logs added instruments
   - Logs removed instruments
   - Logs unchanged instruments
4. **Closes WebSocket** to trigger reconnect
5. **Resubscribes** with new instrument list

Example log output:
```
2025-11-10 08:05:30 - INFO - 🔄 Refreshing ETH instruments...
2025-11-10 08:05:31 - INFO - Instrument changes: 45 added, 50 removed, 5 unchanged
2025-11-10 08:05:31 - INFO - New instruments: ['ETH-15NOV25-3700-C', 'ETH-15NOV25-3700-P', ...]
2025-11-10 08:05:31 - INFO - Removed instruments: ['ETH-10NOV25-3100-C', 'ETH-10NOV25-3100-P', ...]
2025-11-10 08:05:31 - INFO - Closing WebSocket to refresh subscriptions...
2025-11-10 08:05:32 - INFO - ✅ Instrument refresh complete: 50 active instruments
2025-11-10 08:05:33 - INFO - WebSocket connected successfully
2025-11-10 08:05:33 - INFO - Successfully subscribed to 100 channels
```

## Configuration

Environment variables:

```bash
# How often to check for expired instruments (default: 1 hour)
INSTRUMENT_REFRESH_INTERVAL_SEC=3600

# Trigger refresh if no ticks for this long (default: 5 minutes)
# Set in code: self.no_ticks_refresh_threshold_sec = 300
```

## Benefits

1. **No manual intervention** - Collector automatically updates subscriptions
2. **Fast recovery** - Detects expiry within 5 minutes max
3. **Smart scheduling** - Refreshes around expiry times
4. **Continuous data** - No gaps in data collection
5. **Resource efficient** - Doesn't subscribe to expired instruments

## Testing

Test the expiry checker:

```bash
python3 scripts/instrument_expiry_checker.py
```

Expected output:
```
Testing expiry parsing:
============================================================
ETH-10NOV25-3100-C
  Expiry: 2025-11-10 08:00:00+00:00
  Expired: True

Filtering expired instruments:
============================================================
Active instruments: []  # All expired if current time > expiry
```

## Deployment

The changes are backward compatible and require no configuration changes:

1. **Upload updated files** to NAS:
   - `scripts/ws_tick_collector_multi.py`
   - `scripts/instrument_expiry_checker.py`

2. **Restart collector**:
   ```bash
   sudo docker restart eth-collector
   ```

3. **Monitor logs** for refresh messages:
   ```bash
   sudo docker logs -f eth-collector | grep -E "(refresh|expired|Instrument changes)"
   ```

## How It Works in Production

### Normal Operation
- Collector subscribes to top 50 ETH options
- Collects data continuously
- Checks hourly if instruments expired

### At Expiry Time (08:00 UTC)
- Instruments stop trading at 08:00 UTC
- No ticks received for 5 minutes
- Heartbeat monitor detects: "No ticks for 300s"
- Triggers instrument refresh
- Fetches new active instruments
- Resubscribes to WebSocket
- Data collection resumes immediately

### Proactive Refresh
- If instruments expire at 08:00 UTC
- Refresh loop calculates: "Next expiry in 30 minutes"
- Schedules check at 08:01 UTC
- Automatically refreshes 1 minute after expiry
- Minimal downtime (< 1 minute)

## Files Changed

1. `scripts/instrument_expiry_checker.py` - NEW
   - Expiry parsing and checking logic

2. `scripts/ws_tick_collector_multi.py` - MODIFIED
   - Added `_instrument_refresh_loop()` method
   - Added `_refresh_instruments()` method
   - Modified `_heartbeat_monitor()` to trigger refresh
   - Added import for expiry checker

## Future Improvements

1. **Pre-emptive refresh**: Refresh 5 minutes before expiry
2. **Gradual transition**: Subscribe to new instruments before old ones expire
3. **Expiry notifications**: Alert when large % of instruments about to expire
4. **Historical tracking**: Log which instruments were active at what times

## Troubleshooting

**Collector still subscribed to expired instruments?**
- Check logs for "Instrument refresh" messages
- Verify expiry checker module exists and works
- Restart collector: `sudo docker restart eth-collector`

**Too frequent refreshes?**
- Increase `INSTRUMENT_REFRESH_INTERVAL_SEC`
- Check if heartbeat threshold is too short

**No refresh happening?**
- Check logs for errors in `_instrument_refresh_loop`
- Verify Deribit API is accessible
- Check if `get_top_n_options()` returns results

## Summary

Before this fix:
- ❌ Subscribed to expired instruments indefinitely
- ❌ No data after expiry
- ❌ Required manual restart

After this fix:
- ✅ Automatically detects expiry
- ✅ Refreshes within 5 minutes
- ✅ Continuous data collection
- ✅ Smart scheduling around expiry times
- ✅ Zero manual intervention
