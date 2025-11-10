# Synology DS925+ Quick Start - Crypto Collector

## ⚡ Quick Setup Checklist (2 hours total)

### 🔧 Phase 1: Hardware (15 min)
- [ ] Install 2x 4TB drives in bays 1 & 2
- [ ] Connect Ethernet cable
- [ ] Power on NAS
- [ ] Wait for beep + green LED

### 🌐 Phase 2: Initial Setup (30 min)
- [ ] Go to http://find.synology.com
- [ ] Install DSM (formats drives, ~10 min)
- [ ] Create admin account (SAVE PASSWORD!)
- [ ] Update DSM (reboot required)

### 💾 Phase 3: Storage (15 min)
- [ ] Storage Manager → Create Storage Pool
- [ ] Choose **RAID 1** (4TB usable, data redundancy)
- [ ] Create Btrfs volume (use max space)

### 📦 Phase 4: Install Software (20 min)
- [ ] Package Center → Install **Docker**
- [ ] Package Center → Install **Container Manager**
- [ ] Control Panel → Terminal → Enable **SSH**
- [ ] Control Panel → Network → Set **static IP**: `192.168.1.100`

### 📁 Phase 5: Create Folders (5 min)
- [ ] Control Panel → Shared Folder → Create:
  - `docker` (for containers)
  - `crypto-collector` (for app)
  - `backups` (for DB backups)

### 🚀 Phase 6: Deploy Application (30 min)

**On your Mac**:
```bash
cd /Users/doghead/PycharmProjects/datadownloader

# Transfer files to NAS (replace IP and username)
rsync -avz --exclude 'logs/' --exclude '__pycache__/' \
  ./ your-username@192.168.1.100:/volume1/docker/crypto-collector/
```

**SSH to NAS**:
```bash
ssh your-username@192.168.1.100
cd /volume1/docker/crypto-collector

# Create .env file
cp .env.example .env
nano .env
# Edit: Set DATABASE_URL and DB_PASSWORD

# Start services
docker-compose up -d postgres
sleep 10
docker-compose up -d collector

# Check logs
docker-compose logs -f collector
# Should see: "WebSocket connected successfully"
```

### ✅ Phase 7: Verify (10 min)
```bash
# Check containers are running
docker ps

# Check data collection (wait 5 minutes first)
docker-compose exec postgres psql -U postgres -d crypto_data -c \
  "SELECT 'quotes', COUNT(*) FROM eth_option_quotes
   UNION ALL
   SELECT 'depth', COUNT(*) FROM eth_option_orderbook_depth;"

# Should see quotes and depth snapshots
```

### 🔒 Phase 8: Security (10 min)
- [ ] Control Panel → Security → Enable **Auto-block** (5 failed attempts)
- [ ] Control Panel → Security → Firewall → Allow SSH from local network only
- [ ] Control Panel → User → Enable **2FA** (optional but recommended)

### 💾 Phase 9: Backups (10 min)
```bash
# Create backup script
nano /volume1/docker/crypto-collector/backup.sh
```

Paste:
```bash
#!/bin/bash
BACKUP_DIR="/volume1/backups/crypto-collector"
mkdir -p ${BACKUP_DIR}
docker exec crypto_data_db pg_dump -U postgres crypto_data | \
  gzip > ${BACKUP_DIR}/backup_$(date +%Y%m%d_%H%M%S).sql.gz
find ${BACKUP_DIR} -name "backup_*.sql.gz" -mtime +30 -delete
```

```bash
chmod +x /volume1/docker/crypto-collector/backup.sh
```

- [ ] Control Panel → Task Scheduler → Create daily task at 2 AM
  - Script: `/volume1/docker/crypto-collector/backup.sh`

---

## 🎯 Quick Commands Reference

### Check Status
```bash
ssh your-username@192.168.1.100
cd /volume1/docker/crypto-collector

# View running containers
docker ps

# View collector logs
docker-compose logs -f collector

# Check database
docker-compose exec postgres psql -U postgres -d crypto_data -c \
  "SELECT COUNT(*) as quotes FROM eth_option_quotes;"
```

### Restart Collector
```bash
docker-compose restart collector
```

### Stop Everything
```bash
docker-compose down
```

### Start Everything
```bash
docker-compose up -d
```

### View Database Size
```bash
docker-compose exec postgres psql -U postgres -d crypto_data -c \
  "SELECT pg_size_pretty(pg_database_size('crypto_data'));"
```

---

## 📊 What to Expect

**After 1 hour**:
- ~2,000-5,000 quote records
- ~12 depth snapshots (one per 5 min)
- Database size: ~5-10 MB

**After 24 hours**:
- ~100,000-200,000 quote records
- ~288 depth snapshots
- Database size: ~50-100 MB

**After 1 week**:
- ~1-2 million quote records
- ~2,000 depth snapshots
- Database size: ~500 MB - 1 GB
- **Then enable compression** (see full guide)

**After 1 month** (with compression):
- Database size: ~1-2 GB
- Available space: **~3.9 TB remaining** (out of 4 TB)

---

## 🆘 Troubleshooting

### Can't access NAS
```bash
# Find NAS IP
arp -a | grep -i synology

# Or use Synology Assistant (download from synology.com)
```

### Containers won't start
```bash
# Check logs
docker-compose logs

# Restart Docker
sudo synoservicectl --restart pkgctl-Docker
```

### No data being collected
```bash
# Check collector logs
docker-compose logs collector | tail -50

# Should see "Successfully subscribed to 100 channels"
# If errors, check .env file has correct DATABASE_URL
```

### Forgot admin password
- Physical reset button on NAS (hold 4 seconds)
- Warning: Does NOT delete data, only resets admin password

---

## 📚 Full Documentation

See `NAS_SETUP_GUIDE.md` for:
- Detailed explanations
- Advanced configuration
- Performance tuning
- Migration from Mac to NAS
- Security hardening
- Monitoring setup

---

## ✅ Success Criteria

You're done when:
- [ ] Both Docker containers show as "Up" in `docker ps`
- [ ] Database has quote and depth records
- [ ] Latest record timestamp is < 5 minutes old
- [ ] Backup script runs successfully
- [ ] You can SSH into NAS

**Total time**: ~2 hours for complete setup

**You now have a 24/7 crypto data collection system!** 🎉

---

## 💡 Pro Tips

1. **Use Container Manager UI**: Easier than SSH for viewing logs/stats
   - Open Container Manager app on NAS
   - See all containers, logs, and resource usage

2. **Enable Email Notifications**: Get alerts if container stops
   - Control Panel → Notification → Email
   - Set up SMTP
   - Enable notifications for Docker

3. **Monitor Disk Space**: Set up alerts
   - Storage Manager → Storage Pool → Settings
   - Enable space usage notifications at 80%

4. **Remote Access** (optional):
   - Control Panel → External Access → DDNS
   - Set up Dynamic DNS for remote access
   - **Use VPN** for security (don't expose PostgreSQL to internet!)

5. **Regular Maintenance**:
   - Monthly: Check backup restores work
   - Quarterly: Update DSM and Docker images
   - Yearly: Check drive health (Storage Manager → HDD/SSD)

---

Your Synology DS925+ is a powerful platform - enjoy your automated data collection! 🚀
