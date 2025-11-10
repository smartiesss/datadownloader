# Orchestrator Plan - Options Lifecycle Management

**Project:** Options Lifecycle Management System
**PM:** Project Manager Orchestrator
**FE Plan Reference:** `/inbox/OPTION_LIFECYCLE_MANAGEMENT_PLAN.md`
**AC Reference:** `Acceptance-Criteria-Lifecycle.md`
**Date:** 2025-11-10

---

## EXECUTIVE SUMMARY

### Project Status
- **Phase 0 (Immediate Fix):** ✅ COMPLETED (2025-11-10 17:29 UTC)
- **Phase 1-6 (Lifecycle Management):** 🔄 IN PLANNING

### Critical Path
1. **✅ DONE:** Schema fix for BTC trades (AC-000)
2. **NEXT:** Database foundation (AC-001, AC-002, AC-003) - 2 hours
3. **THEN:** Lifecycle manager core (AC-004 through AC-008) - 3 hours
4. **THEN:** Collector integration (AC-009 through AC-012) - 2 hours
5. **THEN:** Full automation (AC-013 through AC-015) - 1 hour
6. **FINALLY:** Testing & monitoring (AC-016 through AC-021) - 2 hours

**Total Estimated Time:** 10 hours (development + testing + monitoring)

---

## TASK BREAKDOWN

### PHASE 0: IMMEDIATE FIX ✅

#### T-000: Apply BTC Trades Schema Fix
**Status:** ✅ COMPLETED
**Assigned to:** PM (executed immediately)
**Time:** 5 minutes
**Dependencies:** None

**Acceptance Criteria:**
- AC-000

**Steps Completed:**
1. ✅ Created `schema/005_fix_btc_trades_iv_column.sql`
2. ✅ Applied migration: `ALTER TABLE btc_option_trades ADD COLUMN iv, index_price`
3. ✅ Verified columns exist: `\d btc_option_trades` shows iv and index_price
4. ✅ Restarted BTC collectors: btc-options-0, btc-options-1, btc-options-2
5. ✅ Verified trade collection: 9 trades collected in 5 minutes

**Result:** BTC trade collection restored. Zero blockers remaining.

---

### PHASE 1: DATABASE FOUNDATION

#### T-001: Create Lifecycle Tables Schema File
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** None
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-001 (instrument_metadata table)
- AC-002 (lifecycle_events table)

**Subtasks:**
1. Create `schema/006_add_lifecycle_tables.sql`
2. Define `instrument_metadata` table with 12 columns
3. Define `lifecycle_events` table with 8 columns
4. Add indexes: 4 on instrument_metadata, 3 on lifecycle_events
5. Convert lifecycle_events to hypertable (1-day chunks)
6. Add retention policy (90 days for lifecycle_events)
7. Add table/column comments for documentation

**Deliverables:**
- `schema/006_add_lifecycle_tables.sql`

**Testing:**
```bash
# Validate SQL syntax
psql -U postgres -d crypto_data -f schema/006_add_lifecycle_tables.sql --dry-run

# Apply migration
docker exec crypto-timescaledb psql -U postgres -d crypto_data -f /docker-entrypoint-initdb.d/006_add_lifecycle_tables.sql

# Verify tables created
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "\dt"
```

---

#### T-002: Apply Lifecycle Tables Migration
**Priority:** P1 - HIGH
**Estimated Time:** 10 minutes
**Dependencies:** T-001
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-001
- AC-002

**Steps:**
1. Copy `schema/006_add_lifecycle_tables.sql` to schema directory
2. Apply migration to running database
3. Verify tables exist: `\dt` shows instrument_metadata and lifecycle_events
4. Verify hypertable conversion: `SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'lifecycle_events'`
5. Test insert into both tables

**Deliverables:**
- instrument_metadata table (empty)
- lifecycle_events table (empty, hypertable)

---

#### T-003: Create Instrument Metadata Population Script
**Priority:** P1 - HIGH
**Estimated Time:** 1 hour
**Dependencies:** T-002
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-003

**Subtasks:**
1. Create `scripts/populate_instrument_metadata.py`
2. Implement `fetch_all_instruments(currency)` using Deribit API
3. Parse instrument_name to extract: strike, option_type (call/put)
4. Implement INSERT ... ON CONFLICT DO UPDATE for idempotency
5. Add error handling (API timeout, network errors)
6. Add progress logging (print every 100 instruments)
7. Add final summary (total instruments per currency)

