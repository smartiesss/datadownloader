#!/bin/bash
#
# Fresh Start - Complete NAS Deployment Reset
# This script wipes everything and deploys from scratch
#

set -e  # Exit on error

echo "========================================"
echo "FRESH START - Complete Reset"
echo "========================================"
echo ""
echo "This will:"
echo "  1. Remove all containers and volumes"
echo "  2. Pull latest code from GitHub"
echo "  3. Set up .env file"
echo "  4. Start fresh containers"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi
echo ""

# Step 1: Complete cleanup
echo "Step 1: Cleaning up old deployment..."
cd /volume1/crypto-collector

# Stop and remove all containers
echo "Stopping containers..."
sudo docker-compose down -v 2>/dev/null || true

# Remove any orphaned containers
echo "Removing orphaned containers..."
sudo docker ps -a | grep -E "eth-|crypto-" | awk '{print $1}' | xargs -r sudo docker rm -f 2>/dev/null || true

# Remove volumes
echo "Removing volumes..."
sudo docker volume ls | grep -E "crypto-collector|timescaledb|grafana" | awk '{print $2}' | xargs -r sudo docker volume rm 2>/dev/null || true

# Clean up any dangling images
echo "Cleaning up Docker resources..."
sudo docker system prune -f

echo "✅ Cleanup complete"
echo ""

# Step 2: Pull latest code
echo "Step 2: Pulling latest code from GitHub..."
git fetch origin
git reset --hard origin/main
git pull origin main

echo "✅ Code updated"
echo ""

# Step 3: Set up .env file
echo "Step 3: Setting up .env file..."

# Check if backup .env exists
if [ -f "/volume1/crypto-collector-backup-20251110-180521/.env" ]; then
    echo "Found backup .env file, copying..."
    cp /volume1/crypto-collector-backup-20251110-180521/.env .env
else
    echo "No backup found, creating new .env from example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and set passwords!"
    echo "Run: nano .env"
    echo "Change POSTGRES_PASSWORD and GRAFANA_PASSWORD"
    echo ""
    read -p "Press Enter after editing .env file..."
fi

# Display current .env
echo ""
echo "Current .env configuration:"
cat .env
echo ""

echo "✅ .env file ready"
echo ""

# Step 4: Create required directories
echo "Step 4: Creating directories..."
mkdir -p logs backups config
echo "✅ Directories created"
echo ""

# Step 5: Start containers
echo "Step 5: Starting containers..."
sudo docker-compose up -d

echo ""
echo "Waiting 15 seconds for database to initialize..."
sleep 15
echo ""

# Step 6: Check container status
echo "Step 6: Checking container status..."
sudo docker-compose ps
echo ""

# Step 7: Show logs
echo "Step 7: Recent logs from collector..."
sudo docker-compose logs --tail=50 collector
echo ""

echo "========================================"
echo "✅ Fresh Start Complete!"
echo "========================================"
echo ""
echo "Monitor with: sudo docker-compose logs -f collector"
echo "Check status: sudo docker-compose ps"
echo "Stop all: sudo docker-compose down"
echo ""
echo "Grafana: http://$(hostname -I | awk '{print $1}'):3000"
echo "  Username: admin"
echo "  Password: (check your .env file)"
echo ""
