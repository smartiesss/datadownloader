# Docker Deployment Checklist - NAS Setup

## Overview

This checklist ensures all recent changes (including full orderbook depth collection) are included in the Docker deployment on your NAS.

## ✅ Pre-Deployment Checklist

### 1. Database Schema Files

Ensure all schema migration files are in the correct order:

```bash
schema/
├── 000_legacy_tables.sql          # Legacy tables (optional)
├── 001_init_timescaledb.sql       # Main tables (quotes, trades)
└── 002_add_orderbook_depth.sql    # ✅ NEW: Orderbook depth table
```

**Action**: Verify files exist and are numbered sequentially
```bash
ls -l schema/*.sql
```

### 2. Docker Compose Configuration

**File**: `docker-compose.yml`

Ensure it includes:

```yaml
version: '3.8'

services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: crypto_data_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: crypto_data
    volumes:
      # Schema initialization
      - ./schema:/docker-entrypoint-initdb.d
      # Data persistence
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  collector:
    build: .
    container_name: eth_options_collector
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      # Database connection
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres:5432/crypto_data

      # WebSocket connection
      DERIBIT_WS_URL: wss://www.deribit.com/ws/api/v2

      # Collection settings
      TOP_N_INSTRUMENTS: 50
      BUFFER_SIZE_QUOTES: 200000
      BUFFER_SIZE_TRADES: 100000
      FLUSH_INTERVAL_SEC: 3

      # ✅ NEW: Periodic snapshot interval for full depth
      SNAPSHOT_INTERVAL_SEC: 300  # 5 minutes

      # Logging
      LOG_LEVEL: INFO
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: python -m scripts.ws_tick_collector

volumes:
  postgres_data:
    driver: local
```

**Key Points**:
- ✅ `schema/002_add_orderbook_depth.sql` will auto-run on first start
- ✅ `SNAPSHOT_INTERVAL_SEC` environment variable configured
- ✅ TimescaleDB image for compression support
- ✅ Health check ensures database is ready before starting collector

### 3. Dockerfile

**File**: `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ ./scripts/
COPY .env .env

# Create logs directory
RUN mkdir -p logs

# Run collector
CMD ["python", "-m", "scripts.ws_tick_collector"]
```

**Verify Dependencies** (`requirements.txt`):
```txt
python-dotenv>=1.0.0
asyncpg>=0.29.0
websockets>=12.0
aiohttp>=3.9.0
psycopg2-binary>=2.9.9
```

### 4. Environment Variables

**File**: `.env` (for Docker)

```bash
# Database Configuration
DB_PASSWORD=your_secure_password_here

# Collection Settings
TOP_N_INSTRUMENTS=50
BUFFER_SIZE_QUOTES=200000
BUFFER_SIZE_TRADES=100000
FLUSH_INTERVAL_SEC=3

# ✅ NEW: Periodic depth snapshot interval
SNAPSHOT_INTERVAL_SEC=300  # 5 minutes (recommended)

# Logging
LOG_LEVEL=INFO

# Optional: Backup configuration
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=30
```

### 5. Files to Include in Docker Build

**Checklist**:
- [x] `scripts/ws_tick_collector.py` - ✅ With periodic snapshot loop
- [x] `scripts/tick_buffer.py` - ✅ With depth buffering
- [x] `scripts/tick_writer.py` - ✅ With write_depth_snapshots()
- [x] `scripts/orderbook_snapshot.py` - ✅ With save_full_depth parameter
- [x] `scripts/instrument_fetcher.py`
- [x] `schema/000_legacy_tables.sql`
- [x] `schema/001_init_timescaledb.sql`
- [x] `schema/002_add_orderbook_depth.sql` - ✅ NEW
- [x] `requirements.txt`
- [x] `.env`
- [x] `Dockerfile`
- [x] `docker-compose.yml`

### 6. Schema Migration Verification

After deploying to NAS, verify schema was applied:

```bash
# SSH into NAS
ssh nas-server

# Check if depth table exists
docker exec -it crypto_data_db psql -U postgres -d crypto_data -c "\dt"

# Expected output should include:
#   eth_option_quotes
#   eth_option_trades
#   eth_option_orderbook_depth  ← NEW TABLE
#   data_gaps
#   collector_status

# Verify depth table schema
docker exec -it crypto_data_db psql -U postgres -d crypto_data -c "\d eth_option_orderbook_depth"

# Expected columns:
#   timestamp, instrument, bids (jsonb), asks (jsonb),
#   mark_price, underlying_price, open_interest, volume_24h
```

## 📋 Deployment Steps

### Step 1: Prepare Files on Local Machine

```bash
# Ensure all changes are committed
git status

# Optional: Create deployment archive
tar -czf deployment-$(date +%Y%m%d).tar.gz \
  scripts/ \
  schema/ \
  Dockerfile \
  docker-compose.yml \
  requirements.txt \
  .env.example
```

### Step 2: Transfer to NAS

```bash
# Using SCP
scp deployment-YYYYMMDD.tar.gz nas-server:/path/to/crypto-collector/

# OR using rsync (recommended for incremental updates)
rsync -avz --exclude 'logs/' --exclude '__pycache__/' \
  ./ nas-server:/path/to/crypto-collector/
```

