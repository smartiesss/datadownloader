# Local Testing Guide - Complete System Validation

This guide walks you through testing the ENTIRE data collection system on your local machine before deploying to NAS.

## Prerequisites

1. **Docker Desktop** installed and running
2. **8GB RAM** available (4GB for database, 2GB per collector)
3. **50GB disk space** for testing
4. **Stable internet** connection

## Step 1: Prepare Environment (5 minutes)

### 1.1 Navigate to project directory
```bash
cd /Users/doghead/PycharmProjects/datadownloader
```

### 1.2 Create .env file from example
```bash
cp .env.example .env
```

### 1.3 Edit .env file
```bash
# Open in your editor
nano .env  # or use VS Code
```

**Required changes:**
```bash
# Database
POSTGRES_DB=crypto_data
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE  # ⚠️ CHANGE THIS!

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=YOUR_GRAFANA_PASSWORD  # ⚠️ CHANGE THIS!

# Logging
LOG_LEVEL=INFO

# Collection settings (defaults are good)
BUFFER_SIZE_QUOTES=200000
BUFFER_SIZE_TRADES=100000
FLUSH_INTERVAL_SEC=3
SNAPSHOT_INTERVAL_SEC=300  # 5 minutes
```

Save and close.

### 1.4 Create required directories
```bash
mkdir -p logs backups config
```

## Step 2: Clean Slate (2 minutes)

If you've run this before, clean up old containers/volumes:

```bash
# Stop any running containers
docker-compose -f docker-compose-production.yml down -v

# Remove old volumes (⚠️ deletes all data)
docker volume rm datadownloader_timescaledb_data datadownloader_grafana_data 2>/dev/null || true

# Clean up Docker resources
docker system prune -f
```

## Step 3: Build and Start (10 minutes)

### 3.1 Build containers
```bash
docker-compose -f docker-compose-production.yml build --no-cache
```

**Expected output:**
```
Building eth-options-collector
Building btc-options-collector
Building perpetuals-collector
Successfully built...
Successfully tagged...
```

### 3.2 Start database first
```bash
docker-compose -f docker-compose-production.yml up -d timescaledb
```

### 3.3 Wait for database to initialize (30 seconds)
```bash
# Watch the database logs
docker-compose -f docker-compose-production.yml logs -f timescaledb
```

**Look for:**
```
LOG:  database system is ready to accept connections
```

Press `Ctrl+C` when you see this.

### 3.4 Verify schema was created
```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "\dt"
```

**Expected output (should see these tables):**
```
                     List of relations
 Schema |              Name               | Type  |  Owner
--------+---------------------------------+-------+----------
 public | btc_option_orderbook_depth      | table | postgres
 public | btc_option_quotes               | table | postgres
 public | btc_option_trades               | table | postgres
 public | collector_status                | table | postgres
 public | data_gaps                       | table | postgres
 public | eth_option_orderbook_depth      | table | postgres
 public | eth_option_quotes               | table | postgres
 public | eth_option_trades               | table | postgres
 public | perpetuals_orderbook_depth      | table | postgres
 public | perpetuals_quotes               | table | postgres
 public | perpetuals_trades               | table | postgres
```

If tables are missing, check: `docker-compose -f docker-compose-production.yml logs timescaledb`

### 3.5 Start all collectors
```bash
docker-compose -f docker-compose-production.yml up -d
```

### 3.6 Check all containers are running
```bash
docker-compose -f docker-compose-production.yml ps
```

**Expected output (all should be "Up"):**
```
NAME                              STATUS
crypto-timescaledb                Up (healthy)
crypto-eth-options-collector      Up
crypto-btc-options-collector      Up
crypto-perpetuals-collector       Up
crypto-grafana                    Up
```

## Step 4: Verify Data Collection (15 minutes)

### 4.1 Watch ETH options collector logs
```bash
docker-compose -f docker-compose-production.yml logs -f eth-options-collector
```

**Look for (within 2 minutes):**
```
INFO - Database connection pool established successfully
INFO - Fetching top 50 ETH options...
INFO - Subscribed instruments: 50
INFO - Successfully subscribed to 100 channels
INFO - Wrote 50 quotes in 0.15s (333 rows/sec)
```

Press `Ctrl+C` after seeing successful writes.

