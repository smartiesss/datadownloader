# Local Testing Instructions

## Your Setup is Ready!

✅ PostgreSQL running on localhost:5432
✅ Database: crypto_data
✅ All 13 tables created:
- btc_option_quotes, btc_option_trades, btc_option_orderbook_depth
- eth_option_quotes, eth_option_trades, eth_option_orderbook_depth
- perpetuals_ohlcv, futures_ohlcv, options_ohlcv
- options_greeks, funding_rates
- collector_status, data_gaps

## Quick Test - BTC WebSocket Collector (Manual - Recommended)

Open a new terminal and run:

```bash
cd /Users/doghead/PycharmProjects/datadownloader

# Set environment variables
export CURRENCY=BTC
export TOP_N_INSTRUMENTS=10
export DATABASE_URL="postgresql://postgres@localhost:5432/crypto_data"
export LOG_LEVEL=INFO

# Run for 3 minutes
timeout 180 python -m scripts.ws_tick_collector_multi
```

You should see:
- "Fetching top 10 BTC options..."
- "WebSocket connected successfully"
- "Successfully subscribed to 20 channels"
- Stats every 60 seconds showing quotes/trades collected

After 3 minutes, check results:
```bash
psql -U postgres -d crypto_data -c "
SELECT COUNT(*) as btc_quotes FROM btc_option_quotes;
"
```

Expected: 50-200 quotes

## Full Testing Guide

See `DEPLOYMENT_GUIDE.md` for comprehensive testing instructions including:
- ETH WebSocket collector
- REST API collector (OHLCV + Greeks)
- Funding rates collector
- Docker Compose full stack test

## Next Steps

1. ✅ Test BTC collector above (3 min)
2. 📖 Read DEPLOYMENT_GUIDE.md
3. 🚀 Deploy to your NAS following Part 2

Everything is ready to go!
