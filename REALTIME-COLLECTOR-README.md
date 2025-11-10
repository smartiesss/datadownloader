# Real-Time Data Collector - Usage Guide

## Overview

The continuous data collector (`scripts/collect_realtime.py`) keeps your database updated with the latest market data from all Deribit instruments.

## What It Collects

### Collection Intervals

| Data Type | Frequency | Instruments |
|-----------|-----------|-------------|
| Perpetuals OHLCV | Every 1 minute | BTC-PERPETUAL, ETH-PERPETUAL |
| Futures OHLCV | Every 1 minute | ~14 active futures contracts |
| Options OHLCV | Every 1 minute | ~1,590 active options |
| Options Greeks | Every 1 hour | ~1,590 active options |
| Instrument List Refresh | Every 1 hour | Auto-discover new/expired contracts |

## Test Results (2025-10-22)

The collector has been tested and verified working:

- **Perpetuals**: 2 instruments collecting successfully
  - Latest: BTC-PERPETUAL: $113,324.50, ETH-PERPETUAL: $4,077.55 (00:53:00)

- **Futures**: 14 instruments collecting successfully
  - BTC futures: 7 contracts (Oct-Sep 2026)
  - ETH futures: 7 contracts (Oct-Sep 2026)
  - Latest timestamp: 00:54:00

- **Options**: 1,590 instruments collecting successfully
  - 10,543 options updated today
  - Latest timestamp: 00:58:00
  - No overflow errors (NUMERIC(12,6) precision)

## Usage

### Basic Usage (Foreground)

Run the collector in the foreground (press Ctrl+C to stop):

```bash
python3 -m scripts.collect_realtime
```

### Background Usage (Recommended)

Run as a background daemon with logging:

```bash
nohup python3 -m scripts.collect_realtime > logs/realtime.log 2>&1 &
```

To check if it's running:

```bash
ps aux | grep collect_realtime
```

To stop it:

```bash
pkill -f collect_realtime
```

### View Live Logs

```bash
tail -f logs/realtime.log
```

## Database Tables Updated

The collector uses UPSERT operations (idempotent) to update these tables:

1. **perpetuals_ohlcv**
   - Columns: timestamp, instrument, open, high, low, close, volume
   - Primary key: (timestamp, instrument)

2. **futures_ohlcv**
   - Columns: timestamp, instrument, expiry_date, open, high, low, close, volume
   - Primary key: (timestamp, instrument)

3. **options_ohlcv**
   - Columns: timestamp, instrument, strike, expiry_date, option_type, open, high, low, close, volume
   - Primary key: (timestamp, instrument)

4. **options_greeks**
   - Columns: timestamp, instrument, delta, gamma, vega, theta, rho
   - Primary key: (timestamp, instrument)

## Rate Limiting

The collector respects Deribit's API rate limits:

- **Delay**: 0.05 seconds between requests (20 req/sec)
- **Compliance**: Well within Deribit's 20 req/sec public API limit
- **Total collection time**: ~90 seconds per full cycle (2 + 14 + 1590 instruments)

## Monitoring

### Check Latest Data

Perpetuals:
```sql
SELECT instrument, timestamp, close
FROM perpetuals_ohlcv
ORDER BY timestamp DESC LIMIT 5;
```

Futures:
```sql
SELECT instrument, expiry_date, timestamp, close
FROM futures_ohlcv
ORDER BY timestamp DESC LIMIT 10;
```

Options:
```sql
SELECT COUNT(*), MAX(timestamp)
FROM options_ohlcv
WHERE timestamp >= CURRENT_DATE;
```

Greeks:
```sql
SELECT instrument, timestamp, delta, gamma, vega
FROM options_greeks
ORDER BY timestamp DESC LIMIT 10;
```

### Check Collection Health

```bash
# Should see log entries every ~90 seconds
tail -f logs/realtime.log | grep "collection complete"
```

## Deployment as systemd Service (Production)

Create `/etc/systemd/system/crypto-collector.service`:

```ini
[Unit]
Description=Crypto Data Real-Time Collector
After=network.target postgresql.service

[Service]
Type=simple
User=postgres
WorkingDirectory=/path/to/datadownloader
ExecStart=/usr/bin/python3 -m scripts.collect_realtime
Restart=always
RestartSec=30
StandardOutput=append:/path/to/datadownloader/logs/realtime.log
StandardError=append:/path/to/datadownloader/logs/realtime.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-collector
sudo systemctl start crypto-collector
sudo systemctl status crypto-collector
```

## Error Handling

The collector includes robust error handling:

1. **API Failures**: Logs error and continues to next instrument
2. **Database Errors**: Rolls back transaction, logs error, continues
3. **Keyboard Interrupt**: Graceful shutdown on Ctrl+C
4. **NULL Values**: Skips illiquid options with no trade data

## Storage Requirements

Expected database growth:

- **Perpetuals**: ~1 MB/day (2 instruments × 1440 min/day × ~350 bytes)
- **Futures**: ~7 MB/day (14 instruments × 1440 min/day × ~350 bytes)
- **Options OHLCV**: ~900 MB/day (1590 instruments × 1440 min/day × ~400 bytes)
- **Options Greeks**: ~150 MB/day (1590 instruments × 24 hours/day × ~400 bytes)

**Total**: ~1 GB/day

**Recommendation**: Set up daily database backups and consider archiving old data after 1 year.

## Troubleshooting

### Collector Not Updating Data

1. Check if process is running:
   ```bash
   ps aux | grep collect_realtime
   ```

2. Check logs for errors:
   ```bash
   tail -100 logs/realtime.log | grep ERROR
   ```

3. Verify database connection:
   ```bash
   PGPASSWORD=postgres psql -U postgres -d crypto_data -c "SELECT 1;"
   ```

### High CPU/Memory Usage

This is normal during options collection (1590 instruments × 0.05s = ~80 seconds).

Expected resource usage:
- CPU: 5-15% during collection cycles
- Memory: ~100-200 MB
- Network: ~50-100 KB/sec during collection

### Missing Data

Check instrument list refresh:
```bash
tail -200 logs/realtime.log | grep "Instruments refreshed"
```

Expected output every hour:
```
Instruments refreshed: 2 perpetuals, 16 futures, 1590 options
```

## Next Steps

1. Let the collector run continuously to build up real-time data
2. Complete historical backfills for futures (Phase 2)
3. Backfill funding rates (Phase 3)
4. Set up monitoring with Healthchecks.io (Phase 4)
5. Configure daily backups (Phase 4)

## Support

For issues or questions, check:
- Logs: `logs/realtime.log`
- Database: `crypto_data` tables
- Source code: `scripts/collect_realtime.py:1`

---

**Last Updated**: 2025-10-22
**Status**: ✅ Tested and verified working
**Process**: Running in background (0c1c20)
