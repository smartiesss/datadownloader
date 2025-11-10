# NAS Deployment & Automation Guide

## Overview

This guide explains how to:
1. Link your NAS to the GitHub repository
2. Deploy code updates automatically
3. Set up automation options (manual, scheduled, webhook)
4. Rollback if issues occur

## Prerequisites

- NAS with Docker containers running (eth-collector, perp-collector)
- SSH access to NAS
- GitHub repository: https://github.com/smartiesss/datadownloader.git

## Initial Setup (One-Time)

### Step 1: SSH to NAS and Install Git

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Check if git is installed
git --version

# If not installed, install via Synology Package Center:
# 1. Open Package Center
# 2. Search for "Git Server"
# 3. Install Git Server package
```

### Step 2: Clone Repository to NAS

```bash
# Navigate to your crypto collector directory
cd /volume1

# If directory already exists, back it up first
sudo mv /volume1/crypto-collector /volume1/crypto-collector-backup-$(date +%Y%m%d)

# Clone the repository
sudo git clone https://github.com/smartiesss/datadownloader.git crypto-collector

# Enter directory
cd crypto-collector

# Verify
ls -la
```

### Step 3: Upload Deployment Script

From your local machine:

```bash
# Upload the deployment script to NAS
scp nas_deploy.sh admin@your-nas-ip:/volume1/crypto-collector/

# SSH to NAS and make it executable
ssh admin@your-nas-ip
sudo chmod +x /volume1/crypto-collector/nas_deploy.sh
```

## Usage

### Manual Deployment

Run the deployment script manually whenever you push code to GitHub:

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Navigate to repository
cd /volume1/crypto-collector

# Run deployment
sudo ./nas_deploy.sh
```

**What it does:**
1. ✅ Pulls latest code from GitHub
2. ✅ Checks for changes (skips restart if no updates)
3. ✅ Creates backup of current code
4. ✅ Stops containers gracefully
5. ✅ Restarts containers with new code
6. ✅ Verifies deployment success
7. ✅ Shows recent logs

**Output example:**
```
================================================
NAS Crypto Collector - Deployment Script
================================================

[1/8] Checking repository...
✓ Repository found

[2/8] Checking for local changes...
✓ No local changes

[3/8] Pulling latest code from GitHub...
✓ Updated from a3b7c4d to f8e2a9b

Changes:
f8e2a9b Fix instrument expiry handling
65dfd56 Add automatic expiry detection

[4/8] Creating backup...
✓ Backup created at /volume1/crypto-collector-backup-20251110-153045

[5/8] Checking for database migrations...
✓ No migration files found

[6/8] Stopping containers...
✓ Containers stopped

[7/8] Waiting for clean shutdown...
✓ Ready to restart

[8/8] Restarting containers...
✓ Containers restarted

================================================
Deployment Complete!
================================================
Updated: a3b7c4d → f8e2a9b
Timestamp: Sun Nov 10 15:30:58 UTC 2025
Backup: /volume1/crypto-collector-backup-20251110-153045
```

### Script Options

```bash
# Skip backup (faster, but risky)
sudo ./nas_deploy.sh --no-backup

# Force deployment even with local changes
sudo ./nas_deploy.sh --force

# Both options
sudo ./nas_deploy.sh --no-backup --force
```

## Automation Options

### Option 1: Scheduled Updates (Cron)

**Pros:** Simple, reliable, no external dependencies
**Cons:** Fixed schedule, may deploy when not needed

Set up cron job to check for updates every hour:

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Edit crontab
sudo crontab -e

# Add this line (checks every hour at :00)
0 * * * * cd /volume1/crypto-collector && ./nas_deploy.sh >> /var/log/nas-deploy.log 2>&1
```

**Alternative schedules:**
```bash
# Every 6 hours
0 */6 * * * cd /volume1/crypto-collector && ./nas_deploy.sh

# Once daily at 3 AM
0 3 * * * cd /volume1/crypto-collector && ./nas_deploy.sh

