# Remaining Backfill Execution Plan
**Date:** 2025-10-23 00:50 HKT
**Owner:** PM Orchestrator
**Status:** 🔄 ACTIVE EXECUTION

---

## Executive Summary

**Current State:**
- ✅ Phase 0: Prerequisites COMPLETE
- ✅ Phase 1: Perpetuals COMPLETE (7.25M rows, real-time)
- ✅ Phase 1.5: Options COMPLETE (2.86M rows, real-time)
- ✅ Phase 4: Real-Time Collection OPERATIONAL (2 processes, 24h uptime)

**Remaining Work:**
- ⏳ Phase 2: Futures Historical Backfill (2019-2025)
- ⏳ Phase 3: Funding Rates + Index Prices Backfill

**Total Estimated Time:** 7.5 hours (2h dev + 5.5h runtime)

---

## Phase 2: Futures Historical Backfill

### Overview

**Goal:** Backfill all historical futures OHLCV data (2019-2025) to complement the real-time collection that's already running.

**Current State:**
- Real-time collection: ✅ Running (last 24 hours data)
- Historical data: ⏳ Missing (2019-2025)
- Estimated gap: ~1,991 instruments × 6 years × 525,600 min/year = ~6.3 billion candles

### Tasks

#### T-009: Fetch Historical Futures Instrument List
**Owner:** ENG
**Effort:** 30 minutes
**Status:** Ready

**Objective:** Get list of ALL historical futures (including expired) from Deribit.

**Implementation:**
```python
# Script: scripts/fetch_futures_history.py
import aiohttp
import asyncio
from datetime import datetime, timedelta

async def fetch_historical_futures():
    """
    Fetch all futures instruments (active + expired)
    Note: Deribit may only provide active instruments via API
    Workaround: Generate list based on known expiry schedule
    """
    base_url = "https://www.deribit.com/api/v2/public/get_instruments"

    # Fetch active futures
    params = {"currency": "BTC", "kind": "future"}
    async with aiohttp.ClientSession() as session:
        async with session.get(base_url, params=params) as resp:
            data = await resp.json()
            active_futures = [i['instrument_name'] for i in data['result']]

    # Generate historical futures list
    # BTC/ETH futures expire: last Friday of each month
    # Start: 2019-06-28 (BTC), 2020-01-31 (ETH)
    historical_futures = generate_historical_futures_list(
        start_date="2019-06-01",
        end_date="2025-10-31",
        currencies=["BTC", "ETH"]
    )

    return active_futures + historical_futures

def generate_historical_futures_list(start_date, end_date, currencies):
    """Generate futures instrument names based on expiry schedule"""
    futures = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        # Last Friday of each month
        last_day = (current.replace(day=28) + timedelta(days=4))
        last_day = last_day.replace(day=1) - timedelta(days=1)

        # Find last Friday
        while last_day.weekday() != 4:  # 4 = Friday
            last_day -= timedelta(days=1)

        for currency in currencies:
            # Format: BTC-27DEC24, ETH-25OCT24
            instrument = f"{currency}-{last_day.strftime('%d%b%y').upper()}"
            futures.append(instrument)

        # Next month
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

    return futures
```

**Deliverables:**
- List of ~150 historical futures instruments (BTC + ETH)
- Saved to: `/data/historical_futures_list.json`

**Acceptance Criteria:**
- AC-007a: List contains all monthly expiries from 2019-06-28 to 2025-10-31

---

#### T-010: Implement backfill_futures.py Script
**Owner:** ENG
**Effort:** 2 hours
**Status:** Ready
**Dependencies:** T-009

**Objective:** Create script to backfill historical futures OHLCV similar to perpetuals script.

**Key Features:**
1. Read futures instrument list from T-009
2. For each instrument, fetch OHLCV from creation date to expiry date
3. Handle expired instruments (may return 404)
4. Batch insert into `futures_ohlcv` table
5. Progress tracking (console + log file)