### 4.2 Watch BTC options collector logs
```bash
docker-compose -f docker-compose-production.yml logs -f btc-options-collector
```

**Look for (within 2 minutes):**
```
INFO - Database connection pool established successfully
INFO - Fetching top 50 BTC options...
INFO - Subscribed instruments: 50
INFO - Successfully subscribed to 100 channels
INFO - Wrote 45 quotes in 0.12s (375 rows/sec)
```

Press `Ctrl+C` after seeing successful writes.

### 4.3 Watch perpetuals collector logs
```bash
docker-compose -f docker-compose-production.yml logs -f perpetuals-collector
```

**Look for (within 1 minute):**
```
INFO - Database connection pool established successfully
INFO - Perpetual instruments: ['BTC-PERPETUAL', 'ETH-PERPETUAL']
INFO - Successfully subscribed to 4 channels
INFO - Wrote 2 quotes in 0.05s (40 rows/sec)
```

Press `Ctrl+C` after seeing successful writes.

### 4.4 Check database has data (after 5 minutes)
```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
    'eth_option_quotes' as table_name,
    COUNT(*) as row_count,
    MAX(timestamp) as latest_data
FROM eth_option_quotes
UNION ALL
SELECT
    'btc_option_quotes',
    COUNT(*),
    MAX(timestamp)
FROM btc_option_quotes
UNION ALL
SELECT
    'perpetuals_quotes',
    COUNT(*),
    MAX(timestamp)
FROM perpetuals_quotes
UNION ALL
SELECT
    'eth_option_trades',
    COUNT(*),
    MAX(timestamp)
FROM eth_option_trades
UNION ALL
SELECT
    'btc_option_trades',
    COUNT(*),
    MAX(timestamp)
FROM btc_option_trades
UNION ALL
SELECT
    'perpetuals_trades',
    COUNT(*),
    MAX(timestamp)
FROM perpetuals_trades
ORDER BY table_name;
"
```

**Expected output (numbers will vary):**
```
     table_name      | row_count |      latest_data
--------------------+-----------+------------------------
 btc_option_quotes  |       450 | 2025-11-10 15:45:23+00
 btc_option_trades  |        89 | 2025-11-10 15:45:18+00
 eth_option_quotes  |       500 | 2025-11-10 15:45:25+00
 eth_option_trades  |       123 | 2025-11-10 15:45:22+00
 perpetuals_quotes  |        20 | 2025-11-10 15:45:24+00
 perpetuals_trades  |        45 | 2025-11-10 15:45:20+00
```

✅ **Success if:**
- All tables have row_count > 0
- latest_data is within last 5 minutes
- Data is flowing continuously

❌ **Failed if:**
- Any table has row_count = 0 after 10 minutes
- latest_data is older than 10 minutes
- See error logs in Step 7

### 4.5 Verify orderbook depth collection
```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
    instrument,
    timestamp,
    jsonb_array_length(bids) as bid_levels,
    jsonb_array_length(asks) as ask_levels
FROM eth_option_orderbook_depth
ORDER BY timestamp DESC
LIMIT 5;
"
```

**Expected output:**
```
    instrument     |         timestamp          | bid_levels | ask_levels
-------------------+----------------------------+------------+------------
 ETH-10NOV25-3100-C| 2025-11-10 15:45:00.123+00 |         20 |         20
 ETH-10NOV25-3200-C| 2025-11-10 15:45:00.456+00 |         18 |         19
 ...
```

✅ **Success:** bid_levels and ask_levels should be ~20 (or less if thin orderbook)

## Step 5: Access Grafana (5 minutes)

### 5.1 Open Grafana
```
http://localhost:3000
```

### 5.2 Login
- Username: `admin` (or from your .env)
- Password: `admin` (or from your .env)

### 5.3 Add TimescaleDB datasource

1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **PostgreSQL**
4. Configure:
   - **Host:** `timescaledb:5432`
   - **Database:** `crypto_data`
   - **User:** `postgres`
   - **Password:** (from your .env)
   - **TLS/SSL Mode:** `disable`
5. Click **Save & Test**

✅ **Success:** "Database Connection OK"

### 5.4 Create a simple dashboard

1. Go to **Dashboards → New Dashboard**
2. Add Panel → Query:

