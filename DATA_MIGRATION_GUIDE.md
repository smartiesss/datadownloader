# Data Migration Guide - Local PostgreSQL to NAS

## Overview

This guide covers migrating existing tick data from your local PostgreSQL database to the NAS Docker deployment.

## Current Setup Analysis

**Local Database**:
- Host: `localhost:5432`
- Database: `crypto_data`
- Current Size: ~400 KB (small, fast migration)
- Tables:
  - `eth_option_quotes` - ~80 KB
  - `eth_option_trades` - ~32 KB
  - `eth_option_orderbook_depth` - ~224 KB (NEW)
  - `data_gaps` - ~40 KB
  - `collector_status` - ~16 KB

**Target Setup**:
- NAS Docker container: `crypto_data_db`
- Same schema (applied via docker-entrypoint-initdb.d)

## Migration Strategies

### Strategy 1: Full Database Dump/Restore (Recommended)

**Best for**:
- One-time migration
- Small to medium databases (< 100 GB)
- When you can tolerate brief downtime

**Advantages**:
- Simple and reliable
- Preserves all data, indexes, and constraints
- Fastest for current database size (~400 KB)

**Time Estimate**: < 5 minutes for current data size

### Strategy 2: Live Replication (Advanced)

**Best for**:
- Large databases (> 100 GB)
- Cannot tolerate downtime
- Continuous sync during migration

**Time Estimate**: Initial sync + ongoing replication

### Strategy 3: Table-by-Table Export/Import

**Best for**:
- Selective data migration
- Schema differences between source and target

---

## 🚀 Migration Procedure: Strategy 1 (Recommended)

### Phase 1: Pre-Migration Preparation

#### Step 1: Verify Current Data

```bash
# Check current data volume
PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    (SELECT COUNT(*) FROM eth_option_quotes WHERE tablename = 'eth_option_quotes') as row_count
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check time range of collected data
PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  SELECT
    'quotes' as table_name,
    COUNT(*) as rows,
    MIN(timestamp) as first_record,
    MAX(timestamp) as latest_record
  FROM eth_option_quotes
  UNION ALL
  SELECT
    'trades',
    COUNT(*),
    MIN(timestamp),
    MAX(timestamp)
  FROM eth_option_trades
  UNION ALL
  SELECT
    'depth',
    COUNT(*),
    MIN(timestamp),
    MAX(timestamp)
  FROM eth_option_orderbook_depth;
"
```

**Document these values** - you'll verify them after migration.

#### Step 2: Stop Local Collector (Optional)

```bash
# Find collector process
ps aux | grep ws_tick_collector

# Stop it (if running)
pkill -f ws_tick_collector

# OR if running in background with PID
kill <PID>
```

**Note**: You can keep collecting during migration if database is small. Final incremental sync is possible.

### Phase 2: Export Data from Local Database

#### Option A: Full Database Backup (Recommended for current size)

```bash
# Create backup directory
mkdir -p ~/crypto_data_backups

# Export entire database (compressed)
PGPASSWORD=password pg_dump \
  -h localhost \
  -U postgres \
  -d crypto_data \
  --format=custom \
  --compress=9 \
  --file=~/crypto_data_backups/crypto_data_$(date +%Y%m%d_%H%M%S).backup

# Verify backup file created
ls -lh ~/crypto_data_backups/
```

**Backup File Size**: Should be ~200-400 KB for current data

#### Option B: SQL Format (Human-Readable)

```bash
# Export as SQL file
PGPASSWORD=password pg_dump \
  -h localhost \
  -U postgres \
  -d crypto_data \
  --format=plain \
  --file=~/crypto_data_backups/crypto_data_$(date +%Y%m%d_%H%M%S).sql

# Compress
gzip ~/crypto_data_backups/crypto_data_*.sql
```

#### Option C: Data-Only (Skip Schema)

If NAS already has schema initialized:

```bash
# Export only data (no schema)
PGPASSWORD=password pg_dump \
  -h localhost \
  -U postgres \
  -d crypto_data \
  --format=custom \
  --data-only \
  --compress=9 \
  --file=~/crypto_data_backups/crypto_data_dataonly_$(date +%Y%m%d_%H%M%S).backup
```

### Phase 3: Transfer Backup to NAS

#### Option A: Direct SCP

```bash
# Transfer backup file to NAS
scp ~/crypto_data_backups/crypto_data_*.backup \
  nas-server:/path/to/crypto-collector/backups/

# Verify transfer
ssh nas-server "ls -lh /path/to/crypto-collector/backups/"
```

#### Option B: Via Docker Volume

