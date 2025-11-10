#!/bin/bash
# NAS Deployment Script with Docker Compose Rebuild
# Usage: ./nas_deploy_compose.sh [--no-backup] [--force]

set -e  # Exit on error

# Configuration
REPO_DIR="/volume1/crypto-collector"
BACKUP_DIR="/volume1/crypto-collector-backup"
GITHUB_REPO="https://github.com/smartiesss/datadownloader.git"
SCRIPTS_DIR="${REPO_DIR}/scripts"
MIGRATIONS_DIR="${REPO_DIR}/migrations"
COMPOSE_FILE="${REPO_DIR}/docker-compose-fixed.yml"  # Your compose file

# Containers to manage
ETH_CONTAINER="eth-collector"
PERP_CONTAINER="perp-collector"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
NO_BACKUP=false
FORCE=false
for arg in "$@"; do
    case $arg in
        --no-backup)
            NO_BACKUP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
    esac
done

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}NAS Crypto Collector - Docker Compose Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if running on NAS (basic check)
if [ ! -d "/volume1" ]; then
    echo -e "${RED}ERROR: This script should be run on the NAS!${NC}"
    echo -e "${YELLOW}Current directory doesn't look like NAS (/volume1 not found)${NC}"
    exit 1
fi

# Step 1: Check if repo directory exists
echo -e "${BLUE}[1/9] Checking repository...${NC}"
if [ ! -d "$REPO_DIR/.git" ]; then
    echo -e "${YELLOW}Git repository not found at $REPO_DIR${NC}"
    echo -e "${YELLOW}Cloning repository...${NC}"

    # Backup existing directory if it exists
    if [ -d "$REPO_DIR" ] && [ "$NO_BACKUP" = false ]; then
        echo -e "${YELLOW}Backing up existing directory to ${BACKUP_DIR}-$(date +%Y%m%d-%H%M%S)${NC}"
        sudo cp -r "$REPO_DIR" "${BACKUP_DIR}-$(date +%Y%m%d-%H%M%S)"
    fi

    # Clone repository
    sudo git clone "$GITHUB_REPO" "$REPO_DIR"
    echo -e "${GREEN}✓ Repository cloned${NC}"
else
    echo -e "${GREEN}✓ Repository found${NC}"
fi

# Step 2: Check for local changes
echo -e "${BLUE}[2/9] Checking for local changes...${NC}"
cd "$REPO_DIR"
if ! sudo git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}WARNING: Local changes detected!${NC}"
    sudo git status --short

    if [ "$FORCE" = false ]; then
        echo -e "${RED}Deployment aborted. Use --force to override.${NC}"
        exit 1
    else
        echo -e "${YELLOW}Stashing local changes (use 'git stash pop' to restore)${NC}"
        sudo git stash
    fi
else
    echo -e "${GREEN}✓ No local changes${NC}"
fi

# Step 3: Pull latest code
echo -e "${BLUE}[3/9] Pulling latest code from GitHub...${NC}"
BEFORE_COMMIT=$(sudo git rev-parse HEAD)
sudo git pull origin main

AFTER_COMMIT=$(sudo git rev-parse HEAD)
if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    echo -e "${GREEN}✓ Already up to date (commit: ${AFTER_COMMIT:0:7})${NC}"
    echo -e "${YELLOW}No changes detected. Skipping container rebuild.${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo -e "${GREEN}Deployment complete - no updates needed${NC}"
    echo -e "${BLUE}================================================${NC}"
    exit 0
else
    echo -e "${GREEN}✓ Updated from ${BEFORE_COMMIT:0:7} to ${AFTER_COMMIT:0:7}${NC}"
    echo ""
    echo -e "${BLUE}Changes:${NC}"
    sudo git log --oneline --decorate --color=always "${BEFORE_COMMIT}..${AFTER_COMMIT}"
    echo ""
fi

# Step 4: Check docker-compose file
echo -e "${BLUE}[4/9] Checking docker-compose file...${NC}"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}ERROR: docker-compose file not found: $COMPOSE_FILE${NC}"
    echo -e "${YELLOW}Please check the COMPOSE_FILE path in this script${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Found: $COMPOSE_FILE${NC}"

# Step 5: Backup current containers
if [ "$NO_BACKUP" = false ]; then
    echo -e "${BLUE}[5/9] Creating backup...${NC}"
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_PATH="${BACKUP_DIR}-${BACKUP_TIMESTAMP}"

    sudo mkdir -p "$BACKUP_PATH"
    sudo cp -r "${SCRIPTS_DIR}" "$BACKUP_PATH/"

    # Export container logs before stopping
    sudo docker logs "$ETH_CONTAINER" > "${BACKUP_PATH}/eth-collector-${BACKUP_TIMESTAMP}.log" 2>&1 || true
    sudo docker logs "$PERP_CONTAINER" > "${BACKUP_PATH}/perp-collector-${BACKUP_TIMESTAMP}.log" 2>&1 || true

    echo -e "${GREEN}✓ Backup created at $BACKUP_PATH${NC}"