# Every 30 minutes
*/30 * * * * cd /volume1/crypto-collector && ./nas_deploy.sh
```

View deployment logs:
```bash
sudo tail -f /var/log/nas-deploy.log
```

### Option 2: GitHub Webhook (Advanced)

**Pros:** Instant deployment on push, efficient
**Cons:** Requires public NAS access or VPN

This requires setting up a webhook listener on your NAS.

#### 2a. Create Webhook Listener Script

```bash
# Create webhook listener
cat > /volume1/crypto-collector/webhook_listener.py << 'EOF'
#!/usr/bin/env python3
"""
Simple webhook listener for GitHub push events.
Triggers deployment script when code is pushed.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import hmac
import hashlib
import os

# IMPORTANT: Set a secret token (same as in GitHub webhook settings)
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your-secret-token-here')
DEPLOY_SCRIPT = '/volume1/crypto-collector/nas_deploy.sh'

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)

        # Verify signature (optional but recommended)
        signature = self.headers.get('X-Hub-Signature-256')
        if signature:
            expected = 'sha256=' + hmac.new(
                WEBHOOK_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'Invalid signature')
                return

        # Parse payload
        try:
            payload = json.loads(body)
            ref = payload.get('ref', '')

            # Only deploy on push to main branch
            if ref == 'refs/heads/main':
                print(f"Received push to main branch. Triggering deployment...")

                # Run deployment script
                result = subprocess.run(
                    ['sudo', DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True
                )

                print(f"Deployment output:\n{result.stdout}")
                if result.stderr:
                    print(f"Deployment errors:\n{result.stderr}")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Deployment triggered')
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Ignored (not main branch)')

        except Exception as e:
            print(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f'Error: {str(e)}'.encode())

if __name__ == '__main__':
    PORT = 8765
    print(f"Starting webhook listener on port {PORT}...")
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    server.serve_forever()
EOF

# Make executable
sudo chmod +x /volume1/crypto-collector/webhook_listener.py
```

#### 2b. Configure GitHub Webhook

1. Go to https://github.com/smartiesss/datadownloader/settings/hooks
2. Click "Add webhook"
3. Set:
   - **Payload URL**: `http://your-nas-ip:8765/webhook` (or use Tailscale URL)
   - **Content type**: `application/json`
   - **Secret**: Your secret token (match `WEBHOOK_SECRET` in script)
   - **Events**: Just the push event
4. Click "Add webhook"

#### 2c. Run Webhook Listener

```bash
# Run in background
export WEBHOOK_SECRET="your-secret-token-here"
sudo nohup python3 /volume1/crypto-collector/webhook_listener.py > /var/log/webhook.log 2>&1 &

# Check if running
ps aux | grep webhook_listener

# View logs
tail -f /var/log/webhook.log
```

**Note:** For security, use Tailscale or VPN instead of exposing port 8765 to the internet.

### Option 3: Watch Script (Continuous Polling)

**Pros:** Simple, no external dependencies
**Cons:** Uses resources continuously

Create a watch script that checks every 5 minutes:

```bash
cat > /volume1/crypto-collector/watch_and_deploy.sh << 'EOF'
#!/bin/bash
# Continuously watch for GitHub updates and deploy

REPO_DIR="/volume1/crypto-collector"
CHECK_INTERVAL=300  # 5 minutes

echo "Starting deployment watcher (checks every ${CHECK_INTERVAL}s)..."

cd "$REPO_DIR"

while true; do
    # Fetch latest
    sudo git fetch origin main > /dev/null 2>&1

    # Check if local is behind remote
    LOCAL=$(sudo git rev-parse HEAD)
    REMOTE=$(sudo git rev-parse origin/main)

    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "[$(date)] Updates detected! Deploying..."
        sudo ./nas_deploy.sh
    else
        echo "[$(date)] No updates"
    fi

    sleep "$CHECK_INTERVAL"
done
EOF

sudo chmod +x /volume1/crypto-collector/watch_and_deploy.sh

# Run in background
sudo nohup /volume1/crypto-collector/watch_and_deploy.sh > /var/log/watch-deploy.log 2>&1 &
```

## Verification

After deployment, verify everything is working:

```bash
# Check container status
sudo docker ps | grep -E 'eth-collector|perp-collector'

# Check recent logs
sudo docker logs --tail 50 eth-collector
sudo docker logs --tail 50 perp-collector

# Look for these indicators:
# ✅ "Successfully subscribed to X channels"
# ✅ "Wrote X ETH quotes"
# ✅ No Python tracebacks or connection errors
```

## Rollback

If deployment causes issues, rollback to previous version:

```bash
# SSH to NAS
ssh admin@your-nas-ip

# Stop containers
sudo docker stop eth-collector perp-collector

# List backups
ls -lt /volume1/crypto-collector-backup-*

# Restore from latest backup (change timestamp as needed)
BACKUP_DIR="/volume1/crypto-collector-backup-20251110-153045"
sudo cp -r "$BACKUP_DIR/scripts/"* /volume1/crypto-collector/scripts/

# Restart containers
sudo docker start eth-collector perp-collector

# Verify
sudo docker logs -f eth-collector
```

**Or rollback via Git:**

```bash
# Check git log
cd /volume1/crypto-collector
sudo git log --oneline -10

# Rollback to specific commit
sudo git reset --hard <commit-hash>

# Run deployment script to restart containers
sudo ./nas_deploy.sh
```

## Recommended Setup

For most use cases, I recommend:

1. **Development workflow:**
   - Push code to GitHub from your local machine
   - Manually run `./nas_deploy.sh` on NAS to deploy
   - Good for testing and controlled deployments

2. **Production workflow:**
   - Set up cron job to check for updates every 6 hours
   - This ensures NAS stays updated without manual intervention
   - Balances automation with stability

```bash
# Add to crontab (checks every 6 hours)
sudo crontab -e

# Add this line:
0 */6 * * * cd /volume1/crypto-collector && ./nas_deploy.sh >> /var/log/nas-deploy.log 2>&1
```

## Troubleshooting

### "Git repository not found"
```bash
# Check if .git directory exists
ls -la /volume1/crypto-collector/.git

# If missing, reclone
cd /volume1
sudo git clone https://github.com/smartiesss/datadownloader.git crypto-collector
```

### "Permission denied"
```bash
# Ensure script is executable
sudo chmod +x /volume1/crypto-collector/nas_deploy.sh

# Check ownership
sudo chown -R admin:users /volume1/crypto-collector
```

### "Container won't start"
```bash
# Check container status
sudo docker ps -a | grep eth-collector

# View full logs
sudo docker logs eth-collector

# Check for port conflicts
sudo netstat -tulpn | grep 5432

# Restart Docker service
sudo systemctl restart docker  # or reboot NAS
```

### "Local changes detected"
```bash
# View changes
cd /volume1/crypto-collector
sudo git status

# Discard local changes
sudo git reset --hard HEAD

# Or use --force flag
sudo ./nas_deploy.sh --force
```

## Security Best Practices

1. **Use SSH keys** instead of passwords for NAS access
2. **Use Tailscale/VPN** instead of exposing ports to internet
3. **Set webhook secrets** if using GitHub webhooks
4. **Review changes** before deploying (`git log` before running script)
5. **Test locally first** before pushing to GitHub
6. **Keep backups** (script creates automatic backups)
7. **Monitor logs** after deployment

## Monitoring

Set up log rotation to prevent log files from growing too large:

```bash
# Create logrotate config
sudo tee /etc/logrotate.d/crypto-collector << EOF
/var/log/nas-deploy.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}

/var/log/webhook.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

## Summary

You now have three deployment options:

| Method | Complexity | Speed | Best For |
|--------|-----------|-------|----------|
| **Manual** | ⭐ Easy | Instant | Development, testing |
| **Cron** | ⭐⭐ Medium | Scheduled | Production, automated |
| **Webhook** | ⭐⭐⭐ Advanced | Instant | CI/CD, immediate updates |

**Quick Start:**
1. Clone repo to NAS: `sudo git clone https://github.com/smartiesss/datadownloader.git /volume1/crypto-collector`
2. Upload script: `scp nas_deploy.sh admin@nas-ip:/volume1/crypto-collector/`
3. Deploy: `sudo ./nas_deploy.sh`

That's it! Your NAS is now linked to GitHub and ready for automated deployments.
