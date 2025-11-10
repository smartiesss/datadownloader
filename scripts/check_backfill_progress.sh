#!/bin/bash
# Quick script to check backfill progress

echo "================================================"
echo "BACKFILL PROGRESS CHECK"
echo "Time: $(date)"
echo "================================================"
echo ""

# Check if process is running
echo "🔍 Process Status:"
if ps aux | grep -q "[b]ackfill_missing_options"; then
    echo "   ✅ Backfill process is RUNNING"
    ps aux | grep "[b]ackfill_missing_options" | awk '{print "   PID:", $2, "| CPU:", $3"%", "| Mem:", $4"%"}'
else
    echo "   ⚠️  Backfill process is NOT running"
fi
echo ""

# Check database status
echo "📊 Database Status:"
psql -U postgres -d crypto_data -c "
SELECT
    currency,
    COUNT(*) as total_records,
    COUNT(DISTINCT symbol) as unique_options,
    pg_size_pretty(pg_total_relation_size('cryptodatadownload_options_daily')) as size
FROM cryptodatadownload_options_daily
GROUP BY currency
ORDER BY currency;" 2>/dev/null
echo ""

# Calculate missing count
echo "🎯 Missing Symbols:"
python3 -c "
import requests
import psycopg2
import os
from dotenv import load_dotenv
import sys

load_dotenv()

try:
    API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
    url = 'https://api.cryptodatadownload.com/v1/data/ohlc/deribit/options/available/'
    response = requests.get(url, headers={'Token': API_KEY}, timeout=10)
    all_options = response.json().get('result', [])

    conn = psycopg2.connect('dbname=crypto_data user=postgres')
    cursor = conn.cursor()

    for currency in ['ETH', 'BTC']:
        available = [opt for opt in all_options if opt.startswith(currency)]
        cursor.execute(f\"SELECT DISTINCT symbol FROM cryptodatadownload_options_daily WHERE currency = '{currency}'\")
        downloaded = set(row[0] for row in cursor.fetchall())
        missing = len(available) - len(downloaded)
        pct_complete = ((len(available) - missing) / len(available)) * 100

        if missing == 0:
            print(f'   ✅ {currency}: Complete! (100.0%)')
        else:
            print(f'   🔄 {currency}: {missing:,} remaining ({pct_complete:.1f}% complete)')

    conn.close()
except Exception as e:
    print(f'   ⚠️  Error checking missing count: {e}')
" 2>/dev/null
echo ""

# Show last few log lines
echo "📝 Latest Log (last 10 lines):"
if [ -f logs/full-backfill.log ]; then
    tail -10 logs/full-backfill.log | sed 's/^/   /'
else
    echo "   ⚠️  Log file not found"
fi
echo ""

echo "================================================"
echo "For live monitoring, run:"
echo "  tail -f logs/full-backfill.log"
echo "================================================"
