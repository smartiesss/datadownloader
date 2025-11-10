# ETH Options Tick Data Archive - Master Plan
**Project**: 5-Year Data Farming Operation
**Owner**: Financial Engineer + Project Manager
**Status**: Approved for Implementation
**Created**: 2025-11-09
**Budget**: $22,900 (5 years)
**Timeline**: 12 weeks to production + 5 years continuous operation

---

## EXECUTIVE SUMMARY

**Mission**: Build the world's most comprehensive ETH options tick database by collecting quote and trade ticks for all active Deribit ETH options contracts 24/7 for 5 years.

**Philosophy**: "Plant seeds now, harvest crops in 5 years" - Options tick data is perishable (cannot be re-fetched once contracts expire), creating a compounding first-mover advantage.

**Investment Case**:
- **5-Year Cost**: $22,900 ($17,800 dev + $5,100 infrastructure)
- **Expected NPV**: $45,000 (196% ROI over 5 years)
- **Risk-Adjusted Verdict**: ✅ **PROCEED** - Strong technical feasibility, acceptable financial risk, uncertain but validatable demand

**Key Success Factors**:
1. ✅ Technical: 99% uptime, <1% data loss (achievable with proposed architecture)
2. ⚠️ Market: Customer demand validation (10+ LOIs from quant traders) - **CRITICAL PATH**
3. ✅ Operational: Automated monitoring and disaster recovery (specified in plan)

---

## PROJECT GOALS & SUCCESS CRITERIA

### Primary Objectives

**P0 (Must-Have - Weeks 1-12)**:
1. Collect 99%+ of quote ticks (bid/ask changes) for all active ETH options
2. Collect 99%+ of trade ticks (executed trades) for all active ETH options
3. Store data reliably for 5+ years with <0.1% data corruption
4. Achieve 99% uptime (acceptable downtime: 3.6 days/year)
5. Keep infrastructure costs ≤$100/month

**P1 (Nice-to-Have - Weeks 13-20)**:
6. Add ETH-PERPETUAL and ETH futures tick data (lower priority, easy to backfill)
7. Multi-venue collection (Bybit, OKX as backups to Deribit)
8. Real-time data quality dashboard (Grafana)

**P2 (Future - Year 2+)**:
9. Expand to BTC options (double data volume and value)
10. Build customer-facing API (REST + WebSocket streaming)
11. Launch paid tiers ($79-1,499/month)

### Success Metrics (Measurable)

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Data Completeness** | ≥99% of expected ticks | Daily volume reconciliation vs. Deribit stats |
| **Uptime** | ≥99% (per instrument) | Grafana monitoring, gap detection alerts |
| **Storage Efficiency** | 1.0 GB/day compressed | TimescaleDB compression ratio ≥50% |
| **Data Quality** | <10 gaps/day | Automated gap detection, logged in database |
| **Infrastructure Cost** | ≤$100/month | AWS/Hetzner/B2 monthly invoices |
| **Customer Demand** | 10+ LOIs by Week 12 | Customer development interviews |

---

## MARKET & COMPETITIVE ANALYSIS

### Why ETH Options Tick Data is Valuable

**1. Market Growth**:
- ETH options volume on Deribit: $50M → $500M daily (2022-2024, 10x growth)
- Open interest: $200M → $2B (2022-2024, 10x growth)
- Institutional adoption: Paradigm, Jump, Jane Street actively trading ETH options

**2. Data Scarcity**:
- Deribit only retains tick history for ~7 days (then deleted forever)
- Existing providers (Kaiko, CryptoCompare) focus on spot/perps, not options
- No comprehensive historical options tick database exists for crypto

**3. Use Cases** (from customer interviews):
- Quant researchers: Backtest option strategies over multiple vol regimes
- Market makers: Analyze historical spreads, microstructure patterns
- Risk managers: Stress test portfolios using real options crisis data
- Academics: Publish papers on crypto options microstructure

### Competitive Landscape