**Deliverables:**
- `scripts/populate_instrument_metadata.py`

**Testing:**
```bash
# Dry run (local)
DATABASE_URL="postgresql://postgres:CryptoTest2024!@localhost:5439/crypto_data" python3 -m scripts.populate_instrument_metadata

# Production run (container)
docker exec crypto-timescaledb python3 -m scripts.populate_instrument_metadata

# Verify population
docker exec crypto-timescaledb psql -U postgres -d crypto_data -c "
SELECT currency, COUNT(*) as total, COUNT(*) FILTER (WHERE is_active) as active
FROM instrument_metadata
GROUP BY currency;
"
```

---

#### T-004: Run Instrument Metadata Population
**Priority:** P1 - HIGH
**Estimated Time:** 5 minutes
**Dependencies:** T-003
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-003

**Steps:**
1. Run `scripts/populate_instrument_metadata.py`
2. Verify ~1,548 instruments populated (728 BTC + 820 ETH)
3. Verify all instruments have `is_active = TRUE`
4. Verify `expiration_timestamp` values are valid (future dates)
5. Spot-check: manually verify 5 random instruments against Deribit API

**Deliverables:**
- Populated instrument_metadata table

**Testing:**
```sql
-- Check totals
SELECT currency, COUNT(*) FROM instrument_metadata GROUP BY currency;
-- Expected: BTC ~728, ETH ~820

-- Check all active
SELECT COUNT(*) FROM instrument_metadata WHERE is_active = FALSE;
-- Expected: 0

-- Check future expiries
SELECT COUNT(*) FROM instrument_metadata
WHERE to_timestamp(expiration_timestamp/1000) < NOW();
-- Expected: 0 (all expiries in future)
```

---

### PHASE 2: LIFECYCLE MANAGER CORE

#### T-005: Create Lifecycle Manager Module Skeleton
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-002
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-004 (partial - class structure only)

**Subtasks:**
1. Create `scripts/lifecycle_manager.py`
2. Define `OptionLifecycleManager` class
3. Add `__init__(database_url, collector_urls, refresh_interval, expiry_buffer)`
4. Add placeholder methods: fetch_active_instruments, detect_expiries, sync_instrument_metadata, calculate_subscription_changes, log_lifecycle_event, periodic_refresh
5. Add logging setup (stdout + file)
6. Add main() entry point with argument parsing
7. Add error handling skeleton (try/except around main loop)

**Deliverables:**
- `scripts/lifecycle_manager.py` (skeleton only, no logic)

**Testing:**
```bash
# Verify imports and syntax
python3 -m py_compile scripts/lifecycle_manager.py

# Verify runs without errors (no-op)
python3 -m scripts.lifecycle_manager --help
```

---

#### T-006: Implement Fetch Active Instruments
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-005
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-004

**Subtasks:**
1. Implement `fetch_active_instruments(currency)` method
2. Call Deribit API: `GET /api/v2/public/get_instruments?currency={currency}&kind=option`
3. Parse JSON response, extract `result` array
4. Filter: `is_active == True`
5. Return list of instrument dicts
6. Add retry logic (3 retries, exponential backoff)
7. Add timeout (10 seconds)
8. Unit test: mock API response, verify parsing

**Deliverables:**
- Working `fetch_active_instruments()` method

**Testing:**
```python
# Unit test
instruments = await lifecycle_manager.fetch_active_instruments('BTC')
assert len(instruments) > 700
assert all('instrument_name' in inst for inst in instruments)
assert all('expiration_timestamp' in inst for inst in instruments)
```

---

#### T-007: Implement Detect Expiries
**Priority:** P1 - HIGH
**Estimated Time:** 20 minutes
**Dependencies:** T-006
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-005

**Subtasks:**
1. Implement `detect_expiries(instruments, buffer_minutes=5)` method
2. Get current time in milliseconds: `int(datetime.now().timestamp() * 1000)`
3. Calculate expiry threshold: `now_ms + (buffer_minutes * 60 * 1000)`
4. Filter instruments where `expiration_timestamp < threshold`
5. Return list of expiring instrument_names
6. Unit test: mock instruments with expiry NOW + 3 minutes, verify detected

**Deliverables:**
- Working `detect_expiries()` method

