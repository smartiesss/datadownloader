# Comprehensive Data Collection Plan - ETH & BTC
## Executive Summary

**Good News**: Your codebase already has most collectors and database schemas! You just need to deploy them.

**Current State**:
- Running: ETH options WebSocket tick collector only
- Available but NOT running: Comprehensive REST API collectors for all data types

**Target State**: Collect ALL data for both ETH and BTC:
1. Spot/Index Prices (ETH, BTC)
2. Perpetuals OHLCV + Orderbook Depth
3. Futures OHLCV
4. Options OHLCV + Orderbook Depth + Greeks + Tick Data
5. Funding Rates (every 8 hours)

**Deployment Time**: ~2 hours
**Storage Growth**: ~3-5 GB/month (with compression)

---

## Architecture Overview

### Two-Tier Collection Strategy

**Tier 1: WebSocket Collectors (Real-time Tick Data)**
- Ultra-high frequency data (every price change)
- Options quotes, trades, orderbook updates
- Currently: ETH only
- Plan: Add BTC

**Tier 2: REST API Collectors (OHLCV + Greeks + Funding)**
- Lower frequency snapshots (1 min - 8 hours)
- Perpetuals, Futures, Options OHLCV, Greeks, Funding Rates
- Currently: NOT running
- Plan: Deploy for ETH + BTC

---

## Database Schema Status

### ✅ Already Created (schema.sql)
```
perpetuals_ohlcv       - ETH + BTC perpetuals 1-min OHLCV
futures_ohlcv          - ETH + BTC futures 1-min OHLCV
options_ohlcv          - ETH + BTC options 1-min OHLCV + bid/ask + IV
options_greeks         - ETH + BTC options Greeks (delta, gamma, vega, theta, rho)
funding_rates          - ETH + BTC perpetual funding rates
index_prices           - ETH + BTC spot index prices
```

### ✅ Already Created (schema/001, 002)
```
eth_option_quotes         - ETH options tick data (WebSocket)
eth_option_trades         - ETH options trades (WebSocket)
eth_option_orderbook_depth - ETH options full orderbook snapshots
```

### ⚠️ Created but NOT Deployed (schema/003)
```
btc_option_quotes         - BTC options tick data (WebSocket)
btc_option_trades         - BTC options trades (WebSocket)
btc_option_orderbook_depth - BTC options full orderbook snapshots
```

---

## Data Collection Matrix

| Data Type | ETH Status | BTC Status | Frequency | Collector |
|-----------|-----------|-----------|-----------|-----------|
| **Options Tick Data** | ✅ Running | ❌ Not deployed | Real-time | ws_tick_collector.py |
| **Options Orderbook Depth** | ✅ Running | ❌ Not deployed | 5 min | ws_tick_collector.py |
| **Options OHLCV + IV** | ❌ Not running | ❌ Not running | 1 min | collect_realtime.py |
| **Options Greeks** | ❌ Not running | ❌ Not running | 1 hour | collect_realtime.py |
| **Perpetuals OHLCV** | ❌ Not running | ❌ Not running | 1 min | collect_realtime.py |
| **Perpetuals Depth** | ⚠️ Missing | ⚠️ Missing | TBD | Need to add |
| **Futures OHLCV** | ❌ Not running | ❌ Not running | 1 min | collect_realtime.py |
| **Funding Rates** | ❌ Not running | ❌ Not running | 8 hours | backfill_funding_rates.py |
| **Spot Index** | ⚠️ Missing | ⚠️ Missing | 1 min | Need to add |

---

## Implementation Plan

### Phase 1: Deploy Existing Collectors (1 hour)

**Step 1.1: Deploy BTC WebSocket Tables**
```sql
-- On NAS, apply schema/003_add_btc_tables.sql
docker-compose exec postgres psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/003_add_btc_tables.sql
```

**Step 1.2: Modify ws_tick_collector.py for Multi-Currency**
Current: Hardcoded to ETH only
Change: Add CURRENCY environment variable support