```bash
# If NAS Docker has backup volume mounted
rsync -avz --progress \
  ~/crypto_data_backups/ \
  nas-server:/path/to/docker/volumes/postgres_backups/
```

### Phase 4: Restore Data to NAS Database

#### Pre-Restore: Ensure NAS Database is Ready

```bash
# SSH to NAS
ssh nas-server
cd /path/to/crypto-collector/

# Verify Docker containers are running
docker-compose ps

# Verify schema is initialized
docker exec crypto_data_db psql -U postgres -d crypto_data -c "\dt"

# Should show: eth_option_quotes, eth_option_trades, eth_option_orderbook_depth, etc.
```

#### Restore: Custom Format (.backup file)

```bash
# Copy backup into container
docker cp /path/to/backups/crypto_data_*.backup crypto_data_db:/tmp/

# Restore database
docker exec -it crypto_data_db pg_restore \
  --username=postgres \
  --dbname=crypto_data \
  --verbose \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  /tmp/crypto_data_*.backup

# Verify restoration
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    'quotes' as table_name,
    COUNT(*) as rows
  FROM eth_option_quotes
  UNION ALL
  SELECT 'trades', COUNT(*) FROM eth_option_trades
  UNION ALL
  SELECT 'depth', COUNT(*) FROM eth_option_orderbook_depth;
"
```

#### Restore: SQL Format (.sql.gz file)

```bash
# Copy SQL file into container
docker cp /path/to/backups/crypto_data_*.sql.gz crypto_data_db:/tmp/

# Restore from SQL
docker exec -i crypto_data_db bash -c \
  "gunzip -c /tmp/crypto_data_*.sql.gz | psql -U postgres -d crypto_data"

# Verify
docker exec crypto_data_db psql -U postgres -d crypto_data -c "SELECT COUNT(*) FROM eth_option_quotes;"
```

### Phase 5: Post-Migration Verification

#### Verify Data Integrity

```bash
# Compare row counts (run on NAS)
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    'quotes' as table_name,
    COUNT(*) as rows,
    MIN(timestamp) as first_record,
    MAX(timestamp) as latest_record
  FROM eth_option_quotes
  UNION ALL
  SELECT 'trades', COUNT(*), MIN(timestamp), MAX(timestamp) FROM eth_option_trades
  UNION ALL
  SELECT 'depth', COUNT(*), MIN(timestamp), MAX(timestamp) FROM eth_option_orderbook_depth;
"

# Compare with values documented in Step 1
# Row counts should match (or be higher if collector kept running)
```

#### Verify Indexes and Constraints

```bash
# Check indexes exist
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    tablename,
    indexname,
    indexdef
  FROM pg_indexes
  WHERE schemaname = 'public'
  ORDER BY tablename, indexname;
"

# Expected indexes:
# - idx_eth_option_quotes_timestamp
# - idx_eth_option_quotes_instrument
# - idx_orderbook_depth_instrument_time
# - idx_orderbook_depth_bids (GIN)
# - idx_orderbook_depth_asks (GIN)
```

#### Test Collector on NAS

```bash
# Start collector (if not already running)
docker-compose up -d collector

# Monitor logs
docker-compose logs -f collector

# Wait 5-10 minutes, then verify new data is being collected
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    MAX(timestamp) as latest_tick,
    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as minutes_ago
  FROM eth_option_quotes;
"

# Should be within 1-2 minutes if collector is running
```

### Phase 6: Cleanup

```bash
# On local machine: Stop local collector permanently
ps aux | grep ws_tick_collector
pkill -f ws_tick_collector

# Optional: Keep local database as backup for a few days
# Then drop it to free space
PGPASSWORD=password dropdb -h localhost -U postgres crypto_data

# On NAS: Remove backup files from container
docker exec crypto_data_db rm /tmp/crypto_data_*.backup
```

---

## 🔄 Incremental Migration (For Continuous Collection)

If you kept the local collector running during migration:

### Step 1: Initial Migration (as above)

Complete Phase 1-5 above.

### Step 2: Export Incremental Data

```bash
# On local machine: Export only new data since initial backup
# Example: Data collected in last 2 hours

PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  COPY (
    SELECT * FROM eth_option_quotes
    WHERE timestamp > NOW() - INTERVAL '2 hours'
  ) TO STDOUT WITH (FORMAT CSV, HEADER)
" > ~/crypto_data_backups/quotes_incremental.csv

PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  COPY (
    SELECT * FROM eth_option_trades
    WHERE timestamp > NOW() - INTERVAL '2 hours'
  ) TO STDOUT WITH (FORMAT CSV, HEADER)
" > ~/crypto_data_backups/trades_incremental.csv

PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  COPY (
    SELECT * FROM eth_option_orderbook_depth
    WHERE timestamp > NOW() - INTERVAL '2 hours'
  ) TO STDOUT WITH (FORMAT CSV, HEADER)
" > ~/crypto_data_backups/depth_incremental.csv
```

