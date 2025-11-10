#!/bin/bash
#
# Quick Health Check for Real-Time Collector
# Run this anytime to verify the collector is working properly
#
# Usage:
#   ./check_collector_health.sh

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 REAL-TIME COLLECTOR HEALTH CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Process Status
echo "1️⃣  PROCESS STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./start_realtime_collector.sh status
echo ""

# 2. Data Freshness
echo "2️⃣  DATA FRESHNESS (Last 5 minutes)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -U postgres -d crypto_data -t -c "
SELECT
    '   New Records: ' || COUNT(*) || ' options in last 5 min' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes';
"

psql -U postgres -d crypto_data -t -c "
SELECT
    '   Latest Data: ' || TO_CHAR(MAX(timestamp) AT TIME ZONE 'Asia/Hong_Kong', 'YYYY-MM-DD HH24:MI:SS') || ' HKT' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '10 minutes';
"

psql -U postgres -d crypto_data -t -c "
SELECT
    '   Data Lag: ' || ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60, 1) || ' minutes' AS status
FROM options_ohlcv;
"
echo ""

# 3. Bid/Ask/IV Coverage
echo "3️⃣  BID/ASK/IV DATA QUALITY (Last 5 minutes)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -U postgres -d crypto_data -t -c "
SELECT
    '   Mark IV Coverage: ' ||
    ROUND(100.0 * COUNT(CASE WHEN mark_iv > 0 THEN 1 END) / NULLIF(COUNT(*), 0), 1) || '%' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes';
"

psql -U postgres -d crypto_data -t -c "
SELECT
    '   Bid Price Coverage: ' ||
    ROUND(100.0 * COUNT(CASE WHEN best_bid_price > 0 THEN 1 END) / NULLIF(COUNT(*), 0), 1) || '%' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes';
"

psql -U postgres -d crypto_data -t -c "
SELECT
    '   Ask Price Coverage: ' ||
    ROUND(100.0 * COUNT(CASE WHEN best_ask_price > 0 THEN 1 END) / NULLIF(COUNT(*), 0), 1) || '%' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes';
"

psql -U postgres -d crypto_data -t -c "
SELECT
    '   Average IV: ' || ROUND(AVG(mark_iv), 2) || '%' AS status
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes' AND mark_iv > 0;
"
echo ""

# 4. Sample Recent Data
echo "4️⃣  RECENT DATA SAMPLE (Last 5 records with IV)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -U postgres -d crypto_data -c "
SELECT
    TO_CHAR(timestamp AT TIME ZONE 'Asia/Hong_Kong', 'HH24:MI:SS') AS time,
    instrument,
    ROUND(best_bid_price::numeric, 4) AS bid,
    ROUND(best_ask_price::numeric, 4) AS ask,
    ROUND(mark_iv::numeric, 1) AS \"IV%\"
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes'
  AND mark_iv > 0
ORDER BY timestamp DESC
LIMIT 5;
"
echo ""

# 5. Collection Rate
echo "5️⃣  COLLECTION RATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -U postgres -d crypto_data -c "
SELECT
    DATE_TRUNC('hour', timestamp) AT TIME ZONE 'Asia/Hong_Kong' AS \"Hour (HKT)\",
    COUNT(*) AS \"Records\",
    COUNT(DISTINCT instrument) AS \"Instruments\",
    COUNT(CASE WHEN mark_iv > 0 THEN 1 END) AS \"With IV\"
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '3 hours'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY \"Hour (HKT)\" DESC
LIMIT 3;
"
echo ""

# 6. Health Summary
echo "6️⃣  HEALTH SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if data is fresh (< 2 minutes old)
FRESHNESS=$(psql -U postgres -d crypto_data -t -A -c "
SELECT EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60
FROM options_ohlcv;
")

# Check IV coverage
IV_COVERAGE=$(psql -U postgres -d crypto_data -t -A -c "
SELECT ROUND(100.0 * COUNT(CASE WHEN mark_iv > 0 THEN 1 END) / NULLIF(COUNT(*), 0), 1)
FROM options_ohlcv
WHERE timestamp > NOW() - INTERVAL '5 minutes';
")

# Check if process is running
if ps -p $(cat .realtime_collector.pid 2>/dev/null) > /dev/null 2>&1; then
    PROCESS_STATUS="✅ RUNNING"
else
    PROCESS_STATUS="❌ STOPPED"
fi

echo "   Process: $PROCESS_STATUS"

if (( $(echo "$FRESHNESS < 2" | bc -l) )); then
    echo "   Data Freshness: ✅ EXCELLENT ($FRESHNESS min old)"
elif (( $(echo "$FRESHNESS < 10" | bc -l) )); then
    echo "   Data Freshness: ⚠️  ACCEPTABLE ($FRESHNESS min old)"
else
    echo "   Data Freshness: ❌ STALE ($FRESHNESS min old)"
fi

if (( $(echo "$IV_COVERAGE > 90" | bc -l) )); then
    echo "   IV Coverage: ✅ EXCELLENT ($IV_COVERAGE%)"
elif (( $(echo "$IV_COVERAGE > 70" | bc -l) )); then
    echo "   IV Coverage: ⚠️  ACCEPTABLE ($IV_COVERAGE%)"
else
    echo "   IV Coverage: ❌ LOW ($IV_COVERAGE%)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Health check complete!"
echo ""
echo "Quick commands:"
echo "  View logs:    tail -f logs/realtime-collector.log"
echo "  Stop:         ./start_realtime_collector.sh stop"
echo "  Start:        ./start_realtime_collector.sh start"
echo "  Restart:      ./start_realtime_collector.sh restart"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
