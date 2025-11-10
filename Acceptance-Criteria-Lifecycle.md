# Acceptance Criteria - Options Lifecycle Management

**Project:** Options Lifecycle Management & Automatic Expiry Handling
**FE Plan:** `/inbox/OPTION_LIFECYCLE_MANAGEMENT_PLAN.md`
**PM:** Project Manager Orchestrator
**Date:** 2025-11-10

---

## PHASE 0: IMMEDIATE FIX (COMPLETED ✅)

### AC-000: BTC Trades Schema Fix
**Status:** ✅ COMPLETED
**Priority:** P0 - CRITICAL (BLOCKING)

**Criteria:**
- ✅ `iv` column exists in `btc_option_trades` table
- ✅ `index_price` column exists in `btc_option_trades` table
- ✅ BTC collector logs show "Successfully flushed X trades" (no more IV column errors)
- ✅ `SELECT COUNT(*) FROM btc_option_trades` returns > 0 within 5 minutes of restart
- ✅ BTC collectors restarted successfully

**Verification:**
```sql
-- Verified 2025-11-10 17:29 UTC
SELECT COUNT(*) FROM btc_option_trades WHERE timestamp > NOW() - INTERVAL '5 minutes';
-- Result: 9 trades collected
```

---

## PHASE 1: DATABASE FOUNDATION

### AC-001: Instrument Metadata Table Created
**Priority:** P1 - HIGH
**Dependencies:** None

**Criteria:**
- [ ] Table `instrument_metadata` exists with correct schema
- [ ] Columns: instrument_name (PK), currency, kind, expiration_timestamp, strike, option_type, is_active, first_seen, last_seen, expired_at, created_at, updated_at
- [ ] Indexes created: idx_instrument_currency, idx_instrument_active, idx_instrument_expiry, idx_instrument_kind
- [ ] `\d instrument_metadata` shows all columns and indexes
- [ ] Test query returns empty result set (no errors)

**SQL Verification:**
```sql
SELECT COUNT(*) FROM instrument_metadata;
-- Expected: 0 rows (initially empty)

SELECT column_name FROM information_schema.columns
WHERE table_name = 'instrument_metadata'
ORDER BY ordinal_position;
-- Expected: 12 columns
```

**Files Created:**
- `schema/006_add_lifecycle_tables.sql`

---

### AC-002: Lifecycle Events Table Created
**Priority:** P1 - HIGH
**Dependencies:** AC-001

**Criteria:**
- [ ] Table `lifecycle_events` exists with correct schema
- [ ] Converted to TimescaleDB hypertable (chunk_time_interval = 1 day)
- [ ] Columns: event_id (PK), timestamp, event_type, currency, instrument_name, connection_id, reason, metadata (JSONB)
- [ ] Indexes created: idx_lifecycle_event_type, idx_lifecycle_currency, idx_lifecycle_instrument
- [ ] Retention policy set (90 days)
- [ ] Test insert and query succeeds

**SQL Verification:**
```sql
SELECT hypertable_name FROM timescaledb_information.hypertables
WHERE hypertable_name = 'lifecycle_events';
-- Expected: 1 row

INSERT INTO lifecycle_events (event_type, currency, reason)
VALUES ('test', 'BTC', 'test_insert');
-- Expected: 1 row inserted
```

**Files Created:**
- `schema/006_add_lifecycle_tables.sql` (same file as AC-001)

---

### AC-003: Instrument Metadata Populated
**Priority:** P1 - HIGH
**Dependencies:** AC-001

**Criteria:**
- [ ] `instrument_metadata` table populated with ALL current BTC + ETH options
- [ ] BTC instruments: ~728 rows (or current count from Deribit API)
- [ ] ETH instruments: ~820 rows (or current count from Deribit API)
- [ ] Total: ~1,548 rows
- [ ] All rows have `is_active = TRUE`
- [ ] `expiration_timestamp` correctly parsed from Deribit API
- [ ] `strike` and `option_type` correctly parsed from instrument_name

