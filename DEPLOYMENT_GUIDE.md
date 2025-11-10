# Comprehensive Data Collection - Deployment Guide

## Overview

This deployment collects **ALL data types** for both ETH and BTC:

**WebSocket Collectors** (Real-time Tick Data):
- ETH options quotes, trades, orderbook depth
- BTC options quotes, trades, orderbook depth

**REST API Collectors** (Periodic Snapshots):
- Perpetuals OHLCV (1-min candles)
- Futures OHLCV (1-min candles)
- Options OHLCV with bid/ask/IV (1-min)
- Options Greeks (hourly)
- Funding rates (every 8 hours)

**Total**: 5 Docker containers + 1 database = 6 containers running 24/7

---

## Prerequisites

**Local Testing (Mac)**:
- Docker Desktop installed
- PostgreSQL client (optional, for verification)
- 4 GB free disk space

**NAS Deployment** (Synology DS925+):
- DSM 7.x with Container Manager
- 2x 4TB drives in RAID 1 (4TB usable)
- Static IP configured
- SSH enabled

---

## Part 1: Local Testing on Mac

### Step 1.1: Apply Database Schemas

First, ensure all schemas are applied to your local PostgreSQL:

```bash
cd /Users/doghead/PycharmProjects/datadownloader

# Start PostgreSQL (if not already running)
# Option A: Use existing local PostgreSQL
psql -U postgres -d crypto_data -f schema.sql
psql -U postgres -d crypto_data -f schema/001_init_timescaledb.sql
psql -U postgres -d crypto_data -f schema/002_add_orderbook_depth.sql
psql -U postgres -d crypto_data -f schema/003_add_btc_tables.sql

# Option B: Use Docker PostgreSQL
docker run -d --name test-postgres \
  -e POSTGRES_PASSWORD=test123 \
  -e POSTGRES_DB=crypto_data \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg16

# Wait 10 seconds for startup
sleep 10

# Apply schemas
cat schema.sql schema/001_init_timescaledb.sql schema/002_add_orderbook_depth.sql schema/003_add_btc_tables.sql | \
  docker exec -i test-postgres psql -U postgres -d crypto_data
```

### Step 1.2: Create .env File

```bash
cp .env.example .env

# Edit .env and set strong passwords
# Minimum changes required:
# POSTGRES_PASSWORD=your_strong_password
# GRAFANA_PASSWORD=your_grafana_password
```

### Step 1.3: Build Docker Images

```bash
# Build the collector image
docker build -t crypto-collector .
```

### Step 1.4: Test Individual Collectors

Before running everything, test each collector individually:

**Test ETH WebSocket Collector** (5 minutes):
```bash
# Set environment variables
export CURRENCY=ETH
export TOP_N_INSTRUMENTS=10  # Start with just 10 for testing
export DATABASE_URL=postgresql://postgres:test123@localhost:5432/crypto_data
export LOG_LEVEL=INFO

# Run for 5 minutes
timeout 300 python -m scripts.ws_tick_collector_multi

# Check results
psql -U postgres -d crypto_data -c "
SELECT 'eth_option_quotes' as table_name, COUNT(*) as rows, MAX(timestamp) as latest
FROM eth_option_quotes
UNION ALL
SELECT 'eth_option_trades', COUNT(*), MAX(timestamp)
FROM eth_option_trades;
"
```

**Expected output**: 50-200 quotes, 5-20 trades

**Test BTC WebSocket Collector** (5 minutes):
```bash
export CURRENCY=BTC
timeout 300 python -m scripts.ws_tick_collector_multi

# Check results
psql -U postgres -d crypto_data -c "
SELECT COUNT(*) as btc_quotes FROM btc_option_quotes;
"
```

**Expected output**: 100-300 quotes

