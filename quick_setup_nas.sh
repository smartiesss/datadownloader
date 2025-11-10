#!/bin/bash
# Quick NAS Setup Script
# Run this on your NAS to set up git and deployment automation

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}NAS Quick Setup - Crypto Collector${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if running on NAS
if [ ! -d "/volume1" ]; then
    echo -e "${RED}ERROR: This script should be run on the NAS!${NC}"
    exit 1
fi

# Step 1: Check Git
echo -e "${BLUE}[1/5] Checking Git installation...${NC}"
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    echo -e "${GREEN}✓ Git installed: $GIT_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ Git not found!${NC}"
    echo -e "${YELLOW}Please install Git Server from Synology Package Center${NC}"
    echo -e "${YELLOW}Then run this script again.${NC}"
    exit 1
fi

# Step 2: Backup existing directory
echo -e "${BLUE}[2/5] Checking existing installation...${NC}"
if [ -d "/volume1/crypto-collector" ]; then
    echo -e "${YELLOW}Existing installation found${NC}"
    BACKUP_DIR="/volume1/crypto-collector-backup-$(date +%Y%m%d-%H%M%S)"
    echo -e "${YELLOW}Creating backup: $BACKUP_DIR${NC}"
    sudo cp -r /volume1/crypto-collector "$BACKUP_DIR"
    echo -e "${GREEN}✓ Backup created${NC}"
else
    echo -e "${GREEN}✓ No existing installation${NC}"
fi

# Step 3: Clone repository
echo -e "${BLUE}[3/5] Cloning repository...${NC}"
cd /volume1

if [ -d "/volume1/crypto-collector/.git" ]; then
    echo -e "${YELLOW}Git repository already exists, skipping clone${NC}"
    cd crypto-collector
    sudo git pull origin main
    echo -e "${GREEN}✓ Repository updated${NC}"
else
    if [ -d "/volume1/crypto-collector" ]; then
        sudo rm -rf /volume1/crypto-collector
    fi
    sudo git clone https://github.com/smartiesss/datadownloader.git crypto-collector
    echo -e "${GREEN}✓ Repository cloned${NC}"
fi

# Step 4: Set permissions
echo -e "${BLUE}[4/5] Setting permissions...${NC}"
cd /volume1/crypto-collector
sudo chmod +x nas_deploy.sh
sudo chmod +x quick_setup_nas.sh
echo -e "${GREEN}✓ Permissions set${NC}"

# Step 5: Show next steps
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${BLUE}Repository cloned to:${NC} /volume1/crypto-collector"
echo -e "${BLUE}Current commit:${NC} $(git rev-parse --short HEAD)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo -e "1. ${BLUE}Test manual deployment:${NC}"
echo -e "   cd /volume1/crypto-collector"
echo -e "   sudo ./nas_deploy.sh"
echo ""
echo -e "2. ${BLUE}Set up automatic updates (recommended):${NC}"
echo -e "   sudo crontab -e"
echo -e "   Add this line for updates every 6 hours:"
echo -e "   ${GREEN}0 */6 * * * cd /volume1/crypto-collector && ./nas_deploy.sh >> /var/log/nas-deploy.log 2>&1${NC}"
echo ""
echo -e "3. ${BLUE}View deployment logs:${NC}"
echo -e "   sudo tail -f /var/log/nas-deploy.log"
echo ""
echo -e "4. ${BLUE}Check container status:${NC}"
echo -e "   sudo docker ps | grep -E 'eth-collector|perp-collector'"
echo ""
echo -e "${YELLOW}For more options, see:${NC} NAS_DEPLOYMENT_GUIDE.md"
echo ""
