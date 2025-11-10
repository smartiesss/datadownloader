#!/bin/bash
#
# Real-Time Data Collector Launcher
# This script starts the real-time collector with proper logging and monitoring
#
# Usage:
#   ./start_realtime_collector.sh        # Start collector
#   ./start_realtime_collector.sh stop   # Stop collector
#   ./start_realtime_collector.sh status # Check status
#   ./start_realtime_collector.sh restart# Restart collector

PROJECT_DIR="/Users/doghead/PycharmProjects/datadownloader"
PID_FILE="$PROJECT_DIR/.realtime_collector.pid"
LOG_FILE="$PROJECT_DIR/logs/realtime-collector.log"
PYTHON="/usr/local/bin/python3"

cd "$PROJECT_DIR" || exit 1

case "${1:-start}" in
    start)
        # Check if already running
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "✅ Collector already running (PID: $PID)"
                echo "   Use './start_realtime_collector.sh status' to check details"
                exit 0
            else
                echo "⚠️  Stale PID file found, removing..."
                rm "$PID_FILE"
            fi
        fi

        echo "🚀 Starting real-time data collector..."
        echo "   Log: $LOG_FILE"

        # Start collector in background
        nohup "$PYTHON" -m scripts.collect_realtime >> "$LOG_FILE" 2>&1 &
        NEW_PID=$!

        # Save PID
        echo "$NEW_PID" > "$PID_FILE"

        # Wait a moment to check if it started successfully
        sleep 2

        if ps -p "$NEW_PID" > /dev/null 2>&1; then
            echo "✅ Collector started successfully!"
            echo "   PID: $NEW_PID"
            echo ""
            echo "📊 Monitoring commands:"
            echo "   Status:  ./start_realtime_collector.sh status"
            echo "   Logs:    tail -f $LOG_FILE"
            echo "   Stop:    ./start_realtime_collector.sh stop"
        else
            echo "❌ Failed to start collector"
            echo "   Check logs: tail -50 $LOG_FILE"
            rm "$PID_FILE"
            exit 1
        fi
        ;;

    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo "⚠️  No PID file found. Checking for running processes..."
            PIDS=$(ps aux | grep '[c]ollect_realtime' | awk '{print $2}')
            if [ -z "$PIDS" ]; then
                echo "✅ No collector processes found"
                exit 0
            else
                echo "Found running collectors: $PIDS"
                echo "Stopping them..."
                pkill -f collect_realtime
                sleep 2
                echo "✅ Collectors stopped"
                exit 0
            fi
        fi

        PID=$(cat "$PID_FILE")
        echo "🛑 Stopping collector (PID: $PID)..."

        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID"
            sleep 2

            # Check if still running
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "⚠️  Process didn't stop gracefully, forcing..."
                kill -9 "$PID"
                sleep 1
            fi

            echo "✅ Collector stopped"
        else
            echo "⚠️  Process not running (PID: $PID)"
        fi

        rm "$PID_FILE"
        ;;

    status)
        echo "📊 Real-Time Collector Status"
        echo "================================"
        echo ""

        # Check PID file
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                UPTIME=$(ps -o etime= -p "$PID" | tr -d ' ')
                CPU=$(ps -o %cpu= -p "$PID" | tr -d ' ')
                MEM=$(ps -o %mem= -p "$PID" | tr -d ' ')

                echo "✅ Status: RUNNING"
                echo "   PID: $PID"
                echo "   Uptime: $UPTIME"
                echo "   CPU: $CPU%"
                echo "   Memory: $MEM%"
            else
                echo "❌ Status: STOPPED (stale PID file)"
                rm "$PID_FILE"
            fi
        else
            echo "❌ Status: STOPPED (no PID file)"
        fi

        echo ""
        echo "📁 Log File: $LOG_FILE"
        if [ -f "$LOG_FILE" ]; then
            LOG_SIZE=$(ls -lh "$LOG_FILE" | awk '{print $5}')
            LAST_ENTRY=$(tail -1 "$LOG_FILE" 2>/dev/null | cut -d' ' -f1-2)
            echo "   Size: $LOG_SIZE"
            echo "   Last entry: $LAST_ENTRY"
        else
            echo "   ⚠️  Log file not found"
        fi

        echo ""
        echo "🗄️  Database Status:"

        # Check data freshness
        FRESH_CHECK=$("$PYTHON" -c "
import psycopg2
from datetime import datetime, timezone

try:
    conn = psycopg2.connect('dbname=crypto_data user=postgres')
    cur = conn.cursor()

    cur.execute(\"\"\"
        SELECT instrument, MAX(timestamp) as latest
        FROM perpetuals_ohlcv
        GROUP BY instrument
        ORDER BY instrument
    \"\"\")

    print('   Perpetuals:')
    for row in cur.fetchall():
        now = datetime.now(timezone.utc)
        lag = (now - row[1].replace(tzinfo=timezone.utc)).total_seconds() / 60
        status = '✅' if lag < 15 else '⚠️'
        print(f'     {status} {row[0]}: {lag:.1f} min lag')

    conn.close()
except Exception as e:
    print(f'   ❌ Error: {e}')
" 2>/dev/null)

        if [ -n "$FRESH_CHECK" ]; then
            echo "$FRESH_CHECK"
        else
            echo "   ⚠️  Unable to check database"
        fi

        echo ""
        echo "📝 Recent Log Entries:"
        if [ -f "$LOG_FILE" ]; then
            tail -5 "$LOG_FILE" | sed 's/^/   /'
        fi
        ;;

    restart)
        echo "🔄 Restarting collector..."
        "$0" stop
        sleep 2
        "$0" start
        ;;

    *)
        echo "Usage: $0 {start|stop|status|restart}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the real-time collector"
        echo "  stop    - Stop the real-time collector"
        echo "  status  - Show collector status and health"
        echo "  restart - Restart the collector"
        exit 1
        ;;
esac
