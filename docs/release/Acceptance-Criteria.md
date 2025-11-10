---
doc_type: acceptance_criteria
owner: orchestrator
updated: 2025-10-21
links:
  - ../../CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md
  - ../tasks/Backlog.md
---

# Acceptance Criteria — Crypto Data Infrastructure

## Summary

This document contains all testable acceptance criteria extracted from the Crypto Data Infrastructure Master Plan. Each criterion is traceable to specific code, tests, and smoke test evidence.

## Acceptance Criteria Index

| ID     | Title                                     | Phase    | Priority | Linked Code/PR | Status |
|--------|-------------------------------------------|----------|----------|----------------|--------|
| AC-001 | Deribit API connectivity validated        | Phase 0  | Critical | TBD            | Pending |
| AC-002 | Database schema created with indexes      | Phase 0  | Critical | TBD            | Pending |
| AC-003 | Log file rotation configured              | Phase 0  | High     | TBD            | Pending |
| AC-004 | Perpetuals OHLCV complete (no gaps)       | Phase 1  | Critical | TBD            | Pending |
| AC-005 | Perpetuals OHLCV sanity checks pass       | Phase 1  | Critical | TBD            | Pending |
| AC-006 | Perpetuals storage ≤ 150 MB               | Phase 1  | Medium   | TBD            | Pending |
| AC-007 | All futures contracts present (2019+)     | Phase 2  | Critical | TBD            | Pending |
| AC-008 | Basis spread computed correctly           | Phase 2  | High     | TBD            | Pending |
| AC-009 | Futures storage ≤ 1.5 GB                  | Phase 2  | Medium   | TBD            | Pending |
| AC-010 | Active options OHLCV complete             | Phase 3  | Critical | TBD            | Pending |
| AC-011 | Implied volatility computed (95%+ strikes)| Phase 3  | Critical | TBD            | Pending |
| AC-012 | Volatility surface visualization generated| Phase 3  | High     | TBD            | Pending |
| AC-013 | Greeks computed for 100% valid options    | Phase 4  | Critical | TBD            | Pending |
| AC-014 | Greeks validation error < 5% RMSE         | Phase 4  | Critical | TBD            | Pending |
| AC-015 | Historical Greeks storage ≤ 2 GB          | Phase 4  | Medium   | TBD            | Pending |
| AC-016 | Real-time collector 24/7 uptime (>99%)    | Phase 5  | Critical | TBD            | Pending |
| AC-017 | Data latency < 5 minutes                  | Phase 5  | High     | TBD            | Pending |
| AC-018 | Healthchecks.io heartbeat active          | Phase 5  | High     | TBD            | Pending |
| AC-019 | Daily backups stored in Backblaze B2      | Phase 5  | Critical | TBD            | Pending |

---

## Phase 0: Prerequisites

### AC-001 — Deribit API Connectivity Validated

**Given:** Deribit public API is accessible
**When:** System calls `/public/test` endpoint
**Then:** Response returns HTTP 200 with valid JSON

**Inputs:**
| Field            | Type    | Example                              | Notes                  |
|------------------|---------|--------------------------------------|------------------------|
| endpoint_url     | string  | https://www.deribit.com/api/v2/public/test | Public test endpoint  |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| status_code      | int     | 200          | HTTP success code      |
| response_valid   | boolean | true         | JSON response parseable|

**Evidence Required:**
- Command: `python -m scripts.test_connectivity`
- Sample output: `{"status": "ok", "api_version": "2.0"}`
- Artifact path: `/tests/evidence/AC-001-connectivity.json`

**Notes/Risks:** API may have rate limits; implement exponential backoff

---

### AC-002 — Database Schema Created with Indexes

**Given:** PostgreSQL 14+ with TimescaleDB installed
**When:** Schema creation script runs
**Then:** All tables created as hypertables with correct indexes

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| schema_file      | string  | schema.sql   | SQL schema definition  |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| tables_created   | int     | 6            | All required tables    |
| hypertables      | int     | 6            | TimescaleDB conversion |