**Implementation Template:**
```python
# scripts/backfill_futures.py
import asyncio
import aiohttp
import argparse
import logging
from datetime import datetime
from db import get_db_connection

class FuturesBackfiller:
    BASE_URL = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
    MAX_CANDLES_PER_CALL = 5000
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec

    async def backfill_instrument(self, instrument: str, start: str, end: str):
        """Backfill single futures instrument"""
        start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
        end_ts = int(datetime.strptime(end, "%Y-%m-%d").timestamp())

        total_candles = 0

        async with aiohttp.ClientSession() as session:
            current_ts = start_ts

            while current_ts < end_ts:
                # Fetch chunk (5000 candles max)
                chunk_end = min(current_ts + (self.MAX_CANDLES_PER_CALL * 60), end_ts)

                try:
                    candles = await self.fetch_ohlcv_chunk(
                        session, instrument, current_ts, chunk_end
                    )

                    if candles:
                        self.upsert_to_db(instrument, candles)
                        total_candles += len(candles)

                        if total_candles % 10000 == 0:
                            logging.info(f"{instrument}: {total_candles:,} candles backfilled")

                    current_ts = chunk_end
                    await asyncio.sleep(self.RATE_LIMIT_DELAY)

                except Exception as e:
                    logging.error(f"{instrument}: Error at {current_ts}: {e}")
                    await asyncio.sleep(1)  # Backoff on error
                    continue

        logging.info(f"{instrument}: COMPLETE - {total_candles:,} candles total")
        return total_candles

    async def fetch_ohlcv_chunk(self, session, instrument, start_ts, end_ts):
        """Fetch single OHLCV chunk from Deribit"""
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts * 1000,
            "end_timestamp": end_ts * 1000,
            "resolution": 1  # 1 minute
        }

        async with session.get(self.BASE_URL, params=params) as resp:
            if resp.status == 404:
                # Instrument doesn't exist (expired, no data)
                return []

            data = await resp.json()

            if 'result' not in data or data['result']['status'] != 'ok':
                raise Exception(f"API error: {data}")

            result = data['result']
            candles = []

            for i in range(len(result['ticks'])):
                candles.append({
                    'timestamp': datetime.fromtimestamp(result['ticks'][i] / 1000),
                    'open': result['open'][i],
                    'high': result['high'][i],
                    'low': result['low'][i],
                    'close': result['close'][i],
                    'volume': result['volume'][i]
                })

            return candles

    def upsert_to_db(self, instrument: str, candles: list):
        """Insert candles into database (idempotent)"""
        conn = get_db_connection()
        cur = conn.cursor()

        # Extract expiry date from instrument name (e.g., BTC-27DEC24)
        expiry_str = instrument.split('-')[1]
        expiry_date = datetime.strptime(expiry_str, "%d%b%y").date()

        query = """
        INSERT INTO futures_ohlcv
        (timestamp, instrument, expiry_date, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, instrument) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """

        rows = [
            (c['timestamp'], instrument, expiry_date,
             c['open'], c['high'], c['low'], c['close'], c['volume'])
            for c in candles
        ]

        cur.executemany(query, rows)
        conn.commit()
        conn.close()

async def main():
    parser = argparse.ArgumentParser(description='Backfill futures OHLCV')
    parser.add_argument('--instruments', help='Comma-separated list or "all"')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--parallel', type=int, default=1, help='Parallel workers')

    args = parser.parse_args()

    # Load instrument list
    if args.instruments == 'all':
        with open('/data/historical_futures_list.json') as f:
            instruments = json.load(f)
    else:
        instruments = args.instruments.split(',')

    backfiller = FuturesBackfiller()

    # Backfill each instrument
    tasks = []
    for instrument in instruments:
        task = backfiller.backfill_instrument(instrument, args.start, args.end)
        tasks.append(task)

        # Limit concurrent tasks
        if len(tasks) >= args.parallel:
            await asyncio.gather(*tasks)
            tasks = []

    if tasks:
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
```

**Deliverables:**
- `scripts/backfill_futures.py` (~400 lines)
- Logging to: `/logs/futures-backfill.log`

**Acceptance Criteria:**
- AC-007b: Script handles expired futures gracefully (404 errors)
- AC-007c: Rate limiting implemented (0.05s delay)
- AC-007d: Idempotent UPSERT operations

---

#### T-011: Execute BTC Futures Backfill
**Owner:** ENG
**Effort:** 3 hours (runtime)
**Status:** Blocked by T-010
**Dependencies:** T-010

**Command:**
```bash
python3 -m scripts.backfill_futures \
  --instruments all \
  --start 2019-06-01 \
  --end 2025-10-23 \
  --parallel 1 > /logs/btc-futures-backfill.log 2>&1 &
```

**Expected Results:**
- ~75 BTC futures contracts
- ~6 years × 525,600 min/year × 75 contracts = ~236M candles
- Storage: ~40 GB (uncompressed)
- Runtime: ~3 hours