**Testing:**
```python
# Unit test - instrument expiring in 3 minutes (within 5-minute buffer)
now_ms = int(datetime.now().timestamp() * 1000)
instruments = [
    {'instrument_name': 'TEST-EXPIRING', 'expiration_timestamp': now_ms + 180000},
    {'instrument_name': 'TEST-FUTURE', 'expiration_timestamp': now_ms + 600000}
]
expiring = lifecycle_manager.detect_expiries(instruments, buffer_minutes=5)
assert 'TEST-EXPIRING' in expiring
assert 'TEST-FUTURE' not in expiring
```

---

#### T-008: Implement Sync Instrument Metadata
**Priority:** P1 - HIGH
**Estimated Time:** 1 hour
**Dependencies:** T-006, T-007
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-006

**Subtasks:**
1. Implement `sync_instrument_metadata(currency)` method
2. Fetch active instruments from Deribit API
3. Detect expiring instruments (5-minute buffer)
4. For each active instrument: INSERT ... ON CONFLICT (instrument_name) DO UPDATE
5. Update: `is_active = TRUE`, `last_seen = NOW()`
6. For expiring instruments: UPDATE `is_active = FALSE`, `expired_at = NOW()`
7. Log statistics: added, updated, expired counts
8. Handle database connection errors
9. Unit test: mock API + DB, verify INSERT/UPDATE logic

**Deliverables:**
- Working `sync_instrument_metadata()` method

**Testing:**
```python
# Integration test
await lifecycle_manager.sync_instrument_metadata('BTC')

# Verify updates
active_count = await db.fetchval("SELECT COUNT(*) FROM instrument_metadata WHERE currency = 'BTC' AND is_active = TRUE")
assert active_count >= 700

# Verify last_seen updated (within last minute)
recent_count = await db.fetchval("SELECT COUNT(*) FROM instrument_metadata WHERE last_seen > NOW() - INTERVAL '1 minute'")
assert recent_count > 0
```

---

#### T-009: Implement Calculate Subscription Changes
**Priority:** P1 - HIGH
**Estimated Time:** 1 hour
**Dependencies:** T-008
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-007

**Subtasks:**
1. Implement `calculate_subscription_changes(currency, connection_id, current_instruments)` method
2. Query instrument_metadata for active instruments (is_active = TRUE)
3. Calculate partition assignment for this connection_id (same logic as orchestrator)
4. Compare: assigned_instruments vs. current_instruments
5. Calculate: to_subscribe = assigned - current, to_unsubscribe = current - assigned, to_keep = intersection
6. Enforce 500 channel limit: `len(to_subscribe) + len(to_keep) <= 250`
7. If limit exceeded, prioritize: keep existing, defer new subscriptions
8. Return dict: {'subscribe': [...], 'unsubscribe': [...], 'keep': [...]}
9. Unit test: mock metadata + current subscriptions, verify diff calculation

**Deliverables:**
- Working `calculate_subscription_changes()` method

**Testing:**
```python
# Unit test
current_instruments = ['INST-1', 'INST-2', 'INST-EXPIRED']
# Mock metadata: INST-1, INST-2 active; INST-3 new; INST-EXPIRED inactive
changes = await lifecycle_manager.calculate_subscription_changes('BTC', 0, current_instruments)
assert 'INST-3' in changes['subscribe']
assert 'INST-EXPIRED' in changes['unsubscribe']
assert 'INST-1' in changes['keep']
assert 'INST-2' in changes['keep']
```

---

#### T-010: Implement Log Lifecycle Event
**Priority:** P2 - MEDIUM
**Estimated Time:** 20 minutes
**Dependencies:** T-002
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-008

**Subtasks:**
1. Implement `log_lifecycle_event(event_type, currency, instrument, connection_id, reason, metadata=None)` method
2. INSERT INTO lifecycle_events with all provided fields
3. Handle metadata as JSONB (use `json.dumps()` if dict provided)
4. Add error handling: log error to stdout, don't crash lifecycle manager
5. Unit test: insert event, verify row exists

**Deliverables:**
- Working `log_lifecycle_event()` method

**Testing:**
```python
# Integration test
await lifecycle_manager.log_lifecycle_event(
    event_type='test',
    currency='BTC',
    instrument='TEST-INST',
    connection_id=0,
    reason='unit_test',
    metadata={'key': 'value'}
)

# Verify inserted
event = await db.fetchrow("SELECT * FROM lifecycle_events WHERE event_type = 'test' AND instrument_name = 'TEST-INST'")
assert event is not None
assert event['metadata'] == {'key': 'value'}
```

---

### PHASE 3: COLLECTOR INTEGRATION