**Evidence Required:**
- Command: `psql -U postgres -d crypto_data -f schema.sql`
- Validation: `SELECT count(*) FROM timescaledb_information.hypertables;` → Expect 6
- Artifact path: `/tests/evidence/AC-002-schema-validation.sql`

**Notes/Risks:** TimescaleDB extension must be installed before schema creation

---

### AC-003 — Log File Rotation Configured

**Given:** Python logging configured
**When:** Application runs
**Then:** Log files rotate at 10 MB max per file

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| log_max_size     | int     | 10485760     | 10 MB in bytes         |
| log_backup_count | int     | 5            | Keep 5 old files       |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| rotation_active  | boolean | true         | Files rotate correctly |

**Evidence Required:**
- Generate 50 MB of logs and verify rotation
- Artifact path: `/logs/` directory with files `app.log`, `app.log.1`, etc.

**Notes/Risks:** Ensure disk space monitoring for log directory

---

## Phase 1: Perpetuals Backfill

### AC-004 — Perpetuals OHLCV Complete (No Gaps)

**Given:** Perpetuals backfill script executed for 2016-2025
**When:** Data quality check runs
**Then:** 100% of expected candles present (no gaps >5 minutes)

**Inputs:**
| Field            | Type    | Example          | Notes                  |
|------------------|---------|------------------|------------------------|
| instruments      | list    | [BTC-PERPETUAL, ETH-PERPETUAL] | Target instruments |
| start_date       | date    | 2016-12-01       | Start of backfill      |
| end_date         | date    | 2025-10-18       | End of backfill        |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| gap_count        | int     | 0            | Gaps >5 minutes        |
| expected_candles | int     | 4730400      | 9 years × 525,600/year |
| actual_candles   | int     | 4730400      | Rows in database       |

**Evidence Required:**
- Command: `python -m scripts.data_quality_checks --table perpetuals_ohlcv`
- Query: See master plan Section 3.1 (gap detection SQL)
- Artifact path: `/tests/evidence/AC-004-gap-report.csv`

**Notes/Risks:** Minor gaps acceptable during exchange maintenance windows (document exceptions)

---

### AC-005 — Perpetuals OHLCV Sanity Checks Pass

**Given:** Perpetuals OHLCV data loaded
**When:** Sanity checks run (high ≥ low, close ∈ [low, high])
**Then:** 0 violations found

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| table_name       | string  | perpetuals_ohlcv | Target table         |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| violations       | int     | 0            | Invalid OHLCV records  |

**Evidence Required:**
- Command: `SELECT COUNT(*) FROM perpetuals_ohlcv WHERE high < low OR close < low OR close > high;`
- Expected: 0
- Artifact path: `/tests/evidence/AC-005-sanity-report.txt`

**Notes/Risks:** If violations found, investigate Deribit API data quality

---

### AC-006 — Perpetuals Storage ≤ 150 MB

**Given:** Perpetuals backfill complete
**When:** Database size checked
**Then:** Storage usage ≤ 150 MB

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| table_name       | string  | perpetuals_ohlcv | Target table         |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| storage_mb       | float   | 145.2        | Storage in megabytes   |

**Evidence Required:**
- Command: `SELECT pg_size_pretty(pg_total_relation_size('perpetuals_ohlcv'));`
- Expected: ≤ 150 MB
- Artifact path: `/tests/evidence/AC-006-storage-report.txt`

**Notes/Risks:** TimescaleDB compression can reduce size by ~50% if needed

---

## Phase 2: Futures Backfill

### AC-007 — All Futures Contracts Present (2019+)

**Given:** Futures backfill script executed
**When:** Contract count checked
**Then:** 150+ unique futures contracts in database

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| currencies       | list    | [BTC, ETH]   | Target currencies      |
| start_date       | date    | 2019-06-01   | Start of futures data  |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| contract_count   | int     | 156          | Unique futures contracts|

