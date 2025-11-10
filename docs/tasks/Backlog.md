---
doc_type: backlog
owner: orchestrator
updated: 2025-10-21
links:
  - ../../CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md
  - ../release/Acceptance-Criteria.md
---

# Backlog — Crypto Data Infrastructure (Phase 0-1 Focus)

## Prioritization Strategy

**Phase 0-1 First:** Prove the pipeline works end-to-end with perpetuals backfill before scaling to futures/options.

## Phase 0: Prerequisites (Critical Path)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-001  | Install Python 3.10+, PostgreSQL, TimescaleDB | ENG  | S      | –          | AC-002      | Ready   | TBD   |
| T-002  | Create database schema (hypertables)   | ENG  | S      | T-001      | AC-002      | Blocked | TBD   |
| T-003  | Test Deribit API connectivity          | ENG  | XS     | –          | AC-001      | Ready   | TBD   |
| T-004  | Set up error logging + file rotation   | ENG  | S      | –          | AC-003      | Ready   | TBD   |

**Phase 0 Acceptance Gate:** All 4 tasks complete → SMK-001, SMK-002, SMK-003 pass

---

## Phase 1: Perpetuals Backfill (Critical Path)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-005  | Implement `backfill_perpetuals.py` script | ENG | M      | T-002, T-003 | AC-004, AC-005, AC-006 | Blocked | TBD |
| T-006  | Backfill BTC-PERPETUAL (2016-2025)     | ENG  | S      | T-005      | AC-004, AC-006 | Blocked | TBD   |
| T-007  | Backfill ETH-PERPETUAL (2017-2025)     | ENG  | S      | T-005      | AC-004, AC-006 | Blocked | TBD   |
| T-008  | Run data quality checks (gaps, outliers) | QA | S      | T-006, T-007 | AC-004, AC-005 | Blocked | TBD |

**Phase 1 Acceptance Gate:** All 4 tasks complete → SMK-004, SMK-005, SMK-006, SMK-007 pass

---

## Phase 2: Futures Backfill (Future Work)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-009  | Fetch list of all historical futures  | ENG  | S      | T-008      | AC-007      | Blocked | TBD   |
| T-010  | Implement `backfill_futures.py` (parallel) | ENG | M    | T-009      | AC-007, AC-009 | Blocked | TBD |
| T-011  | Backfill all BTC futures (2019-2025)   | ENG  | M      | T-010      | AC-007      | Blocked | TBD   |
| T-012  | Backfill all ETH futures (2020-2025)   | ENG  | M      | T-010      | AC-007      | Blocked | TBD   |
| T-013  | Compute basis spread (futures - perp)  | ENG  | S      | T-011, T-012 | AC-008    | Blocked | TBD   |

**Phase 2 Acceptance Gate:** All 5 tasks complete → SMK-008, SMK-009, SMK-010 pass

---

## Phase 3: Options Backfill (Future Work)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-014  | Fetch list of all active options       | ENG  | S      | T-013      | AC-010      | Blocked | TBD   |
| T-015  | Implement `backfill_options.py` (strike filter) | ENG | M | T-014 | AC-010 | Blocked | TBD |
| T-016  | Backfill BTC options (2024-2025, active) | ENG | L    | T-015      | AC-010      | Blocked | TBD   |
| T-017  | Backfill ETH options (2024-2025, active) | ENG | L    | T-015      | AC-010      | Blocked | TBD   |
| T-018  | Compute implied volatility (Newton-Raphson) | ENG | M | T-016, T-017 | AC-011 | Blocked | TBD |
| T-019  | Build volatility surface (strike vs DTE) | ENG | S   | T-018      | AC-012      | Blocked | TBD   |

**Phase 3 Acceptance Gate:** All 6 tasks complete → SMK-011, SMK-012, SMK-013 pass

---

## Phase 4: Historical Greeks (Future Work)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-020  | Implement Black-Scholes Greeks calculator | ENG | M   | T-019      | AC-013, AC-014 | Blocked | TBD |
| T-021  | Fetch risk-free rate proxy (T-bill)    | ENG  | S      | –          | AC-013      | Ready   | TBD   |
| T-022  | Compute Greeks for all options (2022-2025) | ENG | L   | T-020, T-021 | AC-013 | Blocked | TBD |
| T-023  | Validate Greeks vs Deribit (30 days)   | QA   | M      | T-022      | AC-014      | Blocked | TBD   |
| T-024  | Store Greeks in `options_greeks` table | ENG  | S      | T-023      | AC-015      | Blocked | TBD   |

