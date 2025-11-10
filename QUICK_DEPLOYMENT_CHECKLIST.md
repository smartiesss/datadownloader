# Quick Deployment Checklist - NAS Migration

**Time Required:** ~1 hour
**Risk Level:** Low (Full backup + rollback plan included)

---

## 🔴 CRITICAL - DO THIS FIRST

### 1. Backup Database (5 minutes)
```bash
ssh your_nas
cd /path/to/datadownloader
mkdir -p backups/pre-lifecycle-$(date +%Y%m%d_%H%M%S)
docker exec crypto-timescaledb pg_dump -U postgres -d crypto_data -F c -f /backups/pre-lifecycle-$(date +%Y%m%d_%H%M%S)/crypto_data.backup
ls -lh backups/  # Verify backup created
```

---

## 🟡 SHUTDOWN OLD SYSTEM

### 2. Stop All Containers (2 minutes)
```bash
cd /path/to/datadownloader
docker-compose -f docker-compose-multi-conn.yml down
docker ps  # Verify all stopped
```

### 3. Clean Up Space (3 minutes)
```bash
# Remove old containers
docker rm $(docker ps -a --filter "name=crypto-" -q)

# Remove old images (frees 2-4GB)
docker image prune -a --force
```

---

## 🟢 DEPLOY NEW SYSTEM

### 4. Upload New Files (5 minutes)
```bash
# From your local machine
scp docker-compose-lifecycle.yml your_user@your_nas:/path/to/datadownloader/
scp schema/006_instrument_metadata_table.sql your_user@your_nas:/path/to/datadownloader/schema/
scp schema/007_lifecycle_events_table.sql your_user@your_nas:/path/to/datadownloader/schema/
scp scripts/lifecycle_manager.py your_user@your_nas:/path/to/datadownloader/scripts/
scp scripts/collector_control_api.py your_user@your_nas:/path/to/datadownloader/scripts/
scp scripts/ws_multi_conn_orchestrator.py your_user@your_nas:/path/to/datadownloader/scripts/
```

### 5. Apply Migrations (2 minutes)
```bash
# On NAS
ssh your_nas
cd /path/to/datadownloader

# Apply migrations
docker exec -i crypto-timescaledb psql -U postgres -d crypto_data < schema/006_instrument_metadata_table.sql
docker exec -i crypto-timescaledb psql -U postgres -d crypto_data < schema/007_lifecycle_events_table.sql

# Verify tables exist
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "\dt instrument_metadata"
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "\dt lifecycle_events"
```

### 6. Build & Deploy (15 minutes)
```bash
# Build images with new code
docker-compose -f docker-compose-lifecycle.yml build --no-cache

# Start all containers
docker-compose -f docker-compose-lifecycle.yml up -d

# Check all running
docker-compose -f docker-compose-lifecycle.yml ps
```

---

## ✅ VERIFICATION

### 7. Verify System (5 minutes)
```bash
# Check lifecycle managers
docker logs crypto-btc-lifecycle-manager --tail 20
docker logs crypto-eth-lifecycle-manager --tail 20

# Test HTTP APIs
curl http://localhost:8000/health
curl http://localhost:8003/health

# Check data collection (wait 2-3 minutes first)
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT COUNT(*) FROM btc_option_quotes WHERE timestamp > NOW() - INTERVAL '5 minutes';
"
```

**Expected Results:**
- ✅ Lifecycle managers log: "=== Refresh cycle 1 complete ==="
- ✅ Health checks return: `{"status": "healthy"}`
- ✅ Database query returns: >10,000 rows

---

## 🔄 IF SOMETHING GOES WRONG

### Rollback to Old System
```bash
# Stop new system
docker-compose -f docker-compose-lifecycle.yml down

# Restore old system
docker-compose -f docker-compose-multi-conn.yml up -d
```

---

## 📊 MONITORING (Next 24 Hours)

### Watch Logs
```bash
# BTC lifecycle manager
docker logs -f crypto-btc-lifecycle-manager

# ETH lifecycle manager
docker logs -f crypto-eth-lifecycle-manager
```

### Check Status Every Hour
```bash
# All containers running
docker ps | grep crypto-

# Data collection active
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT
    'btc_option_quotes' as table,
    COUNT(*) as rows_last_hour
FROM btc_option_quotes
WHERE timestamp > NOW() - INTERVAL '1 hour';
"
```

---

## 🎯 SUCCESS CRITERIA

**After 1 Hour:**
- [ ] All 10 containers running
- [ ] No errors in lifecycle manager logs
- [ ] Data collecting (>10K rows per 5 minutes)

**After 24 Hours:**
- [ ] Continuous data collection
- [ ] Lifecycle events logged
- [ ] No container restarts

**After Monday 08:00 UTC (First Expiry):**
- [ ] Expired options detected
- [ ] New options subscribed
- [ ] Coverage maintained at 95%+

---

## 📞 QUICK REFERENCE

**View All Container Status:**
```bash
docker-compose -f docker-compose-lifecycle.yml ps
```

**View Logs:**
```bash
docker logs <container-name> --tail 50
```

**Check Database:**
```bash
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "<query>"
```

**Restart Single Container:**
```bash
docker restart <container-name>
```

**Full System Restart:**
```bash
docker-compose -f docker-compose-lifecycle.yml restart
```

---

**🚀 Ready to deploy? Follow the steps above in order.**

**Estimated Time:** 55 minutes total
**Downtime:** ~20 minutes (from stop to start)