**Monitoring:**
```bash
# Check progress
tail -f /logs/btc-futures-backfill.log

# Check database
psql -U postgres -d crypto_data -c "SELECT COUNT(*) FROM futures_ohlcv WHERE instrument LIKE 'BTC-%'"
```

---

#### T-012: Execute ETH Futures Backfill
**Owner:** ENG
**Effort:** 2 hours (runtime)
**Status:** Blocked by T-011
**Dependencies:** T-011 (can run in parallel if rate limits allow)

**Command:**
```bash
python3 -m scripts.backfill_futures \
  --instruments all \
  --start 2020-01-01 \
  --end 2025-10-23 \
  --parallel 1 > /logs/eth-futures-backfill.log 2>&1 &
```

**Expected Results:**
- ~70 ETH futures contracts
- ~5 years × 525,600 min/year × 70 contracts = ~183M candles
- Storage: ~31 GB (uncompressed)
- Runtime: ~2 hours

---

#### T-013: Compute Basis Spread
**Owner:** ENG
**Effort:** 30 minutes
**Status:** Blocked by T-011, T-012
**Dependencies:** T-011, T-012

**Objective:** Compute perpetual-futures basis spread for all timestamps.

**Query:**
```sql
-- Create basis spread view
CREATE MATERIALIZED VIEW futures_basis_spread AS
SELECT
    f.timestamp,
    f.instrument,
    f.expiry_date,
    f.close AS futures_price,
    p.close AS perpetual_price,
    (f.close - p.close) AS basis_spread,
    ((f.close - p.close) / p.close * 100) AS basis_spread_pct,
    EXTRACT(EPOCH FROM (f.expiry_date - f.timestamp)) / 86400 AS days_to_expiry
FROM futures_ohlcv f
JOIN perpetuals_ohlcv p
    ON f.timestamp = p.timestamp
    AND SUBSTRING(f.instrument FROM 1 FOR 3) = SUBSTRING(p.instrument FROM 1 FOR 3)
WHERE p.instrument IN ('BTC-PERPETUAL', 'ETH-PERPETUAL');

CREATE INDEX idx_basis_spread_instrument ON futures_basis_spread(instrument);
CREATE INDEX idx_basis_spread_timestamp ON futures_basis_spread(timestamp);
```

**Deliverables:**
- Materialized view: `futures_basis_spread`
- Visualization script: `scripts/plot_basis_curve.py`

**Acceptance Criteria:**
- AC-008: Basis spread computed for 100% of overlapping timestamps

---

## Phase 3: Funding Rates + Index Prices

### Overview

**Goal:** Backfill funding rates (8-hour intervals) and index prices (1-minute) for perpetuals analysis.

### Tasks

#### T-014: Backfill Funding Rates
**Owner:** ENG
**Effort:** 1 hour (30 min dev + 30 min runtime)
**Status:** Ready
**Dependencies:** None (can start immediately)

**Objective:** Fetch historical funding rates for BTC-PERPETUAL and ETH-PERPETUAL (2016-2025).

**Implementation:**
```python
# scripts/backfill_funding_rates.py
import aiohttp
import asyncio
from datetime import datetime
from db import get_db_connection

async def fetch_funding_rates(instrument: str, start_ts: int, end_ts: int):
    """Fetch funding rate history from Deribit"""
    url = "https://www.deribit.com/api/v2/public/get_funding_rate_history"

    params = {
        "instrument_name": instrument,
        "start_timestamp": start_ts * 1000,
        "end_timestamp": end_ts * 1000
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return data['result']

def upsert_funding_rates(instrument: str, rates: list):
    """Insert funding rates into database"""
    conn = get_db_connection()
    cur = conn.cursor()

    query = """
    INSERT INTO funding_rates (timestamp, instrument, funding_rate)
    VALUES (%s, %s, %s)
    ON CONFLICT (timestamp, instrument) DO UPDATE SET
        funding_rate = EXCLUDED.funding_rate
    """

    rows = [
        (datetime.fromtimestamp(r['timestamp'] / 1000), instrument, r['interest_rate'])
        for r in rates
    ]

    cur.executemany(query, rows)
    conn.commit()
    conn.close()

async def main():
    instruments = ['BTC-PERPETUAL', 'ETH-PERPETUAL']
    start = int(datetime(2016, 12, 1).timestamp())
    end = int(datetime.now().timestamp())

    for instrument in instruments:
        print(f"Fetching {instrument}...")
        rates = await fetch_funding_rates(instrument, start, end)
        upsert_funding_rates(instrument, rates)
        print(f"{instrument}: {len(rates)} rates backfilled")

if __name__ == '__main__':
    asyncio.run(main())
```