**Phase 4 Acceptance Gate:** All 5 tasks complete → SMK-014, SMK-015, SMK-016 pass

---

## Phase 5: Real-Time Collection (Future Work)

| ID     | Title                                  | Role | Effort | Blocked By | ACs         | Status  | Owner |
|--------|----------------------------------------|------|--------|------------|-------------|---------|-------|
| T-025  | Provision DigitalOcean Droplet (4GB RAM) | ENG | S    | –          | AC-016      | Ready   | TBD   |
| T-026  | Deploy PostgreSQL + TimescaleDB on VPS | ENG  | M      | T-025      | AC-016      | Blocked | TBD   |
| T-027  | Implement `collect_realtime.py` (asyncio) | ENG | L    | T-026      | AC-016, AC-017 | Blocked | TBD |
| T-028  | Set up systemd service for auto-restart | ENG | S     | T-027      | AC-016      | Blocked | TBD   |
| T-029  | Configure Healthchecks.io monitoring   | ENG  | S      | T-028      | AC-018      | Blocked | TBD   |
| T-030  | Set up daily backups to Backblaze B2   | ENG  | M      | T-028      | AC-019      | Blocked | TBD   |

**Phase 5 Acceptance Gate:** All 6 tasks complete → SMK-017, SMK-018, SMK-019, SMK-020 pass

---

## Effort Legend

| Code | Effort      | Time Estimate        | Notes                          |
|------|-------------|----------------------|--------------------------------|
| XS   | Extra Small | < 2 hours            | Quick setup or config          |
| S    | Small       | 2-8 hours (< 1 day)  | Single focused task            |
| M    | Medium      | 1-3 days             | Moderate complexity            |
| L    | Large       | 3-7 days             | Multi-step or complex          |
| XL   | Extra Large | > 1 week             | Major deliverable              |

---

## Task Details (Phase 0-1 Only)

### T-001 — Install Python 3.10+, PostgreSQL, TimescaleDB

**Description:** Set up development environment with required dependencies.

**Acceptance Criteria:** AC-002

**Owner:** ENG

**Effort:** S (4 hours)

**Dependencies:** None

**Deliverables:**
- Python 3.10+ installed and verified: `python3 --version`
- PostgreSQL 14+ installed: `psql --version`
- TimescaleDB extension installed: `SELECT * FROM pg_available_extensions WHERE name = 'timescaledb';`

**Commands:**
```bash
# macOS
brew install python@3.10 postgresql@14
brew install timescaledb

# Ubuntu
sudo apt update
sudo apt install python3.10 postgresql-14 postgresql-14-timescaledb
```

**Evidence:**
- Screenshot of version outputs
- Path: `/tests/evidence/T-001-environment-setup.txt`

**Notes:**
- Ensure PostgreSQL service is running: `brew services start postgresql@14` (macOS) or `sudo systemctl start postgresql` (Linux)

---

### T-002 — Create Database Schema (Hypertables)

**Description:** Execute schema.sql to create all required tables as TimescaleDB hypertables.

**Acceptance Criteria:** AC-002

**Owner:** ENG

**Effort:** S (3 hours)

**Dependencies:** T-001

**Deliverables:**
- `schema.sql` file created (see master plan Section 6.1)
- All 6 tables created: perpetuals_ohlcv, futures_ohlcv, options_ohlcv, options_greeks, funding_rates, index_prices
- All 6 tables converted to hypertables

**Commands:**
```bash
# Create database
createdb -U postgres crypto_data

# Execute schema
psql -U postgres -d crypto_data -f schema.sql

# Verify hypertables
psql -U postgres -d crypto_data -c "SELECT * FROM timescaledb_information.hypertables;"
```

**Evidence:**
- Query output showing 6 hypertables
- Path: `/tests/evidence/T-002-schema-validation.sql`

**Notes:**
- Schema includes primary keys (timestamp, instrument) for efficient time-series queries
- Indexes created on instrument column for filtering

---

### T-003 — Test Deribit API Connectivity

**Description:** Verify Deribit public API is accessible and rate limits are understood.

**Acceptance Criteria:** AC-001

**Owner:** ENG

**Effort:** XS (1 hour)

**Dependencies:** None