```sql
SELECT
  time_bucket('1 minute', timestamp) AS time,
  instrument,
  AVG(mark_price) as avg_mark_price
FROM eth_option_quotes
WHERE $__timeFilter(timestamp)
  AND instrument = 'ETH-10NOV25-3100-C'
GROUP BY time, instrument
ORDER BY time
```

3. Set visualization to **Time series**
4. Save dashboard

✅ **Success:** You should see a live price chart

## Step 6: 24-Hour Stability Test

### 6.1 Let it run for 24 hours
```bash
# Check status periodically
docker-compose -f docker-compose-production.yml ps

# Check logs for errors
docker-compose -f docker-compose-production.yml logs --tail=100 --follow
```

### 6.2 Check data growth
```bash
# After 1 hour
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

**Expected growth:**
- After 1 hour: ~300-500 MB
- After 24 hours: ~4-8 GB (before compression)

### 6.3 Check for errors
```bash
docker-compose -f docker-compose-production.yml logs | grep ERROR
```

✅ **Success:** No ERROR lines (or only minor/transient errors)

### 6.4 Verify no data gaps
```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
    instrument,
    COUNT(*) as data_points,
    MAX(timestamp) - MIN(timestamp) as time_range,
    COUNT(*) / EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) as points_per_second
FROM eth_option_quotes
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY instrument
ORDER BY data_points DESC
LIMIT 10;
"
```

**Expected:** ~30-60 points per minute per instrument (0.5-1.0 points_per_second)

## Step 7: Troubleshooting

### Issue: Database won't start
```bash
# Check logs
docker-compose -f docker-compose-production.yml logs timescaledb

# Common causes:
# - Port 5432 already in use → change port in docker-compose-production.yml
# - Insufficient memory → increase Docker Desktop memory limit
# - Corrupted volume → run: docker volume rm datadownloader_timescaledb_data
```

### Issue: Collector won't connect to database
```bash
# Check collector logs
docker-compose -f docker-compose-production.yml logs eth-options-collector

# Common errors:
# - "password authentication failed" → check POSTGRES_PASSWORD in .env
# - "could not translate host name" → ensure timescaledb container is running
# - "column does not exist" → schema not loaded, check timescaledb logs
```

### Issue: No data in database
```bash
# Check if collectors are running
docker-compose -f docker-compose-production.yml ps

# Check collector logs for WebSocket errors
docker-compose -f docker-compose-production.yml logs --tail=200 | grep -E "(ERROR|Exception)"

# Test database connection manually
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "SELECT NOW();"
```

### Issue: High CPU or memory usage
```bash
# Check resource usage
docker stats

# If database using too much memory:
# - Reduce shared_buffers in docker-compose-production.yml
# - Add memory limits to collectors
```

## Step 8: Ready for NAS Deployment

✅ **You're ready to deploy to NAS when:**
1. All 5 containers run for 24 hours without restart
2. No ERROR in logs for 24 hours
3. All tables have continuous data (no gaps > 5 minutes)
4. Database size growing steadily (~4-8 GB/day)
5. Grafana dashboards show live data

📋 **Next:** See `NAS_DEPLOYMENT_GUIDE.md`

## Quick Commands Reference

```bash
# Start all containers
docker-compose -f docker-compose-production.yml up -d

# Stop all containers
docker-compose -f docker-compose-production.yml down

# View logs (all containers)
docker-compose -f docker-compose-production.yml logs -f

# View logs (specific container)
docker-compose -f docker-compose-production.yml logs -f eth-options-collector

# Restart a specific container
docker-compose -f docker-compose-production.yml restart eth-options-collector

# Check container status
docker-compose -f docker-compose-production.yml ps

# Execute SQL query
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "SELECT COUNT(*) FROM eth_option_quotes;"

# Access database shell
docker exec -it crypto-timescaledb psql -U postgres -d crypto_data

# Clean slate (delete everything)
docker-compose -f docker-compose-production.yml down -v
```

## Expected Timeline

- **Setup:** 10 minutes
- **First data:** 2-5 minutes after start
- **Stability test:** 24 hours
- **Total:** ~24 hours 15 minutes

After successful 24-hour test, you're ready for NAS deployment!
