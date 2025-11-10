# Questions for Financial Engineer
## CryptoDataDownload API Integration Project

**Date:** 2025-10-25
**Project:** One-time historical data download from CryptoDataDownload API
**Status:** Awaiting FE Input

---

## Critical Questions (Must Answer Before Starting)

### Q1: Data Priority
**Question:** Which dataset is most critical for your backtesting needs?

**Options:**
- A) Deribit Options (OHLCV + Greeks + IV)
- B) Deribit Futures (Quarterly + Perpetuals)
- C) Both equally important
- D) Options first, then Futures if time permits

**Why this matters:** Determines download order and which data to validate most carefully.

---

### Q2: Historical Data Depth
**Question:** How far back do you need historical data?

**Options:**
- A) Maximum available (~2017-2019 depending on instrument)
- B) Last 3 years only (2022-2025)
- C) Last 5 years only (2020-2025)
- D) Other specific date range: ___________

**Why this matters:** Affects download time and storage requirements. Going back to 2017 means ~2 GB of data vs 500 MB for 3 years.

**Current database coverage:**
- Futures: Some 2019+ data (backfilled)
- Options: Only recent data from real-time collector (2025 only)
- Perpetuals: Recent data only (2025 only)

---

### Q3: Data Granularity
**Question:** What time granularity do you need?

**CryptoDataDownload offers:**
- Daily OHLCV (confirmed available)
- Hourly (may be available for some instruments)
- 1-minute (available for Binance, unclear for Deribit)

**Your preference:**
- A) Daily only (smaller download, faster)
- B) Hourly if available (medium size)
- C) 1-minute if available (very large, may not be available)
- D) Daily for options, Hourly for futures/perpetuals

**Why this matters:**
- Daily: ~2 GB total download
- Hourly: ~30-40 GB total download (24x larger)
- 1-minute: ~1-2 TB download (not practical)

**Recommendation:** Start with daily, can always get hourly later if needed.

---

### Q4: Options Greeks Requirements
**Question:** Which Greeks do you need for options backtesting?

**CryptoDataDownload provides:**
- Delta
- Gamma
- Vega
- Theta
- (Rho may not be available)

**Your needs:**
- A) All available Greeks
- B) Delta and Gamma only (position hedging)
- C) Vega and Theta only (volatility trading)
- D) Delta, Gamma, Vega, Theta (exclude Rho)

**Why this matters:** Determines database schema and validation checks.

**Note:** Your current `options_greeks` table already stores Delta, Gamma, Vega, Theta, Rho from real-time collection.

---

### Q5: Data Validation Strategy
**Question:** How should we validate CryptoDataDownload data accuracy?

**Options:**
- A) Spot-check against Deribit API for recent dates (2024-2025)
- B) Compare statistics (price ranges, volumes) with known benchmarks
- C) Visual inspection of sample data
- D) Trust CryptoDataDownload (they're a reputable provider)
- E) Combination: A + B

**Why this matters:** Determines QA effort and confidence level.

**Recommendation:** Option E (spot-check + statistics validation)

---

### Q6: Duplicate Handling Strategy
**Question:** If we find overlapping data between CryptoDataDownload and your existing database, which should we trust?

**Scenario:** You already have futures data from 2019-2025 (backfilled from Deribit). CryptoDataDownload also has 2019-2025 futures data.

**Options:**
- A) Keep existing data, only fill gaps
- B) Overwrite with CryptoDataDownload data (trust vendor)
- C) Keep whichever has more complete data (bid/ask/IV)
- D) Keep both, mark source in database

**Why this matters:** Affects data merger logic.

**Recommendation:** Option C (keep most complete data). Your current data has bid/ask/IV which may not be in CryptoDataDownload.

---

## Nice-to-Have Questions (Can Decide Later)

### Q7: Download Schedule
**Question:** Should we download everything in one go, or split into batches?

**Options:**
- A) Download all data in one 24-48 hour session
- B) Download options first (test), then futures
- C) Download by year (2017, 2018, etc.)

**Recommendation:** Option B (options first for testing)

---

### Q8: Evidence Documentation
**Question:** Do you need a detailed report of what was downloaded?

**Options:**
- A) Yes, detailed CSV report of all downloaded instruments and date ranges
- B) Yes, summary statistics only (total records, size, coverage)
- C) No, just confirm in database

**Recommendation:** Option B (summary statistics)

---

### Q9: Subscription Management
**Question:** When should we cancel the subscription?

**Options:**
- A) Immediately after successful download and validation
- B) Keep for 1 month in case we need to re-download
- C) Keep ongoing for monthly updates (costs $49.99/month)

**Recommendation:** Option A (cancel after validation). You have real-time collector for ongoing updates.

---

### Q10: Futures Contract Priority
**Question:** For futures, which contracts are most important?

**Options:**
- A) Perpetuals only (BTC-PERPETUAL, ETH-PERPETUAL)
- B) Quarterly contracts only (BTC-30JUN25, etc.)
- C) Both perpetuals and quarterlies
- D) Perpetuals + nearest 2 quarterly contracts

**Why this matters:** You already have good perpetuals coverage from real-time collection. Historical quarterlies may be more valuable.

**Recommendation:** Option C (both), but prioritize expired quarterly contracts (not available from Deribit API anymore).

---

## Your Current Database Status (for reference)

| Data Type | Current Coverage | Size | Source |
|-----------|------------------|------|--------|
| Options OHLCV | Recent only (2025) | 742 MB | Real-time collector |
| Futures OHLCV | 2019-2025 (partial) | 1,487 MB | Deribit backfill |
| Perpetuals OHLCV | Recent only (2025) | 1,165 MB | Real-time collector |
| Options Greeks | Recent only (2025) | 28 MB | Real-time collector |

**Gap:** Missing historical options (pre-2025) and expired futures contracts (2017-2024).

---

## Recommended Answers (PM Suggestion)

If you want to proceed quickly with sensible defaults:

1. **Q1:** C (Both options and futures equally important)
2. **Q2:** A (Maximum available historical data)
3. **Q3:** A (Daily only - keep it simple)
4. **Q4:** D (Delta, Gamma, Vega, Theta)
5. **Q5:** E (Spot-check + statistics)
6. **Q6:** C (Keep most complete data)
7. **Q7:** B (Options first, then futures)
8. **Q8:** B (Summary statistics)
9. **Q9:** A (Cancel after validation)
10. **Q10:** C (Both perpetuals and quarterlies)

**With these defaults, I can proceed with project decomposition immediately.**

---

## Next Steps

1. **You review these questions**
2. **Provide answers** (or approve defaults)
3. **I create Acceptance Criteria & Tasks**
4. **Engineer starts implementation**

**Expected Timeline:** 7-10 days from approval to completion.

---

**Status:** ⏳ Awaiting FE Response
