# CryptoDataDownload Backfill Plan - Rate Limit Recovery

**Date:** 2025-10-26
**Issue:** Rate limiting (HTTP 429) caused massive data gaps
**Status:** 🔴 **CRITICAL - Need to backfill**

---

## 🚨 Problem Summary

### What Happened
Both ETH and BTC downloads hit **CryptoDataDownload API rate limits** (HTTP 429 errors), causing the downloader to skip thousands of options.

### Impact
| Currency | Available | Downloaded | Missing | % Missing |
|----------|-----------|------------|---------|-----------|
| **ETH** | 8,679 | 1,941 | **6,738** | **77.6%** |
| **BTC** | 8,850 | 660 | **8,190** | **92.5%** |
| **TOTAL** | 17,529 | 2,601 | **14,928** | **85.2%** |

### Rate Limit Details
- **ETH:** Hit rate limit at symbol #429, got 5,831 total 429 errors
- **BTC:** Hit rate limit at symbol #787
- **Throttle message:** "Request was throttled. Expected available in ~2800 seconds (~47 minutes)"

---

## 📋 Root Cause Analysis

### Why This Happened

1. **API Rate Limit:** CryptoDataDownload has undocumented rate limits
   - Appears to be ~400-800 requests total (not per second)
   - Requires ~30-60 minute cooldown period

2. **Our Approach:** Downloaded too fast
   - Used 200ms delay (5 req/sec)
   - But API limit seems to be TOTAL requests, not per-second

3. **Script Behavior:** Original script ignored 429 errors
   - Continued downloading despite rate limits
   - Marked symbols as "no data" when actually throttled

---

## ✅ Solution: Smart Backfill Script

### New Script Created
`scripts/backfill_missing_options.py`

### Key Features

1. **Identifies Missing Symbols**
   - Compares API's available options vs database
   - Only downloads what's missing

2. **Intelligent Rate Limit Handling**
   - Detects HTTP 429 responses
   - Parses "Expected available in X seconds"
   - Automatically waits for cooldown + 5 second buffer
   - Resumes automatically

3. **Slower Default Rate**
   - 1 second delay between requests (not 200ms)
   - Reduces chance of hitting limits again

4. **Resume Capability**
   - Uses database to track progress
   - Can stop/start without losing progress

---

## 🎯 Backfill Strategy

### Recommended Approach

#### Phase 1: ETH Backfill (Tonight)
```bash
# Run ETH backfill
chmod +x scripts/backfill_missing_options.py
python3 scripts/backfill_missing_options.py ETH > logs/eth-backfill.log 2>&1 &
```

**Estimated time:** ~112 minutes (6,738 symbols × 1 sec)
**Expected rate limits:** 8-10 cooldown periods
**Total time with cooldowns:** ~4-6 hours

#### Phase 2: BTC Backfill (Tomorrow)
```bash
# Run BTC backfill after ETH completes
python3 scripts/backfill_missing_options.py BTC > logs/btc-backfill.log 2>&1 &
```

**Estimated time:** ~137 minutes (8,190 symbols × 1 sec)
**Expected rate limits:** 10-12 cooldown periods
**Total time with cooldowns:** ~5-8 hours

---

## 📊 Expected Results After Backfill

### ETH (After backfill)
- **Before:** 1,941 symbols, 26,078 records
- **After:** 8,679 symbols (~4.5x more), ~100,000-120,000 records (~4x more)

### BTC (After backfill)
- **Before:** 660 symbols, 3,095 records
- **After:** 8,850 symbols (~13x more), ~100,000-120,000 records (~30x more)

### Combined Dataset
- **Total Options:** ~17,500 (both BTC and ETH)
- **Total Records:** ~200,000-250,000 daily candles
- **Database Size:** ~50-70 MB (from current 6 MB)

---

## 🔍 Monitoring Backfill Progress

### Check Progress (While Running)
```bash
# Watch database growth in real-time
watch -n 30 'psql -U postgres -d crypto_data -c "
SELECT
    currency,
    COUNT(*) as total_records,
    COUNT(DISTINCT symbol) as unique_options,
    pg_size_pretty(pg_total_relation_size(\"cryptodatadownload_options_daily\")) as size
FROM cryptodatadownload_options_daily
GROUP BY currency
ORDER BY currency;"'
```