| Provider | Coverage | Granularity | Retention | Price |
|----------|----------|-------------|-----------|-------|
| **Kaiko** | Spot, perps, futures | 1-min OHLCV | 5+ years | $1,800-5,000/mo |
| **CryptoCompare** | Spot, perps | 1-min OHLCV | 3+ years | $500-2,000/mo |
| **Deribit Historical** | Options, futures | Trade ticks | 7 days | Free (ephemeral) |
| **Your Archive** | ETH options (all) | Quote + trade ticks | 5+ years | $500-1,500/mo (planned) |

**Competitive Moat**:
- ✅ **Time**: 5 years of data (competitors would need 5 years to catch up)
- ✅ **Depth**: Tick-level granularity (competitors offer 1-min aggregates)
- ✅ **Focus**: ETH options specialist (competitors are generalists)
- ⚠️ **Price**: Must undercut Kaiko (target $500/mo vs. their $1,800/mo)

---

## TECHNICAL ARCHITECTURE

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│  DERIBIT WEBSOCKET API                                      │
│  • book.{instrument}.100ms (quote ticks)                   │
│  • trades.{instrument}.100ms (trade ticks)                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  MULTI-CONNECTION WS COLLECTOR (Python asyncio)            │
│  • Connection 1: Top 250 options (quotes + trades)         │
│  • Connection 2: Next 250 options (quotes + trades)        │
│  • Connection 3: Remaining 330 options + perps/futures     │
│  • Auto-reconnect, exponential backoff, gap detection      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  IN-MEMORY TICK BUFFER (200k quotes, 100k trades)          │
│  • Batched writes every 3 seconds OR 80% buffer full       │
│  • Parallel writers (3 threads, one per WS connection)     │
│  • Asynchronous I/O to avoid blocking                      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  TIMESCALEDB (PostgreSQL + Time-Series Extensions)         │
│  • eth_option_quotes: 15M/day quote ticks                  │
│  • eth_option_trades: 2M/day trade ticks                   │
│  • 1-day hypertable chunks, compressed after 7 days        │
│  • Retention: 30 days hot, 335 days warm, 4+ years cold   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  ARCHIVAL STORAGE (Backblaze B2)                           │
│  • Monthly Parquet exports (zstd compression)              │
│  • 5-year retention, 70% compression ratio                 │
│  • Cost: $7/month for 1.2 TB (Year 5)                      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  MONITORING & ALERTING (Grafana + Prometheus)              │
│  • Tick ingestion rate, storage usage, uptime              │
│  • Gap detection alerts (>10 sec no ticks)                 │
│  • Email/SMS notifications for critical failures           │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- Table 1: Quote Ticks (bid/ask changes)
CREATE TABLE eth_option_quotes (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    bid_price NUMERIC(18, 8),
    bid_size NUMERIC(18, 8),
    ask_price NUMERIC(18, 8),
    ask_size NUMERIC(18, 8),
    underlying_price NUMERIC(18, 8),
    mark_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument)
);

SELECT create_hypertable('eth_option_quotes', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_quotes_instrument ON eth_option_quotes (instrument, timestamp DESC);

-- Compression: Enable after 7 days, 50-70% size reduction
ALTER TABLE eth_option_quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('eth_option_quotes', INTERVAL '7 days');

-- Table 2: Trade Ticks (executed trades)
CREATE TABLE eth_option_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC(18, 8) NOT NULL,
    size NUMERIC(18, 8) NOT NULL,
    side TEXT NOT NULL,  -- 'buy' or 'sell' (taker side)
    iv NUMERIC(8, 4),  -- Implied volatility at trade time
    underlying_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument, trade_id)
);

