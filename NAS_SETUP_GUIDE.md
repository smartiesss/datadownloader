# Synology DS925+ Setup Guide - Crypto Data Collector

## Hardware Overview

**Your Setup**:
- **Model**: Synology DS925+ (4-bay NAS, AMD Ryzen R1600, 4GB RAM)
- **Storage**: 2x 4TB Seagate hard drives (8TB total capacity)
- **Purpose**: Docker-based crypto data collection with PostgreSQL + TimescaleDB

---

## Phase 1: Initial NAS Setup (30-60 minutes)

### Step 1: Physical Installation

1. **Install Hard Drives**:
   - Open the drive bays (tool-less design on DS925+)
   - Insert both 4TB drives into bays 1 and 2
   - Secure the drives (they should click into place)

2. **Connect to Network**:
   - Connect Ethernet cable from NAS to your router
   - Connect power adapter
   - Press power button

3. **Wait for Boot**:
   - First boot takes 3-5 minutes
   - Status LED will turn green when ready
   - You'll hear a beep sound

### Step 2: Find Your NAS

**Option A: Using Synology Assistant (Recommended)**

1. Download from: https://www.synology.com/en-us/support/download
2. Install on your Mac
3. Run Synology Assistant - it will auto-discover your NAS on the network
4. Click on your NAS, then click "Connect"

**Option B: Web Browser Discovery**

1. Go to: http://find.synology.com
2. It will scan your network and find the NAS
3. Click on your NAS to start setup

### Step 3: DiskStation Manager (DSM) Installation

1. **Install DSM**:
   - Click "Setup" or "Install"
   - Choose "Install now" (will format drives - this is expected)
   - Wait 10 minutes for DSM installation
   - NAS will reboot automatically

2. **Create Admin Account**:
   - Server name: `crypto-nas` (or your preference)
   - Admin username: Choose a strong username (NOT "admin")
   - Admin password: Use a strong password (save it in a password manager!)
   - Click "Next"

3. **Update DSM**:
   - Click "Update now" if prompted
   - Wait 5-10 minutes
   - NAS will reboot again

4. **QuickConnect Setup** (Optional):
   - Allows remote access to your NAS
   - Can skip for now (local network only is more secure)

---

## Phase 2: Storage Configuration

### Step 1: Create Storage Pool (RAID Configuration)

**Go to**: Storage Manager → Storage Pool

**Recommended Configuration: RAID 1 (Mirroring)**

Why RAID 1?
- ✅ **Data redundancy**: If one drive fails, data is safe
- ✅ **Usable capacity**: 4TB (half of total)
- ✅ **Read performance**: Better than single drive
- ❌ **Tradeoff**: Lose 4TB for redundancy

Alternative: RAID 0 (Striping)
- ✅ **Full capacity**: 8TB usable
- ✅ **Better performance**: Faster reads/writes
- ❌ **No redundancy**: If one drive fails, ALL data is lost
- **NOT RECOMMENDED** for production data

**Setup Steps**:

1. Click "Create" → "Create Storage Pool"
2. Select **RAID 1** (SHR-1 also works, gives same result with 2 drives)
3. Select both drives
4. Click "Next"
5. **Drive check**: Choose "Quick" (faster) or "Extended" (more thorough)
6. Click "Next" → "Apply"
7. Wait 5-10 minutes for storage pool creation

### Step 2: Create Volume

1. Storage Manager will automatically prompt to create a volume
2. Click "Create" → "Create Volume"
3. Select your storage pool
4. **Volume size**: Use maximum available (~3.6TB with RAID 1)
5. **File system**: Choose **Btrfs** (recommended for data integrity)
6. Click "Next" → "Apply"

---

## Phase 3: Essential Packages Installation

### Step 1: Open Package Center

Go to: **Main Menu** → **Package Center**

### Step 2: Install Docker

1. Search for "Docker"
2. Click "Install"
3. Wait 2-3 minutes
4. When installed, Docker icon appears in Main Menu

### Step 3: Install Container Manager (Optional but Recommended)

1. Search for "Container Manager"
2. This is Synology's UI for Docker
3. Click "Install"
4. Provides easier management than command-line only

### Step 4: Enable SSH Access

1. Go to **Control Panel** → **Terminal & SNMP**
2. Check "Enable SSH service"
3. Port: Keep default **22** (or change for security)
4. Click "Apply"

### Step 5: Create Shared Folders

Go to **Control Panel** → **Shared Folder**

Create these folders:

1. **docker** - For Docker data
   - Click "Create"
   - Name: `docker`
   - Description: "Docker persistent data"
   - Enable recycle bin: No
   - Enable encryption: Optional (slight performance hit)