**Evidence Required:**
- Command: `SELECT COUNT(DISTINCT instrument) FROM futures_ohlcv;`
- Expected: ≥ 150
- Artifact path: `/tests/evidence/AC-007-futures-count.txt`

**Notes/Risks:** Expired contracts are included for historical basis analysis

---

### AC-008 — Basis Spread Computed Correctly

**Given:** Futures and perpetuals data overlapping
**When:** Basis spread calculation runs
**Then:** Non-null basis for 100% of overlapping timestamps

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| futures_table    | string  | futures_ohlcv | Futures data          |
| perps_table      | string  | perpetuals_ohlcv | Perpetuals data    |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| null_basis_pct   | float   | 0.0          | Percentage null values |

**Evidence Required:**
- Command: Basis spread = futures_price - perpetual_price
- Validation: Check for realistic contango/backwardation ratios (60/40)
- Artifact path: `/tests/evidence/AC-008-basis-validation.csv`

**Notes/Risks:** Basis should be annualized for comparison across different expiries

---

### AC-009 — Futures Storage ≤ 1.5 GB

**Given:** Futures backfill complete
**When:** Database size checked
**Then:** Storage usage ≤ 1.5 GB

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| table_name       | string  | futures_ohlcv | Target table          |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| storage_gb       | float   | 1.42         | Storage in gigabytes   |

**Evidence Required:**
- Command: `SELECT pg_size_pretty(pg_total_relation_size('futures_ohlcv'));`
- Expected: ≤ 1.5 GB
- Artifact path: `/tests/evidence/AC-009-storage-report.txt`

**Notes/Risks:** Monitor growth rate for capacity planning

---

## Phase 3: Options Backfill

### AC-010 — Active Options OHLCV Complete

**Given:** Options backfill script executed (2024-2025, active only)
**When:** Data completeness checked
**Then:** All active options (DTE > 0) have OHLCV data

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| currencies       | list    | [BTC, ETH]   | Target currencies      |
| start_date       | date    | 2024-01-01   | Start of options data  |
| active_only      | boolean | true         | Skip expired options   |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| active_options   | int     | 2345         | Unique active options  |
| coverage_pct     | float   | 100.0        | Percentage with data   |

**Evidence Required:**
- Command: `SELECT COUNT(DISTINCT instrument) FROM options_ohlcv WHERE expiry_date > NOW();`
- Expected: 2000+ active options
- Artifact path: `/tests/evidence/AC-010-options-coverage.csv`

**Notes/Risks:** Accept data gaps for expired options (documented limitation)

---

### AC-011 — Implied Volatility Computed (95%+ Strikes)

**Given:** Options OHLCV data loaded
**When:** IV computation runs (Newton-Raphson method)
**Then:** 95%+ of strikes have valid implied volatility

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| table_name       | string  | options_ohlcv | Target table          |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| iv_coverage_pct  | float   | 97.3         | Percentage with IV     |

**Evidence Required:**
- Command: `SELECT COUNT(*) FROM options_ohlcv WHERE implied_volatility IS NOT NULL;`
- Expected: ≥ 95%
- Artifact path: `/tests/evidence/AC-011-iv-coverage.csv`

**Notes/Risks:** Deep OTM options may fail IV convergence (acceptable)

---

### AC-012 — Volatility Surface Visualization Generated

**Given:** Implied volatility computed for all strikes
**When:** Visualization script runs
**Then:** Heatmap shows smooth vol smile (strike vs. DTE)

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| snapshot_date    | date    | 2025-10-18   | Date for surface plot  |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| plot_file        | string  | vol_surface_20251018.png | Output file     |

**Evidence Required:**
- Command: `python -m scripts.plot_vol_surface --date 2025-10-18`
- Visual validation: Smooth smile, no spikes
- Artifact path: `/tests/evidence/AC-012-vol-surface.png`