**Test REST Collector** (2 minutes):
```bash
# This will collect perpetuals, futures, options OHLCV, and Greeks
timeout 120 python -m scripts.collect_realtime

# Check results
psql -U postgres -d crypto_data -c "
SELECT 'perpetuals_ohlcv' as table_name, COUNT(*) FROM perpetuals_ohlcv
UNION ALL SELECT 'futures_ohlcv', COUNT(*) FROM futures_ohlcv
UNION ALL SELECT 'options_ohlcv', COUNT(*) FROM options_ohlcv
UNION ALL SELECT 'options_greeks', COUNT(*) FROM options_greeks;
"
```

**Expected output**: 2-10 rows per table

**Test Funding Collector** (1 minute):
```bash
python -m scripts.funding_rates_collector &
COLLECTOR_PID=$!

# Wait 60 seconds
sleep 60

# Stop it
kill $COLLECTOR_PID

# Check results
psql -U postgres -d crypto_data -c "
SELECT COUNT(*) as funding_rates FROM funding_rates;
"
```

**Expected output**: 10-50 rows (depends on available history)

### Step 1.5: Test Full Stack with Docker Compose

```bash
# Start all services
docker-compose -f docker-compose-comprehensive.yml up -d

# Check all containers are running
docker ps

# Expected output: 6 containers running
# - crypto-timescaledb
# - ws-collector-eth
# - ws-collector-btc
# - rest-collector
# - funding-collector
# - crypto-grafana

# Monitor logs from all collectors
docker-compose -f docker-compose-comprehensive.yml logs -f

# Press Ctrl+C to stop watching logs
```

### Step 1.6: Verify Data Collection

Wait 10 minutes, then check all tables:

```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
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
"
```

**Success Criteria**:
- All tables have `rows > 0`
- All tables have `age < 10 minutes`
- No errors in logs

### Step 1.7: Stop Test Environment

```bash
docker-compose -f docker-compose-comprehensive.yml down

# Clean up test database (optional)
docker rm -f test-postgres
```

---

## Part 2: Deploy to Synology NAS

### Step 2.1: Prepare NAS

SSH into your NAS:
```bash
ssh your-username@192.168.68.62
```

### Step 2.2: Transfer Files to NAS

**On your Mac**:
```bash
cd /Users/doghead/PycharmProjects/datadownloader

# Create tarball (excludes logs, cache, etc.)
tar -czf /tmp/crypto-collector-full.tar.gz \
  --exclude='logs/*' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='backups/*' \
  .

# Upload to NAS via File Station web interface:
# 1. Open http://192.168.68.62:5000 in browser
# 2. Go to File Station
# 3. Navigate to /volume1/docker/
# 4. Upload crypto-collector-full.tar.gz
```

### Step 2.3: Extract and Configure on NAS

**On NAS (via SSH)**:
```bash
cd /volume1/docker

# Extract files
mkdir -p crypto-collector
cd crypto-collector
tar -xzf ../crypto-collector-full.tar.gz

# Create .env file
cp .env.example .env
nano .env

# Edit these critical settings:
# POSTGRES_PASSWORD=<strong password>
# GRAFANA_PASSWORD=<strong password>

# Save and exit (Ctrl+X, then Y, then Enter)
```

### Step 2.4: Apply Database Schemas

```bash
cd /volume1/docker/crypto-collector

# Start only database first
sudo docker-compose -f docker-compose-comprehensive.yml up -d timescaledb

# Wait for database to be ready (30 seconds)
sleep 30

# Apply all schemas
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/schema.sql
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/001_init_timescaledb.sql
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/002_add_orderbook_depth.sql
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/003_add_btc_tables.sql

# Verify schemas
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"

# Expected: 13 tables
# - btc_option_orderbook_depth
# - btc_option_quotes
# - btc_option_trades
# - collector_status
# - data_gaps
# - eth_option_orderbook_depth
# - eth_option_quotes
# - eth_option_trades
# - funding_rates
# - futures_ohlcv
# - index_prices
# - options_greeks
# - options_ohlcv
# - perpetuals_ohlcv
```

### Step 2.5: Create Logs and Config Directories

```bash
cd /volume1/docker/crypto-collector

mkdir -p logs config backups
chmod 777 logs backups  # Allow container to write
chmod 755 config
```

### Step 2.6: Start All Services

