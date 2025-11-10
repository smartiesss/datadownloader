#!/bin/bash
# Watchdog: Auto-restart collector if no new ticks for 5 minutes
# Run this every 5 minutes via cron: */5 * * * * /path/to/watchdog.sh

set -e

# Configuration
MAX_TICK_AGE=300  # 5 minutes in seconds
LOGFILE="/var/log/collector-watchdog.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"
}

# Check if collector is running
if ! docker ps | grep -q "eth-collector"; then
    log "ERROR: Collector container not running - starting it..."
    cd /share/Container/datadownloader  # Adjust path for NAS
    docker-compose up -d collector
    log "Collector started"
    exit 0
fi

# Check last tick age
LAST_TICK_AGE=$(docker exec eth-timescaledb psql -U postgres -d crypto_data -t -c \
  "SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))), 9999) FROM eth_option_quotes;" \
  2>/dev/null | tr -d ' ')

if [ -z "$LAST_TICK_AGE" ]; then
    log "WARNING: Cannot query database - collector may be initializing"
    exit 0
fi

# Convert to integer
LAST_TICK_AGE=${LAST_TICK_AGE%.*}

if [ "$LAST_TICK_AGE" -gt "$MAX_TICK_AGE" ]; then
    log "ALERT: No ticks for ${LAST_TICK_AGE}s (threshold: ${MAX_TICK_AGE}s) - restarting collector..."
    
    # Restart collector
    cd /share/Container/datadownloader
    docker-compose restart collector
    
    log "Collector restarted - monitoring recovery..."
    
    # Wait 30s and verify ticks are coming in
    sleep 30
    NEW_TICK_AGE=$(docker exec eth-timescaledb psql -U postgres -d crypto_data -t -c \
      "SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))), 9999) FROM eth_option_quotes;" \
      2>/dev/null | tr -d ' ')
    NEW_TICK_AGE=${NEW_TICK_AGE%.*}
    
    if [ "$NEW_TICK_AGE" -lt 60 ]; then
        log "SUCCESS: Collector recovered - receiving ticks"
    else
        log "ERROR: Collector still not receiving ticks - manual intervention needed!"
    fi
else
    log "OK: Last tick ${LAST_TICK_AGE}s ago - healthy"
fi