**Notes/Risks:** Manual visual inspection required for smoothness

---

## Phase 4: Historical Greeks

### AC-013 — Greeks Computed for 100% Valid Options

**Given:** Options price data available (2022-2025)
**When:** Black-Scholes Greeks calculator runs
**Then:** Delta, gamma, vega, theta computed for 100% of options with valid prices

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| start_date       | date    | 2022-01-01   | Start of Greeks calc   |
| end_date         | date    | 2025-10-18   | End of Greeks calc     |
| parallel_workers | int     | 8            | CPU cores              |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| greeks_coverage_pct | float | 100.0       | Percentage with Greeks |

**Evidence Required:**
- Command: `python -m scripts.compute_historical_greeks --start 2022-01-01 --end 2025-10-18 --parallel 8`
- Expected: 100% coverage
- Artifact path: `/tests/evidence/AC-013-greeks-coverage.csv`

**Notes/Risks:** Requires risk-free rate proxy (3-month T-bill)

---

### AC-014 — Greeks Validation Error < 5% RMSE

**Given:** Historical Greeks computed
**When:** Validation runs against Deribit live Greeks (last 30 days)
**Then:** RMSE error < 0.05 for delta, gamma, vega, theta

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| validation_window| int     | 30           | Days to validate       |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| delta_rmse       | float   | 0.032        | Delta RMSE             |
| gamma_rmse       | float   | 0.041        | Gamma RMSE             |
| vega_rmse        | float   | 0.028        | Vega RMSE              |
| theta_rmse       | float   | 0.035        | Theta RMSE             |

**Evidence Required:**
- Command: `python -m scripts.validate_greeks --days 30`
- Formula: `RMSE = sqrt(mean((computed - deribit)^2))`
- Artifact path: `/tests/evidence/AC-014-greeks-rmse.csv`

**Notes/Risks:** 5% error acceptable for historical analysis; not for live trading

---

### AC-015 — Historical Greeks Storage ≤ 2 GB

**Given:** Historical Greeks computed (2022-2025)
**When:** Database size checked
**Then:** Storage usage ≤ 2 GB

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| table_name       | string  | options_greeks | Target table         |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| storage_gb       | float   | 1.87         | Storage in gigabytes   |

**Evidence Required:**
- Command: `SELECT pg_size_pretty(pg_total_relation_size('options_greeks'));`
- Expected: ≤ 2 GB
- Artifact path: `/tests/evidence/AC-015-storage-report.txt`

**Notes/Risks:** Monitor storage growth for forward collection

---

## Phase 5: Real-Time Collection

### AC-016 — Real-Time Collector 24/7 Uptime (>99%)

**Given:** Collector deployed as systemd service on VPS
**When:** Uptime monitored over 7 days
**Then:** Uptime ≥ 99.9%

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| monitoring_window| int     | 7            | Days to monitor        |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| uptime_pct       | float   | 99.95        | Percentage uptime      |

**Evidence Required:**
- Command: `sudo systemctl status crypto-collector.service`
- Healthchecks.io dashboard showing uptime
- Artifact path: `/tests/evidence/AC-016-uptime-report.png`

**Notes/Risks:** DigitalOcean SLA is 99.99%; service should match

---

### AC-017 — Data Latency < 5 Minutes

**Given:** Real-time collector running
**When:** Latency measured (data timestamp - collection time)
**Then:** Median latency < 5 minutes

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| measurement_window| int    | 24           | Hours to measure       |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| median_latency_sec | int   | 180          | Median latency (seconds)|
| p95_latency_sec  | int     | 280          | 95th percentile        |

**Evidence Required:**
- Query: `SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency) FROM collection_metrics;`
- Expected: < 300 seconds
- Artifact path: `/tests/evidence/AC-017-latency-report.csv`

