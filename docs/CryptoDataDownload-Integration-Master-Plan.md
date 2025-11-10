# CryptoDataDownload API Integration - Master Plan

## Executive Summary

**Objective:** Integrate CryptoDataDownload API ($49.99/month) to backfill historical options, futures, and perpetuals data from Deribit, then cancel subscription after one-time download.

**Business Case:**
- One-time cost: $49.99 (vs. $5,000+/month alternatives)
- Historical data coverage: 2017-present for Deribit
- Fills data gaps in current database (currently only has data from recent backfills)
- After download, use existing real-time collector for ongoing updates

**Scope:**
1. Download historical Deribit options data (OHLCV + Greeks)
2. Download historical Deribit futures data (quarterly + perpetuals)
3. Merge with existing database without duplicates
4. Validate data integrity
5. Cancel subscription after successful download

---

## Current State Analysis

### Existing Database (as of 2025-10-25)
- **Total Size:** 4.1 GB
- **Options Data:** 742 MB (recent data only, collected via real-time collector)
- **Futures Data:** 1,487 MB (backfilled from Deribit API)
- **Perpetuals Data:** 1,165 MB (real-time collection)
- **Coverage:** Limited historical depth (weeks to months)

### Gap Analysis
**Missing Historical Data:**
- Options: Pre-2025 historical options with bid/ask/IV
- Futures: Expired quarterly contracts (2017-2024)
- Perpetuals: Historical perpetuals data before real-time collection started
- Greeks: Historical options Greeks for backtesting

---

## CryptoDataDownload API Capabilities

### Deribit Endpoints Available

#### 1. Deribit Futures (`/ohlc/deribit/futures/`)
- **Coverage:** 135+ futures assets
- **Contracts:** Quarterly + Perpetuals
- **Granularity:** Daily OHLCV
- **Historical Depth:** Back to ~2017

#### 2. Deribit Options
- **Data Types:**
  - Daily OHLCV for live and historical contracts
  - Summarized contract information
  - Greeks (Delta, Gamma, Vega, Theta)
  - Average Implied Volatility
  - Top 100 option transactions by USD value
- **Coverage:** BTC and ETH options
- **Historical Depth:** Back to options inception

### Data Formats
- JSON (preferred for API integration)
- CSV (alternative for bulk download)
- XLSX (not recommended for automation)

### Authentication
- Token-based: `Token <your_token_id>`
- Can use URL parameter: `?auth_token=<token>`

---

## Integration Strategy

### Phase 1: One-Time Historical Download (Week 1)
**Goal:** Download all historical Deribit data before current database coverage

**Approach:**
1. Subscribe to API ($49.99)
2. Download all historical data
3. Store in database with deduplication
4. Validate completeness
5. Cancel subscription

### Phase 2: Ongoing Updates (Week 2+)
**Goal:** Use existing real-time collector for new data

**Approach:**
- Continue real-time collection (already running)
- No additional API costs
- CryptoDataDownload data provides historical foundation

---

## Technical Architecture

### New Components Needed

#### 1. CryptoDataDownload Client
```
scripts/cryptodata_client.py
- Handles authentication
- Fetches historical data via API
- Supports JSON/CSV formats
- Rate limiting (TBD based on API limits)
```

#### 2. Historical Data Downloader
```
scripts/download_historical_cryptodata.py
- Downloads Deribit futures (all expired contracts)
- Downloads Deribit options (all historical contracts)
- Downloads Deribit perpetuals (historical data)
- Progress tracking and resumable downloads
```

#### 3. Data Merger
```
scripts/merge_cryptodata.py
- Checks for duplicates (timestamp + instrument)
- Fills gaps in existing data
- Validates data integrity
- Reports statistics
```

#### 4. Download Tracker
```
.cryptodata_download_status.json
- Tracks downloaded instruments
- Records download timestamps
- Prevents re-downloading
- Enables resume on failure
```

### Database Schema Compatibility

**Existing Tables:**
- `options_ohlcv` - Compatible (same structure)
- `futures_ohlcv` - Compatible (same structure)
- `perpetuals_ohlcv` - Compatible (same structure)
- `options_greeks` - May need new columns for CryptoDataDownload Greeks

**Validation:**
- Ensure timestamp formats match
- Verify instrument naming conventions (Deribit format)
- Check for timezone consistency (UTC)

---

## Data Volume Estimates

### Expected Downloads