**Deliverables:**
- Python script `test_connectivity.py` that calls `/public/test` endpoint
- Successful API response logged

**Commands:**
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

**Evidence:**
- JSON response saved to `/tests/evidence/T-003-connectivity.json`

**Notes:**
- Public API rate limit: 20 req/sec
- No authentication required for public endpoints

---

### T-004 — Set Up Error Logging + File Rotation

**Description:** Configure Python logging with rotating file handlers (10 MB max per file, keep 5 backups).

**Acceptance Criteria:** AC-003

**Owner:** ENG

**Effort:** S (2 hours)

**Dependencies:** None

**Deliverables:**
- Logging configuration in `logging_config.py`
- Test script that generates 50 MB of logs to verify rotation

**Configuration:**
```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5
)
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Evidence:**
- Log files in `/logs/` directory: `app.log`, `app.log.1`, `app.log.2`, etc.
- Path: `/logs/`

**Notes:**
- Ensure `/logs/` directory exists or is created automatically

---

### T-005 — Implement `backfill_perpetuals.py` Script

**Description:** Create Python script to backfill perpetuals OHLCV from Deribit API (2016-2025).

**Acceptance Criteria:** AC-004, AC-005, AC-006

**Owner:** ENG

**Effort:** M (2 days)

**Dependencies:** T-002, T-003

**Deliverables:**
- `scripts/backfill_perpetuals.py` with CLI arguments: `--instruments`, `--start`, `--end`, `--resolution`
- API rate limiting with exponential backoff
- Database upsert logic (idempotent writes)

**API Endpoint:**
- `/public/get_tradingview_chart_data`
- Max 5,000 candles per call
- Resolution: 1 (1 minute)

**Pseudocode:**
```python
for instrument in [BTC-PERPETUAL, ETH-PERPETUAL]:
    for date_chunk in date_range(start, end, chunk_size=5000):
        data = fetch_ohlcv(instrument, date_chunk, resolution=1)
        upsert_to_db(data)
        sleep(0.05)  # Rate limit: 20 req/sec
```

**Evidence:**
- Script runs without errors
- Path: `/scripts/backfill_perpetuals.py`

**Notes:**
- Use `aiohttp` for async HTTP requests
- Implement exponential backoff for 429 errors (rate limit)

---

### T-006 — Backfill BTC-PERPETUAL (2016-2025)

**Description:** Execute backfill script for BTC-PERPETUAL from 2016-12-01 to 2025-10-18.

**Acceptance Criteria:** AC-004, AC-006

**Owner:** ENG

**Effort:** S (2 hours runtime)

**Dependencies:** T-005

**Deliverables:**
- BTC-PERPETUAL OHLCV data in `perpetuals_ohlcv` table
- ~2,365,200 rows (9 years × 525,600 min/year ÷ 2)

**Command:**
```bash
python scripts/backfill_perpetuals.py \
  --instruments BTC-PERPETUAL \
  --start 2016-12-01 \
  --end 2025-10-18 \
  --resolution 1
```

**Evidence:**
- Row count query: `SELECT COUNT(*) FROM perpetuals_ohlcv WHERE instrument = 'BTC-PERPETUAL';`
- Expected: ~2,365,200 rows
- Path: `/tests/evidence/T-006-btc-backfill.txt`

**Notes:**
- Runtime: ~2 hours (5,000 candles per call, 0.05s sleep)

---

### T-007 — Backfill ETH-PERPETUAL (2017-2025)

**Description:** Execute backfill script for ETH-PERPETUAL from 2017-01-01 to 2025-10-18.

**Acceptance Criteria:** AC-004, AC-006

**Owner:** ENG

**Effort:** S (2 hours runtime)

**Dependencies:** T-005

**Deliverables:**
- ETH-PERPETUAL OHLCV data in `perpetuals_ohlcv` table
- ~2,365,200 rows (8 years × 525,600 min/year ÷ 2)

**Command:**
```bash
python scripts/backfill_perpetuals.py \
  --instruments ETH-PERPETUAL \
  --start 2017-01-01 \
  --end 2025-10-18 \
  --resolution 1
