# Comprehensive Crypto Data Collector - Project Plan

## Project Overview

**Goal:** Build a fully automated data collection system that captures:
- BTC + ETH perpetual futures (full orderbook depth + trades)
- BTC + ETH options (full orderbook depth + trades + Greeks)
- Automatic detection of new options listings
- Automatic removal of expired options
- 24/7 operation on NAS via Docker

## Current Status (2025-11-10)

### ✅ Completed Components
- [x] ETH options WebSocket collector with Greeks
- [x] BTC options WebSocket collector with Greeks
- [x] Perpetuals WebSocket collector (BTC-PERPETUAL, ETH-PERPETUAL)
- [x] Expiry detection logic (`instrument_expiry_checker.py`)
- [x] Full orderbook depth capture (20 levels via REST snapshots)
- [x] TimescaleDB schema with compression
- [x] Docker containerization
- [x] GitHub repository for code sync

### ⚠️ Partial/Needs Improvement
- [ ] New options detection (currently only on restart)
- [ ] Unified docker-compose for all collectors
- [ ] NAS deployment automation
- [ ] Production testing and validation

### ❌ Blocking Issues
- [ ] NAS database container failing to start
- [ ] Schema mismatch between code and database

## Project Phases

### Phase 1: Local Testing & Validation (TODAY)
**Goal:** Get everything working perfectly on local machine

**Tasks:**
- T-001: Create production docker-compose with all collectors
- T-002: Test database schema initialization
- T-003: Verify ETH options collector (orderbook + trades)
- T-004: Verify BTC options collector (orderbook + trades)
- T-005: Verify perpetuals collector (BTC/ETH)
- T-006: Test expiry detection with real instruments
- T-007: Verify 24-hour continuous operation
- T-008: Check data quality (no gaps, correct depth)

**Success Criteria:**
- All 5 containers running (DB, ETH-options, BTC-options, Perpetuals, Grafana)
- Data flowing to database for all instrument types
- No errors in logs for 24 hours
- Full orderbook depth captured (20 levels)

### Phase 2: NAS Deployment (AFTER Phase 1 Success)
**Goal:** Deploy tested system to NAS

**Tasks:**
- T-009: Create NAS-specific docker-compose (no port conflicts, no CPU limits)
- T-010: Create automated deployment script
- T-011: Deploy to NAS via git pull
- T-012: Verify NAS system resources (RAM, disk space)
- T-013: Set up automatic restart on failure
- T-014: Configure log rotation

**Success Criteria:**
- All containers start on NAS without errors
- Data collection running for 7 days without intervention
- Grafana accessible from network

### Phase 3: Enhancements (FUTURE)
**Goal:** Add advanced features

**Tasks:**
- T-015: Real-time new instrument detection (hourly refresh)
- T-016: WebSocket auto-resubscribe for new options
- T-017: Auto-unsubscribe from expired options
- T-018: Alerting for data gaps
- T-019: Backup automation
- T-020: Performance optimization

## Acceptance Criteria

### AC-001: Complete Data Coverage
- **GIVEN** system is running
- **WHEN** I query the database
- **THEN** I should see:
  - BTC-PERPETUAL orderbook (20 levels) and trades
  - ETH-PERPETUAL orderbook (20 levels) and trades
  - Top 50 BTC options orderbook (20 levels) and trades
  - Top 50 ETH options orderbook (20 levels) and trades
  - Greeks for all options
  - No data gaps > 1 minute

### AC-002: Expiry Detection
- **GIVEN** an option is about to expire
- **WHEN** expiry time + 5 minutes has passed
- **THEN** collector should stop fetching that instrument

### AC-003: New Instrument Detection
- **GIVEN** system is running
- **WHEN** a new option is listed on Deribit
- **THEN** system should detect and start collecting within 1 hour

### AC-004: 24/7 Reliability
- **GIVEN** system deployed to NAS
- **WHEN** running for 7 days
- **THEN** uptime should be > 99.9%
  - **AND** auto-reconnect on WebSocket disconnects
  - **AND** auto-restart on container failure

### AC-005: NAS Resource Efficiency
- **GIVEN** system running on NAS
- **THEN** resource usage should be:
  - Memory: < 4GB total
  - CPU: < 50% average
  - Disk growth: < 10GB/day
  - Network: < 1Mbps average

## Data Collection Specifications

### Perpetuals (BTC-PERPETUAL, ETH-PERPETUAL)
**Source:** WebSocket + REST API
**Frequency:**
- WebSocket: Real-time (100ms updates)
- REST snapshots: Every 5 minutes