#### Deribit Futures (2017-2025)
- **Instruments:** ~135 futures contracts
- **Timespan:** ~8 years
- **Granularity:** Daily candles
- **Estimated Records:** 135 contracts × 2,920 days = ~394,200 records
- **Estimated Size:** ~200-400 MB

#### Deribit Options (2019-2025)
- **Instruments:** Thousands of historical contracts
- **Timespan:** ~6 years (options started ~2019)
- **Granularity:** Daily candles
- **Estimated Records:** ~2-3 million records
- **Estimated Size:** ~800 MB - 1.5 GB

#### Deribit Perpetuals (2018-2025)
- **Instruments:** BTC-PERPETUAL, ETH-PERPETUAL
- **Timespan:** ~7 years
- **Granularity:** Daily candles (may have hourly)
- **Estimated Records:** 2 × 2,555 days = ~5,110 daily records
- **Estimated Size:** ~5-10 MB (negligible)

**Total Expected Download:** ~1-2 GB historical data

**Final Database Size:** 4.1 GB (current) + 1.5 GB (historical) = ~5.6 GB

---

## Risk Analysis

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits unknown | High | Implement conservative rate limiting, monitor responses |
| Data format mismatch | Medium | Validate sample data before bulk download |
| Database duplicates | Medium | Use UPSERT with timestamp+instrument unique constraint |
| Download interruption | Low | Implement resume capability with progress tracking |
| Insufficient disk space | Low | Check available space (need ~2 GB free) |

### Business Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| API doesn't have expected data | High | Test with trial/sample before committing |
| Data quality issues | Medium | Validate against Deribit API spot checks |
| Subscription cancellation issues | Low | Document cancellation process upfront |

---

## Success Criteria

### Must-Have (P0)
1. ✅ Download all available Deribit futures historical data
2. ✅ Download all available Deribit options historical data with Greeks
3. ✅ Merge into database without duplicates
4. ✅ Validate data completeness (no gaps)
5. ✅ Successfully cancel subscription after download

### Should-Have (P1)
1. ✅ Download resumable (can restart if interrupted)
2. ✅ Progress tracking dashboard
3. ✅ Data validation report
4. ✅ Automatic deduplication

### Nice-to-Have (P2)
1. ⭕ Compare CryptoDataDownload data vs Deribit API for accuracy
2. ⭕ Generate download evidence report
3. ⭕ Automated subscription cancellation

---

## Timeline Estimate

### Week 1: Development & Testing (5-7 days)
- Day 1: Subscribe to API, test authentication
- Day 2: Develop `cryptodata_client.py`
- Day 3: Develop `download_historical_cryptodata.py`
- Day 4: Test with small dataset (1 month of data)
- Day 5: Implement data merger and deduplication
- Day 6-7: Full download execution (24-48 hours runtime)

### Week 2: Validation & Cleanup (2-3 days)
- Day 1: Validate data completeness
- Day 2: Generate evidence report
- Day 3: Cancel subscription

**Total Duration:** 7-10 days

---

## Cost-Benefit Analysis

### Costs
- **Subscription:** $49.99 (one-time)
- **Development Time:** ~2-3 days
- **Disk Space:** +1.5 GB

### Benefits
- **Historical Data:** 6-8 years of Deribit data
- **Cost Savings:** Avoid $5,000+/month alternatives
- **Backtesting:** Enable accurate historical strategy testing
- **Data Completeness:** Fill gaps in current dataset

**ROI:** Extremely high (historical data for <$50)

---

## Next Steps

1. **PM Decision:** Approve plan and timeline
2. **Subscribe:** Purchase CryptoDataDownload API access
3. **Engineer:** Implement integration code
4. **QA:** Validate sample downloads
5. **Execute:** Run full historical download
6. **Verify:** Check data completeness
7. **Cancel:** Terminate subscription

---

## Questions for Financial Engineer

1. **Priority:** Which dataset is most critical? (Options, Futures, or Perpetuals?)
2. **Granularity:** Do we need daily only, or also hourly/minute data if available?
3. **Date Range:** Any specific start date for historical data? (e.g., 2020+ only?)
4. **Validation:** How should we validate CryptoDataDownload data accuracy?
5. **Greeks:** Do we need all Greeks or specific ones? (Delta, Gamma, Vega, Theta, Rho?)

---

**Document Status:** Draft Master Plan
**Created:** 2025-10-25
**Author:** Project Manager
**Next Action:** Await FE approval to proceed with decomposition
