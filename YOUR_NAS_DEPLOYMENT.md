# YOUR NAS DEPLOYMENT - Customized for smartiesnas

**Your Setup:**
- Location: `/volume1/crypto-collector`
- User: `smartiesbul`
- Database Password: `CryptoNAS2024!`
- Current State: **STOPPED** (perfect for migration!)
- Volumes: Data preserved in `crypto-collector_timescaledb_data`

---

## 🎯 YOUR SITUATION - PERFECT FOR MIGRATION!

**Good News:**
- ✅ No containers running (nothing to stop)
- ✅ Database volumes exist (data is safe)
- ✅ No cleanup needed
- ✅ Ready for fresh deployment

**What We Need to Do:**
1. Check your current docker-compose.yml structure
2. Apply database migrations
3. Deploy new lifecycle-enabled system
4. Verify everything works

---

## STEP 1: CHECK CURRENT SETUP (Run These on NAS)

```bash
# See your current docker-compose configuration
sudo cat docker-compose.yml

# Verify database volume has data
sudo docker run --rm -v crypto-collector_timescaledb_data:/data alpine ls -lh /data/pgdata
# If you see files, your data is safe!

# Check your requirements.txt
cat requirements.txt
```

**After running these, share the output so I can see:**
1. What services are defined in your docker-compose.yml
2. If you're using multi-connection or single collector
3. If database migrations already exist

---

## STEP 2: START DATABASE ONLY (To Apply Migrations)

Since your containers are stopped, we need to start the database temporarily to apply migrations:

```bash
cd /volume1/crypto-collector

# Start only the database
sudo docker-compose up -d timescaledb

# Wait for database to be ready (30 seconds)
sleep 30

# Check if database is running
sudo docker ps
# Should show: timescaledb container running
```

---

## STEP 3: APPLY DATABASE MIGRATIONS

**First, let's check if tables already exist:**

```bash
sudo docker exec -i $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "\dt" | grep -E "instrument_metadata|lifecycle_events"
```

**If tables DON'T exist, apply migrations:**

```bash
# Migration 006 - instrument_metadata table
sudo docker exec -i $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data << 'EOF'
-- Drop existing table if recreating
DROP TABLE IF EXISTS instrument_metadata CASCADE;

-- Create instrument_metadata table
CREATE TABLE instrument_metadata (
    instrument_name TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    strike_price NUMERIC(18, 8),
    expiry_date TIMESTAMPTZ,
    option_type TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    listed_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_instrument_metadata_currency ON instrument_metadata(currency);
CREATE INDEX idx_instrument_metadata_is_active ON instrument_metadata(is_active);
CREATE INDEX idx_instrument_metadata_expiry_date ON instrument_metadata(expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_instrument_metadata_active_by_currency ON instrument_metadata(currency, is_active);

SELECT 'Migration 006 complete' as status;
EOF

# Migration 007 - lifecycle_events table
sudo docker exec -i $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data << 'EOF'
-- Drop existing table if recreating
DROP TABLE IF EXISTS lifecycle_events CASCADE;

-- Create lifecycle_events table
CREATE TABLE lifecycle_events (
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id SERIAL,
    event_type TEXT NOT NULL,
    instrument_name TEXT,
    currency TEXT NOT NULL,
    collector_id TEXT,
    details JSONB,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_time, id)
);

-- Convert to hypertable
SELECT create_hypertable('lifecycle_events', 'event_time');

-- Create indexes
CREATE INDEX idx_lifecycle_events_event_type ON lifecycle_events(event_type);
CREATE INDEX idx_lifecycle_events_currency ON lifecycle_events(currency);
CREATE INDEX idx_lifecycle_events_instrument ON lifecycle_events(instrument_name);
CREATE INDEX idx_lifecycle_events_collector ON lifecycle_events(collector_id);
CREATE INDEX idx_lifecycle_events_success ON lifecycle_events(success) WHERE success = FALSE;

-- Add retention policy (keep 90 days of lifecycle events)
SELECT add_retention_policy('lifecycle_events', INTERVAL '90 days');

SELECT 'Migration 007 complete' as status;
EOF
```

**Verify migrations applied:**

```bash
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "\dt instrument_metadata"
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "\dt lifecycle_events"
```

**Expected output:**
```
                    List of relations
 Schema |        Name         | Type  |  Owner
--------+---------------------+-------+----------
 public | instrument_metadata | table | postgres
```

---

## STEP 4: UPLOAD NEW FILES TO NAS

**On your local machine, run these commands:**