**Step 1.3: Deploy REST API Collector**
Current: collect_realtime.py exists but not in docker-compose.yml
Change: Add service to docker-compose.yml

**Step 1.4: Deploy Funding Rates Collector**
Current: backfill_funding_rates.py exists
Change: Add to docker-compose.yml for continuous collection

### Phase 2: Add Missing Collectors (30 min)

**Step 2.1: Add Perpetuals Orderbook Depth Collector**
- Create new table: `perpetuals_orderbook_depth`
- Add collector method to fetch orderbook snapshots
- Frequency: Every 5 minutes (same as options)

**Step 2.2: Add Spot/Index Price Collector**
- Table exists: `index_prices`
- Add collector method using `/public/get_index_price` API
- Frequency: Every 1 minute

### Phase 3: Testing & Verification (30 min)

**Step 3.1: Verify All Tables Receiving Data**
```sql
-- Check all tables have recent data
SELECT 'perpetuals_ohlcv' as table_name, COUNT(*), MAX(timestamp) FROM perpetuals_ohlcv
UNION ALL
SELECT 'futures_ohlcv', COUNT(*), MAX(timestamp) FROM futures_ohlcv
-- ... etc for all tables
```

**Step 3.2: Monitor Data Quality**
- Check for gaps
- Verify row counts match expectations
- Monitor disk usage

---

## Detailed Implementation Steps

### STEP 1: Stop Current Collector on NAS

```bash
# SSH to NAS
ssh your-username@192.168.68.62
cd /volume1/crypto-collector

# Stop current collector
sudo docker-compose down

# Backup current .env
cp .env .env.backup
```

### STEP 2: Apply Database Schemas

```bash
# Apply BTC tables
sudo docker-compose exec postgres psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/003_add_btc_tables.sql

# Verify schemas exist
sudo docker-compose exec postgres psql -U postgres -d crypto_data -c "
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"
```

Expected output: 13 tables
```
eth_option_quotes
eth_option_trades
eth_option_orderbook_depth
btc_option_quotes
btc_option_trades
btc_option_orderbook_depth
perpetuals_ohlcv
futures_ohlcv
options_ohlcv
options_greeks
funding_rates
index_prices
data_gaps
collector_status
```

### STEP 3: Create Multi-Currency WebSocket Collector