**SQL Verification:**
```sql
SELECT currency, COUNT(*) as total,
       COUNT(*) FILTER (WHERE is_active = TRUE) as active
FROM instrument_metadata
GROUP BY currency;
-- Expected: BTC ~728, ETH ~820, all active = TRUE
```

**Files Created:**
- `scripts/populate_instrument_metadata.py`

---

## PHASE 2: LIFECYCLE MANAGER CORE

### AC-004: Lifecycle Manager Fetches Active Instruments
**Priority:** P1 - HIGH
**Dependencies:** AC-003

**Criteria:**
- [ ] `fetch_active_instruments(currency)` returns list of active options from Deribit API
- [ ] Filters only `kind='option'` and `is_active=True`
- [ ] Returns instrument dictionaries with: instrument_name, expiration_timestamp, strike, option_type
- [ ] Handles API errors gracefully (retry logic, timeout)
- [ ] Unit test: mock API response, verify parsing

**Test:**
```python
instruments = await lifecycle_manager.fetch_active_instruments('BTC')
assert len(instruments) > 700
assert all('instrument_name' in inst for inst in instruments)
```

**Files Modified/Created:**
- `scripts/lifecycle_manager.py` (new)

---

### AC-005: Lifecycle Manager Detects Expiries
**Priority:** P1 - HIGH
**Dependencies:** AC-004

**Criteria:**
- [ ] `detect_expiries(instruments, buffer_minutes=5)` identifies instruments expiring within buffer
- [ ] Compares `expiration_timestamp` with `current_time + buffer`
- [ ] Returns list of instrument names expiring soon
- [ ] Unit test: manually set expiry to NOW + 2 minutes, verify detected

**Test:**
```python
# Mock instrument expiring in 3 minutes
instruments = [{'instrument_name': 'TEST', 'expiration_timestamp': now_ms + 180000}]
expiring = await lifecycle_manager.detect_expiries(instruments, buffer_minutes=5)
assert 'TEST' in expiring
```

**Files Modified/Created:**
- `scripts/lifecycle_manager.py`

---

### AC-006: Lifecycle Manager Syncs Metadata Table
**Priority:** P1 - HIGH
**Dependencies:** AC-004, AC-005

**Criteria:**
- [ ] `sync_instrument_metadata(currency)` updates instrument_metadata table
- [ ] Marks expired instruments as `is_active = FALSE` and sets `expired_at`
- [ ] Adds new instruments (INSERT ... ON CONFLICT DO UPDATE)
- [ ] Updates `last_seen` timestamp for active instruments
- [ ] Logs sync statistics (added, expired, updated)

**Test:**
```python
await lifecycle_manager.sync_instrument_metadata('BTC')

# Verify expired instruments marked inactive
expired_count = await db.fetchval(
    "SELECT COUNT(*) FROM instrument_metadata WHERE is_active = FALSE"
)
assert expired_count > 0 (if expiries occurred)
```

**Files Modified/Created:**
- `scripts/lifecycle_manager.py`

---

### AC-007: Lifecycle Manager Calculates Subscription Changes
**Priority:** P1 - HIGH
**Dependencies:** AC-006

**Criteria:**
- [ ] `calculate_subscription_changes()` returns dict with 'subscribe', 'unsubscribe', 'keep' lists
- [ ] Compares current collector subscriptions vs. active instruments in metadata
- [ ] Identifies expired instruments to unsubscribe
- [ ] Identifies new instruments to subscribe
- [ ] Respects 500 channel limit (250 instruments × 2 channels)
- [ ] Unit test: mock current subscriptions + metadata, verify diff calculation

**Test:**
```python
changes = await lifecycle_manager.calculate_subscription_changes('BTC', 0, current_instruments)
assert 'subscribe' in changes
assert 'unsubscribe' in changes
assert len(changes['subscribe']) + len(changes['keep']) <= 250
```

