# Deployment Guide - NAS Deployment

**Complete guide for deploying ETH Options Tick Data Collector to QNAP/TerraMaster NAS**

---

## Prerequisites

1. **NAS Hardware**:
   - QNAP TS-873A / QU805 or TerraMaster F8-423 (8-bay recommended)
   - Minimum 8GB RAM (16GB recommended)
   - Docker support (Container Station for QNAP, TOS for TerraMaster)

2. **Storage**:
   - 4× hard drives (1-2TB each for RAID 5)
   - Usable capacity: 2-6TB (sufficient for 5+ years)

3. **Network**:
   - Static IP for NAS (or DHCP reservation)
   - 2.5GbE or 10GbE connection (optional but recommended)

---

## Step 1: Prepare NAS

### QNAP Setup

1. Access QTS web interface: `http://nas-ip:8080`
2. Install Container Station:
   - App Center → Search "Container Station" → Install
3. Enable SSH:
   - Control Panel → Telnet / SSH → Enable SSH (port 22)
4. Create data directory:
   ```bash
   ssh admin@nas-ip
   mkdir -p /share/Container/crypto-data
   mkdir -p /share/Backup/crypto-backups
   ```

### TerraMaster Setup

1. Access TOS web interface: `http://nas-ip`
2. Install Docker:
   - Applications → Docker → Install
3. Enable SSH:
   - Control Panel → Terminal → Enable SSH
4. Create data directory:
   ```bash
   ssh admin@nas-ip
   mkdir -p /mnt/md0/docker/crypto-data
   mkdir -p /mnt/md0/backups/crypto
   ```

---

## Step 2: Transfer Files to NAS

### Option A: Git Clone (Recommended)

```bash
# SSH into NAS
ssh admin@nas-ip

# Clone repository
cd /share/Container  # QNAP
# OR
cd /mnt/md0/docker  # TerraMaster

git clone https://github.com/youruser/datadownloader.git
cd datadownloader
```

### Option B: SCP Upload

```bash
# From your local machine
scp -r /Users/doghead/PycharmProjects/datadownloader admin@nas-ip:/share/Container/
```

---

## Step 3: Configure Environment

```bash
# SSH into NAS and navigate to project directory
cd /share/Container/datadownloader

# Copy environment template
cp .env.example .env

# Edit environment file
nano .env
```

**Important: Change these values in .env**:
```bash
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE
GRAFANA_PASSWORD=YOUR_GRAFANA_PASSWORD_HERE
TZ=Asia/Hong_Kong  # Your timezone
```

---

## Step 4: Deploy with Docker Compose

```bash
# Verify Docker is running
docker --version
docker-compose --version

# Start all services
docker-compose up -d

# Expected output:
# Creating network "datadownloader_crypto_net" ... done
# Creating volume "datadownloader_timescaledb_data" ... done
# Creating volume "datadownloader_grafana_data" ... done
# Creating eth-timescaledb ... done
# Creating eth-collector ... done
# Creating eth-grafana ... done
```

---

## Step 5: Verify Deployment

### Check Container Status

```bash
docker-compose ps

# Expected output:
# NAME              STATUS       PORTS
# eth-timescaledb   Up (healthy) 0.0.0.0:5432->5432/tcp
# eth-collector     Up           
# eth-grafana       Up           0.0.0.0:3000->3000/tcp
```

### Check Collector Logs

```bash
docker-compose logs -f collector

# Expected output (within 30 seconds):
# INFO - Connected to Deribit WebSocket
# INFO - Subscribed to 50 ETH options
# INFO - Wrote 145 quotes in 0.01s (14500 rows/sec)
```

### Check Database

```bash
docker exec -it eth-timescaledb psql -U postgres -d crypto_data

# Run query:
SELECT COUNT(*) as ticks, 
       MIN(timestamp) as first_tick, 
       MAX(timestamp) as last_tick
FROM eth_option_quotes;

# Expected: Ticks should increase every 3 seconds
```

---

## Step 6: Access Grafana

1. Open browser: `http://nas-ip:3000`
2. Login:
   - Username: `admin`
   - Password: (from .env GRAFANA_PASSWORD)
3. Change default password on first login
4. Import dashboard (future step)

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs timescaledb
docker-compose logs collector

# Common issue: Port conflict
# Solution: Stop local PostgreSQL
brew services stop postgresql@14
```

### Collector can't connect to database

```bash
# Verify database is healthy
docker-compose ps timescaledb

# Check network
docker network inspect datadownloader_crypto_net

# Restart collector
docker-compose restart collector
```

### Out of memory errors

```bash
# Check NAS memory usage
free -h

# Reduce shared_buffers in docker-compose.yml:
# Change: shared_buffers=2GB
# To: shared_buffers=1GB

# Restart
docker-compose down
docker-compose up -d
```

---

## Maintenance Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f collector
docker-compose logs -f timescaledb
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart collector only
docker-compose restart collector
```

### Update Code

```bash
# Pull latest code
git pull origin main

# Rebuild and restart collector
docker-compose build collector
docker-compose up -d collector
```

### Backup Database

```bash
# Create backup
docker exec eth-timescaledb pg_dump -U postgres crypto_data > /share/Backup/crypto-backups/backup_$(date +%Y%m%d).sql

# Restore backup
docker exec -i eth-timescaledb psql -U postgres crypto_data < /share/Backup/crypto-backups/backup_20251109.sql
```

### Stop Services

```bash
# Stop (data preserved)
docker-compose down

# Stop and remove data (DANGER)
docker-compose down -v
```

---

## Enabling Multi-Currency (BTC, SOL)

```bash
# Edit currency configuration
nano config/currencies.yaml

# Change: enabled: false
# To: enabled: true
# (for BTC or SOL)

# Restart collector
docker-compose restart collector
```

---

## Resource Usage

**Expected resource consumption**:

| Service | CPU | RAM | Disk I/O |
|---------|-----|-----|----------|
| TimescaleDB | 10-20% | 2-4GB | 10-50 MB/s |
| Collector | 5-10% | 1-2GB | <1 MB/s |
| Grafana | <5% | 200-500MB | <1 MB/s |
| **Total** | **20-35%** | **3-6GB** | **10-50 MB/s** |

**Suitable for**:
- 8GB NAS: ✅ (4GB for OS + 4GB for Docker)
- 16GB NAS: ✅ (plenty of headroom)

---

## Next Steps

1. ✅ Deploy to NAS (this guide)
2. Create Grafana dashboards (T-003)
3. Set up automated backups (T-004)
4. Enable BTC/SOL collection (T-005)
5. Add email alerts (T-006)

---

**Need help?** Check logs first:
```bash
docker-compose logs -f
```