2. **crypto-collector** - For application files
   - Name: `crypto-collector`
   - Description: "Crypto data collector application"

3. **backups** - For database backups
   - Name: `backups`
   - Description: "Database backups"
   - Enable recycle bin: Yes (extra safety)

---

## Phase 4: Network Configuration

### Step 1: Set Static IP Address (Recommended)

**Go to**: Control Panel → Network → Network Interface

1. Select your LAN connection
2. Click "Edit"
3. Select "Use manual configuration"
4. Enter:
   - **IP Address**: `192.168.1.100` (or choose based on your network)
   - **Subnet mask**: `255.255.255.0`
   - **Gateway**: Your router IP (usually `192.168.1.1`)
   - **DNS Server**: `8.8.8.8` (Google DNS) or your router IP
5. Click "OK"
6. Test: ping the new IP from your Mac: `ping 192.168.1.100`

### Step 2: Configure Firewall (Optional but Recommended)

**Go to**: Control Panel → Security → Firewall

1. Enable firewall
2. Create rule for **SSH** (port 22):
   - Allow from your local network only: `192.168.1.0/24`
3. Create rule for **PostgreSQL** (port 5432):
   - Allow from local network only
4. Create rule for **DSM** (ports 5000, 5001):
   - Allow from local network

---

## Phase 5: Docker Setup

### Step 1: SSH into NAS

From your Mac:

```bash
# Replace with your NAS IP and username
ssh your-username@192.168.1.100

# Enter your password when prompted
```

### Step 2: Create Project Directory

```bash
# Create directories
sudo mkdir -p /volume1/docker/crypto-collector
sudo mkdir -p /volume1/docker/crypto-collector/postgres-data
sudo mkdir -p /volume1/docker/crypto-collector/logs

# Set permissions
sudo chown -R your-username:users /volume1/docker/crypto-collector
```

### Step 3: Transfer Application Files

**On your Mac** (in a new terminal, keep SSH session open):

```bash
# Navigate to project directory
cd /Users/doghead/PycharmProjects/datadownloader

# Transfer entire project to NAS
# Replace 192.168.1.100 with your NAS IP
rsync -avz --progress \
  --exclude 'logs/' \
  --exclude '__pycache__/' \
  --exclude '.git/' \
  --exclude '*.pyc' \
  ./ your-username@192.168.1.100:/volume1/docker/crypto-collector/
```

**Or using SCP**:

```bash
# Create tar archive
tar -czf crypto-collector.tar.gz \
  scripts/ \
  schema/ \
  requirements.txt \
  Dockerfile \
  docker-compose.yml \
  .env.example

# Copy to NAS
scp crypto-collector.tar.gz your-username@192.168.1.100:/volume1/docker/

# On NAS (in SSH session):
cd /volume1/docker
tar -xzf crypto-collector.tar.gz -C crypto-collector/
```

---

## Phase 6: Configure Application

### Step 1: Create Environment File

**On NAS (SSH session)**:

```bash
cd /volume1/docker/crypto-collector

# Copy example to .env
cp .env.example .env

# Edit with nano
nano .env
```

**Edit .env file**:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:YOUR_SECURE_PASSWORD@postgres:5432/crypto_data
DB_PASSWORD=YOUR_SECURE_PASSWORD

# Collection Settings
TOP_N_INSTRUMENTS=50
BUFFER_SIZE_QUOTES=200000
BUFFER_SIZE_TRADES=100000
FLUSH_INTERVAL_SEC=3

# Periodic depth snapshot interval (5 minutes)
SNAPSHOT_INTERVAL_SEC=300

# Logging
LOG_LEVEL=INFO
```

**Save**: Ctrl+O, Enter, Ctrl+X

**IMPORTANT**: Replace `YOUR_SECURE_PASSWORD` with a strong password!

### Step 2: Update docker-compose.yml

Check if docker-compose.yml has correct volume paths:

```bash
nano docker-compose.yml
```

**Ensure volumes section has**:

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /volume1/docker/crypto-collector/postgres-data
```

---

## Phase 7: Deploy Application

### Step 1: Pull Docker Images

```bash
cd /volume1/docker/crypto-collector

# Pull TimescaleDB image
docker pull timescale/timescaledb:latest-pg15
```

### Step 2: Build Application Image

```bash
# Build the crypto collector image
docker-compose build
```

### Step 3: Start Services

```bash
# Start PostgreSQL first
docker-compose up -d postgres

# Wait 10 seconds for database to initialize
sleep 10

# Check database is ready
docker-compose logs postgres | tail -20

# Should see: "database system is ready to accept connections"
```