**Files Modified/Created:**
- `scripts/lifecycle_manager.py`

---

### AC-008: Lifecycle Manager Logs Events
**Priority:** P2 - MEDIUM
**Dependencies:** AC-002

**Criteria:**
- [ ] `log_lifecycle_event()` inserts row into lifecycle_events table
- [ ] Required fields populated: event_type, currency, timestamp
- [ ] Optional fields: instrument_name, connection_id, reason, metadata (JSONB)
- [ ] Handles database errors gracefully (doesn't crash lifecycle manager)

**Test:**
```sql
SELECT COUNT(*) FROM lifecycle_events WHERE event_type = 'test';
-- Expected: at least 1 row after test
```

**Files Modified/Created:**
- `scripts/lifecycle_manager.py`

---

## PHASE 3: COLLECTOR INTEGRATION

### AC-009: Collector Has HTTP Control API
**Priority:** P1 - HIGH
**Dependencies:** None (independent of lifecycle manager)

**Criteria:**
- [ ] WebSocket collector starts HTTP API on port `8000 + connection_id`
- [ ] Endpoints: POST `/subscribe`, POST `/unsubscribe`, GET `/status`
- [ ] API returns JSON responses
- [ ] API accessible from lifecycle manager container
- [ ] Environment variable `ENABLE_LIFECYCLE_API=true` enables API

**Test:**
```bash
curl http://localhost:8000/status
# Expected: {"connection_id": 0, "currency": "BTC", "instruments": [...], "channel_count": 500}

curl -X POST http://localhost:8000/subscribe -H "Content-Type: application/json" -d '{"instruments": ["BTC-10NOV25-100000-C"]}'
# Expected: {"status": "ok"}
```

**Files Modified:**
- `scripts/ws_tick_collector_multi.py`

---

### AC-010: Collector Subscribes to New Instruments
**Priority:** P1 - HIGH
**Dependencies:** AC-009

**Criteria:**
- [ ] POST `/subscribe` endpoint accepts `{"instruments": [...]}`
- [ ] Sends WebSocket `public/subscribe` message to Deribit
- [ ] Adds instruments to internal `self.instruments` list
- [ ] Returns success response
- [ ] Logs subscription action
- [ ] Handles subscription errors (instrument not found, rate limit, etc.)

**Test:**
```python
response = await http_client.post(
    'http://btc-options-0:8000/subscribe',
    json={'instruments': ['BTC-10NOV25-100000-C']}
)
assert response.status == 200
assert await response.json() == {'status': 'ok'}
```

**Files Modified:**
- `scripts/ws_tick_collector_multi.py`

---

### AC-011: Collector Unsubscribes from Expired Instruments
**Priority:** P1 - HIGH
**Dependencies:** AC-009

**Criteria:**
- [ ] POST `/unsubscribe` endpoint accepts `{"instruments": [...]}`
- [ ] Sends WebSocket `public/unsubscribe` message to Deribit
- [ ] Removes instruments from internal `self.instruments` list
- [ ] Returns success response
- [ ] Logs unsubscription action
- [ ] Handles unsubscription errors gracefully

**Test:**
```python
response = await http_client.post(
    'http://btc-options-0:8000/unsubscribe',
    json={'instruments': ['BTC-10NOV25-100000-C']}
)
assert response.status == 200
assert await response.json() == {'status': 'ok'}
```

**Files Modified:**
- `scripts/ws_tick_collector_multi.py`

---

### AC-012: Collector Reports Status
**Priority:** P2 - MEDIUM
**Dependencies:** AC-009

**Criteria:**
- [ ] GET `/status` endpoint returns current subscription state
- [ ] Response includes: connection_id, currency, instruments list, channel_count
- [ ] Channel count calculated as `len(instruments) * 2`
- [ ] Response format is valid JSON

**Test:**
```python
response = await http_client.get('http://btc-options-0:8000/status')
data = await response.json()
assert 'connection_id' in data
assert 'instruments' in data
assert data['channel_count'] == len(data['instruments']) * 2
```

**Files Modified:**
- `scripts/ws_tick_collector_multi.py`

---

## PHASE 4: FULL AUTOMATION

### AC-013: Lifecycle Manager Periodic Refresh Loop
**Priority:** P1 - HIGH
**Dependencies:** AC-004, AC-005, AC-006, AC-007, AC-008, AC-010, AC-011

**Criteria:**
- [ ] `periodic_refresh(interval_sec=300)` runs as background task
- [ ] Every 5 minutes: fetches active instruments, syncs metadata, calculates changes, sends API calls
- [ ] Sends subscribe/unsubscribe requests to all collectors via HTTP API
- [ ] Logs all changes to lifecycle_events table
- [ ] Handles API failures gracefully (retry logic)
- [ ] Continues running after errors (doesn't crash)

**Test:**
```python
# Start lifecycle manager, wait 6 minutes
await asyncio.sleep(360)

# Check lifecycle_events for sync activity
events = await db.fetch("SELECT * FROM lifecycle_events WHERE event_type = 'sync' AND timestamp > NOW() - INTERVAL '10 minutes'")
assert len(events) >= 1  # At least one sync cycle
```

**Files Modified:**
- `scripts/lifecycle_manager.py`

---

### AC-014: Lifecycle Manager Container Deployed
**Priority:** P1 - HIGH
**Dependencies:** AC-013

**Criteria:**
- [ ] `lifecycle-manager` service added to docker-compose-multi-conn.yml
- [ ] Environment variables set: DATABASE_URL, REFRESH_INTERVAL_SEC, EXPIRY_BUFFER_MINUTES
- [ ] Collector URLs configured: BTC_COLLECTOR_0_URL, ETH_COLLECTOR_0_URL, etc.
- [ ] Container starts successfully (`docker ps` shows running)
- [ ] Container logs show periodic refresh activity
- [ ] Container restarts on failure (restart: unless-stopped)

**Test:**
```bash
docker-compose -f docker-compose-multi-conn.yml ps lifecycle-manager
# Expected: STATUS = Up

docker-compose -f docker-compose-multi-conn.yml logs lifecycle-manager | grep "periodic_refresh"
# Expected: log entries showing refresh cycles
```

**Files Modified:**
- `docker-compose-multi-conn.yml`

---

### AC-015: Collectors Expose Control API Ports
**Priority:** P1 - HIGH
**Dependencies:** AC-009

**Criteria:**
- [ ] BTC collectors expose ports 8000-8002
- [ ] ETH collectors expose ports 8003-8006
- [ ] Ports accessible from lifecycle-manager container
- [ ] Environment variable `CONTROL_API_PORT` set correctly
- [ ] Environment variable `ENABLE_LIFECYCLE_API=true` set

**Test:**
```bash
# From lifecycle-manager container
curl http://btc-options-0:8000/status
curl http://eth-options-0:8003/status
# Expected: JSON responses from all collectors
```

**Files Modified:**
- `docker-compose-multi-conn.yml`

---

## PHASE 5: END-TO-END TESTING

### AC-016: Expiry Simulation Test Passes
**Priority:** P1 - HIGH
**Dependencies:** AC-013, AC-014, AC-015

**Criteria:**
- [ ] Manually set `expiration_timestamp` to `NOW() + 2 minutes` for test instrument
- [ ] Wait 3 minutes (past expiry buffer)
- [ ] Verify lifecycle manager detected expiry and sent unsubscribe command
- [ ] Verify collector unsubscribed from instrument
- [ ] Verify lifecycle_events table shows `event_type='unsubscribed'`
- [ ] Verify instrument marked `is_active=FALSE` in instrument_metadata

**Test:**
```sql
-- Set up test expiry
UPDATE instrument_metadata
SET expiration_timestamp = (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT + 120000
WHERE instrument_name = 'BTC-TEST-100000-C';

-- Wait 3 minutes, then check
SELECT * FROM lifecycle_events WHERE instrument_name = 'BTC-TEST-100000-C' AND event_type = 'unsubscribed';
-- Expected: 1 row
```

**Files:** N/A (manual test)

---

### AC-017: New Instrument Detection Test Passes
**Priority:** P1 - HIGH
**Dependencies:** AC-013, AC-014, AC-015

**Criteria:**
- [ ] Manually insert new instrument into instrument_metadata (with future expiry)
- [ ] Wait 6 minutes (one refresh cycle)
- [ ] Verify lifecycle manager detected new instrument
- [ ] Verify collector subscribed to new instrument
- [ ] Verify lifecycle_events table shows `event_type='subscribed'`
- [ ] Verify quotes/trades being collected for new instrument

**Test:**
```sql
-- Insert test instrument
INSERT INTO instrument_metadata (instrument_name, currency, kind, expiration_timestamp, is_active)
VALUES ('BTC-17NOV25-105000-C', 'BTC', 'option', (EXTRACT(EPOCH FROM NOW() + INTERVAL '7 days') * 1000)::BIGINT, TRUE);

-- Wait 6 minutes, then check
SELECT * FROM lifecycle_events WHERE instrument_name = 'BTC-17NOV25-105000-C' AND event_type = 'subscribed';
-- Expected: 1 row
```

**Files:** N/A (manual test)

---

### AC-018: Container Restart Test Passes
**Priority:** P2 - MEDIUM
**Dependencies:** AC-014, AC-015

**Criteria:**
- [ ] Restart lifecycle-manager container
- [ ] Verify container starts successfully
- [ ] Verify periodic refresh resumes after restart
- [ ] Restart collector container (btc-options-0)
- [ ] Verify collector queries instrument_metadata for active instruments
- [ ] Verify collector subscribes only to active instruments (not expired)

**Test:**
```bash
docker-compose -f docker-compose-multi-conn.yml restart lifecycle-manager
docker-compose -f docker-compose-multi-conn.yml restart btc-options-0

# Wait 2 minutes, check logs
docker-compose -f docker-compose-multi-conn.yml logs lifecycle-manager | tail -50
docker-compose -f docker-compose-multi-conn.yml logs btc-options-0 | tail -50
# Expected: no errors, subscriptions successful
```

**Files:** N/A (manual test)

---

### AC-019: Coverage Stability Test (24 Hours)
**Priority:** P1 - HIGH
**Dependencies:** AC-013, AC-014, AC-015

**Criteria:**
- [ ] System runs for 24 hours without intervention
- [ ] Coverage remains at 95%+ for both BTC and ETH
- [ ] No subscription attempts to expired instruments (check logs)
- [ ] All expiry events logged in lifecycle_events table
- [ ] New instruments (if any) automatically subscribed
- [ ] No memory leaks (container memory usage stable)

**Test:**
```sql
-- After 24 hours
SELECT currency, COUNT(*) as subscribed_count
FROM (
    SELECT DISTINCT instrument_name,
           CASE WHEN instrument_name LIKE 'BTC%' THEN 'BTC' ELSE 'ETH' END as currency
    FROM btc_option_quotes
    WHERE timestamp > NOW() - INTERVAL '1 hour'
    UNION
    SELECT DISTINCT instrument_name,
           CASE WHEN instrument_name LIKE 'BTC%' THEN 'BTC' ELSE 'ETH' END as currency
    FROM eth_option_quotes
    WHERE timestamp > NOW() - INTERVAL '1 hour'
) active_instruments
GROUP BY currency;

-- Compare to total available from Deribit API
-- Expected: coverage >= 95% for both currencies
```

**Files:** N/A (24-hour soak test)

---

## PHASE 6: MONITORING & OBSERVABILITY

### AC-020: Grafana Dashboard Created
**Priority:** P2 - MEDIUM
**Dependencies:** AC-002, AC-019

**Criteria:**
- [ ] Dashboard created: "Options Lifecycle Management"
- [ ] Panel 1: Coverage over time (% of available instruments subscribed)
- [ ] Panel 2: Subscription changes per hour (subscribed, unsubscribed, total)
- [ ] Panel 3: Expired instruments count (last 24 hours)
- [ ] Panel 4: Lifecycle manager status (last refresh time, errors)
- [ ] Dashboard accessible at http://localhost:3000

**Test:**
- Visual verification in Grafana UI

**Files:** N/A (Grafana dashboard JSON export optional)

---

### AC-021: Coverage Alert Configured
**Priority:** P2 - MEDIUM
**Dependencies:** AC-020

**Criteria:**
- [ ] Alert rule: "Coverage drops below 95%"
- [ ] Alert checks every 5 minutes
- [ ] Alert triggers if BTC OR ETH coverage < 95%
- [ ] Alert notification configured (email/Slack/webhook)
- [ ] Test alert triggers correctly (manually reduce coverage)

**Test:**
```sql
-- Manually mark 10% of instruments as inactive
UPDATE instrument_metadata SET is_active = FALSE WHERE instrument_name IN (
    SELECT instrument_name FROM instrument_metadata WHERE currency = 'BTC' LIMIT 73
);

-- Wait 10 minutes, verify alert triggered
```

**Files:** N/A (Grafana alert configuration)

---

## SUCCESS METRICS

### Immediate (Post Schema Fix) - ✅ COMPLETED
- ✅ BTC trades inserting successfully (9 trades collected in 5 minutes)
- ✅ `btc_option_trades` table has >0 rows
- ✅ No more IV column errors in logs

### 24 Hours After Lifecycle Deployment
- [ ] Coverage remains at 95%+ for both BTC and ETH
- [ ] No subscription attempts to expired instruments
- [ ] All expiry events logged in lifecycle_events table
- [ ] New instruments (if any) automatically subscribed
- [ ] Lifecycle manager container running without restarts

### 7 Days After Deployment
- [ ] Coverage stable at 95%+ despite daily/weekly expiries
- [ ] instrument_metadata table accurately reflects active instruments
- [ ] lifecycle_events table shows regular sync activity (every 5 minutes)
- [ ] No manual intervention required
- [ ] Database growth rate acceptable (<10GB/day)

---

## RISKS & MITIGATIONS

### R-1: Mid-Collection Unsubscribe Causes Data Loss
**Severity:** LOW
**Mitigation:** Unsubscribe 5 minutes BEFORE expiry (AC-005)
**Acceptance:** No data gaps in final 5 minutes before expiry

### R-2: New Instrument Subscription Exceeds 500 Channel Limit
**Severity:** MEDIUM
**Mitigation:** Lifecycle manager checks total channel count before subscribing (AC-007)
**Acceptance:** Total channels never exceeds 500 per connection

### R-3: Deribit API Rate Limiting
**Severity:** LOW
**Mitigation:** 1 API call per 5 minutes = 0.003 req/sec (well below 20 req/sec limit)
**Acceptance:** No rate limit errors in logs

### R-4: Database Bloat from Expired Instrument Metadata
**Severity:** LOW
**Mitigation:** Retention policy on instrument_metadata (keep only last 6 months)
**Acceptance:** Table size <100MB after 6 months

### R-5: Lifecycle Manager Failure Causes Coverage Degradation
**Severity:** MEDIUM
**Mitigation:** Docker restart policy + health checks; collectors continue with stale lists
**Acceptance:** Coverage degrades <5% during lifecycle manager downtime

---

**Total Acceptance Criteria:** 21 (1 completed, 20 pending)
**Estimated Timeline:** 8-10 hours (development + testing + monitoring setup)
