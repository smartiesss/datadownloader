# CoinAPI $30 Credit Download - Status

**Started:** 2025-10-26 00:31 HKT
**Process ID:** 77134
**Status:** 🔄 RUNNING

---

## 📊 Download Strategy

**Phase 1: Last 7 Days (Priority)**
- Target: ALL BTC and ETH options (~2,200+ symbols)
- Granularity: 1-minute candles
- Est. cost: ~$6-10 for recent data

**Phase 2: Extended History (90 days)**
- Target: Top 100 most important options
- Fills gap from day 8 to day 90
- Uses remaining budget

---

## 💰 Budget Plan

- **Total Budget:** $30.00
- **Estimated Requests:** ~10,000 API calls
- **Cost per Request:** ~$0.003
- **Expected Coverage:**
  - Last 7 days: ALL 2,200+ options ✅
  - Last 90 days: Top 100 options ✅

---

## 📋 What You're Getting

### Data Schema Created:
**Table:** `coinapi_options_ohlcv`

**Columns:**
- Time fields: `time_period_start`, `time_period_end`, `time_open`, `time_close`
- Instrument: `symbol_id`, `currency` (BTC/ETH), `strike`, `expiry_date`, `option_type` (C/P)
- OHLCV: `price_open`, `price_high`, `price_low`, `price_close`, `volume_traded`, `trades_count`
- Metadata: `period_id` (1MIN), `downloaded_at`

### Example Data:
```json
{
    "time_period_start": "2025-10-18T17:00:00Z",
    "price_open": 0.59325,
    "price_high": 0.60525,
    "price_low": 0.57775,
    "price_close": 0.588,
    "volume_traded": 0,
    "symbol_id": "DERIBIT_OPT_BTC_USD_251031_170000_P"
}
```

---

## 🔍 Monitoring Commands

### Check if downloader is running:
```bash
ps aux | grep coinapi_smart_downloader | grep -v grep
```

### Check current progress:
```bash
tail -f logs/coinapi-download.log
```

### Check database records:
```bash
psql -U postgres -d crypto_data -c "
SELECT
    COUNT(*) as total_candles,
    COUNT(DISTINCT symbol_id) as unique_symbols,
    MIN(time_period_start) as earliest_data,
    MAX(time_period_start) as latest_data,
    pg_size_pretty(pg_total_relation_size('coinapi_options_ohlcv')) as table_size
FROM coinapi_options_ohlcv;
"
```

### Check by currency:
```bash
psql -U postgres -d crypto_data -c "
SELECT
    currency,
    COUNT(*) as candles,
    COUNT(DISTINCT symbol_id) as symbols,
    MIN(time_period_start) as earliest,
    MAX(time_period_start) as latest
FROM coinapi_options_ohlcv
GROUP BY currency;
"
```

---

## ⏱️ Expected Timeline

- **Initial symbol fetch:** 1-2 minutes (downloading 2,200+ symbol metadata)
- **Phase 1 download:** 30-60 minutes (last 7 days for all options)
- **Phase 2 download:** 20-40 minutes (extended history for top 100)
- **Total runtime:** ~1-2 hours

**Current Status:** Still in initial setup (fetching symbols)

---

## 📈 Expected Results

After completion, you should have:

**Total Candles:** ~500,000 - 1,000,000 1-minute candles
- BTC options: ~300,000 candles
- ETH options: ~400,000 candles

**Date Coverage:**
- Recent data (last 7 days): 100% coverage for all active options
- Historical data (8-90 days): Top 100 options only

**Database Size:** ~200-400 MB

---

## ✅ Quality Checks (Run After Completion)

```bash
# 1. Check data completeness
psql -U postgres -d crypto_data -c "
SELECT
    DATE(time_period_start) as date,
    COUNT(*) as candles_per_day,
    COUNT(DISTINCT symbol_id) as unique_options
FROM coinapi_options_ohlcv
GROUP BY DATE(time_period_start)
ORDER BY date DESC
LIMIT 10;
"

# 2. Check for gaps
psql -U postgres -d crypto_data -c "
SELECT
    symbol_id,
    MIN(time_period_start) as first_candle,
    MAX(time_period_start) as last_candle,
    COUNT(*) as total_candles
FROM coinapi_options_ohlcv
GROUP BY symbol_id
HAVING COUNT(*) > 100
ORDER BY COUNT(*) DESC
LIMIT 20;
"

# 3. Verify 1-minute granularity
psql -U postgres -d crypto_data -c "
SELECT
    period_id,
    COUNT(*) as count
FROM coinapi_options_ohlcv
GROUP BY period_id;
"
```

---

## 🎯 Next Steps After Download

1. **Verify Data Quality**
   - Run quality checks above
   - Spot-check a few options manually

2. **Calculate IV from OHLCV**
   - Use price data to compute implied volatility
   - Compare with your real-time IV collection

3. **Merge with Real-Time Data**
   - Your real-time collector captures new data going forward
   - CoinAPI data fills historical gap

4. **Start Backtesting!**
   - You now have 7-90 days of 1-minute options data
   - Perfect for testing your IV strategies

---

**Status:** ⏳ Download in progress...
**Check back in:** 30 minutes

---

## 💡 Tips

- **Don't stop the process** - It will automatically manage budget
- **Let it run overnight** - Safe to leave running
- **Real-time collector still works** - No conflicts, independent systems

---

**Last Updated:** 2025-10-26 00:35 HKT
