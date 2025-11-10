---
doc_type: smoke_plan
owner: orchestrator
updated: 2025-10-21
links:
  - ../release/Acceptance-Criteria.md
  - ../../CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md
---

# Smoke Plan — Crypto Data Infrastructure

## Purpose

Fast, high-signal end-to-end validation to catch obvious breakages before deployment. Each smoke test maps to specific acceptance criteria and can be executed with a single copy-paste command.

## Environment Setup

**Local Development:**
- Python 3.10+
- PostgreSQL 14+ with TimescaleDB
- Database: `crypto_data`
- Environment variables: None required (public API)

**Commands:**
```bash
# Activate virtual environment
source venv/bin/activate

# Set working directory
cd /Users/doghead/PycharmProjects/datadownloader
```

---

## Phase 0 Smoke Tests

### SMK-001: API Connectivity Check

**Purpose:** Verify Deribit public API is accessible

**Pre-requisites:**
- Python 3.10+ installed
- Internet connection

**Steps:**
```bash
python -m scripts.test_connectivity
```

**Expected Output:**
```json
{
  "status": "ok",
  "api_version": "2.0",
  "timestamp": 1698765432000
}
```

**Pass Criteria:**
- Exit code 0
- Response contains `"status": "ok"`
- HTTP status code 200

**Evidence:**
- Save JSON response to `/tests/evidence/SMK-001-connectivity.json`

**ACs Covered:** AC-001

**Estimated Runtime:** 5 seconds

---

### SMK-002: Database Schema Validation

**Purpose:** Verify all tables created as hypertables with correct structure

**Pre-requisites:**
- PostgreSQL 14+ with TimescaleDB installed
- Database `crypto_data` exists
- Schema executed: `psql -U postgres -d crypto_data -f schema.sql`

**Steps:**
```bash
psql -U postgres -d crypto_data -c "SELECT * FROM timescaledb_information.hypertables;"
```

**Expected Output:**
```
 hypertable_schema | hypertable_name  | owner    | num_dimensions | num_chunks | ...
-------------------+------------------+----------+----------------+------------+-----
 public            | perpetuals_ohlcv | postgres |              1 |          0 | ...
 public            | futures_ohlcv    | postgres |              1 |          0 | ...
 public            | options_ohlcv    | postgres |              1 |          0 | ...
 public            | options_greeks   | postgres |              1 |          0 | ...
 public            | funding_rates    | postgres |              1 |          0 | ...
 public            | index_prices     | postgres |              1 |          0 | ...
(6 rows)
```

**Pass Criteria:**
- 6 hypertables present
- All hypertables have `num_dimensions = 1` (timestamp)
- No errors

**Evidence:**
- Save query output to `/tests/evidence/SMK-002-hypertables.txt`

**ACs Covered:** AC-002

**Estimated Runtime:** 2 seconds

---

### SMK-003: Log File Rotation Check

**Purpose:** Verify logging configured with file rotation (10 MB max per file)

**Pre-requisites:**
- Logging configuration in `logging_config.py`
- `/logs/` directory exists

**Steps:**
```bash
# Generate 50 MB of test logs
python -m scripts.generate_test_logs --size 50

# Check for rotated files
ls -lh logs/
```

**Expected Output:**
```
-rw-r--r-- 1 user staff  10M Oct 21 14:30 app.log
-rw-r--r-- 1 user staff  10M Oct 21 14:29 app.log.1
-rw-r--r-- 1 user staff  10M Oct 21 14:28 app.log.2
-rw-r--r-- 1 user staff  10M Oct 21 14:27 app.log.3
-rw-r--r-- 1 user staff  10M Oct 21 14:26 app.log.4
```

**Pass Criteria:**
- 5 log files present (app.log + 4 backups)
- Each file ≤ 10 MB
- Oldest file is app.log.4 (5th backup discarded)

**Evidence:**
- Screenshot of `ls -lh logs/` output
- Path: `/tests/evidence/SMK-003-log-rotation.png`

**ACs Covered:** AC-003

**Estimated Runtime:** 10 seconds

---