#### T-011: Add HTTP Control API to Collector
**Priority:** P1 - HIGH
**Estimated Time:** 1 hour
**Dependencies:** None (independent)
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-009

**Subtasks:**
1. Modify `scripts/ws_tick_collector_multi.py`
2. Add imports: `from aiohttp import web`
3. Add `start_control_api()` method
4. Create aiohttp.web.Application
5. Add routes: POST /subscribe, POST /unsubscribe, GET /status
6. Start API server on port `8000 + connection_id`
7. Add environment variable check: `ENABLE_LIFECYCLE_API` (default: false)
8. Call `start_control_api()` in collector `start()` method (as background task)
9. Add error handling: log API errors, don't crash collector

**Deliverables:**
- Modified `scripts/ws_tick_collector_multi.py` with HTTP API

**Testing:**
```bash
# Local test (single collector)
CURRENCY=BTC CONNECTION_ID=0 ENABLE_LIFECYCLE_API=true CONTROL_API_PORT=8000 python3 -m scripts.ws_tick_collector_multi

# Verify API responds
curl http://localhost:8000/status
# Expected: JSON with connection_id, currency, instruments, channel_count
```

---

#### T-012: Implement Subscribe Endpoint
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-011
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-010

**Subtasks:**
1. Implement `api_subscribe(request)` handler in collector
2. Parse JSON body: `data = await request.json()`
3. Extract instruments list: `instruments = data['instruments']`
4. Call `self.subscribe_instruments(instruments)` (new method)
5. Implement `subscribe_instruments()`:
   - Build channels list: `["quote.{inst}", "trades.{inst}"]` for each instrument
   - Send WebSocket message: `{"method": "public/subscribe", "params": {"channels": [...]}}`
   - Add to `self.instruments` list
   - Log subscription
6. Return JSON: `{'status': 'ok', 'subscribed_count': len(instruments)}`
7. Handle errors: WebSocket errors, invalid instrument names

**Deliverables:**
- Working POST /subscribe endpoint

**Testing:**
```bash
curl -X POST http://localhost:8000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"instruments": ["BTC-10NOV25-100000-C"]}'
# Expected: {"status": "ok", "subscribed_count": 1}

# Verify subscription in collector logs
# Expected: "Subscribed to 1 new instruments"
```

---

#### T-013: Implement Unsubscribe Endpoint
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-011
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-011

**Subtasks:**
1. Implement `api_unsubscribe(request)` handler in collector
2. Parse JSON body: `data = await request.json()`
3. Extract instruments list: `instruments = data['instruments']`
4. Call `self.unsubscribe_instruments(instruments)` (new method)
5. Implement `unsubscribe_instruments()`:
   - Build channels list: `["quote.{inst}", "trades.{inst}"]`
   - Send WebSocket message: `{"method": "public/unsubscribe", "params": {"channels": [...]}}`
   - Remove from `self.instruments` list
   - Log unsubscription
6. Return JSON: `{'status': 'ok', 'unsubscribed_count': len(instruments)}`
7. Handle errors: WebSocket errors, instrument not in list

**Deliverables:**
- Working POST /unsubscribe endpoint

**Testing:**
```bash
curl -X POST http://localhost:8000/unsubscribe \
  -H "Content-Type: application/json" \
  -d '{"instruments": ["BTC-10NOV25-100000-C"]}'
# Expected: {"status": "ok", "unsubscribed_count": 1}

# Verify unsubscription in collector logs
# Expected: "Unsubscribed from 1 expired instruments"
```

---

#### T-014: Implement Status Endpoint
**Priority:** P2 - MEDIUM
**Estimated Time:** 15 minutes
**Dependencies:** T-011
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-012

**Subtasks:**
1. Implement `api_status(request)` handler in collector
2. Build response dict:
   - `connection_id`: self.connection_id
   - `currency`: self.currency
   - `instruments`: self.instruments (full list)
   - `channel_count`: len(self.instruments) * 2
3. Return JSON: `web.json_response(response_data)`

**Deliverables:**
- Working GET /status endpoint

**Testing:**
```bash
curl http://localhost:8000/status
# Expected: {"connection_id": 0, "currency": "BTC", "instruments": [...], "channel_count": 500}
```

---

### PHASE 4: FULL AUTOMATION

#### T-015: Implement Periodic Refresh Loop
**Priority:** P1 - HIGH
**Estimated Time:** 1 hour
**Dependencies:** T-009, T-012, T-013
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-013

