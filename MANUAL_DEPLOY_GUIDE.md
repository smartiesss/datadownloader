# Manual Deployment Guide - Perpetual Collector to NAS

## Step 1: Upload Files (requires password 4 times)

```bash
# Upload perpetual writer
scp scripts/tick_writer_perp.py smartiesbul@192.168.68.62:/volume1/crypto-collector/scripts/

# Upload perpetual collector
scp scripts/ws_perp_collector.py smartiesbul@192.168.68.62:/volume1/crypto-collector/scripts/

# Upload fixed tick writer (with trade bug fix)
scp scripts/tick_writer_multi.py smartiesbul@192.168.68.62:/volume1/crypto-collector/scripts/

# Upload new schema
scp schema/004_add_perpetual_tick_tables.sql smartiesbul@192.168.68.62:/volume1/crypto-collector/schema/
```

## Step 2: SSH into NAS and apply schema

```bash
ssh smartiesbul@192.168.68.62
```

Once logged in, run these commands:

```bash
cd /volume1/crypto-collector

# Apply perpetual schema
docker exec timescaledb psql -U postgres -d crypto_data -f /schema/004_add_perpetual_tick_tables.sql

# Verify tables created
docker exec timescaledb psql -U postgres -d crypto_data -c "\dt perpetuals*"
```

## Step 3: Add perpetual collector to docker-compose.yml

Still SSH'd into NAS, edit docker-compose.yml:

```bash
nano docker-compose.yml
```

Add this at the end of the file (before the final closing line):

```yaml
  # ============================================================================
  # PERPETUAL FUTURES COLLECTOR (BTC-PERPETUAL, ETH-PERPETUAL)
  # ============================================================================
  perp-collector:
    image: python:3.11-slim
    container_name: perp-collector
    restart: unless-stopped
    volumes:
      - ./scripts:/app/scripts
      - ./logs:/app/logs
      - ./.env:/app/.env
    working_dir: /app
    command: >
      sh -c "pip install --no-cache-dir asyncpg aiohttp websockets python-dotenv &&
             python -m scripts.ws_perp_collector"
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@timescaledb:5432/crypto_data
      - LOG_LEVEL=INFO
      - DERIBIT_WS_URL=wss://www.deribit.com/ws/api/v2
      - BUFFER_SIZE_QUOTES=200000
      - BUFFER_SIZE_TRADES=100000
      - FLUSH_INTERVAL_SEC=3
      - SNAPSHOT_INTERVAL_SEC=300
    depends_on:
      - timescaledb
    networks:
      - crypto-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

## Step 4: Restart containers

```bash
# Stop old collectors
docker-compose stop ws-collector-eth ws-collector-btc

# Start all collectors (including new perpetual collector)
docker-compose up -d

# Wait 10 seconds
sleep 10

# Check status
docker-compose ps

# View perpetual collector logs
docker-compose logs --tail=50 perp-collector
```

## Step 5: Verify data collection

```bash
# Check for perpetual trades (should see increasing count)
docker exec timescaledb psql -U postgres -d crypto_data -c "
SELECT
  'perpetuals_quotes' as table,
  COUNT(*) as count,
  MAX(timestamp) as last_update
FROM perpetuals_quotes
UNION ALL
SELECT
  'perpetuals_trades' as table,
  COUNT(*) as count,
  MAX(timestamp) as last_update
FROM perpetuals_trades
ORDER BY table;
"
```

## Step 6: Monitor logs

```bash
# Follow perpetual collector logs
docker-compose logs -f perp-collector

# Press Ctrl+C to exit log view
```

## Expected Results

After 1-2 minutes, you should see:
- Perpetual trades: ~100-200 trades/minute (BTC + ETH combined)
- Perpetual quotes: ~400-700 quotes/minute
- No errors in logs

## Troubleshoot

If no trades appearing:
```bash
# Check container is running
docker ps | grep perp

# Check for errors
docker-compose logs perp-collector | grep ERROR

# Restart if needed
docker-compose restart perp-collector
```