**Expected Results:**
- ~9 years × 365 days × 3 rates/day = ~9,855 rates (per instrument)
- Total: ~19,710 rates (BTC + ETH)
- Storage: ~10 MB
- Runtime: 30 minutes

**Command:**
```bash
python3 -m scripts.backfill_funding_rates > /logs/funding-rates-backfill.log 2>&1
```

**Acceptance Criteria:**
- AC-010: Funding rates present for 100% of 8-hour intervals (2016-2025)

---

#### T-015: Backfill Index Prices
**Owner:** ENG
**Effort:** 1 hour (30 min dev + 30 min runtime)
**Status:** Ready
**Dependencies:** None (can run in parallel with T-014)

**Objective:** Fetch 1-minute index prices for BTC-USD and ETH-USD (spot proxy).

**Implementation:**
```python
# scripts/backfill_index_prices.py
# Similar to backfill_perpetuals.py but using /public/get_index_price endpoint
# Note: Historical index prices may need to be fetched via TradingView API
#       or derived from perpetuals close prices (approximation)

async def backfill_index_prices(currency: str, start: str, end: str):
    """
    Workaround: Use perpetuals close as index price proxy
    Deribit index price = weighted average of spot exchanges
    Perpetuals track index closely (arbitrage)
    """
    query = """
    INSERT INTO index_prices (timestamp, currency, price)
    SELECT
        timestamp,
        SUBSTRING(instrument FROM 1 FOR 3) AS currency,
        close AS price
    FROM perpetuals_ohlcv
    WHERE instrument = %s
    ON CONFLICT (timestamp, currency) DO UPDATE SET
        price = EXCLUDED.price
    """

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (f"{currency}-PERPETUAL",))
    conn.commit()
    conn.close()

async def main():
    currencies = ['BTC', 'ETH']

    for currency in currencies:
        print(f"Backfilling {currency} index prices...")
        await backfill_index_prices(currency, '2016-12-01', '2025-10-23')

        # Verify
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM index_prices WHERE currency = %s", (currency,))
        count = cur.fetchone()[0]
        print(f"{currency}: {count:,} index prices backfilled")
        conn.close()

if __name__ == '__main__':
    asyncio.run(main())
```

**Expected Results:**
- BTC: ~3.78M prices (mirrors BTC-PERPETUAL)
- ETH: ~3.47M prices (mirrors ETH-PERPETUAL)
- Storage: ~50 MB
- Runtime: 30 minutes (mostly database copy)

**Command:**
```bash
python3 -m scripts.backfill_index_prices > /logs/index-prices-backfill.log 2>&1
```

**Acceptance Criteria:**
- AC-011: Index prices present for 100% of 1-minute intervals (2016-2025)

---

## Real-Time Collection Verification

### Current Status Check

**Objective:** Ensure real-time collectors continue running during backfill operations.

**Checks:**
```bash
# 1. Check process count
ps aux | grep collect_realtime | grep -v grep
# Expected: 2 processes

# 2. Check last data timestamp
psql -U postgres -d crypto_data -c "
SELECT
    instrument,
    MAX(timestamp) AS latest,
    NOW() - MAX(timestamp) AS lag
FROM perpetuals_ohlcv
GROUP BY instrument
ORDER BY instrument
"
# Expected: Lag < 15 minutes

# 3. Check log for recent activity
tail -50 /logs/realtime-test.log | grep -E 'collection complete|ERROR'
# Expected: Regular "collection complete" messages, no errors

# 4. Check database write rate
psql -U postgres -d crypto_data -c "
SELECT
    schemaname,
    tablename,
    n_tup_ins AS inserts,
    n_tup_upd AS updates,
    last_autovacuum
FROM pg_stat_user_tables
WHERE tablename IN ('perpetuals_ohlcv', 'futures_ohlcv', 'options_ohlcv')
ORDER BY tablename
"
# Expected: Increasing insert/update counts
```

**Action if Collectors Stopped:**
```bash
# Restart collectors
pkill -f collect_realtime
nohup python3 -m scripts.collect_realtime > /logs/realtime.log 2>&1 &
```