**Subtasks:**
1. Implement `periodic_refresh(interval_sec=300)` method in lifecycle manager
2. Main loop structure:
   ```python
   while True:
       try:
           for currency in ['BTC', 'ETH']:
               await self.sync_instrument_metadata(currency)
               for connection_id in range(num_connections[currency]):
                   changes = await self.calculate_subscription_changes(...)
                   if changes['subscribe']:
                       await self.send_subscribe_request(connection_id, changes['subscribe'])
                   if changes['unsubscribe']:
                       await self.send_unsubscribe_request(connection_id, changes['unsubscribe'])
                   await self.log_lifecycle_event(...)
           await asyncio.sleep(interval_sec)
       except Exception as e:
           logger.error(f"Error in periodic refresh: {e}")
           await asyncio.sleep(60)  # Short retry on error
   ```
3. Implement `send_subscribe_request(connection_id, instruments)`:
   - Get collector URL from env vars
   - HTTP POST to collector `/subscribe` endpoint
   - Handle HTTP errors (retry 3 times)
4. Implement `send_unsubscribe_request(connection_id, instruments)`:
   - GET collector URL from env vars
   - HTTP POST to collector `/unsubscribe` endpoint
   - Handle HTTP errors (retry 3 times)
5. Add comprehensive logging (debug level for details, info level for summary)
6. Integration test: run for 10 minutes, verify refresh cycles

**Deliverables:**
- Working `periodic_refresh()` method
- Fully functional lifecycle manager

**Testing:**
```python
# Integration test (10 minutes)
lifecycle_manager = OptionLifecycleManager(...)
await lifecycle_manager.periodic_refresh(interval_sec=300)

# Verify lifecycle events logged
events = await db.fetch("SELECT * FROM lifecycle_events WHERE timestamp > NOW() - INTERVAL '15 minutes'")
assert len(events) >= 2  # At least 2 sync cycles (one per currency)
```

---

#### T-016: Add Lifecycle Manager to Docker Compose
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-015
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-014

**Subtasks:**
1. Modify `docker-compose-multi-conn.yml`
2. Add `lifecycle-manager` service:
   - image: same as collectors (shared Dockerfile)
   - command: `python -m scripts.lifecycle_manager`
   - depends_on: timescaledb (service_healthy)
   - restart: unless-stopped
   - environment variables:
     - DATABASE_URL
     - REFRESH_INTERVAL_SEC=300
     - EXPIRY_BUFFER_MINUTES=5
     - BTC_COLLECTOR_0_URL=http://btc-options-0:8000
     - BTC_COLLECTOR_1_URL=http://btc-options-1:8001
     - BTC_COLLECTOR_2_URL=http://btc-options-2:8002
     - ETH_COLLECTOR_0_URL=http://eth-options-0:8003
     - ETH_COLLECTOR_1_URL=http://eth-options-1:8004
     - ETH_COLLECTOR_2_URL=http://eth-options-2:8005
     - ETH_COLLECTOR_3_URL=http://eth-options-3:8006
   - volumes: ./logs:/app/logs
   - networks: crypto_net
   - resources: memory limit 512M, reservation 256M
3. Test locally: `docker-compose -f docker-compose-multi-conn.yml up lifecycle-manager`

**Deliverables:**
- Updated `docker-compose-multi-conn.yml` with lifecycle-manager service

**Testing:**
```bash
docker-compose -f docker-compose-multi-conn.yml up -d lifecycle-manager
docker-compose -f docker-compose-multi-conn.yml ps lifecycle-manager
# Expected: STATUS = Up

docker-compose -f docker-compose-multi-conn.yml logs lifecycle-manager | head -50
# Expected: log entries showing periodic refresh starting
```

---

#### T-017: Expose Collector Control API Ports
**Priority:** P1 - HIGH
**Estimated Time:** 20 minutes
**Dependencies:** T-011
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-015

**Subtasks:**
1. Modify `docker-compose-multi-conn.yml`
2. For each collector service (btc-options-0 through eth-options-3):
   - Add `ports` section mapping container port to host port
   - btc-options-0: "8000:8000"
   - btc-options-1: "8001:8001"
   - btc-options-2: "8002:8002"
   - eth-options-0: "8003:8003"
   - eth-options-1: "8004:8004"
   - eth-options-2: "8005:8005"
   - eth-options-3: "8006:8006"
3. Add environment variable: `CONTROL_API_PORT={port}` for each collector
4. Add environment variable: `ENABLE_LIFECYCLE_API=true` for each collector
5. Test: `docker-compose -f docker-compose-multi-conn.yml up -d`