**Notes/Risks:** Spikes during API rate limiting are acceptable

---

### AC-018 — Healthchecks.io Heartbeat Active

**Given:** Collector sending heartbeats
**When:** Healthchecks.io dashboard checked
**Then:** Heartbeat received every 15 minutes

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| heartbeat_url    | string  | https://hc-ping.com/UUID | Healthchecks URL  |
| interval_min     | int     | 15           | Heartbeat frequency    |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| last_ping_time   | datetime| 2025-10-21 14:30 | Last successful ping |

**Evidence Required:**
- Healthchecks.io dashboard screenshot
- Artifact path: `/tests/evidence/AC-018-healthchecks.png`

**Notes/Risks:** Alert configured if heartbeat missed >15 minutes

---

### AC-019 — Daily Backups Stored in Backblaze B2

**Given:** Daily backup cron job configured
**When:** Backup verification runs
**Then:** Daily backups present in Backblaze B2 (last 30 days)

**Inputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| backup_bucket    | string  | crypto-backups | B2 bucket name       |
| retention_days   | int     | 30           | Days to retain         |

**Outputs:**
| Field            | Type    | Example      | Notes                  |
|------------------|---------|--------------|------------------------|
| backup_count     | int     | 30           | Backups in last 30 days|

**Evidence Required:**
- Command: `b2 ls crypto-backups | wc -l`
- Expected: ≥ 30 files
- Artifact path: `/tests/evidence/AC-019-backup-list.txt`

**Notes/Risks:** Test restore procedure monthly to verify backup integrity

---

## Traceability Matrix

| AC     | Tasks             | Smoke Tests     | Evidence Path                          |
|--------|-------------------|-----------------|----------------------------------------|
| AC-001 | T-003             | SMK-001         | /tests/evidence/AC-001-connectivity.json|
| AC-002 | T-002             | SMK-002         | /tests/evidence/AC-002-schema-validation.sql|
| AC-003 | T-004             | SMK-003         | /logs/                                 |
| AC-004 | T-006, T-007      | SMK-004         | /tests/evidence/AC-004-gap-report.csv  |
| AC-005 | T-008             | SMK-006         | /tests/evidence/AC-005-sanity-report.txt|
| AC-006 | T-006, T-007      | SMK-007         | /tests/evidence/AC-006-storage-report.txt|
| AC-007 | T-009, T-011, T-012| SMK-008        | /tests/evidence/AC-007-futures-count.txt|
| AC-008 | T-013             | SMK-009         | /tests/evidence/AC-008-basis-validation.csv|
| AC-009 | T-009, T-011, T-012| SMK-010        | /tests/evidence/AC-009-storage-report.txt|
| AC-010 | T-014, T-016, T-017| SMK-011        | /tests/evidence/AC-010-options-coverage.csv|
| AC-011 | T-018             | SMK-012         | /tests/evidence/AC-011-iv-coverage.csv |
| AC-012 | T-019             | SMK-013         | /tests/evidence/AC-012-vol-surface.png |
| AC-013 | T-020, T-022      | SMK-014         | /tests/evidence/AC-013-greeks-coverage.csv|
| AC-014 | T-023             | SMK-016         | /tests/evidence/AC-014-greeks-rmse.csv |
| AC-015 | T-024             | SMK-015         | /tests/evidence/AC-015-storage-report.txt|
| AC-016 | T-028             | SMK-017         | /tests/evidence/AC-016-uptime-report.png|
| AC-017 | T-027             | SMK-018         | /tests/evidence/AC-017-latency-report.csv|
| AC-018 | T-029             | SMK-020         | /tests/evidence/AC-018-healthchecks.png|
| AC-019 | T-030             | SMK-019         | /tests/evidence/AC-019-backup-list.txt |

---

**End of Acceptance Criteria Document**

This orchestration output structures work and verification. It is not trading, legal, accounting, or tax advice. Handle secrets securely and follow your organization's policies.