**Data Captured:**
- Best bid/ask price and amount
- Mark price
- Index price
- Funding rate (8-hour)
- Open interest
- Full orderbook (20 levels)
- All trades

### Options (BTC + ETH, Top 50 by Open Interest)
**Source:** WebSocket + REST API
**Frequency:**
- WebSocket: Real-time (100ms updates)
- REST snapshots: Every 5 minutes

**Data Captured:**
- Best bid/ask price and amount
- Mark price
- Underlying price
- Greeks (delta, gamma, theta, vega, rho)
- Implied volatility (bid, ask, mark)
- Open interest
- Last price
- Full orderbook (20 levels)
- All trades

### Instrument Selection Logic
```python
# Perpetuals: Hardcoded list
instruments = ['BTC-PERPETUAL', 'ETH-PERPETUAL']

# Options: Dynamic top N by open interest
eth_options = fetch_top_n_options(currency='ETH', n=50, sort_by='open_interest')
btc_options = fetch_top_n_options(currency='BTC', n=50, sort_by='open_interest')

# Filter expired options
active_eth_options = filter_expired_instruments(eth_options)
active_btc_options = filter_expired_instruments(btc_options)
```

## Technical Architecture

```
┌─────────────────────────────────────────────────────┐
│                   NAS Docker Host                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ ETH Options  │  │ BTC Options  │               │
│  │  Collector   │  │  Collector   │               │
│  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                        │
│  ┌──────▼──────────────────▼───────┐               │
│  │    Perpetuals Collector         │               │
│  │  (BTC-PERP + ETH-PERP)          │               │
│  └──────┬──────────────────────────┘               │
│         │                                           │
│  ┌──────▼──────────────────────────┐               │
│  │      TimescaleDB                │               │
│  │  - Hypertables (1-day chunks)   │               │
│  │  - Compression (7-day policy)   │               │
│  │  - Retention (90-day status)    │               │
│  └─────────────────────────────────┘               │
│                                                     │
│  ┌─────────────────────────────────┐               │
│  │         Grafana                  │               │
│  │    (Data Visualization)          │               │
│  └─────────────────────────────────┘               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Database Schema

### Tables
1. `eth_option_quotes` - ETH options Level 1 quotes + Greeks
2. `eth_option_trades` - ETH options trades
3. `eth_option_orderbook_depth` - ETH options full orderbook (20 levels)
4. `btc_option_quotes` - BTC options Level 1 quotes + Greeks
5. `btc_option_trades` - BTC options trades
6. `btc_option_orderbook_depth` - BTC options full orderbook (20 levels)
7. `perpetuals_quotes` - Perpetuals Level 1 quotes + funding
8. `perpetuals_trades` - Perpetuals trades
9. `perpetuals_orderbook_depth` - Perpetuals full orderbook (20 levels)

### Storage Estimates
- Options quotes: ~15M/day × 2 currencies = 30M/day → ~3.6 GB/day uncompressed
- Options trades: ~2M/day × 2 currencies = 4M/day → ~400 MB/day uncompressed
- Perpetuals quotes: ~10M/day × 2 instruments = 20M/day → ~2 GB/day uncompressed
- Perpetuals trades: ~1M/day × 2 instruments = 2M/day → ~200 MB/day uncompressed
- Orderbook snapshots: ~288 snapshots/day × 100 instruments → ~2 GB/day uncompressed

**Total: ~8.2 GB/day uncompressed → ~3-4 GB/day with compression**

## Next Steps

1. **TODAY:** Create production docker-compose and test locally
2. **Verify:** 24-hour local test with all collectors
3. **Deploy:** Push to NAS after local validation
4. **Monitor:** 7-day stability test on NAS
5. **Enhance:** Add real-time new instrument detection

## Risk Mitigation

### Risk 1: NAS Database Won't Start
**Mitigation:** Test locally first, fix all issues before NAS deployment

### Risk 2: Data Loss During Restart
**Mitigation:** In-memory buffers flush before shutdown, auto-reconnect on failure

### Risk 3: Missed New Options Listings
**Mitigation:** Phase 3 enhancement - hourly instrument refresh

### Risk 4: NAS Resource Exhaustion
**Mitigation:** Memory limits in docker-compose, compression policies, log rotation

## Success Metrics

### Week 1
- [ ] All collectors running locally for 24 hours
- [ ] Zero errors in logs
- [ ] Data quality > 99% (no gaps)

### Week 2
- [ ] NAS deployment successful
- [ ] 7-day continuous operation on NAS
- [ ] Grafana dashboards functional

### Month 1
- [ ] 30-day uptime > 99.5%
- [ ] Database size < 120 GB (4 GB/day × 30)
- [ ] All new options detected and collected