**Deliverables:**
- Updated `docker-compose-multi-conn.yml` with exposed ports

**Testing:**
```bash
# Rebuild and restart collectors
docker-compose -f docker-compose-multi-conn.yml up -d --build

# Test each collector API
for port in 8000 8001 8002 8003 8004 8005 8006; do
  curl http://localhost:$port/status
done
# Expected: 7 JSON responses
```

---

### PHASE 5: END-TO-END TESTING

#### T-018: Execute Expiry Simulation Test
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-016, T-017
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-016

**Steps:**
1. Manually set expiry for test instrument:
   ```sql
   UPDATE instrument_metadata
   SET expiration_timestamp = (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT + 120000
   WHERE instrument_name = 'BTC-10NOV25-100000-C';
   ```
2. Wait 3 minutes (past 5-minute buffer)
3. Check lifecycle_events for unsubscribe event:
   ```sql
   SELECT * FROM lifecycle_events
   WHERE instrument_name = 'BTC-10NOV25-100000-C' AND event_type = 'unsubscribed';
   ```
4. Verify collector logs show unsubscription
5. Verify instrument marked inactive:
   ```sql
   SELECT is_active, expired_at FROM instrument_metadata
   WHERE instrument_name = 'BTC-10NOV25-100000-C';
   ```

**Pass Criteria:**
- lifecycle_events shows unsubscribed event
- instrument_metadata shows is_active = FALSE
- Collector logs show unsubscription message

---

#### T-019: Execute New Instrument Test
**Priority:** P1 - HIGH
**Estimated Time:** 30 minutes
**Dependencies:** T-016, T-017
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-017

**Steps:**
1. Insert test instrument:
   ```sql
   INSERT INTO instrument_metadata (instrument_name, currency, kind, expiration_timestamp, is_active)
   VALUES ('BTC-TEST-NEW-105000-C', 'BTC', 'option',
           (EXTRACT(EPOCH FROM NOW() + INTERVAL '7 days') * 1000)::BIGINT, TRUE);
   ```
2. Wait 6 minutes (one refresh cycle)
3. Check lifecycle_events for subscribed event
4. Verify collector logs show subscription
5. Check for quote/trade data:
   ```sql
   SELECT COUNT(*) FROM btc_option_quotes
   WHERE instrument_name = 'BTC-TEST-NEW-105000-C' AND timestamp > NOW() - INTERVAL '5 minutes';
   ```

**Pass Criteria:**
- lifecycle_events shows subscribed event
- Collector logs show subscription message
- Quote data being collected (if instrument exists on Deribit)

---

#### T-020: Execute Container Restart Test
**Priority:** P2 - MEDIUM
**Estimated Time:** 20 minutes
**Dependencies:** T-016, T-017
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-018

**Steps:**
1. Restart lifecycle manager:
   ```bash
   docker-compose -f docker-compose-multi-conn.yml restart lifecycle-manager
   ```
2. Check logs for successful restart
3. Restart collector:
   ```bash
   docker-compose -f docker-compose-multi-conn.yml restart btc-options-0
   ```
4. Verify collector queries instrument_metadata
5. Verify collector subscribes only to active instruments

**Pass Criteria:**
- Lifecycle manager resumes periodic refresh
- Collector subscribes to correct instruments
- No errors in logs

---

#### T-021: Execute 24-Hour Stability Test
**Priority:** P1 - HIGH
**Estimated Time:** 24 hours (mostly waiting)
**Dependencies:** T-016, T-017, T-018, T-019, T-020
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-019

**Steps:**
1. Deploy full system (lifecycle manager + all collectors)
2. Let run for 24 hours without intervention
3. Monitor coverage every hour:
   ```sql
   SELECT currency, COUNT(DISTINCT instrument_name) as subscribed_count
   FROM (
       SELECT instrument_name, 'BTC' as currency FROM btc_option_quotes WHERE timestamp > NOW() - INTERVAL '1 hour'
       UNION
       SELECT instrument_name, 'ETH' as currency FROM eth_option_quotes WHERE timestamp > NOW() - INTERVAL '1 hour'
   ) active
   GROUP BY currency;
   ```
4. Check lifecycle_events for regular sync activity (every 5 minutes)
5. Check container logs for errors
6. Check memory usage: `docker stats --no-stream`

**Pass Criteria:**
- Coverage >= 95% throughout 24 hours
- No errors in logs
- Memory usage stable (<512MB for lifecycle manager)
- lifecycle_events shows 288 sync cycles (24 hours × 12 cycles/hour)