---

## Execution Timeline

### Parallel Execution Strategy

**Hour 0-2: Implementation Phase**
- T-009: Fetch futures list (30 min)
- T-010: Implement backfill_futures.py (1.5 hours)
- T-014: Implement funding rates backfill (30 min) - parallel
- T-015: Implement index prices backfill (30 min) - parallel

**Hour 2-5: Futures Backfill**
- T-011: BTC futures backfill (3 hours)
- T-012: ETH futures backfill (2 hours) - start after T-011 or parallel if rate limits OK

**Hour 5-6: Funding + Index**
- T-014: Execute funding rates backfill (30 min)
- T-015: Execute index prices backfill (30 min) - parallel

**Hour 6-7: Verification**
- T-013: Compute basis spread (30 min)
- Run data quality checks
- Generate completion report

**Total: 7 hours**

---

## Acceptance Criteria Summary

| AC ID | Description | Verification |
|-------|-------------|--------------|
| AC-007 | All futures contracts from 2019+ present | Row count query |
| AC-008 | Basis spread computed for all timestamps | Materialized view row count |
| AC-009 | Futures storage ≤ 1.5 GB | pg_total_relation_size |
| AC-010 | Funding rates complete (8-hour intervals) | Gap detection query |
| AC-011 | Index prices complete (1-minute intervals) | Gap detection query |

---

## Risk Mitigation

### Risk 1: Expired Futures Data Unavailable
**Probability:** HIGH
**Impact:** MEDIUM
**Mitigation:**
- Generate instrument list from known expiry schedule
- Accept 404 errors gracefully
- Document which instruments have no data

### Risk 2: API Rate Limits During Backfill
**Probability:** MEDIUM
**Impact:** MEDIUM
**Mitigation:**
- Sequential execution (not parallel) for futures
- 0.05s delay between requests
- Exponential backoff on 429 errors

### Risk 3: Database Disk Space Exhaustion
**Probability:** LOW
**Impact:** HIGH
**Mitigation:**
- Monitor disk usage before/during backfill
- Expected total: ~1.5 GB (well under available space)
- Can pause/resume backfill if needed

### Risk 4: Real-Time Collector Interference
**Probability:** LOW
**Impact:** LOW
**Mitigation:**
- Collectors use UPSERT (idempotent)
- Different time ranges (real-time vs. historical)
- Monitor collector health during backfill

---

## Deliverables Checklist

### Code
- [ ] `scripts/fetch_futures_history.py` (T-009)
- [ ] `scripts/backfill_futures.py` (T-010)
- [ ] `scripts/backfill_funding_rates.py` (T-014)
- [ ] `scripts/backfill_index_prices.py` (T-015)
- [ ] `scripts/compute_basis_spread.sql` (T-013)

### Data
- [ ] `/data/historical_futures_list.json` (T-009)
- [ ] `futures_ohlcv` table populated (T-011, T-012)
- [ ] `funding_rates` table populated (T-014)
- [ ] `index_prices` table populated (T-015)
- [ ] `futures_basis_spread` materialized view (T-013)

### Evidence
- [ ] `/logs/btc-futures-backfill.log` (T-011)
- [ ] `/logs/eth-futures-backfill.log` (T-012)
- [ ] `/logs/funding-rates-backfill.log` (T-014)
- [ ] `/logs/index-prices-backfill.log` (T-015)
- [ ] `/tests/evidence/futures-row-counts.txt`
- [ ] `/tests/evidence/funding-rates-validation.txt`
- [ ] `/tests/evidence/index-prices-validation.txt`

### Reports
- [ ] Completion report (all ACs met)
- [ ] Data quality report (gaps, sanity checks)
- [ ] Storage usage report (per table)
- [ ] Update PROJECT-STATUS-REPORT.md

---

## Next Steps (Immediate)

1. **Verify real-time collectors running** ✅ (checking now)
2. **Start T-009**: Fetch futures instrument list (30 min)
3. **Parallel T-014, T-015**: Implement funding/index backfill scripts (1 hour)
4. **Start T-010**: Implement futures backfill script (1.5 hours)
5. **Execute backfills sequentially** (5 hours)
6. **Verification and reporting** (30 min)

**Estimated Completion:** 2025-10-23 08:00 HKT (~7 hours from now)

---

**Document Owner:** PM Orchestrator
**Last Updated:** 2025-10-23 00:50 HKT
**Next Review:** After T-010 completion