### Check Logs
```bash
# ETH backfill log
tail -f logs/eth-backfill.log

# BTC backfill log
tail -f logs/btc-backfill.log

# Count rate limit hits
grep -c "Rate limit hit" logs/eth-backfill.log
```

### Check Remaining
```bash
# How many symbols left to backfill?
python3 -c "
import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
url = 'https://api.cryptodatadownload.com/v1/data/ohlc/deribit/options/available/'
response = requests.get(url, headers={'Token': API_KEY})
all_options = response.json().get('result', [])

conn = psycopg2.connect('dbname=crypto_data user=postgres')
cursor = conn.cursor()

for currency in ['ETH', 'BTC']:
    available = [opt for opt in all_options if opt.startswith(currency)]
    cursor.execute(f\"SELECT DISTINCT symbol FROM cryptodatadownload_options_daily WHERE currency = '{currency}'\")
    downloaded = set(row[0] for row in cursor.fetchall())
    missing = len(available) - len(downloaded)
    print(f'{currency}: {missing} remaining')
"
```

---

## ⚠️ Important Notes

### Rate Limiting
- **Expect 8-12 rate limit hits** during backfill
- Each hit = ~30-60 minute wait
- Script will handle this automatically
- **Do not kill the script** when it says "Sleeping until rate limit resets"

### API Costs
- Flat $49.99/month - unlimited requests
- But rate-limited to ~400-800 requests per cooldown period
- Total backfill = ~15,000 requests across multiple cooldown periods

### Database
- Backfill uses `ON CONFLICT DO NOTHING`
- Safe to run multiple times
- Won't create duplicates

### Overnight Run
- **Recommended:** Start backfill before bed
- Let it run overnight with rate limit handling
- Check results in the morning

---

## 🚀 How to Run Backfill

### Option 1: Run Now (ETH only)
```bash
cd /Users/doghead/PycharmProjects/datadownloader
chmod +x scripts/backfill_missing_options.py
nohup python3 scripts/backfill_missing_options.py ETH > logs/eth-backfill.log 2>&1 &

# Check progress
tail -f logs/eth-backfill.log
```

### Option 2: Run Both (Sequentially)
```bash
# Create a script to run both
cat > run_full_backfill.sh <<'EOF'
#!/bin/bash
echo "Starting ETH backfill..."
python3 scripts/backfill_missing_options.py ETH
echo "ETH backfill complete! Starting BTC backfill..."
python3 scripts/backfill_missing_options.py BTC
echo "All backfills complete!"
EOF

chmod +x run_full_backfill.sh
nohup ./run_full_backfill.sh > logs/full-backfill.log 2>&1 &
```

### Option 3: Delayed Start (Wait for rate limit to reset)
```bash
# Wait 1 hour, then start
echo "python3 scripts/backfill_missing_options.py ETH" | at now + 1 hour
```

---

## 📈 Success Criteria

Backfill is successful when:
- ✅ ETH missing count = 0
- ✅ BTC missing count = 0
- ✅ Total records > 200,000
- ✅ No errors in final log summary

---

## 🛠️ Troubleshooting

### If Backfill Fails
1. Check log files for errors
2. Verify API key is valid
3. Check database connection
4. Manually run check for missing symbols

### If Progress Stalls
- Script is likely waiting for rate limit cooldown
- Check log for "Sleeping until rate limit resets"
- **DO NOT KILL** - let it wait

### If You Need to Stop/Restart
- Script is safe to stop (Ctrl+C)
- Uses database to track progress
- Re-running will skip already downloaded symbols

---

## 📝 Next Steps

### Immediate (Now)
1. Review this plan
2. Decide on timing (now vs overnight)
3. Start ETH backfill

### After ETH Completes (~4-6 hours)
1. Verify ETH data quality
2. Check missing count = 0
3. Start BTC backfill

### After BTC Completes (~5-8 hours)
1. Verify BTC data quality
2. Generate comprehensive data report
3. Begin backtesting with complete dataset

---

**Summary:** Due to rate limiting, 85% of available options data is missing. The new backfill script intelligently handles rate limits and will recover all missing data over the next 8-14 hours.

**Recommendation:** Start ETH backfill now or before bed, let it run overnight with automatic rate limit handling.