---

### PHASE 6: MONITORING & OBSERVABILITY

#### T-022: Create Grafana Dashboard
**Priority:** P2 - MEDIUM
**Estimated Time:** 1 hour
**Dependencies:** AC-002 (lifecycle_events table)
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-020

**Steps:**
1. Access Grafana: http://localhost:3000
2. Create new dashboard: "Options Lifecycle Management"
3. Add Panel 1: Coverage over time
   - Query: `SELECT ... FROM instrument_metadata WHERE is_active = TRUE`
   - Visualization: Time series
4. Add Panel 2: Subscription changes per hour
   - Query: `SELECT event_type, COUNT(*) FROM lifecycle_events GROUP BY event_type`
   - Visualization: Bar chart
5. Add Panel 3: Expired instruments count
   - Query: `SELECT COUNT(*) FROM instrument_metadata WHERE expired_at > NOW() - INTERVAL '24 hours'`
   - Visualization: Stat
6. Add Panel 4: Lifecycle manager status
   - Query: `SELECT MAX(timestamp) FROM lifecycle_events`
   - Visualization: Stat (time since last refresh)
7. Save dashboard

**Deliverables:**
- Grafana dashboard (manual configuration, optional JSON export)

---

#### T-023: Configure Coverage Alert
**Priority:** P2 - MEDIUM
**Estimated Time:** 30 minutes
**Dependencies:** T-022
**Assigned to:** TBD

**Acceptance Criteria:**
- AC-021

**Steps:**
1. In Grafana, create Alert Rule
2. Name: "Options Coverage Below 95%"
3. Query:
   ```sql
   WITH active_subscriptions AS (
       SELECT currency, COUNT(DISTINCT instrument_name) as subscribed
       FROM (...) GROUP BY currency
   ),
   total_instruments AS (
       SELECT currency, COUNT(*) as total
       FROM instrument_metadata WHERE is_active = TRUE GROUP BY currency
   )
   SELECT a.currency, (a.subscribed::float / t.total) * 100 as coverage_pct
   FROM active_subscriptions a JOIN total_instruments t ON a.currency = t.currency;
   ```
4. Condition: coverage_pct < 95
5. Evaluate every: 5 minutes
6. Alert notification: (configure email/Slack/webhook as needed)
7. Test alert: manually mark 10% instruments inactive, verify alert triggers

**Deliverables:**
- Configured alert rule in Grafana

---

## DEPENDENCIES GRAPH

```
T-000 (Schema Fix) ✅
  ↓
[PHASE 1: DATABASE]
  T-001 (Create Schema File) → T-002 (Apply Migration)
                                   ↓
                                T-003 (Population Script) → T-004 (Run Population)
                                   ↓
[PHASE 2: LIFECYCLE CORE]
  T-005 (Skeleton) → T-006 (Fetch Instruments)
                       ↓
                    T-007 (Detect Expiries)
                       ↓
                    T-008 (Sync Metadata) → T-009 (Calculate Changes)
                       ↓
  T-010 (Log Events) ────────────────────┘
                       ↓
[PHASE 3: COLLECTOR API]
  T-011 (Control API) → T-012 (Subscribe Endpoint)
                      → T-013 (Unsubscribe Endpoint)
                      → T-014 (Status Endpoint)
                       ↓
[PHASE 4: AUTOMATION]
  T-015 (Periodic Refresh) [depends on T-009, T-012, T-013]
     ↓
  T-016 (Add to Docker Compose) [depends on T-015]
     ↓
  T-017 (Expose Ports) [depends on T-011]
     ↓
[PHASE 5: TESTING]
  T-018 (Expiry Test) [depends on T-016, T-017]
  T-019 (New Instrument Test) [depends on T-016, T-017]
  T-020 (Restart Test) [depends on T-016, T-017]
     ↓
  T-021 (24-Hour Stability) [depends on T-018, T-019, T-020]
     ↓
[PHASE 6: MONITORING]
  T-022 (Grafana Dashboard) → T-023 (Alert Configuration)
```

---

## CRITICAL PATH SEQUENCE