### Step 3: Import Incremental Data to NAS

```bash
# Transfer CSV files
scp ~/crypto_data_backups/*_incremental.csv \
  nas-server:/path/to/crypto-collector/backups/

# On NAS: Import incremental data
docker cp /path/to/crypto-collector/backups/quotes_incremental.csv crypto_data_db:/tmp/
docker cp /path/to/crypto-collector/backups/trades_incremental.csv crypto_data_db:/tmp/
docker cp /path/to/crypto-collector/backups/depth_incremental.csv crypto_data_db:/tmp/

docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  COPY eth_option_quotes FROM '/tmp/quotes_incremental.csv' WITH (FORMAT CSV, HEADER);
  COPY eth_option_trades FROM '/tmp/trades_incremental.csv' WITH (FORMAT CSV, HEADER);
  COPY eth_option_orderbook_depth FROM '/tmp/depth_incremental.csv' WITH (FORMAT CSV, HEADER);
"
```

---

## 📊 Migration Estimation

### Current Data Size: ~400 KB

**Estimated Timeline**:
1. **Export**: 10-30 seconds
2. **Transfer to NAS**: 1-5 seconds (local network)
3. **Restore**: 10-30 seconds
4. **Verification**: 1 minute

**Total**: < 5 minutes

### Future Data Size Projections

**After 1 month** (~750 MB):
- Export: 2-5 minutes
- Transfer: 1-2 minutes (1 Gbps network)
- Restore: 3-10 minutes
- **Total**: ~15-20 minutes

**After 1 year** (~9 GB without compression):
- Export: 20-30 minutes
- Transfer: 10-15 minutes
- Restore: 30-60 minutes
- **Total**: ~1-2 hours

**With TimescaleDB Compression** (~900 MB after 1 year):
- Export: 5-10 minutes
- Transfer: 1-2 minutes
- Restore: 10-20 minutes
- **Total**: ~20-30 minutes

---

## 🚨 Troubleshooting

### Restore Fails: "relation already exists"

**Cause**: Schema already initialized by Docker entrypoint

**Solution**: Use `--data-only` flag or `--clean --if-exists`

```bash
docker exec -it crypto_data_db pg_restore \
  --username=postgres \
  --dbname=crypto_data \
  --data-only \
  --verbose \
  /tmp/crypto_data_*.backup
```

### Timestamp Timezone Issues

**Symptom**: Timestamps appear offset after migration

**Check**:
```bash
# Local database timezone
PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "SHOW timezone;"

# NAS database timezone
docker exec crypto_data_db psql -U postgres -d crypto_data -c "SHOW timezone;"
```

**Solution**: Ensure both use same timezone (UTC recommended)

### Missing Depth Data After Migration

**Cause**: Schema not applied before restore

**Solution**:
```bash
# Manually apply depth schema
docker exec -i crypto_data_db psql -U postgres -d crypto_data < schema/002_add_orderbook_depth.sql

# Then retry restore
```

---

## ✅ Post-Migration Checklist

- [ ] All tables migrated successfully
- [ ] Row counts match source database
- [ ] Timestamp ranges correct
- [ ] Indexes recreated
- [ ] Collector running on NAS
- [ ] New data being collected
- [ ] Local collector stopped
- [ ] Backup files transferred and verified
- [ ] Cleanup completed

---

## 📚 Useful Commands Reference

### Export Specific Table

```bash
PGPASSWORD=password pg_dump \
  -h localhost -U postgres -d crypto_data \
  --table=eth_option_orderbook_depth \
  --format=custom \
  --file=depth_table.backup
```

### Check Database Size

```bash
# Local
PGPASSWORD=password psql -h localhost -U postgres -d crypto_data -c "
  SELECT pg_size_pretty(pg_database_size('crypto_data'));
"

# NAS
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT pg_size_pretty(pg_database_size('crypto_data'));
"
```

### Export Schema Only

```bash
PGPASSWORD=password pg_dump \
  -h localhost -U postgres -d crypto_data \
  --schema-only \
  --file=schema_only.sql
```

---

## Summary

**All existing data (including new depth snapshots) can be easily migrated to NAS using pg_dump/pg_restore**. With the current data size (~400 KB), migration takes < 5 minutes.

**Recommendation**: Perform migration after 1-2 weeks of local collection to ensure system is stable, then migrate everything to NAS in a single operation.