## Phase 1 Smoke Tests

### SMK-004: Perpetuals Row Count Check

**Purpose:** Verify complete perpetuals backfill (no missing data)

**Pre-requisites:**
- T-006 complete (BTC-PERPETUAL backfilled)
- T-007 complete (ETH-PERPETUAL backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT
    instrument,
    COUNT(*) AS row_count,
    MIN(timestamp) AS earliest,
    MAX(timestamp) AS latest
  FROM perpetuals_ohlcv
  GROUP BY instrument;
"
```

**Expected Output:**
```
   instrument   | row_count | earliest            | latest
----------------+-----------+---------------------+---------------------
 BTC-PERPETUAL  | 2365200   | 2016-12-01 00:00:00 | 2025-10-18 23:59:00
 ETH-PERPETUAL  | 2365200   | 2017-01-01 00:00:00 | 2025-10-18 23:59:00
(2 rows)
```

**Pass Criteria:**
- BTC-PERPETUAL: ~2,365,200 rows (±1%)
- ETH-PERPETUAL: ~2,365,200 rows (±1%)
- Earliest/latest dates match expected range

**Evidence:**
- Save query output to `/tests/evidence/SMK-004-row-count.txt`

**ACs Covered:** AC-004

**Estimated Runtime:** 3 seconds

---

### SMK-005: Gap Detection Check

**Purpose:** Verify no gaps >5 minutes in perpetuals data

**Pre-requisites:**
- T-006, T-007 complete (perpetuals backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT
    instrument,
    timestamp,
    LAG(timestamp) OVER (PARTITION BY instrument ORDER BY timestamp) AS prev_timestamp,
    timestamp - LAG(timestamp) OVER (PARTITION BY instrument ORDER BY timestamp) AS gap
  FROM perpetuals_ohlcv
  WHERE timestamp - LAG(timestamp) OVER (PARTITION BY instrument ORDER BY timestamp) > INTERVAL '5 minutes'
  ORDER BY gap DESC
  LIMIT 10;
"
```

**Expected Output:**
```
 instrument | timestamp | prev_timestamp | gap
------------+-----------+----------------+-----
(0 rows)
```

**Pass Criteria:**
- 0 gaps >5 minutes
- OR: Documented exceptions (exchange maintenance) listed in report

**Evidence:**
- Save query output to `/tests/evidence/SMK-005-gaps.txt`
- If gaps found, save detailed report with justification

**ACs Covered:** AC-004

**Estimated Runtime:** 5 seconds

---

### SMK-006: OHLCV Sanity Check

**Purpose:** Verify no invalid OHLCV relationships (high < low, close out of range)

**Pre-requisites:**
- T-006, T-007 complete (perpetuals backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT COUNT(*) AS violations
  FROM perpetuals_ohlcv
  WHERE high < low OR close < low OR close > high OR open < low OR open > high;
"
```

**Expected Output:**
```
 violations
------------
          0
(1 row)
```

**Pass Criteria:**
- 0 violations
- All OHLCV data internally consistent

**Evidence:**
- Save query output to `/tests/evidence/SMK-006-sanity.txt`

**ACs Covered:** AC-005

**Estimated Runtime:** 3 seconds

---

### SMK-007: Perpetuals Storage Check

**Purpose:** Verify storage usage ≤ 150 MB

**Pre-requisites:**
- T-006, T-007 complete (perpetuals backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT pg_size_pretty(pg_total_relation_size('perpetuals_ohlcv')) AS storage_size;
"
```

**Expected Output:**
```
 storage_size
--------------
 145 MB
(1 row)
```

**Pass Criteria:**
- Storage ≤ 150 MB
- If exceeds, investigate compression options

**Evidence:**
- Save query output to `/tests/evidence/SMK-007-storage.txt`

**ACs Covered:** AC-006

**Estimated Runtime:** 2 seconds

---

## Phase 2 Smoke Tests (Future)

### SMK-008: Futures Contract Count Check

**Purpose:** Verify 150+ unique futures contracts backfilled

**Pre-requisites:**
- T-011, T-012 complete (futures backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT COUNT(DISTINCT instrument) AS contract_count
  FROM futures_ohlcv;
"
```

**Expected:** ≥ 150 contracts

**ACs Covered:** AC-007

---

### SMK-009: Basis Spread Validation

**Purpose:** Verify basis spread computed for all overlapping timestamps

**Pre-requisites:**
- T-013 complete (basis spread computed)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT
    COUNT(*) AS total_rows,
    COUNT(basis_spread) AS rows_with_basis,
    100.0 * COUNT(basis_spread) / COUNT(*) AS coverage_pct
  FROM basis_spreads;
"
```

**Expected:** coverage_pct = 100.0

**ACs Covered:** AC-008

---

### SMK-010: Futures Storage Check

**Purpose:** Verify storage usage ≤ 1.5 GB

**Pre-requisites:**
- T-011, T-012 complete (futures backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT pg_size_pretty(pg_total_relation_size('futures_ohlcv')) AS storage_size;
"
```

**Expected:** ≤ 1.5 GB

**ACs Covered:** AC-009

---

## Phase 3 Smoke Tests (Future)

### SMK-011: Active Options Coverage Check

**Purpose:** Verify all active options have OHLCV data

**Pre-requisites:**
- T-016, T-017 complete (options backfilled)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT COUNT(DISTINCT instrument) AS active_options
  FROM options_ohlcv
  WHERE expiry_date > NOW();
"
```

**Expected:** ≥ 2000 active options

**ACs Covered:** AC-010

---

### SMK-012: Implied Volatility Coverage Check

**Purpose:** Verify 95%+ strikes have valid IV

**Pre-requisites:**
- T-018 complete (IV computed)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT
    100.0 * COUNT(CASE WHEN implied_volatility IS NOT NULL THEN 1 END) / COUNT(*) AS iv_coverage_pct
  FROM options_ohlcv;
"
```

**Expected:** ≥ 95.0

**ACs Covered:** AC-011

---

### SMK-013: Volatility Surface Visualization

**Purpose:** Verify vol surface heatmap generated

**Pre-requisites:**
- T-019 complete (vol surface built)

**Steps:**
```bash
python -m scripts.plot_vol_surface --date 2025-10-18 --output tests/evidence/SMK-013-vol-surface.png
```

**Expected:** PNG file created with smooth vol smile

**ACs Covered:** AC-012

---

## Phase 4 Smoke Tests (Future)

### SMK-014: Greeks Delta Range Check

**Purpose:** Verify delta values within valid range (calls: [0,1], puts: [-1,0])

**Pre-requisites:**
- T-022 complete (Greeks computed)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT COUNT(*) AS violations
  FROM options_greeks
  WHERE (option_type = 'call' AND (delta < 0 OR delta > 1))
     OR (option_type = 'put' AND (delta < -1 OR delta > 0));
"
```

**Expected:** 0 violations

**ACs Covered:** AC-013

---

### SMK-015: Greeks Storage Check

**Purpose:** Verify storage usage ≤ 2 GB

**Pre-requisites:**
- T-024 complete (Greeks stored)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT pg_size_pretty(pg_total_relation_size('options_greeks')) AS storage_size;
"
```

**Expected:** ≤ 2 GB

**ACs Covered:** AC-015

---

### SMK-016: Greeks RMSE Validation

**Purpose:** Verify computed Greeks vs Deribit live Greeks (RMSE < 5%)

**Pre-requisites:**
- T-023 complete (Greeks validated)

**Steps:**
```bash
python -m scripts.validate_greeks --days 30 --output tests/evidence/SMK-016-rmse.csv
```

**Expected:**
- delta_rmse < 0.05
- gamma_rmse < 0.05
- vega_rmse < 0.05
- theta_rmse < 0.05

**ACs Covered:** AC-014

---

## Phase 5 Smoke Tests (Future)

### SMK-017: Real-Time Collector Uptime Check

**Purpose:** Verify 24/7 collector uptime ≥ 99.9% over 7 days

**Pre-requisites:**
- T-028 complete (systemd service deployed)

**Steps:**
```bash
# Check systemd service status
sudo systemctl status crypto-collector.service

# Check uptime from Healthchecks.io dashboard
curl https://healthchecks.io/api/v1/checks/UUID | jq '.status'
```

**Expected:** status = "up", uptime ≥ 99.9%

**ACs Covered:** AC-016

---

### SMK-018: Data Latency Check

**Purpose:** Verify median latency < 5 minutes

**Pre-requisites:**
- T-027 complete (real-time collector running)

**Steps:**
```bash
psql -U postgres -d crypto_data -c "
  SELECT
    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_seconds) AS median_latency,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_seconds) AS p95_latency
  FROM collection_metrics
  WHERE timestamp > NOW() - INTERVAL '24 hours';
"
```

**Expected:** median_latency < 300 seconds (5 minutes)

**ACs Covered:** AC-017

---

### SMK-019: Backup Verification

**Purpose:** Verify daily backups present in Backblaze B2

**Pre-requisites:**
- T-030 complete (backups configured)

**Steps:**
```bash
b2 ls crypto-backups | tail -30
```

**Expected:** 30 backup files (last 30 days)

**ACs Covered:** AC-019

---

### SMK-020: Healthchecks.io Heartbeat

**Purpose:** Verify heartbeat active (pings every 15 minutes)

**Pre-requisites:**
- T-029 complete (Healthchecks.io configured)

**Steps:**
```bash
curl https://healthchecks.io/api/v1/checks/UUID | jq '.last_ping'
```

**Expected:** last_ping < 15 minutes ago

**ACs Covered:** AC-018

---

## Smoke Test Execution Order (Phase 0-1)

```
1. SMK-001 (API connectivity)          → 5 sec
2. SMK-002 (Database schema)           → 2 sec
3. SMK-003 (Log rotation)              → 10 sec
4. SMK-004 (Row count)                 → 3 sec
5. SMK-005 (Gap detection)             → 5 sec
6. SMK-006 (OHLCV sanity)              → 3 sec
7. SMK-007 (Storage check)             → 2 sec
-------------------------------------------
TOTAL RUNTIME (Phase 0-1): 30 seconds
```

## Smoke Test Pass Rate Target

- **Phase 0:** 100% pass rate required (SMK-001, SMK-002, SMK-003)
- **Phase 1:** 100% pass rate required (SMK-004, SMK-005, SMK-006, SMK-007)
- **Overall:** Zero tolerance for failures; investigate and fix immediately

## Evidence Collection

All smoke test evidence stored in `/tests/evidence/` with naming convention:
- `SMK-XXX-<description>.<ext>`
- Example: `SMK-001-connectivity.json`

## Smoke Test Automation (Future)

Create master smoke runner:
```bash
#!/bin/bash
# Run all Phase 0-1 smoke tests

echo "Running Phase 0 Smoke Tests..."
python -m scripts.test_connectivity > tests/evidence/SMK-001-connectivity.json
psql -U postgres -d crypto_data -f tests/smoke/SMK-002-schema.sql > tests/evidence/SMK-002-hypertables.txt
python -m scripts.generate_test_logs --size 50 && ls -lh logs/ > tests/evidence/SMK-003-log-rotation.txt

echo "Running Phase 1 Smoke Tests..."
psql -U postgres -d crypto_data -f tests/smoke/SMK-004-row-count.sql > tests/evidence/SMK-004-row-count.txt
psql -U postgres -d crypto_data -f tests/smoke/SMK-005-gaps.sql > tests/evidence/SMK-005-gaps.txt
psql -U postgres -d crypto_data -f tests/smoke/SMK-006-sanity.sql > tests/evidence/SMK-006-sanity.txt
psql -U postgres -d crypto_data -f tests/smoke/SMK-007-storage.sql > tests/evidence/SMK-007-storage.txt

echo "Smoke tests complete. Check /tests/evidence/ for results."
```

---

**End of Smoke Plan Document**

This orchestration output structures work and verification. It is not trading, legal, accounting, or tax advice. Handle secrets securely and follow your organization's policies.
