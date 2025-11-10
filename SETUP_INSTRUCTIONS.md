# NAS Setup Instructions - Follow These Steps

## Step 1: SSH to Your NAS

Open your terminal and connect to your NAS:

```bash
ssh admin@your-nas-ip
```

Replace `your-nas-ip` with your actual NAS IP address (or Tailscale hostname if using Tailscale).

---

## Step 2: Check Git Installation

Once connected to NAS, run:

```bash
git --version
```

**Expected result:** Should show git version (e.g., `git version 2.x.x`)

**If git is not installed:**
1. Open Synology Package Center (via web browser)
2. Search for "Git Server"
3. Click "Install"
4. Wait for installation to complete
5. Run `git --version` again to confirm

---

## Step 3: Backup Existing Crypto Collector (If Exists)

Check if you already have a crypto-collector directory:

```bash
ls -la /volume1/crypto-collector
```

**If directory exists, back it up:**

```bash
sudo mv /volume1/crypto-collector /volume1/crypto-collector-backup-$(date +%Y%m%d-%H%M%S)
```

**If directory doesn't exist, skip this step.**

---

## Step 4: Clone Repository from GitHub

```bash
cd /volume1
sudo git clone https://github.com/smartiesss/datadownloader.git crypto-collector
```

**Expected output:**
```
Cloning into 'crypto-collector'...
remote: Enumerating objects: 150, done.
remote: Counting objects: 100% (150/150), done.
remote: Compressing objects: 100% (100/100), done.
remote: Total 150 (delta 50), reused 140 (delta 45), pack-reused 0
Receiving objects: 100% (150/150), 100.00 KiB | 1.00 MiB/s, done.
Resolving deltas: 100% (50/50), done.
```

---

## Step 5: Verify Repository and Make Scripts Executable

```bash
cd /volume1/crypto-collector
ls -la
```

**Expected:** You should see files like `nas_deploy.sh`, `quick_setup_nas.sh`, `scripts/`, etc.

**Make deployment scripts executable:**

```bash
sudo chmod +x nas_deploy.sh
sudo chmod +x quick_setup_nas.sh
```

---

## Step 6: Verify Current Container Status

Check if your containers are running:

```bash
sudo docker ps | grep -E 'eth-collector|perp-collector|timescaledb'
```

**Expected:** Should show 3 running containers:
- eth-collector
- perp-collector
- eth-timescaledb

**Note the container names** - they should match what's in the deployment script.

---

## Step 7: Test Manual Deployment (DRY RUN)

Let's verify the git setup is working:

```bash
# Check current commit
git log -1 --oneline

# Check if we can pull (should say already up to date)
sudo git pull origin main
```

**Expected:** Should show "Already up to date" since we just cloned.

---

## Step 8: Run First Deployment

This will test the deployment script but won't actually update anything (since we just cloned):

```bash
cd /volume1/crypto-collector
sudo ./nas_deploy.sh
```

**Expected output:**
- Repository check: ✓
- No local changes: ✓
- Already up to date (no code changes)
- **Should skip container restart** (since no updates)

**If it works:** Great! The deployment system is ready.

**If there are errors:** Copy the error message and send it to me.

---

## Step 9: Set Up Automatic Updates (Cron Job)

Now let's set up automatic updates every 6 hours:

```bash
# Edit crontab
sudo crontab -e
```

**This will open a text editor. Add this line at the bottom:**

```
0 */6 * * * cd /volume1/crypto-collector && ./nas_deploy.sh >> /var/log/nas-deploy.log 2>&1
```

**How to save:**
- If using `vi` editor: Press `Esc`, then type `:wq` and press Enter
- If using `nano` editor: Press `Ctrl+X`, then `Y`, then Enter

**Verify cron job was added:**

```bash
sudo crontab -l | grep nas_deploy
```

**Expected:** Should show the cron job you just added.

---

## Step 10: Create Log File and Test

```bash
# Create log directory if needed
sudo mkdir -p /var/log

# Test that logging works
echo "Test log entry" | sudo tee -a /var/log/nas-deploy.log

# View the log
sudo tail /var/log/nas-deploy.log
```