### Step 4: Verify Database Schema

```bash
# Check tables were created
docker-compose exec postgres psql -U postgres -d crypto_data -c "\dt"

# Should see:
# eth_option_quotes
# eth_option_trades
# eth_option_orderbook_depth
# data_gaps
# collector_status
```

### Step 5: Start Collector

```bash
# Start collector service
docker-compose up -d collector

# View logs
docker-compose logs -f collector

# Should see:
# - "Fetching top 50 ETH options..."
# - "Initial snapshot complete: 50 quotes, 50 depth snapshots"
# - "WebSocket connected successfully"
# - "Successfully subscribed to 100 channels"
```

**Press Ctrl+C to exit logs (collector keeps running)**

---

## Phase 8: Verification and Monitoring

### Step 1: Check Running Containers

```bash
docker ps

# Should show 2 containers:
# - crypto_data_db (postgres)
# - eth_options_collector
```

### Step 2: Verify Data Collection

```bash
# Wait 5 minutes, then check database
docker-compose exec postgres psql -U postgres -d crypto_data -c "
  SELECT
    'quotes' as type,
    COUNT(*) as total,
    MAX(timestamp) as latest
  FROM eth_option_quotes
  UNION ALL
  SELECT 'depth', COUNT(*), MAX(timestamp)
  FROM eth_option_orderbook_depth;
"

# Expected:
# quotes: 500-1000 records
# depth: 50-100 snapshots
```

### Step 3: Check Container Resources

```bash
# View container stats (CPU, memory, network)
docker stats

# Press Ctrl+C to exit
```

### Step 4: Enable Auto-Start on Boot

```bash
# Edit docker-compose.yml if not already set
nano docker-compose.yml

# Ensure both services have:
# restart: unless-stopped

# Restart containers to apply
docker-compose restart
```

---

## Phase 9: Enable TimescaleDB Compression

**Wait 1 week** for initial data collection, then:

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d crypto_data

# Enable compression for quotes
ALTER TABLE eth_option_quotes
SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument');

SELECT add_compression_policy(
  'eth_option_quotes',
  INTERVAL '7 days'
);

# Enable compression for depth
ALTER TABLE eth_option_orderbook_depth
SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument');

SELECT add_compression_policy(
  'eth_option_orderbook_depth',
  INTERVAL '7 days'
);

# Exit psql
\q
```

**Expected compression**: 80-90% storage reduction after 7 days!

---

## Phase 10: Setup Automated Backups

### Step 1: Create Backup Script

```bash
nano /volume1/docker/crypto-collector/backup_db.sh
```

**Paste this script**:

```bash
#!/bin/bash
# Database backup script for Synology NAS

BACKUP_DIR="/volume1/backups/crypto-collector"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="crypto_data_backup_${DATE}.sql.gz"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Backup database
docker exec crypto_data_db pg_dump -U postgres crypto_data | gzip > ${BACKUP_DIR}/${BACKUP_FILE}

# Keep only last 30 days of backups
find ${BACKUP_DIR} -name "crypto_data_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_FILE}"
logger "Crypto database backup completed: ${BACKUP_FILE}"
```

**Make executable**:

```bash
chmod +x /volume1/docker/crypto-collector/backup_db.sh
```

### Step 2: Schedule with Synology Task Scheduler

1. Go to **Control Panel** → **Task Scheduler**
2. Click "Create" → "Scheduled Task" → "User-defined script"
3. **General**:
   - Task name: `Crypto DB Backup`
   - User: `root`
   - Enabled: ✓
4. **Schedule**:
   - Run on: Daily
   - Time: 2:00 AM
5. **Task Settings**:
   - User-defined script:
     ```bash
     /volume1/docker/crypto-collector/backup_db.sh >> /volume1/docker/crypto-collector/logs/backup.log 2>&1
     ```
6. Click "OK"

---

## Phase 11: Monitoring Setup

### Step 1: Create Monitoring Script

```bash
nano /volume1/docker/crypto-collector/monitor.sh
```

```bash
#!/bin/bash
# Monitor crypto collector health

echo "=== Crypto Collector Status ==="
echo "Time: $(date)"
echo ""

# Check containers
echo "Container Status:"
docker ps --filter "name=crypto" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Check database size
echo "Database Size:"
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    pg_size_pretty(pg_database_size('crypto_data')) as total_size;
"
echo ""