else
    echo -e "${YELLOW}[5/9] Skipping backup (--no-backup)${NC}"
fi

# Step 6: Check if database migrations needed
echo -e "${BLUE}[6/9] Checking for database migrations...${NC}"
if [ -d "$MIGRATIONS_DIR" ]; then
    MIGRATION_FILES=$(find "$MIGRATIONS_DIR" -name "*.sql" -type f)
    if [ -n "$MIGRATION_FILES" ]; then
        echo -e "${YELLOW}Found migration files:${NC}"
        echo "$MIGRATION_FILES"
        echo -e "${YELLOW}Run migrations manually if needed:${NC}"
        echo "  sudo docker exec eth-timescaledb psql -U postgres -d crypto_data -f /path/to/migration.sql"
    else
        echo -e "${GREEN}✓ No migration files found${NC}"
    fi
else
    echo -e "${GREEN}✓ No migrations directory${NC}"
fi

# Step 7: Stop and remove containers (docker-compose down)
echo -e "${BLUE}[7/9] Stopping containers with docker-compose...${NC}"
cd "$REPO_DIR"
sudo docker-compose -f "$COMPOSE_FILE" stop $ETH_CONTAINER $PERP_CONTAINER || true
echo -e "${GREEN}✓ Containers stopped${NC}"

# Step 8: Rebuild containers (docker-compose build)
echo -e "${BLUE}[8/9] Rebuilding containers with new code...${NC}"
sudo docker-compose -f "$COMPOSE_FILE" build $ETH_CONTAINER $PERP_CONTAINER
echo -e "${GREEN}✓ Containers rebuilt${NC}"

# Step 9: Start containers (docker-compose up)
echo -e "${BLUE}[9/9] Starting containers...${NC}"
sudo docker-compose -f "$COMPOSE_FILE" up -d $ETH_CONTAINER $PERP_CONTAINER
echo -e "${GREEN}✓ Containers started${NC}"

# Wait for containers to initialize
echo ""
echo -e "${BLUE}Waiting 15 seconds for initialization...${NC}"
sleep 15

# Verify deployment
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Deployment Verification${NC}"
echo -e "${BLUE}================================================${NC}"

# Check container status
echo -e "${BLUE}Container Status:${NC}"
ETH_STATUS=$(sudo docker ps --filter "name=$ETH_CONTAINER" --format "{{.Status}}" || echo "Not found")
PERP_STATUS=$(sudo docker ps --filter "name=$PERP_CONTAINER" --format "{{.Status}}" || echo "Not found")

if [[ "$ETH_STATUS" == *"Up"* ]]; then
    echo -e "${GREEN}✓ $ETH_CONTAINER: $ETH_STATUS${NC}"
else
    echo -e "${RED}✗ $ETH_CONTAINER: $ETH_STATUS${NC}"
fi

if [[ "$PERP_STATUS" == *"Up"* ]]; then
    echo -e "${GREEN}✓ $PERP_CONTAINER: $PERP_STATUS${NC}"
else
    echo -e "${RED}✗ $PERP_CONTAINER: $PERP_STATUS${NC}"
fi

# Show recent logs
echo ""
echo -e "${BLUE}Recent ETH Collector Logs (last 30 lines):${NC}"
sudo docker logs --tail 30 "$ETH_CONTAINER" 2>&1 | tail -30

echo ""
echo -e "${BLUE}Recent Perp Collector Logs (last 20 lines):${NC}"
sudo docker logs --tail 20 "$PERP_CONTAINER" 2>&1 | tail -20

# Summary
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "Updated: ${BEFORE_COMMIT:0:7} → ${AFTER_COMMIT:0:7}"
echo -e "Timestamp: $(date)"
if [ "$NO_BACKUP" = false ]; then
    echo -e "Backup: $BACKUP_PATH"
fi
echo ""
echo -e "${YELLOW}Monitor logs with:${NC}"
echo -e "  sudo docker logs -f $ETH_CONTAINER"
echo -e "  sudo docker logs -f $PERP_CONTAINER"
echo ""
echo -e "${YELLOW}Check data collection:${NC}"
echo -e "  sudo docker exec eth-timescaledb psql -U postgres -d crypto_data -c \"SELECT COUNT(*), MAX(timestamp) FROM eth_option_quotes;\""
echo ""
echo -e "${YELLOW}Rollback if needed:${NC}"
echo -e "  cd $REPO_DIR && sudo git reset --hard ${BEFORE_COMMIT}"
echo -e "  sudo docker-compose -f $COMPOSE_FILE build $ETH_CONTAINER $PERP_CONTAINER"
echo -e "  sudo docker-compose -f $COMPOSE_FILE up -d $ETH_CONTAINER $PERP_CONTAINER"
echo ""