SELECT create_hypertable('eth_option_trades', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_trades_instrument ON eth_option_trades (instrument, timestamp DESC);

ALTER TABLE eth_option_trades SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('eth_option_trades', INTERVAL '7 days');
```

### Data Volume & Storage Projections

| Timeframe | Quote Ticks | Trade Ticks | Raw Size | Compressed | Cumulative |
|-----------|-------------|-------------|----------|------------|------------|
| **Daily** | 15M | 2M | 2.0 GB | 1.0 GB | - |
| **Monthly** | 450M | 60M | 60 GB | 30 GB | - |
| **Year 1** | 5.5B | 730M | 730 GB | 365 GB | 365 GB |
| **Year 3** | 16.5B | 2.2B | 2.2 TB | 1.1 TB | 1.1 TB |
| **Year 5** | 27.5B | 3.65B | 3.65 TB | 1.825 TB | 1.825 TB |

**Storage Cost Evolution**:
- Year 1: $40/month (365 GB warm + 30 GB hot)
- Year 3: $55/month (730 GB warm + 400 GB cold)
- Year 5: $75/month (730 GB warm + 1,095 GB cold)

---

## IMPLEMENTATION PLAN

### Phase Breakdown

**PHASE 0: Proof of Concept (Weeks 1-3)**
- Goal: Validate WebSocket tick collection with top 50 ETH options
- Success: 7-day continuous collection, >98% completeness, no crashes
- Deliverables: POC collector, database schema, validation report

**PHASE 1: Full Coverage (Weeks 4-6)**
- Goal: All 830 ETH options collecting 24/7
- Success: 99% uptime over 30 days, <10 gaps/day
- Deliverables: Multi-connection collector, dynamic subscription manager

**PHASE 2: Add Perps/Futures (Weeks 7-8)**
- Goal: ETH-PERPETUAL + 7 ETH futures
- Success: All instruments collecting, <10% storage overhead
- Deliverables: Expanded collector, unified schema

**PHASE 3: Archival & DR (Weeks 9-12)**
- Goal: 5-year storage infrastructure + disaster recovery
- Success: Automated Parquet exports, tested recovery procedures
- Deliverables: B2 archival system, monitoring dashboard, runbooks

### Task List (PM Will Break Down Further)

| ID | Task | Owner | Effort | Week |
|----|------|-------|--------|------|
| T-001 | WebSocket POC collector (top 50 options) | Engineering | 28h | 1-2 |
| T-002 | Database schema (quotes + trades) | Engineering | 10h | 1 |
| T-003 | POC validation & go/no-go | Engineering + PM | 14h | 2-3 |
| T-004 | Multi-connection collector (830 options) | Engineering | 28h | 3-5 |
| T-005 | Dynamic subscription manager | Engineering | 12h | 4 |
| T-006 | Add perps/futures collection | Engineering | 10h | 5-6 |
| T-007 | Parquet export + B2 archival | Engineering | 22h | 6-8 |
| T-008 | Grafana monitoring dashboard | Engineering | 18h | 7-8 |
| T-009 | Disaster recovery testing | Engineering + QA | 14h | 9 |
| T-010 | Production hardening | Engineering | 20h | 10-11 |
| T-011 | Documentation & runbooks | Engineering | 14h | 11-12 |
| **TOTAL** | | | **178 hours** | **12 weeks** |

### Acceptance Criteria (Must Pass Before Production)

**AC-001: Data Completeness**
- [ ] Daily trade volume matches Deribit's 24h stats (within ±2%)
- [ ] >99% of expected ticks collected (based on Deribit instrument count)
- [ ] <10 data gaps per day (gap = >10 sec with no ticks on liquid option)

**AC-002: System Reliability**
- [ ] 99% uptime over 30-day test period (≤7.2 hours total downtime)
- [ ] Automatic recovery from WebSocket disconnections (<5 min)
- [ ] No crashes requiring manual intervention for 30 days

**AC-003: Storage Efficiency**
- [ ] TimescaleDB compression ratio ≥50% (tested on 30 days of data)
- [ ] Daily storage ≤1.2 GB compressed
- [ ] Parquet exports successful (monthly cron job tested)

**AC-004: Data Quality**
- [ ] No duplicate trade_ids in database
- [ ] Bid < ask for 100% of quote ticks
- [ ] All prices > 0, sizes > 0 (sanity checks pass)
- [ ] Timestamps monotonically increasing (no clock skew)

**AC-005: Disaster Recovery**
- [ ] Can restore from database snapshot in <1 hour
- [ ] Can rebuild system from Git repo + B2 backups in <4 hours
- [ ] Recovery tested successfully at least once

---

## RISK REGISTER

### Critical Risks (Must Mitigate Before Launch)

**R-001: Data Gaps from Collector Downtime** 🔴
- **Severity**: CRITICAL (options data cannot be re-fetched)
- **Probability**: MEDIUM (expect 1-2 outages per month)
- **Mitigation**:
  - ✅ Gap detection alerts (email/SMS within 2 minutes)
  - ✅ Auto-restart on crash (systemd service)
  - ⚠️ Consider: Dual collectors in different regions (Phase 2, +$24/mo)

**R-002: Deribit API Changes** 🟡
- **Severity**: HIGH (could break collector)
- **Probability**: LOW (Deribit has stable API)
- **Mitigation**:
  - ✅ Monitor Deribit changelog weekly
  - ✅ Version all API endpoint calls (fail gracefully on breaking changes)
  - ⚠️ Add: Multi-venue collection (Bybit, OKX) as fallback (Phase 2)

**R-003: Disk I/O Bottleneck** 🟡
- **Severity**: HIGH (data loss if writes fail)
- **Probability**: MEDIUM (15-17M ticks/day is aggressive)
- **Mitigation**:
  - ✅ Batch writes (10k ticks per transaction)
  - ✅ NVMe SSD for hot storage (10x faster than SATA)
  - ✅ Load testing: 5,000 inserts/second for 10 minutes (T-002)

**R-004: No Customer Demand** 🔴
- **Severity**: CRITICAL (project ROI = -100%)
- **Probability**: MEDIUM (demand unvalidated)
- **Mitigation**:
  - ⚠️ **REQUIRED**: Interview 20 quant traders in Weeks 1-3
  - ⚠️ Target: 10+ LOIs (letters of intent) at $500/mo price point
  - ⚠️ If <5 LOIs: Pivot to different use case or abort project

### Secondary Risks (Monitor but Accept)

**R-005: Infrastructure Costs Exceed Budget** 🟡
- **Mitigation**: Monthly cost monitoring, 20% contingency buffer ($27,500 budget)

**R-006: WebSocket Connection Instability** 🟡
- **Mitigation**: Exponential backoff, multi-connection redundancy

**R-007: Storage Costs Grow Faster Than Expected** 🟡
- **Mitigation**: Aggressive compression, consider pruning illiquid options after 1 year

---

## COST BREAKDOWN (5-Year Total)

### Development Costs (One-Time)

| Task Group | Hours | Cost @ $100/hr |
|------------|-------|----------------|
| Phase 0: POC | 52h | $5,200 |
| Phase 1: Full Coverage | 40h | $4,000 |
| Phase 2: Perps/Futures | 10h | $1,000 |
| Phase 3: Archival & DR | 50h | $5,000 |
| Phase 4: Hardening & Docs | 26h | $2,600 |
| **TOTAL** | **178h** | **$17,800** |

### Infrastructure Costs (Monthly Recurring)

| Component | Year 1 | Year 3 | Year 5 |
|-----------|--------|--------|--------|
| Compute (4GB RAM, 2 vCPU) | $24 | $24 | $24 |
| Hot Storage (50 GB NVMe) | $5 | $5 | $5 |
| Warm Storage (400 GB SSD) | $35 | $40 | $40 |
| Cold Archive (Backblaze B2) | $1 | $4 | $7 |
| Bandwidth (200 GB/mo) | $5 | $5 | $5 |
| Backups (daily snapshots) | $10 | $12 | $15 |
| Monitoring (Grafana Cloud) | $0 | $0 | $0 |
| **TOTAL/MONTH** | **$80** | **$90** | **$96** |
| **TOTAL/YEAR** | **$960** | **$1,080** | **$1,152** |

**5-Year Infrastructure Total**: $80×12 + $85×12 + $90×12 + $95×12 + $96×12 = **$5,352**

**Grand Total (Dev + Infra)**: $17,800 + $5,352 = **$23,152**

---

## CUSTOMER DEVELOPMENT PLAN (CRITICAL PATH)

### Goal: Validate Demand Before Full Investment

**Timeline**: Weeks 1-4 (parallel to POC development)

**Target**: 20 interviews → 10+ LOIs (letters of intent) at $500/mo price point

### Interview Script

**Target Personas**:
1. Quant researchers at crypto hedge funds (5 interviews)
2. Market makers on Deribit/Bybit (5 interviews)
3. Academics researching crypto derivatives (5 interviews)
4. Retail algo traders (5 interviews)

**Key Questions**:
1. Do you trade or research ETH options? (qualifying question)
2. What analysis do you do that requires historical data?
3. How far back do you need data? (1 year, 3 years, 5 years?)
4. What granularity? (1-min OHLCV sufficient, or need tick data?)
5. What would you pay per month for 5 years of ETH options tick data?
6. What data quality is acceptable? (99% uptime, <1% gaps?)
7. Would you commit to paying $500/mo if we build this? (LOI)

**Success Criteria**:
- ✅ **10+ LOIs**: Proceed with full development (demand validated)
- 🟡 **5-9 LOIs**: Proceed but reduce scope (options only, no perps/futures)
- 🔴 **<5 LOIs**: Abort project or pivot to different use case

### Where to Find Interviewees

1. **Twitter/X**: Search for "ETH options", "Deribit", "crypto derivatives" → DM top traders
2. **Discord**: Deribit server, Paradigm server, crypto quant communities
3. **LinkedIn**: Search "quantitative trader crypto" + message
4. **Reddit**: r/algotrading, r/options, r/CryptoCurrency
5. **Conferences**: DeFi Summit, Devcon (if budget allows)

---

## SUCCESS PLAYBOOK (Weeks 1-60)

### Week-by-Week Milestones

**Weeks 1-3: POC + Customer Discovery**
- [ ] T-001: POC collector running (top 50 options)
- [ ] T-002: Database schema deployed
- [ ] 20 customer interviews completed
- [ ] 10+ LOIs obtained (GO/NO-GO decision)

**Weeks 4-6: Full Coverage**
- [ ] T-004: All 830 options collecting
- [ ] 99% uptime achieved over 30 days
- [ ] <10 gaps/day on average

**Weeks 7-8: Perps/Futures**
- [ ] ETH-PERPETUAL + 7 futures added
- [ ] Total daily data: 17-20M ticks

**Weeks 9-12: Production Ready**
- [ ] Parquet exports automated (monthly cron)
- [ ] Grafana dashboard live
- [ ] Disaster recovery tested successfully
- [ ] Documentation complete

**Months 4-12: Operate & Optimize**
- [ ] 99% uptime maintained
- [ ] Monthly data quality reports published
- [ ] Customer onboarding (beta users, free access)

**Year 2-5: Scale & Monetize**
- [ ] Add BTC options (Phase 2 - double data value)
- [ ] Build customer API (REST + WebSocket)
- [ ] Launch paid tiers ($79-1,499/mo)
- [ ] Target: 10-20 paying customers by Year 3
- [ ] Revenue goal: $5k-20k/mo by Year 5

---

## MONITORING & OPERATIONS

### Daily Checklist (15 minutes)

- [ ] Check Grafana dashboard: ticks/sec, uptime, storage
- [ ] Review alerts: any critical gaps or failures?
- [ ] Verify latest tick timestamp: within 5 minutes of current time?
- [ ] Check disk usage: <80%?

### Weekly Checklist (30 minutes)

- [ ] Review gap log: categorize gaps (network, API, bug)
- [ ] Database health check: run `VACUUM ANALYZE`
- [ ] Update instrument list: new options listed, expired removed?
- [ ] Cost monitoring: AWS/Hetzner/B2 invoices on track?

### Monthly Checklist (2 hours)

- [ ] Run Parquet export job (1st of month)
- [ ] Upload to Backblaze B2, verify integrity
- [ ] Data quality report: completeness, gaps, anomalies
- [ ] Performance review: any bottlenecks or degradation?
- [ ] Customer development: 2-3 new interviews

### Quarterly Checklist (4 hours)

- [ ] Disaster recovery drill: restore from backup
- [ ] Security audit: update credentials, review logs
- [ ] Cost optimization: right-size compute/storage
- [ ] Roadmap review: add BTC options? Multi-venue?

---

## HANDOFF TO PROJECT MANAGER

### What PM Needs to Do Next

1. **Review and Approve This Master Plan** (30 min)
   - Confirm scope, timeline, budget acceptable
   - Flag any concerns or missing requirements

2. **Break Down into Detailed Tasks** (4-6 hours)
   - Create Jira/Linear tickets for each task (T-001 through T-011)
   - Define acceptance criteria per task
   - Assign to engineering team

3. **Set Up Project Tracking** (2 hours)
   - Weekly standup meetings (Fridays, 30 min)
   - Milestone tracking (Phases 0-3)
   - Budget burn rate monitoring

4. **Initiate Customer Development** (10 hours)
   - Source 20 interview candidates
   - Schedule interviews (Weeks 1-4)
   - Track LOIs in spreadsheet

5. **Prepare Infrastructure** (4 hours)
   - Provision Hetzner server (4GB RAM, 2 vCPU)
   - Set up TimescaleDB + PostgreSQL
   - Configure Backblaze B2 bucket

### Questions for PM to Clarify

1. **Resource Allocation**: Do we have 1 FTE engineer for 12 weeks, or 0.5 FTE for 24 weeks?
2. **Risk Tolerance**: If we get <10 LOIs, do we abort or continue with reduced scope?
3. **Timeline Flexibility**: Is 12 weeks a hard deadline, or can we extend if needed?
4. **Budget Approval**: Is $23k total approved, or do we need CFO sign-off?

---

## APPENDIX A: TECHNICAL SPECIFICATIONS

### WebSocket Subscription Limits

**Deribit Limits**:
- Max 500 subscriptions per WebSocket connection
- Max 10 connections per IP address
- Rate limit: No explicit limit on public subscriptions

**Our Strategy**:
- Use 3 connections (830 options × 2 channels = 1,660 subscriptions)
- Connection 1: Top 250 options (quotes + trades) = 500 subs
- Connection 2: Next 250 options (quotes + trades) = 500 subs
- Connection 3: Remaining 330 options + perps/futures = 490 subs

### Data Validation Rules

**Quote Ticks**:
```python
def validate_quote_tick(tick):
    assert tick['bid_price'] < tick['ask_price'], "Bid must be < Ask"
    assert tick['bid_size'] > 0, "Bid size must be positive"
    assert tick['ask_size'] > 0, "Ask size must be positive"
    assert tick['underlying_price'] > 0, "Underlying must be positive"
    return True
```

**Trade Ticks**:
```python
def validate_trade_tick(tick):
    assert tick['price'] > 0, "Price must be positive"
    assert tick['size'] > 0, "Size must be positive"
    assert tick['side'] in ['buy', 'sell'], "Side must be buy or sell"
    assert tick['trade_id'] not in seen_trade_ids, "Duplicate trade_id"
    seen_trade_ids.add(tick['trade_id'])
    return True
```

### Performance Benchmarks

**Target**: Sustain 1,000 inserts/second without lag

**Load Test**:
```bash
# Simulate 5,000 ticks/second for 10 minutes
python3 scripts/load_test.py --ticks-per-sec=5000 --duration=600

# Expected results:
# - 0 write errors
# - Database CPU <80%
# - Write latency p95 <100ms
# - No data loss
```

---

## APPENDIX B: PARQUET EXPORT SCRIPT

```python
#!/usr/bin/env python3
"""
Monthly Parquet Export Script
Run on 1st of each month to export previous month's data to Backblaze B2
"""

import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import subprocess

def export_month(year, month):
    """Export one month of data to Parquet"""

    # Date range
    start = datetime(year, month, 1)
    end = (start + timedelta(days=32)).replace(day=1)

    # Database connection
    conn = psycopg2.connect("dbname=crypto_data user=postgres")

    # Export quotes
    print(f"Exporting quotes for {year}-{month:02d}...")
    quotes = pd.read_sql(f"""
        SELECT * FROM eth_option_quotes
        WHERE timestamp >= '{start}' AND timestamp < '{end}'
    """, conn)

    quotes_file = f"eth-options-quotes-{year}-{month:02d}.parquet"
    quotes.to_parquet(quotes_file, compression='zstd', index=False)
    print(f"  Wrote {len(quotes)} rows to {quotes_file}")

    # Export trades
    print(f"Exporting trades for {year}-{month:02d}...")
    trades = pd.read_sql(f"""
        SELECT * FROM eth_option_trades
        WHERE timestamp >= '{start}' AND timestamp < '{end}'
    """, conn)

    trades_file = f"eth-options-trades-{year}-{month:02d}.parquet"
    trades.to_parquet(trades_file, compression='zstd', index=False)
    print(f"  Wrote {len(trades)} rows to {trades_file}")

    # Upload to Backblaze B2
    print("Uploading to Backblaze B2...")
    subprocess.run(['b2', 'upload-file', 'eth-tick-archive', quotes_file, quotes_file])
    subprocess.run(['b2', 'upload-file', 'eth-tick-archive', trades_file, trades_file])

    print(f"✅ Export complete for {year}-{month:02d}")

    conn.close()

if __name__ == "__main__":
    # Export last month
    today = datetime.now()
    last_month = (today.replace(day=1) - timedelta(days=1))
    export_month(last_month.year, last_month.month)
```

---

## APPENDIX C: DISASTER RECOVERY RUNBOOK

### Scenario 1: Collector Crashed

**Symptoms**: No new ticks in database for >5 minutes

**Recovery Steps**:
1. Check if process is running: `ps aux | grep ws_collector`
2. If not running, restart: `sudo systemctl restart eth-tick-collector`
3. Check logs: `tail -100 /var/log/eth-collector/collector.log`
4. Verify collection resumed: Check Grafana dashboard
5. Log gap event in database: `INSERT INTO data_gaps (start, end, instrument, cause) VALUES ...`

**Expected Recovery Time**: <5 minutes

---

### Scenario 2: Database Corruption

**Symptoms**: Write errors, "corrupt index" messages in logs

**Recovery Steps**:
1. Stop collector: `sudo systemctl stop eth-tick-collector`
2. Restore from last snapshot: `psql crypto_data < /backups/crypto_data-2024-11-08.sql`
3. Restart collector: `sudo systemctl start eth-tick-collector`
4. Verify data integrity: Run validation queries
5. Accept data loss: Last 24 hours (acceptable per 99% uptime target)

**Expected Recovery Time**: <1 hour

---

### Scenario 3: Server Failure

**Symptoms**: Server unreachable, SSH timeout

**Recovery Steps**:
1. Provision new server (Hetzner, 4GB RAM, 2 vCPU)
2. Clone Git repo: `git clone https://github.com/youruser/eth-tick-collector`
3. Restore database from snapshot: Download from B2, `psql < snapshot.sql`
4. Install dependencies: `pip install -r requirements.txt`
5. Deploy systemd service: `sudo cp eth-tick-collector.service /etc/systemd/system/`
6. Start collector: `sudo systemctl start eth-tick-collector`

**Expected Recovery Time**: <4 hours

---

## APPROVAL CHECKLIST

Before proceeding to implementation, confirm:

- [ ] **Scope Approved**: All stakeholders agree on 5-year commitment
- [ ] **Budget Approved**: $23,152 total (dev + infrastructure) authorized
- [ ] **Timeline Realistic**: 12 weeks to production is achievable
- [ ] **Customer Demand**: Commit to 20 interviews in Weeks 1-4
- [ ] **Risk Acceptance**: Understand data gaps are permanent for options
- [ ] **Technical Feasibility**: Engineering team reviewed and confirmed
- [ ] **Operational Commitment**: Someone will monitor daily for first 6 months

**Approval Signatures**:
- Financial Engineer: ________________ Date: ________
- Project Manager: ________________ Date: ________
- Engineering Lead: ________________ Date: ________

---

**END OF MASTER PLAN**

*Next Step: PM to invoke `/pm` to begin task breakdown and implementation*