**File: scripts/ws_tick_collector_multi.py** (we'll create this)

This will:
- Accept CURRENCY environment variable (ETH or BTC)
- Subscribe to currency-specific WebSocket channels
- Write to currency-specific tables

### STEP 4: Update docker-compose.yml

Add these services:
1. `ws-collector-eth` - WebSocket collector for ETH (current one, renamed)
2. `ws-collector-btc` - WebSocket collector for BTC (new)
3. `rest-collector` - REST API collector for OHLCV/Greeks (new)
4. `funding-collector` - Funding rates collector (new)

### STEP 5: Update .env Configuration

Add these variables:
```bash
# WebSocket Collectors
WS_ETH_TOP_N_INSTRUMENTS=50
WS_BTC_TOP_N_INSTRUMENTS=50

# REST Collector
REST_PERPETUAL_INTERVAL=60     # 1 minute
REST_FUTURES_INTERVAL=60       # 1 minute
REST_OPTIONS_OHLCV_INTERVAL=60 # 1 minute
REST_GREEKS_INTERVAL=3600      # 1 hour

# Funding Collector
FUNDING_INTERVAL=28800         # 8 hours
```

---

## Expected Storage Requirements

### Tier 1: WebSocket Tick Data (High Frequency)

**Options Tick Data (quotes + trades)**:
- ETH: ~15M quotes/day = ~1.5 GB/day uncompressed, ~500 MB compressed
- BTC: ~20M quotes/day = ~2.0 GB/day uncompressed, ~700 MB compressed
- **Total**: ~1.2 GB/day compressed

**Options Orderbook Depth (every 5 min)**:
- ETH: 288 snapshots/day × 100 instruments = ~50 MB/day
- BTC: 288 snapshots/day × 150 instruments = ~75 MB/day
- **Total**: ~125 MB/day

### Tier 2: REST API Data (Low Frequency)

**OHLCV (1-min candles)**:
- Perpetuals: 2 instruments × 1440 candles/day = ~5 MB/day
- Futures: ~10 instruments × 1440 candles/day = ~25 MB/day
- Options: ~250 instruments × 1440 candles/day = ~300 MB/day
- **Total**: ~330 MB/day

**Greeks (1-hour snapshots)**:
- Options: ~250 instruments × 24 snapshots/day = ~10 MB/day

**Funding Rates (every 8 hours)**:
- Perpetuals: 2 instruments × 3 rates/day = <1 MB/day

### Total Storage Growth

**Per Day**: ~1.2 GB (tick) + 0.125 GB (depth) + 0.33 GB (OHLCV) + 0.01 GB (Greeks) = **~1.7 GB/day uncompressed**

**With TimescaleDB Compression** (50-70% reduction after 7 days):
- **~700 MB/day compressed**
- **~21 GB/month**
- **~250 GB/year**

**Your 4TB NAS**: Can store **~16 years** of data with compression!

---

## Extensibility for Future Symbols

### Adding New Cryptocurrencies (SOL, AVAX, etc.)

**Database**: No changes needed! Tables use TEXT instrument column

**WebSocket Collector**:
```bash
# Just add new Docker service in docker-compose.yml
ws-collector-sol:
  environment:
    CURRENCY: SOL
    TOP_N_INSTRUMENTS: 30
```

**REST Collector**: Already fetches all currencies from `fetch_instruments()` API

### Adding New Data Types

**Pattern**: Copy existing collector and modify
1. Create table schema
2. Add collector method
3. Add Docker service
4. Update .env with interval settings

---

## Code Changes Required

### 1. Create ws_tick_collector_multi.py

**Changes from current ws_tick_collector.py**:
```python
# Current (hardcoded):
CURRENCY = "ETH"

# New (from environment):
CURRENCY = os.getenv('CURRENCY', 'ETH')  # Default ETH for backward compatibility
TOP_N = int(os.getenv(f'WS_{CURRENCY}_TOP_N_INSTRUMENTS', 50))

# Update table names:
quotes_table = f"{CURRENCY.lower()}_option_quotes"
trades_table = f"{CURRENCY.lower()}_option_trades"
depth_table = f"{CURRENCY.lower()}_option_orderbook_depth"
```

### 2. Update collect_realtime.py

**Current**: Fetches both BTC and ETH
**Change**: Add database connection string from environment

```python
def __init__(self):
    db_url = os.getenv('DATABASE_URL', 'dbname=crypto_data user=postgres')
    self.db_conn_str = db_url.replace('postgresql://', '').replace('postgres:', 'user=postgres password=').replace('@timescaledb:5432/', ' dbname=')
```

### 3. Create funding_rates_collector.py

**Based on**: backfill_funding_rates.py
**Changes**:
- Run continuously instead of one-time backfill
- Fetch every 8 hours
- Add to Docker service

### 4. Update docker-compose.yml

**Add these services**:

```yaml
  ws-collector-eth:
    build: .
    container_name: ws-collector-eth
    command: python -m scripts.ws_tick_collector_multi
    environment:
      CURRENCY: ETH
      WS_ETH_TOP_N_INSTRUMENTS: ${WS_ETH_TOP_N_INSTRUMENTS:-50}
      DATABASE_URL: ${DATABASE_URL}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      - timescaledb
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  ws-collector-btc:
    build: .
    container_name: ws-collector-btc
    command: python -m scripts.ws_tick_collector_multi
    environment:
      CURRENCY: BTC
      WS_BTC_TOP_N_INSTRUMENTS: ${WS_BTC_TOP_N_INSTRUMENTS:-50}
      DATABASE_URL: ${DATABASE_URL}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      - timescaledb
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  rest-collector:
    build: .
    container_name: rest-collector
    command: python -m scripts.collect_realtime
    environment:
      DATABASE_URL: ${DATABASE_URL}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      PERPETUAL_INTERVAL: ${REST_PERPETUAL_INTERVAL:-60}
      FUTURES_INTERVAL: ${REST_FUTURES_INTERVAL:-60}
      OPTIONS_OHLCV_INTERVAL: ${REST_OPTIONS_OHLCV_INTERVAL:-60}
      GREEKS_INTERVAL: ${REST_GREEKS_INTERVAL:-3600}
    depends_on:
      - timescaledb
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  funding-collector:
    build: .
    container_name: funding-collector
    command: python -m scripts.funding_rates_collector
    environment:
      DATABASE_URL: ${DATABASE_URL}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      FUNDING_INTERVAL: ${FUNDING_INTERVAL:-28800}
    depends_on:
      - timescaledb
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Backup current database: `pg_dump -U postgres crypto_data > backup_$(date +%Y%m%d).sql`
- [ ] Backup current docker-compose.yml
- [ ] Backup current .env
- [ ] Document current disk usage: `df -h`

### Deployment

- [ ] Stop current collectors: `docker-compose down`
- [ ] Apply BTC schema: `003_add_btc_tables.sql`
- [ ] Copy modified code to NAS
- [ ] Update docker-compose.yml
- [ ] Update .env with new variables
- [ ] Rebuild images: `docker-compose build`
- [ ] Start all services: `docker-compose up -d`

### Post-Deployment Verification

- [ ] All 5 containers running: `docker ps` (timescaledb, ws-eth, ws-btc, rest, funding)
- [ ] No errors in logs: `docker-compose logs --tail=50`
- [ ] Data flowing to all tables (wait 5 minutes, then query each table)
- [ ] Disk space check: `df -h`
- [ ] Set up monitoring alerts

---

## Verification Queries

### Check All Tables Have Data

```sql
-- Run this after 10 minutes of collection
SELECT
  'eth_option_quotes' as table_name,
  COUNT(*) as rows,
  MAX(timestamp) as latest,
  NOW() - MAX(timestamp) as age
FROM eth_option_quotes
UNION ALL
SELECT 'btc_option_quotes', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM btc_option_quotes
UNION ALL
SELECT 'perpetuals_ohlcv', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM perpetuals_ohlcv
UNION ALL
SELECT 'futures_ohlcv', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM futures_ohlcv
UNION ALL
SELECT 'options_ohlcv', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM options_ohlcv
UNION ALL
SELECT 'options_greeks', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM options_greeks
UNION ALL
SELECT 'funding_rates', COUNT(*), MAX(timestamp), NOW() - MAX(timestamp)
FROM funding_rates
ORDER BY age DESC;
```

**Expected Output**:
- All tables show age < 10 minutes
- Row counts increasing over time

### Check Data Quality

```sql
-- Check for instruments per currency
SELECT
  SUBSTRING(instrument FROM 1 FOR 3) as currency,
  COUNT(DISTINCT instrument) as num_instruments,
  MIN(timestamp) as first_data,
  MAX(timestamp) as latest_data
FROM eth_option_quotes
GROUP BY currency;

-- Should show ETH and BTC
```

---

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Container Health**
   - All 5 containers running
   - CPU/memory usage < 80%
   - No restart loops

2. **Data Freshness**
   - Latest timestamp < 5 minutes old for all tables
   - No gaps > 5 minutes in tick data

3. **Disk Usage**
   - Alert at 80% capacity
   - Monitor daily growth rate

4. **API Rate Limits**
   - Monitor 429 errors in logs
   - Adjust intervals if hitting limits

### Simple Monitoring Script

```bash
#!/bin/bash
# /volume1/crypto-collector/monitor.sh

echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"

echo ""
echo "=== Latest Data Timestamps ==="
docker-compose exec postgres psql -U postgres -d crypto_data -c "
SELECT 'eth_quotes' as table_name, MAX(timestamp) as latest FROM eth_option_quotes
UNION ALL SELECT 'btc_quotes', MAX(timestamp) FROM btc_option_quotes
UNION ALL SELECT 'perpetuals', MAX(timestamp) FROM perpetuals_ohlcv;
"

echo ""
echo "=== Disk Usage ==="
df -h /volume1
```

Run via cron every hour:
```
0 * * * * /volume1/crypto-collector/monitor.sh > /volume1/crypto-collector/logs/monitor.log
```

---

## Rollback Plan

If something goes wrong:

```bash
# Stop all containers
docker-compose down

# Restore backup files
cp .env.backup .env
cp docker-compose.yml.backup docker-compose.yml

# Start only the original collector
docker-compose up -d timescaledb collector

# Verify
docker ps
docker-compose logs collector
```

---

## Next Steps After Deployment

### Week 1: Stability & Monitoring
- Monitor container health daily
- Check disk growth matches predictions
- Look for error patterns in logs

### Week 2: Enable Compression
```sql
-- Enable compression on all hypertables after 7 days
ALTER TABLE perpetuals_ohlcv SET (timescaledb.compress);
SELECT add_compression_policy('perpetuals_ohlcv', INTERVAL '7 days');
-- Repeat for all tables
```

### Month 1: Add Continuous Aggregates (Materialized Views)
```sql
-- Pre-compute common queries (e.g., hourly OHLCV from tick data)
CREATE MATERIALIZED VIEW hourly_eth_options
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', timestamp) as hour,
  instrument,
  FIRST(best_bid_price, timestamp) as open,
  MAX(best_bid_price) as high,
  MIN(best_bid_price) as low,
  LAST(best_bid_price, timestamp) as close
FROM eth_option_quotes
GROUP BY hour, instrument;
```

### Month 3: Grafana Dashboards
- Real-time tick rate graphs
- Data quality metrics
- Disk usage forecasting
- Options chain visualizations

---

## Estimated Timeline

| Phase | Tasks | Time | Dependencies |
|-------|-------|------|--------------|
| **Code Changes** | Create multi-currency collectors | 2 hours | None |
| **Testing Locally** | Test on Mac before NAS | 1 hour | Code changes |
| **NAS Deployment** | Transfer files, update configs | 30 min | Testing |
| **Database Setup** | Apply schemas, verify | 15 min | NAS deployment |
| **Container Startup** | docker-compose up, monitor | 15 min | Database setup |
| **Verification** | Check all tables, data quality | 30 min | Containers running |
| **Documentation** | Update NAS guides | 30 min | Verification complete |
| **TOTAL** | | **5 hours** | |

**Fast Track** (skip local testing): **2 hours**

---

## Summary

**What You Have**:
- ✅ All database schemas
- ✅ All collector scripts
- ✅ ETH options WebSocket collector (running on NAS)

**What You Need**:
- 🔧 Make collectors multi-currency (add CURRENCY env var)
- 🔧 Add Docker services for REST, funding collectors
- 🔧 Deploy BTC schema to database
- 🔧 Update .env configuration
- ✅ Start all services

**After Deployment**:
- 📊 13 tables collecting data (4 ETH options tick, 4 BTC options tick, 5 OHLCV/Greeks/Funding)
- 🌍 Both ETH and BTC comprehensive coverage
- 🚀 Easy to add SOL, AVAX, etc. (just add Docker service)
- 💾 ~21 GB/month storage growth (you have 4 TB!)
- ⚡ 5 Docker containers running 24/7

**Your Next Action**: Would you like me to start creating the code changes? I can:
1. Create the multi-currency WebSocket collector
2. Create the funding rates continuous collector
3. Update docker-compose.yml
4. Update .env.example

Then you can test locally on Mac before deploying to NAS.