```bash
# Set your NAS details
NAS_USER="smartiesbul"
NAS_IP="your_nas_ip_here"  # Replace with actual IP
NAS_PATH="/volume1/crypto-collector"

# Upload new docker-compose file
scp docker-compose-lifecycle.yml $NAS_USER@$NAS_IP:$NAS_PATH/

# Upload new Python scripts
scp scripts/lifecycle_manager.py $NAS_USER@$NAS_IP:$NAS_PATH/scripts/
scp scripts/collector_control_api.py $NAS_USER@$NAS_IP:$NAS_PATH/scripts/
scp scripts/ws_multi_conn_orchestrator.py $NAS_USER@$NAS_IP:$NAS_PATH/scripts/

# Upload schema files (if not already there)
scp schema/006_instrument_metadata_table.sql $NAS_USER@$NAS_IP:$NAS_PATH/schema/
scp schema/007_lifecycle_events_table.sql $NAS_USER@$NAS_IP:$NAS_PATH/schema/
```

**Or if you prefer rsync (faster for multiple files):**

```bash
rsync -avz --exclude 'logs' --exclude '*.pyc' --exclude '__pycache__' --exclude '.git' \
    scripts/lifecycle_manager.py \
    scripts/collector_control_api.py \
    scripts/ws_multi_conn_orchestrator.py \
    docker-compose-lifecycle.yml \
    $NAS_USER@$NAS_IP:$NAS_PATH/
```

---

## STEP 5: FIX FILE PERMISSIONS (IMPORTANT!)

**On NAS, fix ownership of new files:**

```bash
cd /volume1/crypto-collector

# Change ownership of new files to your user
sudo chown smartiesbul:users docker-compose-lifecycle.yml
sudo chown smartiesbul:users scripts/lifecycle_manager.py
sudo chown smartiesbul:users scripts/collector_control_api.py
sudo chown smartiesbul:users scripts/ws_multi_conn_orchestrator.py

# Make sure docker-compose file is readable
sudo chmod 644 docker-compose-lifecycle.yml

# Verify permissions
ls -la docker-compose-lifecycle.yml
ls -la scripts/lifecycle_manager.py
ls -la scripts/collector_control_api.py
```

---

## STEP 6: STOP DATABASE & DEPLOY NEW SYSTEM

```bash
cd /volume1/crypto-collector

# Stop the temporary database
sudo docker-compose down

# Build new images with lifecycle management code
sudo docker-compose -f docker-compose-lifecycle.yml build --no-cache

# This will take 5-10 minutes
# You'll see output like:
# Building timescaledb... Done
# Building btc-options-0... Done
# ...

# Start all containers with lifecycle management
sudo docker-compose -f docker-compose-lifecycle.yml up -d

# Wait 30 seconds for startup
sleep 30

# Check all containers running
sudo docker-compose -f docker-compose-lifecycle.yml ps
```

**Expected Output:**
```
Name                            State    Ports
crypto-timescaledb              Up       5432/tcp
crypto-btc-options-0            Up       8000/tcp
crypto-btc-options-1            Up       8001/tcp
crypto-btc-options-2            Up       8002/tcp
crypto-eth-options-0            Up       8003/tcp
crypto-eth-options-1            Up       8004/tcp
crypto-eth-options-2            Up       8005/tcp
crypto-eth-options-3            Up       8006/tcp
crypto-btc-lifecycle-manager    Up
crypto-eth-lifecycle-manager    Up
crypto-perpetuals-collector     Up
crypto-grafana                  Up       3000/tcp
```

---

## STEP 7: VERIFY DEPLOYMENT

**Check lifecycle managers are working:**

```bash
# Check BTC lifecycle manager logs
sudo docker logs crypto-btc-lifecycle-manager --tail 50

# Expected to see:
# Starting lifecycle manager for BTC...
# Database connection pool created
# Fetching active BTC options from Deribit...
# Found 728 active options on exchange
# === Refresh cycle 1 complete | Tracked: 728 ===

# Check ETH lifecycle manager logs
sudo docker logs crypto-eth-lifecycle-manager --tail 50

# Expected similar output for ETH
```

**Test HTTP control APIs:**

```bash
# Test BTC collector
curl http://localhost:8000/health
# Expected: {"status": "healthy", "timestamp": "..."}

# Test ETH collector
curl http://localhost:8003/health
# Expected: {"status": "healthy", "timestamp": "..."}

# Get collector status
curl http://localhost:8000/api/status
# Expected: JSON with instruments list, currency: BTC, etc.
```

**Check data collection (wait 2-3 minutes first):**