```bash
cd /volume1/docker/crypto-collector

# Build images (first time only)
sudo docker-compose -f docker-compose-comprehensive.yml build

# Start all services
sudo docker-compose -f docker-compose-comprehensive.yml up -d

# Check all containers are running
sudo docker ps

# Expected: 6 containers
# CONTAINER ID   IMAGE                           STATUS
# xxxx           crypto-collector                Up 10 seconds   ws-collector-eth
# xxxx           crypto-collector                Up 10 seconds   ws-collector-btc
# xxxx           crypto-collector                Up 10 seconds   rest-collector
# xxxx           crypto-collector                Up 10 seconds   funding-collector
# xxxx           grafana/grafana:latest          Up 12 seconds   crypto-grafana
# xxxx           timescale/timescaledb:latest    Up 42 seconds   crypto-timescaledb
```

### Step 2.7: Monitor Logs

```bash
# Watch all logs in real-time
sudo docker-compose -f docker-compose-comprehensive.yml logs -f

# Watch specific collector
sudo docker logs -f ws-collector-eth

# Check for errors
sudo docker-compose -f docker-compose-comprehensive.yml logs | grep -i error

# Should see NO errors (except maybe initial connection retries)
```

### Step 2.8: Verify Data Collection (Wait 10 minutes)

```bash
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
  'eth_option_quotes' as table_name,
  COUNT(*) as rows,
  MIN(timestamp) as first,
  MAX(timestamp) as latest,
  NOW() - MAX(timestamp) as age
FROM eth_option_quotes
UNION ALL
SELECT 'btc_option_quotes', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM btc_option_quotes
UNION ALL
SELECT 'eth_option_trades', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM eth_option_trades
UNION ALL
SELECT 'btc_option_trades', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM btc_option_trades
UNION ALL
SELECT 'perpetuals_ohlcv', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM perpetuals_ohlcv
UNION ALL
SELECT 'options_greeks', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM options_greeks
UNION ALL
SELECT 'funding_rates', COUNT(*), MIN(timestamp), MAX(timestamp), NOW() - MAX(timestamp)
FROM funding_rates;
"
```

**Success Criteria**:
- All tables show `age < 10 minutes`
- ETH quotes: > 1000 rows
- BTC quotes: > 1000 rows
- Perpetuals OHLCV: > 10 rows
- Options Greeks: > 100 rows
- Funding rates: > 10 rows

---

## Part 3: Monitoring & Maintenance

### Daily Monitoring

```bash
# Quick health check
cd /volume1/docker/crypto-collector

# Check all containers running
sudo docker ps | grep crypto

# Check latest data age
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT MAX(timestamp) as latest_eth_quote FROM eth_option_quotes
UNION ALL SELECT MAX(timestamp) as latest_btc_quote FROM btc_option_quotes;
"

# If latest data is > 10 minutes old, restart collectors
sudo docker-compose -f docker-compose-comprehensive.yml restart ws-collector-eth ws-collector-btc
```

### Weekly Maintenance

```bash
# Check disk usage
df -h /volume1

# Check database size
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT pg_size_pretty(pg_database_size('crypto_data'));
"

# Check row counts
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
  'eth_quotes' as table_name,
  COUNT(*) as rows,
  pg_size_pretty(pg_total_relation_size('eth_option_quotes')) as size
FROM eth_option_quotes
UNION ALL
SELECT 'btc_quotes', COUNT(*), pg_size_pretty(pg_total_relation_size('btc_option_quotes'))
FROM btc_option_quotes;
"
```

### Enable Compression (After 1 Week)

```bash
sudo docker exec crypto-timescaledb psql -U postgres -d crypto_data <<EOF
-- Enable compression on all hypertables
ALTER TABLE perpetuals_ohlcv SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'instrument'
);
SELECT add_compression_policy('perpetuals_ohlcv', INTERVAL '7 days');

ALTER TABLE futures_ohlcv SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'instrument'
);
SELECT add_compression_policy('futures_ohlcv', INTERVAL '7 days');

ALTER TABLE options_ohlcv SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'instrument'
);
SELECT add_compression_policy('options_ohlcv', INTERVAL '7 days');

ALTER TABLE options_greeks SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'instrument'
);
SELECT add_compression_policy('options_greeks', INTERVAL '7 days');

ALTER TABLE funding_rates SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'instrument'
);
SELECT add_compression_policy('funding_rates', INTERVAL '7 days');
EOF
```