### Step 3: Initial Deployment on NAS

```bash
# SSH into NAS
ssh nas-server
cd /path/to/crypto-collector/

# Create .env file from template
cp .env.example .env
nano .env  # Edit with your configuration

# Build and start services
docker-compose up -d --build

# Monitor logs
docker-compose logs -f collector
```

### Step 4: Verify Deployment

```bash
# Check running containers
docker ps

# Check collector logs for depth collection
docker-compose logs collector | grep -i "depth\|snapshot"

# Expected log entries:
# - "Fetching periodic REST API snapshot..."
# - "Periodic snapshot complete: X quotes, Y depth snapshots"
# - "STATS | ... | Depth: X | ..."

# Verify database tables
docker exec -it crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    COUNT(*) as depth_snapshots,
    COUNT(DISTINCT instrument) as instruments,
    MIN(timestamp) as first,
    MAX(timestamp) as latest
  FROM eth_option_orderbook_depth;
"

# After 5-10 minutes, should see depth snapshots
```

### Step 5: Enable TimescaleDB Compression (Recommended)

```bash
# After initial data collection (e.g., 1 week)
docker exec -it crypto_data_db psql -U postgres -d crypto_data

# Enable compression for depth table
ALTER TABLE eth_option_orderbook_depth
SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument');

SELECT add_compression_policy(
  'eth_option_orderbook_depth',
  INTERVAL '7 days'
);

# Enable compression for quotes table (if not already)
ALTER TABLE eth_option_quotes
SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument');

SELECT add_compression_policy(
  'eth_option_quotes',
  INTERVAL '7 days'
);
```

## 🔄 Update Deployment (After Initial Setup)

When you need to update code:

```bash
# On NAS
cd /path/to/crypto-collector/

# Pull latest code (if using Git)
git pull

# OR sync from local machine
# (on local machine)
rsync -avz --exclude 'logs/' ./scripts/ nas-server:/path/to/crypto-collector/scripts/

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Verify updated code is running
docker-compose logs -f collector
```

## 📊 Monitoring and Maintenance

### Health Checks

```bash
# Check collector status
docker-compose ps

# Check database size
docker exec -it crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check latest data timestamps
docker exec -it crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    'quotes' as type,
    COUNT(*) as count,
    MAX(timestamp) as latest
  FROM eth_option_quotes
  UNION ALL
  SELECT
    'depth' as type,
    COUNT(*) as count,
    MAX(timestamp) as latest
  FROM eth_option_orderbook_depth;
"
```

### Backup Script

Create `scripts/backup_db.sh`:

```bash
#!/bin/bash
# Backup script for Docker deployment

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="crypto_data_backup_${DATE}.sql.gz"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Backup database
docker exec crypto_data_db pg_dump -U postgres crypto_data | gzip > ${BACKUP_DIR}/${BACKUP_FILE}

# Keep only last 30 days of backups
find ${BACKUP_DIR} -name "crypto_data_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_FILE}"
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /path/to/crypto-collector/scripts/backup_db.sh >> /path/to/logs/backup.log 2>&1
```

## ✅ Final Verification Checklist

Before considering deployment complete:

- [ ] All 3 schema files applied successfully
- [ ] `eth_option_orderbook_depth` table exists with correct schema
- [ ] Collector is running without errors
- [ ] WebSocket connection is stable
- [ ] Periodic snapshots are running every 5 minutes
- [ ] Depth data is being saved to database
- [ ] Stats logging shows depth metrics
- [ ] Database backups are configured
- [ ] Monitoring alerts are set up
- [ ] TimescaleDB compression is enabled (after 1 week)

## 🚨 Troubleshooting

### Schema Not Applied

**Symptom**: `eth_option_orderbook_depth` table doesn't exist

**Solution**:
```bash
# Manually apply schema
docker exec -i crypto_data_db psql -U postgres -d crypto_data < schema/002_add_orderbook_depth.sql

# Verify
docker exec crypto_data_db psql -U postgres -d crypto_data -c "\d eth_option_orderbook_depth"
```

### No Depth Data Collected

**Symptom**: `SELECT COUNT(*) FROM eth_option_orderbook_depth;` returns 0

**Check**:
```bash
# Verify SNAPSHOT_INTERVAL_SEC is set
docker-compose exec collector env | grep SNAPSHOT

# Check collector logs for errors
docker-compose logs collector | grep -i "error\|exception"

# Verify periodic snapshot loop is running
docker-compose logs collector | grep "Periodic snapshot"
```

**Solution**: Ensure `SNAPSHOT_INTERVAL_SEC` is set in docker-compose.yml environment section

### Collector Crashes on Startup

**Check**:
```bash
docker-compose logs collector

# Common issues:
# 1. Database not ready - ensure healthcheck is configured
# 2. Missing environment variables - check .env file
# 3. Import errors - verify all Python files are copied
```

## 📚 Additional Resources

- TimescaleDB Compression: https://docs.timescale.com/use-timescale/latest/compression/
- Docker Compose: https://docs.docker.com/compose/
- PostgreSQL Backups: https://www.postgresql.org/docs/current/backup.html
- Deribit API: https://docs.deribit.com/

---

**All depth collection features will be automatically included** when deploying with this configuration! ✅
