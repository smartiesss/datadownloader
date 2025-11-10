---
doc_type: questions
owner: orchestrator
recipient: FE
due_date: 2025-10-22
updated: 2025-10-21
---

# Questions for Financial Engineer (Due: 2025-10-22)

## Status: No Blocking Questions

After analyzing the master plan document (`CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md`), I have found **no blocking questions** for Phase 0-1 execution. The master plan is comprehensive and provides all necessary technical specifications.

## Phase 0-1 Clarifications (Optional - For Optimization)

### Q-001: Data Gap Tolerance Threshold (Non-Blocking)

**Context:** AC-004 specifies "100% of expected candles present (no gaps >5 minutes)"

**Question:** During exchange maintenance windows (documented by Deribit), are data gaps acceptable?

**Why Needed:** To set realistic expectations for QA validation in SMK-005

**Proposed Default:** Allow gaps during documented Deribit maintenance windows; flag all other gaps for investigation

**Blocking:** None (QA can proceed with strict criteria and refine based on actual results)

**Priority:** Low

**Due Date:** Before T-008 (QA checks) - Day 3

---

### Q-002: Storage Optimization Trigger (Non-Blocking)

**Context:** AC-006 specifies storage d 150 MB for perpetuals

**Question:** If storage exceeds 150 MB (but < 200 MB), should we:
- A) Accept the overage and update the AC
- B) Implement TimescaleDB compression immediately
- C) Flag as blocker and investigate

**Why Needed:** To define escalation path if storage estimate is off

**Proposed Default:** Option A (accept up to 200 MB); compression can be deferred to Phase 2

**Blocking:** None (proceed with 150 MB target, adjust if needed)

**Priority:** Low

**Due Date:** End of Phase 1 (Day 3)

---

## Phase 2-5 Questions (Future - Not Blocking Phase 0-1)

### Q-003: Futures Basis Spread Annualization (Future)

**Context:** AC-008 requires basis spread computation

**Question:** Should basis spread be annualized for comparison across different expiries?

**Why Needed:** To ensure apples-to-apples comparison of contango/backwardation across quarterly vs monthly futures

**Proposed Default:** Yes, annualize basis = (futures_price - perp_price) / perp_price × (365 / days_to_expiry)

**Blocking:** T-013 (Phase 2)

**Priority:** Medium

**Due Date:** Before Phase 2 starts (Week 1)

---

### Q-004: Options IV Convergence Failure Threshold (Future)

**Context:** AC-011 specifies 95%+ IV coverage

**Question:** For deep OTM options where Newton-Raphson fails to converge, should we:
- A) Mark IV as NULL and accept <100% coverage
- B) Use fallback proxy (e.g., ATM IV adjusted for moneyness)
- C) Flag as data quality issue

**Why Needed:** To handle edge cases in IV computation

**Proposed Default:** Option A (accept NULL for <5% of strikes)

**Blocking:** T-018 (Phase 3)

**Priority:** Medium

**Due Date:** Before Phase 3 starts (Week 2)

---

### Q-005: Greeks Risk-Free Rate Proxy (Future)

**Context:** AC-013 requires risk-free rate for Black-Scholes computation

**Question:** Which proxy should we use for historical risk-free rate (2022-2025)?
- A) Constant 5% (simple but inaccurate)
- B) Fetch historical 3-month T-bill rates from FRED API
- C) Use 0% (crypto-native approach)

**Why Needed:** To ensure Greeks accuracy

**Proposed Default:** Option B (fetch T-bill rates from FRED)

**Blocking:** T-021 (Phase 4)

**Priority:** High

**Due Date:** Before Phase 4 starts (Week 3)

---

## Assumptions Requiring Validation (Non-Urgent)

The following assumptions were made from the master plan. Please confirm or correct:

### A-001: Perpetuals Start Date

**Assumption:** BTC-PERPETUAL data available from 2016-12-01

**Source:** Master plan Section 2.1

**Validation Needed:** Confirm Deribit API provides data from this date

**Impact if Wrong:** Adjust start date in T-006

**Validation Method:** Will test in T-003 (API connectivity check)

---

### A-002: Storage Estimates

**Assumption:**
- Perpetuals: 150 MB
- Futures: 1.5 GB
- Options: 500 MB
- Greeks: 2 GB

**Source:** Master plan Section 1.2

**Validation Needed:** Confirm estimates match actual data after backfill

**Impact if Wrong:** May need larger VPS disk or implement compression sooner

**Validation Method:** Will measure in SMK-007, SMK-010, SMK-015

---

### A-003: API Rate Limits

**Assumption:** Deribit public API allows 20 req/sec

**Source:** Master plan Section 5.1

**Validation Needed:** Confirm current rate limits (may have changed since plan creation)

**Impact if Wrong:** Backfill runtime may be longer; need more aggressive backoff

**Validation Method:** Will test in T-003 and monitor 429 errors during backfill

---

## FE Sign-Off Required (End of Phase 1)

The following deliverables will require FE review and approval before Phase 2:

1. **Data Quality Report:** Gap analysis + outlier detection for perpetuals (T-008)
2. **Storage Report:** Actual vs. estimated storage usage (SMK-007)
3. **Phase 1 Completion:** All ACs met, all smoke tests passed

**Sign-off Due:** End of Day 3 (Phase 1 complete)

---

## Communication Protocol

**Response SLA:**
- **Normal Priority:** 24 business hours
- **URGENT:** 4 hours

**How to Respond:**
- Reply via `/finance` slash command
- Reference question ID (e.g., "Q-001: Approved")
- Provide explicit answer or decision

**Escalation:**
- If no response within SLA ’ PM escalates to user
- If blocker >48h ’ PM proposes default and proceeds with risk documentation

---

## Summary

**Total Questions:** 5 (0 blocking, 5 future)

**Immediate Action Required:** None - Phase 0-1 can proceed without FE input

**Future Action Required:** Respond to Q-003, Q-004, Q-005 before Phase 2-4

**Next Steps:**
1. PM proceeds with Phase 0 kickoff (T-001, T-003, T-004)
2. FE reviews this document at leisure
3. FE responds to future questions before respective phases start

---

**Document Status:** Active (monitoring for new questions)

**Last Updated:** 2025-10-21

---

This orchestration output structures work and verification. It is not trading, legal, accounting, or tax advice. Handle secrets securely and follow your organization's policies.
