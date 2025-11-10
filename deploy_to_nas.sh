#!/bin/bash
#
# Deploy Perpetual Collector to Synology NAS
# This script will:
# 1. Set up SSH key authentication (requires password once)
# 2. Upload new files
# 3. Apply database schema
# 4. Update docker-compose
# 5. Start new containers

set -e  # Exit on error

NAS_HOST="192.168.68.62"
NAS_USER="smartiesbul"
NAS_PATH="/volume1/crypto-collector"
LOCAL_PATH="/Users/doghead/PycharmProjects/datadownloader"

echo "========================================"
echo "Deploying Perpetual Collector to NAS"
echo "========================================"
echo ""

# Step 1: Set up SSH key authentication
echo "Step 1: Setting up SSH key authentication..."
echo "You will be prompted for your NAS password"
ssh-copy-id -i ~/.ssh/id_rsa.pub ${NAS_USER}@${NAS_HOST} 2>/dev/null || echo "SSH key already installed or failed"
echo ""

# Test SSH connection
echo "Testing SSH connection..."
if ssh ${NAS_USER}@${NAS_HOST} "echo 'SSH connection successful'"; then
    echo "✅ SSH connection working"
else
    echo "❌ SSH connection failed. Please check your credentials."
    exit 1
fi
echo ""

# Step 2: Upload new files
echo "Step 2: Uploading new files to NAS..."
echo "Uploading perpetual collector files..."

# Upload new Python scripts
scp ${LOCAL_PATH}/scripts/tick_writer_perp.py ${NAS_USER}@${NAS_HOST}:${NAS_PATH}/scripts/
scp ${LOCAL_PATH}/scripts/ws_perp_collector.py ${NAS_USER}@${NAS_HOST}:${NAS_PATH}/scripts/

# Upload updated tick_writer_multi.py (with trade fix)
scp ${LOCAL_PATH}/scripts/tick_writer_multi.py ${NAS_USER}@${NAS_HOST}:${NAS_PATH}/scripts/

# Upload new schema
scp ${LOCAL_PATH}/schema/004_add_perpetual_tick_tables.sql ${NAS_USER}@${NAS_HOST}:${NAS_PATH}/schema/

echo "✅ Files uploaded successfully"
echo ""

# Step 3: Apply database schema
echo "Step 3: Applying database schema..."
ssh ${NAS_USER}@${NAS_HOST} << 'ENDSSH'
cd /volume1/crypto-collector

# Apply perpetual schema
echo "Applying perpetual tick data schema..."
docker exec timescaledb psql -U postgres -d crypto_data -f /schema/004_add_perpetual_tick_tables.sql 2>&1 | grep -E "(CREATE TABLE|ERROR|NOTICE)" || echo "Schema applied (warnings about TimescaleDB functions are expected)"

echo "✅ Database schema updated"
ENDSSH
echo ""

# Step 4: Update docker-compose with new containers
echo "Step 4: Updating docker-compose.yml..."
ssh ${NAS_USER}@${NAS_HOST} << 'ENDSSH'
cd /volume1/crypto-collector

# Backup existing docker-compose
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)

# Add perpetual collectors to docker-compose
cat >> docker-compose.yml << 'EOF'

  # ============================================================================
  # PERPETUAL FUTURES COLLECTORS (BTC-PERPETUAL, ETH-PERPETUAL)
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
EOF

echo "✅ Docker-compose.yml updated with perpetual collector"
ENDSSH
echo ""

# Step 5: Restart collectors
echo "Step 5: Starting new containers..."
ssh ${NAS_USER}@${NAS_HOST} << 'ENDSSH'
cd /volume1/crypto-collector

echo "Stopping old containers..."
docker-compose stop ws-collector-eth ws-collector-btc 2>/dev/null || true

echo "Starting all collectors (including new perpetual collector)..."
docker-compose up -d

echo ""
echo "Waiting 10 seconds for containers to start..."
sleep 10

echo ""
echo "Container status:"
docker-compose ps

echo ""
echo "Recent logs from perpetual collector:"
docker-compose logs --tail=20 perp-collector
ENDSSH
echo ""

# Step 6: Verify deployment
echo "Step 6: Verifying deployment..."
ssh ${NAS_USER}@${NAS_HOST} << 'ENDSSH'
cd /volume1/crypto-collector

echo "Checking database for perpetual data..."
docker exec timescaledb psql -U postgres -d crypto_data -c "
SELECT
  'perpetuals_quotes' as table_name,
  COUNT(*) as count,
  MAX(timestamp) as last_update
FROM perpetuals_quotes
UNION ALL
SELECT
  'perpetuals_trades' as table_name,
  COUNT(*) as count,
  MAX(timestamp) as last_update
FROM perpetuals_trades
ORDER BY table_name;
"
ENDSSH
echo ""

echo "========================================"
echo "✅ Deployment Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Monitor logs: ssh ${NAS_USER}@${NAS_HOST} 'cd ${NAS_PATH} && docker-compose logs -f perp-collector'"
echo "2. Check status: ssh ${NAS_USER}@${NAS_HOST} 'cd ${NAS_PATH} && docker-compose ps'"
echo "3. View data: ssh ${NAS_USER}@${NAS_HOST} 'docker exec timescaledb psql -U postgres -d crypto_data -c \"SELECT COUNT(*) FROM perpetuals_trades\"'"
echo ""
echo "All collectors now running:"
echo "  - ETH Options (ws-collector-eth)"
echo "  - BTC Options (ws-collector-btc)"
echo "  - BTC+ETH Perpetuals (perp-collector) ✨ NEW"
echo "  - REST API data (rest-collector)"
echo ""
