#!/bin/bash
# Setup Persistent Collector for macOS
# This creates a LaunchAgent that runs the collector 24/7 and auto-restarts on reboot

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="$HOME/Library/LaunchAgents/com.crypto.eth-options-collector.plist"
LOG_DIR="$SCRIPT_DIR/logs"

echo "========================================="
echo "ETH Options Collector - Persistent Setup"
echo "========================================="
echo ""

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Create LaunchAgent plist
cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crypto.eth-options-collector</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>-m</string>
        <string>scripts.ws_tick_collector</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd_stderr.log</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>60</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created LaunchAgent plist: $PLIST_FILE"
echo ""

# Load the LaunchAgent
echo "Loading LaunchAgent..."
launchctl unload "$PLIST_FILE" 2>/dev/null || true  # Unload if already loaded
launchctl load "$PLIST_FILE"

echo "✅ LaunchAgent loaded successfully"
echo ""

# Wait a moment for it to start
sleep 3

# Check if it's running
echo "Checking collector status..."
if pgrep -f "python.*ws_tick_collector" > /dev/null; then
    echo "✅ Collector is running!"
    echo ""
    echo "Process details:"
    ps aux | grep -E "python.*ws_tick_collector" | grep -v grep
else
    echo "❌ Collector failed to start. Check logs:"
    echo "   tail -f $LOG_DIR/launchd_stderr.log"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "The collector will now run persistently:"
echo "  - Starts automatically on login/reboot"
echo "  - Auto-restarts if it crashes"
echo "  - Survives terminal closure"
echo ""
echo "Management Commands:"
echo "  - View logs:     tail -f $LOG_DIR/ws_tick_collector.log"
echo "  - Check status:  launchctl list | grep crypto"
echo "  - Stop:          launchctl unload $PLIST_FILE"
echo "  - Start:         launchctl load $PLIST_FILE"
echo "  - Restart:       launchctl unload $PLIST_FILE && launchctl load $PLIST_FILE"
echo ""
echo "Database status:"
psql -h localhost -U postgres -d crypto_data -c "
  SELECT
    'quotes' as type,
    COUNT(*) as records,
    MAX(timestamp) as latest
  FROM eth_option_quotes
  UNION ALL
  SELECT 'depth', COUNT(*), MAX(timestamp) FROM eth_option_orderbook_depth;
" 2>/dev/null || echo "  (Run 'psql -h localhost -U postgres -d crypto_data' to check)"
echo ""
