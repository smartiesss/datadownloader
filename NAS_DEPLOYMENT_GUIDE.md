# NAS Deployment Guide - Production System

This guide assumes you've successfully completed the **LOCAL_TESTING_GUIDE.md** and your system ran for 24 hours without errors.

## Prerequisites

✅ **MUST have completed:**
- [x] Local testing for 24 hours
- [x] All collectors running without errors
- [x] Database receiving data continuously
- [x] No memory/CPU issues

📋 **NAS Requirements:**
- Synology/QNAP/TerraMaster NAS with Docker support
- 8GB RAM minimum (16GB recommended)
- 200GB free disk space minimum
- SSH access to NAS
- Git installed on NAS

## Step 1: Deploy to NAS

Simply use the fresh_start_nas.sh script we created earlier:

```bash
# SSH into NAS
ssh smartiesbul@192.168.68.62
cd /volume1/crypto-collector

# Pull latest code
git pull

# Run deployment script
sudo bash fresh_start_nas.sh
```

This will automatically:
1. Clean up old containers/volumes
2. Pull latest code
3. Set up .env
4. Start all containers
5. Show you the logs

## Step 2: Verify Deployment

After fresh_start_nas.sh completes, verify:

```bash
# Check all containers running
sudo docker-compose ps

# Should see:
# - crypto-timescaledb (healthy)
# - crypto-eth-options
# - crypto-btc-options  
# - crypto-perpetuals
# - crypto-grafana
```

## Step 3: Monitor

Use the monitoring commands from LOCAL_TESTING_GUIDE.md

That's it! The system is now running 24/7 on your NAS.
