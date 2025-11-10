# Greeks Collection - Deployment Guide

## Summary

Successfully implemented Greeks collection for ETH options. Local testing confirmed Greeks (delta, gamma, theta, vega, rho) and IV values are being collected and stored in the database.

## Test Results (Local)

```
Total quotes (3 min):   779
Quotes with delta:      128 (16% - from WebSocket ticker)
Quotes with gamma:      128
Quotes with mark_iv:    128
Quotes with OI:         128
```

Sample data:
- Delta: 1.0 (deep ITM calls), 0.0 (puts)
- Gamma: 0.0 (deep ITM options)
- Mark IV: 121.36%
- Open Interest: Populated

## Changes Made

### 1. Database Migration (`migrations/add_greeks_columns.sql`)

Added 11 columns to `eth_option_quotes`:
- `delta`, `gamma`, `theta`, `vega`, `rho` - Greek values
- `implied_volatility`, `bid_iv`, `ask_iv`, `mark_iv` - IV values
- `open_interest`, `last_price` - Additional fields

### 2. Collector Updates (`scripts/ws_tick_collector_multi.py`)

**Changed subscription channel:**
- From: `book.{instrument}.100ms` (only bid/ask)
- To: `ticker.{instrument}.100ms` (includes Greeks)

**Updated quote extraction (lines 415-444):**
```python
greeks = data.get('greeks', {})

quote = {
    'timestamp': datetime.fromtimestamp(data['timestamp'] / 1000),
    'instrument_name': data['instrument_name'],
    'best_bid_price': data.get('best_bid_price'),
    'best_bid_amount': data.get('best_bid_amount'),
    'best_ask_price': data.get('best_ask_price'),
    'best_ask_amount': data.get('best_ask_amount'),
    'underlying_price': data.get('underlying_price'),
    'mark_price': data.get('mark_price'),
    # Greeks from nested dictionary
    'delta': greeks.get('delta'),
    'gamma': greeks.get('gamma'),
    'theta': greeks.get('theta'),
    'vega': greeks.get('vega'),
    'rho': greeks.get('rho'),
    # IV fields
    'implied_volatility': data.get('mark_iv'),
    'bid_iv': data.get('bid_iv'),
    'ask_iv': data.get('ask_iv'),
    'mark_iv': data.get('mark_iv'),
    # Additional fields
    'open_interest': data.get('open_interest'),
    'last_price': data.get('last_price')
}
```

### 3. Writer Updates (`scripts/tick_writer_multi.py`)

**Updated INSERT statement (lines 259-283):**
- Added 11 new columns to INSERT
- Changed `ON CONFLICT DO NOTHING` to `ON CONFLICT DO UPDATE SET`
- Used `COALESCE` to merge data from REST API and WebSocket

This allows:
- REST API writes initial quote with mark/underlying prices
- WebSocket ticker writes Greeks for same timestamp+instrument
- COALESCE merges both: keeps non-NULL values from each source

## Deployment Steps for NAS

### Step 1: Run Database Migration

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Run migration SQL
sudo docker exec eth-timescaledb psql -U postgres -d crypto_data < /volume1/crypto-collector/migrations/add_greeks_columns.sql

# Verify columns added
sudo docker exec eth-timescaledb psql -U postgres -d crypto_data -c "\d eth_option_quotes"
```

Expected output: Should show all 11 new columns.

### Step 2: Upload Updated Code

Upload these files to NAS:
1. `/volume1/crypto-collector/scripts/ws_tick_collector_multi.py`
2. `/volume1/crypto-collector/scripts/tick_writer_multi.py`

```bash
# From local machine
scp scripts/ws_tick_collector_multi.py admin@your-nas:/volume1/crypto-collector/scripts/
scp scripts/tick_writer_multi.py admin@your-nas:/volume1/crypto-collector/scripts/
```

### Step 3: Restart ETH Collector Container

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Restart eth-collector container
sudo docker restart eth-collector

# Watch logs to verify Greeks collection
sudo docker logs -f eth-collector
```

Look for:
- `Successfully subscribed to X channels` (should be 2x instruments: ticker + trades)
- `Wrote X ETH quotes` (should see regular writes)
- No errors about missing columns

### Step 4: Verify Greeks in Database

```sql
-- Check quote counts
SELECT
    COUNT(*) as total_quotes,
    COUNT(delta) as quotes_with_delta,
    COUNT(gamma) as quotes_with_gamma,
    COUNT(mark_iv) as quotes_with_iv
FROM eth_option_quotes
WHERE timestamp > NOW() - INTERVAL '5 minutes';

-- Sample quotes with Greeks
SELECT
    instrument,
    timestamp,
    delta,
    gamma,
    theta,
    vega,
    mark_iv,
    open_interest
FROM eth_option_quotes
WHERE timestamp > NOW() - INTERVAL '5 minutes'
  AND delta IS NOT NULL
ORDER BY timestamp DESC
LIMIT 10;
```

Expected results:
- 16-20% of quotes should have Greeks (WebSocket ticker updates)
- Delta should be between 0-1
- Gamma should be positive
- Mark IV should be reasonable (50-200%)

## Rollback Plan

If issues occur:

1. **Revert code:**
   ```bash
   # Use git to restore previous version
   cd /volume1/crypto-collector
   git checkout HEAD~1 scripts/ws_tick_collector_multi.py
   git checkout HEAD~1 scripts/tick_writer_multi.py
   ```

2. **Restart container:**
   ```bash
   sudo docker restart eth-collector
   ```

3. **Database columns remain** (no harm, will just be NULL)

## Notes

- Greek columns can be NULL (for quotes from REST API or old data)
- WebSocket ticker provides Greeks for ~16-20% of quotes
- COALESCE merge strategy ensures no data loss from either source
- No breaking changes - backward compatible with existing queries

## Success Criteria

✅ Database migration completes without errors
✅ Collector subscribes to ticker channels successfully
✅ Quotes are written to database with Greeks populated
✅ Sample queries show delta, gamma, theta, vega, mark_iv values
✅ No increase in error rates

## Support

If issues occur:
1. Check collector logs: `sudo docker logs eth-collector`
2. Check database connection: `sudo docker exec eth-timescaledb psql -U postgres -d crypto_data`
3. Verify schema: `\d eth_option_quotes`
4. Check for NULL Greeks: Run verification SQL above