# Check latest data
echo "Latest Data:"
docker exec crypto_data_db psql -U postgres -d crypto_data -c "
  SELECT
    'quotes' as type,
    COUNT(*) as total,
    MAX(timestamp) as latest,
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60, 1) as minutes_ago
  FROM eth_option_quotes
  UNION ALL
  SELECT 'depth', COUNT(*), MAX(timestamp),
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60, 1)
  FROM eth_option_orderbook_depth;
"
```

```bash
chmod +x /volume1/docker/crypto-collector/monitor.sh
```

**Run anytime to check status**:

```bash
/volume1/docker/crypto-collector/monitor.sh
```

---

## Phase 12: Migrate Existing Data (Optional)

If you collected data on your Mac and want to migrate it:

### On Your Mac:

```bash
# Export database
PGPASSWORD=password pg_dump -h localhost -U postgres -d crypto_data \
  --format=custom --compress=9 \
  --file=~/crypto_data_backup.backup

# Transfer to NAS
scp ~/crypto_data_backup.backup your-username@192.168.1.100:/volume1/backups/
```

### On NAS:

```bash
# Restore to NAS database
docker exec -i crypto_data_db pg_restore \
  --username=postgres \
  --dbname=crypto_data \
  --clean --if-exists \
  < /volume1/backups/crypto_data_backup.backup

# Verify
docker exec crypto_data_db psql -U postgres -d crypto_data -c \
  "SELECT COUNT(*) FROM eth_option_quotes;"
```

---

## Security Best Practices

1. **Change Default SSH Port**:
   - Control Panel → Terminal & SNMP
   - Change port from 22 to something like 2222

2. **Enable Auto-Block**:
   - Control Panel → Security → Account
   - Enable auto-block after 5 failed login attempts

3. **Enable HTTPS for DSM**:
   - Control Panel → Security → Certificate
   - Add a self-signed certificate

4. **Regular Updates**:
   - Control Panel → Update & Restore
   - Enable auto-install for DSM updates

5. **Enable 2FA** (Two-Factor Authentication):
   - Control Panel → User & Group
   - Your account → Edit → Enable 2-factor authentication

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs postgres
docker-compose logs collector

# Check permissions
ls -la /volume1/docker/crypto-collector/postgres-data/

# Restart
docker-compose down
docker-compose up -d
```

### Database Connection Issues

```bash
# Check PostgreSQL is listening
docker exec crypto_data_db netstat -an | grep 5432

# Check environment variables
docker exec eth_options_collector env | grep DATABASE

# Test connection
docker exec crypto_data_db psql -U postgres -d crypto_data -c "SELECT 1;"
```

### Out of Space

```bash
# Check disk usage
df -h /volume1

# Check Docker disk usage
docker system df

# Clean up old images/containers
docker system prune -a
```

---

## Performance Tuning

### For PostgreSQL/TimescaleDB

Add to docker-compose.yml under postgres service:

```yaml
environment:
  POSTGRES_INITDB_ARGS: "-E UTF8 --lc-collate=C --lc-ctype=C"
  POSTGRES_MAX_CONNECTIONS: "100"
  POSTGRES_SHARED_BUFFERS: "512MB"  # 25% of available RAM
  POSTGRES_WORK_MEM: "4MB"
```

---

## Summary Checklist

- [ ] NAS physically set up with 2x 4TB drives
- [ ] RAID 1 storage pool created (~4TB usable)
- [ ] Btrfs volume created
- [ ] Docker and Container Manager installed
- [ ] SSH enabled
- [ ] Static IP configured
- [ ] Shared folders created
- [ ] Application files transferred
- [ ] .env file configured with strong password
- [ ] Docker containers started
- [ ] Data collection verified
- [ ] Automated backups scheduled
- [ ] Monitoring script created
- [ ] TimescaleDB compression enabled (after 1 week)
- [ ] Security hardening completed

---

## Next Steps

After setup is complete:

1. **Monitor for 24-48 hours**: Check logs daily
2. **Verify backups**: Test restore from backup after 1 week
3. **Enable compression**: After 7 days, run compression commands
4. **Migrate Mac data**: Transfer existing local data if needed
5. **Stop Mac collector**: Once NAS is stable, stop local collection

**Estimated Total Storage Usage**:
- 1 month: ~1-2 GB
- 1 year: ~10-20 GB (with compression)
- 5 years: ~50-100 GB (with compression)

You have **4TB available**, so space is not a concern! ✅

---

## Support Resources

- **Synology Community**: https://community.synology.com/
- **Docker Documentation**: https://docs.docker.com/
- **TimescaleDB Docs**: https://docs.timescale.com/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

---

**Your NAS is ready to become a 24/7 crypto data collection powerhouse!** 🚀