1. **✅ T-000** (5 min) - COMPLETED
2. **T-001** → **T-002** → **T-003** → **T-004** (2 hours total)
3. **T-005** → **T-006** → **T-007** → **T-008** → **T-009** (3 hours total)
4. **T-010** (parallel, 20 min)
5. **T-011** → **T-012** → **T-013** → **T-014** (2 hours total)
6. **T-015** (1 hour)
7. **T-016** + **T-017** (50 min total, parallel)
8. **T-018** + **T-019** + **T-020** (1.5 hours total, parallel)
9. **T-021** (24 hours, unattended)
10. **T-022** + **T-023** (1.5 hours total)

**Total Active Development Time:** 10 hours
**Total Wait Time (24-hour test):** 24 hours
**Total Calendar Time:** ~2 days

---

## RESOURCE ALLOCATION

### Developer Skills Required
- **Python async/await:** T-005 through T-015 (lifecycle manager)
- **Database (PostgreSQL/TimescaleDB):** T-001 through T-004, T-008
- **HTTP APIs (aiohttp):** T-011 through T-014
- **Docker/Docker Compose:** T-016, T-017
- **Testing/QA:** T-018 through T-021
- **Grafana/Monitoring:** T-022, T-023

### Recommended Assignment
- **Developer 1 (Backend):** T-001 through T-010, T-015, T-016 (lifecycle manager core + deployment)
- **Developer 2 (API/Integration):** T-011 through T-014, T-017 (collector API + Docker config)
- **QA Engineer:** T-018 through T-021 (testing)
- **DevOps/Monitoring:** T-022, T-023 (observability)

**Parallel Work Possible:**
- T-005 through T-010 (lifecycle manager) can run parallel to T-011 through T-014 (collector API)
- This reduces timeline from 10 hours → ~6 hours with 2 developers

---

## ROLLOUT PLAN

### Stage 1: Local Development & Testing (Day 1)
- Complete T-001 through T-017
- Deploy to local Docker environment
- Execute T-018, T-019, T-020 (integration tests)
- **Checkpoint:** All integration tests pass

### Stage 2: Production Deployment (Day 1 Evening)
- Deploy to NAS production environment
- Start T-021 (24-hour stability test)
- Monitor closely for first 2 hours
- **Checkpoint:** No errors in first 2 hours

### Stage 3: Monitoring & Observability (Day 2)
- Complete T-022, T-023 (Grafana dashboard + alerts)
- Continue monitoring T-021 (24-hour test)
- **Checkpoint:** Coverage stable at 95%+ for 24 hours

### Stage 4: Handoff to Operations (Day 3)
- Document operational procedures
- Train user on monitoring dashboard
- Create runbook for common issues
- **Final Checkpoint:** System running autonomously

---

## RISK MITIGATION

### Risk 1: API Rate Limiting
**Probability:** Low
**Impact:** Medium
**Mitigation:** Built into design (1 API call per 5 minutes = 0.003 req/sec, well below 20 req/sec limit)
**Fallback:** Increase refresh interval to 10 minutes

### Risk 2: Collector API Downtime
**Probability:** Low
**Impact:** Medium
**Mitigation:** Retry logic in lifecycle manager (3 retries with exponential backoff)
**Fallback:** Manual restart of affected collector

### Risk 3: Database Connection Loss
**Probability:** Low
**Impact:** High
**Mitigation:** Connection pooling + automatic reconnection in asyncpg
**Fallback:** Lifecycle manager restart (Docker auto-restart policy)

### Risk 4: Memory Leak in Lifecycle Manager
**Probability:** Low
**Impact:** High
**Mitigation:** Strict resource limits (512MB memory limit in Docker)
**Detection:** Monitor memory usage in T-021 (24-hour test)
**Fallback:** Scheduled daily restart (if leak confirmed)

---

## SUCCESS CRITERIA SUMMARY

### Immediate (Post-Deployment)
- ✅ Schema fix applied (AC-000) - COMPLETED
- [ ] All 21 acceptance criteria met (AC-001 through AC-021)
- [ ] Lifecycle manager container running
- [ ] All collector APIs responding
- [ ] No errors in logs

### 24 Hours
- [ ] Coverage >= 95% for BTC and ETH
- [ ] lifecycle_events shows 288 sync cycles
- [ ] No subscription attempts to expired instruments
- [ ] Memory usage stable (<512MB)

### 7 Days
- [ ] Coverage stable at 95%+ throughout week
- [ ] Automatic expiry handling working (daily/weekly expiries)
- [ ] New instruments automatically detected and subscribed
- [ ] Zero manual interventions required

---

**Total Tasks:** 23 (1 completed, 22 pending)
**Critical Path:** 10 hours active development + 24 hours testing
**Calendar Time:** 2-3 days to full production deployment