```

**Evidence:**
- Row count query: `SELECT COUNT(*) FROM perpetuals_ohlcv WHERE instrument = 'ETH-PERPETUAL';`
- Expected: ~2,365,200 rows
- Path: `/tests/evidence/T-007-eth-backfill.txt`

**Notes:**
- Can run in parallel with T-006 if using separate API keys or respecting rate limits

---

### T-008 — Run Data Quality Checks (Gaps, Outliers)

**Description:** Execute data quality validation scripts to detect gaps >5 minutes and OHLCV sanity violations.

**Acceptance Criteria:** AC-004, AC-005

**Owner:** QA

**Effort:** S (2 hours)

**Dependencies:** T-006, T-007

**Deliverables:**
- `scripts/data_quality_checks.py` with SQL queries from master plan
- Gap report (CSV)
- Sanity check report (CSV)

**Commands:**
```bash
python -m scripts.data_quality_checks --table perpetuals_ohlcv
```

**Checks:**
1. **Gap Detection:**
   ```sql
   SELECT timestamp, LAG(timestamp) OVER (ORDER BY timestamp) AS prev_timestamp,
          timestamp - LAG(timestamp) OVER (ORDER BY timestamp) AS gap
   FROM perpetuals_ohlcv
   WHERE gap > INTERVAL '5 minutes'
   ORDER BY gap DESC;
   ```
   Expected: 0 gaps >5 minutes (or documented exceptions)

2. **OHLCV Sanity:**
   ```sql
   SELECT * FROM perpetuals_ohlcv
   WHERE high < low OR close < low OR close > high;
   ```
   Expected: 0 violations

**Evidence:**
- Gap report: `/tests/evidence/T-008-gap-report.csv`
- Sanity report: `/tests/evidence/T-008-sanity-report.csv`

**Notes:**
- Minor gaps during exchange maintenance are acceptable (document in report)

---

## Critical Path (Phase 0-1)

```
T-001 (Install deps)
  ↓
T-002 (Create schema) ←──────┐
  ↓                          │
T-005 (Implement backfill) ←─┤
  ↓                          │
T-006 (BTC backfill)         │
T-007 (ETH backfill)         │
  ↓                          │
T-008 (QA checks)            │
                             │
T-003 (API test) ────────────┘
T-004 (Logging) [parallel]
```

**Total Duration (Phase 0-1):** 6 days (assuming sequential execution, 8 hrs/day)
- Phase 0: 1 day
- Phase 1: 5 days (2 days dev + 3 days runtime + QA)

**Parallelization Opportunities:**
- T-001, T-003, T-004 can run in parallel (Phase 0: 1 day → 4 hours)
- T-006, T-007 can run in parallel (Phase 1: 5 days → 3 days)

**Optimized Duration:** 3.5 days

---

## Risk Register (Phase 0-1)

| Risk ID | Description                          | Probability | Impact | Mitigation                          | Owner |
|---------|--------------------------------------|-------------|--------|-------------------------------------|-------|
| R-001   | Deribit API rate limits hit          | Medium      | High   | Exponential backoff, cache responses| ENG   |
| R-002   | Historical data gaps (maintenance)   | High        | Medium | Document exceptions, accept gaps    | QA    |
| R-003   | Database disk space exhausted        | Low         | High   | Monitor storage, implement compression| ENG |
| R-004   | Python dependency conflicts          | Low         | Medium | Use virtualenv, pin versions        | ENG   |
| R-005   | TimescaleDB installation fails       | Low         | High   | Follow official docs, test on VM first| ENG |

---

## Questions for Financial Engineer

None at this time. Phase 0-1 is well-defined in the master plan.

---

## Questions for QA

**Q-001:** What is the acceptable gap threshold for perpetuals data?
- Master plan says "no gaps >5 minutes"
- Is this absolute, or can we document exceptions for known exchange maintenance windows?
- **Proposed Default:** Allow gaps during documented maintenance, flag all others
- **Due Date:** Before T-008 starts
- **Blocking:** T-008

---

## Next Steps

1. **PM assigns owners** to T-001, T-003, T-004 (Phase 0 tasks)
2. **ENG starts T-001** (install dependencies)
3. **ENG starts T-003** (API connectivity test) in parallel
4. **ENG starts T-004** (logging setup) in parallel
5. **PM moves T-001, T-003, T-004 to In-Progress.md** when work begins
6. **PM gates Phase 1 start** on Phase 0 completion (all SMK-001, SMK-002, SMK-003 pass)

---

**End of Backlog Document**

This orchestration output structures work and verification. It is not trading, legal, accounting, or tax advice. Handle secrets securely and follow your organization's policies.