---

## Part 4: Backup & Recovery

### Setup Automated Backups

```bash
cd /volume1/docker/crypto-collector

# Create backup script
nano backup.sh
```

Paste this content:
```bash
#!/bin/bash
BACKUP_DIR="/volume1/backups/crypto-collector"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p ${BACKUP_DIR}

# Backup database
docker exec crypto-timescaledb pg_dump -U postgres crypto_data | \
  gzip > ${BACKUP_DIR}/backup_${DATE}.sql.gz

# Keep only last 30 days
find ${BACKUP_DIR} -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup complete: ${BACKUP_DIR}/backup_${DATE}.sql.gz"
```

Save and make executable:
```bash
chmod +x backup.sh

# Test it
./backup.sh
```

**Setup Daily Cron Job** (via Synology Task Scheduler):
1. Open DSM Control Panel
2. Go to Task Scheduler
3. Create → Scheduled Task → User-defined script
4. General: Name = "Crypto Data Backup", User = root
5. Schedule: Daily at 2:00 AM
6. Task Settings: User-defined script = `/volume1/docker/crypto-collector/backup.sh`

### Restore from Backup

```bash
cd /volume1/backups/crypto-collector

# List backups
ls -lh backup_*.sql.gz

# Restore from specific backup
gunzip -c backup_20251109_020000.sql.gz | \
  docker exec -i crypto-timescaledb psql -U postgres -d crypto_data
```

---

## Part 5: Troubleshooting

### Problem: Containers Keep Restarting

**Solution**:
```bash
# Check logs for errors
sudo docker logs ws-collector-eth --tail=100

# Common issues:
# 1. Database not ready → Wait 30 seconds and restart
# 2. Permission denied on logs → chmod 777 logs
# 3. Out of memory → Reduce TOP_N_INSTRUMENTS in .env
```

### Problem: No Data Being Collected

**Solution**:
```bash
# Check collector is subscribing
sudo docker logs ws-collector-eth | grep -i "subscribed"

# Should see: "Successfully subscribed to 100 channels"

# If not, check DATABASE_URL
sudo docker exec ws-collector-eth env | grep DATABASE_URL
```

### Problem: Database Growing Too Fast

**Solution**:
```bash
# Enable compression immediately (instead of waiting 7 days)
# See "Enable Compression" section above

# Or reduce data collection:
# Edit .env and set:
# WS_ETH_TOP_N=25  # Reduce from 50
# WS_BTC_TOP_N=25
# SNAPSHOT_INTERVAL_SEC=600  # Increase from 300 (10 min instead of 5)
```

---

## Success Metrics

After 24 hours, you should see:
- **ETH quotes**: 100,000 - 200,000 rows
- **BTC quotes**: 150,000 - 300,000 rows
- **Perpetuals OHLCV**: ~2,880 rows (1440 per instrument)
- **Options OHLCV**: ~300,000 rows (~250 instruments × 1440)
- **Options Greeks**: ~6,000 rows (~250 instruments × 24)
- **Funding rates**: ~6 rows (3 per perpetual)

**Database size**: ~100-200 MB (uncompressed), ~50-100 MB (compressed after 7 days)

After 1 week:
- **Database size**: ~1-2 GB (compressed)
- **Disk space used**: < 1% of 4TB

Your NAS is now collecting comprehensive crypto data 24/7!

---

## Next Steps

1. **Set up Grafana dashboards** (http://your-nas-ip:3000)
2. **Enable compression** after 1 week
3. **Monitor daily** via Task Scheduler
4. **Add more currencies** (SOL, AVAX) by adding new ws-collector services

Enjoy your automated data collection system!