```bash
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "
SELECT
    'btc_option_quotes' as table_name,
    COUNT(*) as recent_rows,
    MAX(timestamp) as last_update
FROM btc_option_quotes
WHERE timestamp > NOW() - INTERVAL '5 minutes'
UNION ALL
SELECT
    'eth_option_quotes',
    COUNT(*),
    MAX(timestamp)
FROM eth_option_quotes
WHERE timestamp > NOW() - INTERVAL '5 minutes';
"
```

**Expected Output:**
```
    table_name     | recent_rows |          last_update
-------------------+-------------+-------------------------------
 btc_option_quotes |       15000 | 2025-11-11 10:35:45.123+00
 eth_option_quotes |       16000 | 2025-11-11 10:35:46.456+00
```

**✅ If you see thousands of rows, data collection is working!**

---

## STEP 8: VERIFY LIFECYCLE MANAGEMENT

**Check instrument metadata populated:**

```bash
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "
SELECT
    currency,
    COUNT(*) as total_instruments,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active,
    COUNT(*) FILTER (WHERE is_active = FALSE) as expired
FROM instrument_metadata
GROUP BY currency;
"
```

**Expected Output:**
```
 currency | total_instruments | active | expired
----------+-------------------+--------+---------
 BTC      |               728 |    728 |       0
 ETH      |               820 |    820 |       0
```

**Check lifecycle events logged:**

```bash
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "
SELECT
    event_type,
    currency,
    COUNT(*) as count,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
FROM lifecycle_events
WHERE event_time > NOW() - INTERVAL '1 hour'
GROUP BY event_type, currency;
"
```

**Expected Output:**
```
    event_type     | currency | count | successful
-------------------+----------+-------+------------
 instrument_listed | BTC      |   728 |        728
 instrument_listed | ETH      |   820 |        820
 subscription_added| BTC      |   728 |        728
 subscription_added| ETH      |   820 |        820
```

**✅ If you see these events, lifecycle management is working!**

---

## TROUBLESHOOTING

### Problem: Permission Denied Errors

**Symptom:** `permission denied while trying to connect to Docker daemon socket`

**Solution:**
```bash
# Add your user to docker group (requires logout/login after)
sudo usermod -aG docker smartiesbul

# Or just use sudo for all docker commands (recommended on NAS)
sudo docker ps
sudo docker-compose ps
```

---

### Problem: Container Keeps Restarting

**Symptom:** `docker ps` shows container restarting repeatedly

**Solution:**
```bash
# Check logs for errors
sudo docker logs <container-name> --tail 100

# Common issues:
# 1. Database not ready - wait 60 seconds and check again
# 2. Missing files - verify files uploaded correctly
# 3. Permission issues - check file ownership
```

---

### Problem: Can't Access HTTP API

**Symptom:** `curl http://localhost:8000/health` connection refused

**Solution:**
```bash
# Check if container is running
sudo docker ps | grep btc-options-0

# Check if port is exposed
sudo docker port crypto-btc-options-0

# Check container logs
sudo docker logs crypto-btc-options-0 --tail 50

# Wait 60 seconds for full startup, then try again
```

---

## MONITORING (NEXT 24 HOURS)

**Check status every hour:**

```bash
# All containers running
sudo docker ps

# Lifecycle managers working
sudo docker logs crypto-btc-lifecycle-manager --tail 20
sudo docker logs crypto-eth-lifecycle-manager --tail 20

# Data still collecting
sudo docker exec $(sudo docker ps --filter "name=timescaledb" -q) psql -U postgres -d crypto_data -c "
SELECT COUNT(*) FROM btc_option_quotes WHERE timestamp > NOW() - INTERVAL '10 minutes';
"
# Should return >20,000 rows
```

---

## IF SOMETHING GOES WRONG - ROLLBACK

```bash
# Stop new system
sudo docker-compose -f docker-compose-lifecycle.yml down

# Start old system (if you had docker-compose.yml working before)
sudo docker-compose -f docker-compose.yml up -d

# Or restore from backup if you had one
```

---

## NEXT STEPS AFTER 24 HOURS

1. ✅ Verify all containers still running
2. ✅ Check lifecycle events being logged
3. ✅ Verify data collection continuous
4. ✅ Wait for Monday 08:00 UTC expiry to test automatic unsubscribe

---

## SUMMARY OF DIFFERENCES FROM GENERIC GUIDE

**Your Specific Setup:**
- ✅ Use `sudo` for all docker commands
- ✅ Database password: `CryptoNAS2024!` (not `CryptoTest2024!`)
- ✅ Path: `/volume1/crypto-collector`
- ✅ User: `smartiesbul`
- ✅ No cleanup needed (system already stopped)
- ✅ Volumes already exist (data preserved)

---

**Ready to proceed? Start with STEP 1 to check your current setup!**

Then we'll adapt the deployment based on what we find.
