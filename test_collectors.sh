#!/bin/bash
# Quick test script for collectors

echo "=========================================="
echo "COMPREHENSIVE DATA COLLECTORS - LOCAL TEST"
echo "=========================================="
echo ""

DATABASE_URL="postgresql://postgres@localhost:5432/crypto_data"

# Test 1: BTC WebSocket Collector (3 minutes)
echo "Test 1: BTC WebSocket Collector (3 minutes)"
echo "--------------------------------------------"
export CURRENCY=BTC
export TOP_N_INSTRUMENTS=10
export DATABASE_URL="$DATABASE_URL"
export LOG_LEVEL=INFO

timeout 180 python -m scripts.ws_tick_collector_multi &
BTC_PID=$!

echo "✅ BTC collector started (PID: $BTC_PID)"
echo "⏳ Waiting 3 minutes..."
sleep 180

echo ""
echo "Checking BTC data..."
psql -U postgres -d crypto_data -c "SELECT COUNT(*) as btc_quotes FROM btc_option_quotes;"

echo ""
echo "=========================================="
echo "Test complete! Check DEPLOYMENT_GUIDE.md for full testing instructions"
echo "=========================================="