---

## Step 11: Verify Setup is Complete

Run these verification commands:

```bash
echo "=== VERIFICATION CHECKLIST ==="
echo ""

# 1. Git repository
echo "1. Git Repository:"
[ -d "/volume1/crypto-collector/.git" ] && echo "   ✓ Git repo exists" || echo "   ✗ Git repo missing"

# 2. Deployment script
echo "2. Deployment Script:"
[ -x "/volume1/crypto-collector/nas_deploy.sh" ] && echo "   ✓ nas_deploy.sh is executable" || echo "   ✗ nas_deploy.sh not executable"

# 3. Cron job
echo "3. Cron Job:"
sudo crontab -l | grep -q "nas_deploy.sh" && echo "   ✓ Cron job configured" || echo "   ✗ Cron job missing"

# 4. Containers
echo "4. Docker Containers:"
sudo docker ps | grep -q "eth-collector" && echo "   ✓ eth-collector running" || echo "   ✗ eth-collector not running"
sudo docker ps | grep -q "perp-collector" && echo "   ✓ perp-collector running" || echo "   ✗ perp-collector not running"

# 5. Git remote
echo "5. Git Remote:"
cd /volume1/crypto-collector && git remote -v | grep -q "smartiesss/datadownloader" && echo "   ✓ Correct GitHub repository" || echo "   ✗ Wrong repository"

echo ""
echo "=== SETUP COMPLETE ==="
```

**All items should show ✓**

---

## Step 12: Test the Full Workflow

Now let's test the complete workflow:

1. **I'll make a small change and push to GitHub** (from local machine)
2. **You'll run the deployment script** (on NAS)
3. **We'll verify the update works**

**On your NAS, run:**

```bash
# Show current commit
cd /volume1/crypto-collector
git log -1 --oneline

# Tell me this commit hash and I'll push an update
```

---

## What Happens Next?

After setup:

1. **You make code changes locally** → commit → push to GitHub
2. **Every 6 hours, your NAS automatically:**
   - Checks GitHub for updates
   - Pulls new code if available
   - Backs up current code
   - Restarts containers with new code
   - Logs everything to `/var/log/nas-deploy.log`

3. **Or manually trigger deployment anytime:**
   ```bash
   ssh admin@your-nas-ip
   cd /volume1/crypto-collector
   sudo ./nas_deploy.sh
   ```

---

## Monitoring

**View deployment logs:**
```bash
sudo tail -f /var/log/nas-deploy.log
```

**View collector logs:**
```bash
sudo docker logs -f eth-collector
```

**Check when last deployment ran:**
```bash
sudo tail -20 /var/log/nas-deploy.log | grep "Deployment Complete"
```

---

## Troubleshooting

**"Permission denied" error:**
```bash
sudo chown -R admin:users /volume1/crypto-collector
sudo chmod +x /volume1/crypto-collector/*.sh
```

**Cron job not running:**
```bash
# Check cron service status (Synology)
sudo synoservice --status crond

# Restart cron if needed
sudo synoservice --restart crond
```

**Container won't start:**
```bash
# View full container logs
sudo docker logs eth-collector

# Check container status
sudo docker ps -a | grep eth-collector
```

---

## Summary Checklist

- [ ] SSH to NAS successful
- [ ] Git installed and working
- [ ] Repository cloned to `/volume1/crypto-collector`
- [ ] Deployment scripts are executable
- [ ] Test deployment ran successfully
- [ ] Cron job configured (every 6 hours)
- [ ] Verification checklist shows all ✓
- [ ] Containers are running

Once all items are checked, your NAS is fully automated!

---

## Quick Reference

```bash
# Manual deployment
ssh admin@nas-ip
cd /volume1/crypto-collector && sudo ./nas_deploy.sh

# View logs
sudo tail -f /var/log/nas-deploy.log

# Check container status
sudo docker ps | grep -E 'eth|perp'

# Rollback if needed
sudo cp -r /volume1/crypto-collector-backup-YYYYMMDD-HHMMSS/scripts/* /volume1/crypto-collector/scripts/
sudo docker restart eth-collector perp-collector
```
