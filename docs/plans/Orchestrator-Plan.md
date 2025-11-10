---
doc_type: plan
owner: orchestrator
updated: 2025-10-21
links:
  - ../../CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md
  - ../release/Acceptance-Criteria.md
  - ../tasks/Backlog.md
  - ../tests/Smoke-Plan.md
---

# Orchestrator Plan — Crypto Data Infrastructure (Phase 0-1)

## Executive Summary

**Project:** Self-sustaining crypto derivatives data infrastructure
**Business Case:** $21,300/year savings (98% cost reduction vs. buying data)
**Timeline:** 4 weeks (62 hours total effort across 5 phases)
**Current Focus:** Phase 0-1 (Foundation + Perpetuals Backfill)
**Gate Strategy:** Prove pipeline works end-to-end before scaling to futures/options

## Scope

### In-Scope (Phase 0-1)
- Development environment setup (Python, PostgreSQL, TimescaleDB)
- Database schema creation with TimescaleDB hypertables
- Deribit API connectivity validation
- Backfill 9 years of perpetuals OHLCV data (BTC, ETH)
- Data quality validation (gaps, sanity checks)
- Logging infrastructure with rotation

### Out-of-Scope (Future Phases)
- Futures backfill (Phase 2)
- Options backfill + IV computation (Phase 3)
- Historical Greeks calculation (Phase 4)
- 24/7 real-time collection on VPS (Phase 5)

## Milestones & Dates

| Milestone | Description | Target Date | Status | Gate Criteria |
|-----------|-------------|-------------|--------|---------------|
| **M0** | Phase 0 Complete (Prerequisites) | Day 1 | Pending | SMK-001, SMK-002, SMK-003 pass |
| **M1** | Phase 1 Complete (Perpetuals) | Day 3 | Pending | SMK-004, SMK-005, SMK-006, SMK-007 pass |
| **M2** | Phase 2 Complete (Futures) | Week 1 | Future | SMK-008, SMK-009, SMK-010 pass |
| **M3** | Phase 3 Complete (Options) | Week 2 | Future | SMK-011, SMK-012, SMK-013 pass |
| **M4** | Phase 4 Complete (Greeks) | Week 3 | Future | SMK-014, SMK-015, SMK-016 pass |
| **M5** | Phase 5 Complete (Real-time) | Week 4 | Future | SMK-017, SMK-018, SMK-019, SMK-020 pass |

**Current Focus:** M0 → M1 (Days 1-3)

## Swimlanes

### Financial Engineer (FE) Lane

**Phase 0-1 Responsibilities:**
- ✅ Master plan delivered (CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md)
- ✅ Technical specifications defined (API endpoints, data models)
- ⏳ Available for clarification questions (Q-001 pending)
- ⏳ Review data quality reports after Phase 1

**Deliverables:**
- [x] Master plan document
- [ ] Approval of Phase 0-1 completion

**Blockers:** None

---

### Engineering (ENG) Lane

**Phase 0 Tasks:**
| ID    | Task | Effort | Dependencies | Status | Owner |
|-------|------|--------|--------------|--------|-------|
| T-001 | Install Python 3.10+, PostgreSQL, TimescaleDB | S (4h) | – | Ready | TBD |
| T-002 | Create database schema (hypertables) | S (3h) | T-001 | Blocked | TBD |
| T-003 | Test Deribit API connectivity | XS (1h) | – | Ready | TBD |
| T-004 | Set up error logging + file rotation | S (2h) | – | Ready | TBD |

**Phase 0 Total:** 10 hours (can be parallelized to 4 hours)

**Phase 1 Tasks:**
| ID    | Task | Effort | Dependencies | Status | Owner |
|-------|------|--------|--------------|--------|-------|
| T-005 | Implement `backfill_perpetuals.py` script | M (2d) | T-002, T-003 | Blocked | TBD |
| T-006 | Backfill BTC-PERPETUAL (2016-2025) | S (2h) | T-005 | Blocked | TBD |
| T-007 | Backfill ETH-PERPETUAL (2017-2025) | S (2h) | T-005 | Blocked | TBD |

**Phase 1 ENG Total:** 20 hours (2.5 days)

**Deliverables:**
- [ ] Environment setup validated (T-001)
- [ ] Database schema deployed (T-002)
- [ ] API connectivity confirmed (T-003)
- [ ] Logging configured (T-004)
- [ ] Backfill script implemented (T-005)
- [ ] Perpetuals data loaded (T-006, T-007)

**Blockers:** None for T-001, T-003, T-004 (can start immediately)

---

### QA (Smoke Tester) Lane

**Phase 0 Tests:**
| ID      | Test | ACs Covered | Dependencies | Status |
|---------|------|-------------|--------------|--------|
| SMK-001 | API Connectivity Check | AC-001 | T-003 | Blocked |
| SMK-002 | Database Schema Validation | AC-002 | T-002 | Blocked |
| SMK-003 | Log File Rotation Check | AC-003 | T-004 | Blocked |

**Phase 1 Tests:**
| ID      | Test | ACs Covered | Dependencies | Status |
|---------|------|-------------|--------------|--------|
| SMK-004 | Perpetuals Row Count Check | AC-004 | T-006, T-007 | Blocked |
| SMK-005 | Gap Detection Check | AC-004 | T-006, T-007 | Blocked |
| SMK-006 | OHLCV Sanity Check | AC-005 | T-006, T-007 | Blocked |
| SMK-007 | Perpetuals Storage Check | AC-006 | T-006, T-007 | Blocked |

**Phase 0-1 QA Total:** 8 hours

**Deliverables:**
- [ ] Smoke test evidence for Phase 0 (3 tests)
- [ ] Smoke test evidence for Phase 1 (4 tests)
- [ ] Data quality report with gap/outlier analysis

**Blockers:** Waiting on ENG completion of T-002, T-003, T-004 (Phase 0)

---

### Orchestrator (PM) Lane

**Phase 0-1 Responsibilities:**
- [x] Extract acceptance criteria from master plan (19 ACs)
- [x] Create task breakdown (30 tasks across 5 phases)
- [x] Define smoke test plan (20 tests)
- [x] Publish Orchestrator Plan, Backlog, Acceptance Criteria docs
- [ ] Assign owners to T-001, T-003, T-004 (Phase 0 kickoff)
- [ ] Track progress in Daily-Status.md
- [ ] Gate Phase 1 start on Phase 0 completion
- [ ] Coordinate FE/ENG/QA via questions/handoffs

**Deliverables:**
- [x] Acceptance-Criteria.md (19 ACs with traceability)
- [x] Backlog.md (Phase 0-1 detailed, Phase 2-5 high-level)
- [x] Smoke-Plan.md (7 tests for Phase 0-1)
- [x] Orchestrator-Plan.md (this document)
- [ ] Daily-Status.md (ongoing)

**Blockers:** None

---

## Dependencies (Phase 0-1)

```
Phase 0:
--------
T-001 (Install deps) ────────┐
                             ├─→ T-002 (Schema) ─────┐
T-003 (API test) ────────────┤                       ├─→ T-005 (Backfill script)
                             │                       │
T-004 (Logging) [parallel] ──┘                       │
                                                     │
Phase 1:                                             │
--------                                             │
T-005 (Backfill script) ←────────────────────────────┘
  ↓
T-006 (BTC backfill) ────┐
                         ├─→ T-008 (QA checks) ─→ SMK-004, SMK-005, SMK-006, SMK-007
T-007 (ETH backfill) ────┘

Gate Checks:
------------
SMK-001, SMK-002, SMK-003 (Phase 0) → GATE → Phase 1 starts
SMK-004, SMK-005, SMK-006, SMK-007 (Phase 1) → GATE → Phase 2 planning
```

**Critical Path:** T-001 → T-002 → T-005 → T-006/T-007 → T-008 → Smoke Tests
**Duration:** 3.5 days (optimized with parallelization)

## Risks & Mitigations

| Risk ID | Description | Probability | Impact | Mitigation | Owner | Status |
|---------|-------------|-------------|--------|------------|-------|--------|
| **R-001** | Deribit API rate limits (20 req/sec) | Medium | High | Exponential backoff, 0.05s sleep between calls | ENG | Open |
| **R-002** | Historical data gaps (exchange maintenance) | High | Medium | Document exceptions, accept gaps <1% | QA | Open |
| **R-003** | Database disk space exhausted | Low | High | Monitor storage, TimescaleDB compression | ENG | Open |
| **R-004** | Python dependency conflicts | Low | Medium | Use virtualenv, pin versions in requirements.txt | ENG | Open |
| **R-005** | TimescaleDB installation fails | Low | High | Test on VM first, follow official docs | ENG | Open |
| **R-006** | Backfill runtime exceeds estimates | Medium | Low | Run overnight, parallelize BTC/ETH | ENG | Open |
| **R-007** | Data quality issues (corrupted OHLCV) | Low | Medium | Implement sanity checks, re-fetch if violations | QA | Open |

**Top 3 Risks for Phase 0-1:**
1. **R-001:** API rate limits → Could extend Phase 1 runtime from 4h to 8h
2. **R-002:** Data gaps → May require documenting exceptions vs. achieving 100% coverage
3. **R-006:** Backfill runtime → Could delay Phase 1 completion by 1 day

**Risk Monitoring:**
- Track API 429 errors in logs (R-001)
- Run gap detection query daily during backfill (R-002)
- Monitor `/data/` disk usage (R-003)

## Communication Cadence

**Daily Standups (Async):**
- Update `/docs/status/Daily-Status.md` with:
  - Yesterday: Completed tasks
  - Today: In-progress tasks
  - Blockers: Risks/issues

**Weekly Reviews:**
- Friday EOD: Milestone review
- Deliverables: Updated Backlog.md, Acceptance-Criteria.md

**Ad-Hoc:**
- Questions via `/handoff/outbox/Questions-to-{FE|ENG|QA}.md`
- SLA: 24h response (4h for URGENT)

## Phase 0 Execution Plan (Day 1)

**Hour 0-1: Kickoff**
- PM assigns owners to T-001, T-003, T-004
- ENG starts T-001 (install dependencies)
- ENG starts T-003 (API test) in parallel

**Hour 1-2: Environment Setup**
- T-001: Install Python 3.10, PostgreSQL 14, TimescaleDB
- T-003: Test Deribit `/public/test` endpoint
- T-004: Configure logging with rotation

**Hour 2-3: Database Setup**
- T-002: Create schema.sql with 6 hypertables
- T-002: Execute schema: `psql -U postgres -d crypto_data -f schema.sql`

**Hour 3-4: Validation (QA)**
- SMK-001: API connectivity check
- SMK-002: Database schema validation (6 hypertables)
- SMK-003: Log rotation check (generate 50 MB logs)

**Gate Check (End of Day 1):**
- ✅ All Phase 0 tasks complete (T-001, T-002, T-003, T-004)
- ✅ All Phase 0 smoke tests pass (SMK-001, SMK-002, SMK-003)
- ✅ Evidence collected in `/tests/evidence/`
- ✅ Phase 1 unblocked

## Phase 1 Execution Plan (Days 2-3)

**Day 2: Implement Backfill Script**
- T-005: Develop `backfill_perpetuals.py` (8 hours)
  - CLI args: --instruments, --start, --end, --resolution
  - API rate limiting with exponential backoff
  - Database upsert (idempotent writes)
  - Error logging

**Day 3: Execute Backfill + QA**
- Hour 0-2: T-006 (BTC-PERPETUAL backfill, 2h runtime)
- Hour 2-4: T-007 (ETH-PERPETUAL backfill, 2h runtime, parallel)
- Hour 4-6: T-008 (QA data quality checks)
  - Gap detection SQL
  - OHLCV sanity checks
  - Storage verification
- Hour 6-7: Smoke tests (SMK-004, SMK-005, SMK-006, SMK-007)

**Gate Check (End of Day 3):**
- ✅ All Phase 1 tasks complete (T-005, T-006, T-007, T-008)
- ✅ All Phase 1 smoke tests pass
- ✅ Data quality report approved by FE
- ✅ Phase 2 planning can begin

## Success Metrics (Phase 0-1)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Phase 0 completion | Day 1 (4h) | TBD | Pending |
| Phase 1 completion | Day 3 (20h) | TBD | Pending |
| Smoke test pass rate | 100% (7/7 tests) | TBD | Pending |
| Perpetuals row count | ~4.73M rows (BTC+ETH) | TBD | Pending |
| Data gap count | 0 gaps >5 min | TBD | Pending |
| OHLCV violations | 0 violations | TBD | Pending |
| Storage usage | ≤150 MB | TBD | Pending |
| Backfill runtime | ≤4 hours | TBD | Pending |

## Acceptance Criteria Summary (Phase 0-1)

**Phase 0 (Critical):**
- AC-001: Deribit API connectivity validated
- AC-002: Database schema created with indexes
- AC-003: Log file rotation configured

**Phase 1 (Critical):**
- AC-004: Perpetuals OHLCV complete (no gaps >5 min)
- AC-005: Perpetuals OHLCV sanity checks pass
- AC-006: Perpetuals storage ≤ 150 MB

**Total:** 6 acceptance criteria for Phase 0-1

## Next Steps (Immediate Actions)

1. **PM → Assign Owners**
   - T-001: Install dependencies → Assign to ENG
   - T-003: API connectivity → Assign to ENG
   - T-004: Logging setup → Assign to ENG

2. **PM → Create Daily-Status.md Template**
   - Initialize status tracking

3. **PM → Invoke /coder for Phase 0 Kickoff**
   - Handoff Acceptance-Criteria.md, Backlog.md, Smoke-Plan.md
   - Request effort estimate validation for T-001 through T-008
   - Confirm technical feasibility (any missing dependencies?)

4. **PM → Invoke /qa for Smoke Plan Review**
   - Validate smoke tests are copy-paste ready
   - Confirm expected outputs are deterministic
   - Identify any missing edge cases

5. **ENG → Start Phase 0 Tasks**
   - T-001, T-003, T-004 (can run in parallel)
   - Target: Complete by end of Day 1

## Document Links

**Planning:**
- Master Plan: `/CRYPTO_DATA_INFRASTRUCTURE_MASTER_PLAN.md`
- Orchestrator Plan: `/docs/plans/Orchestrator-Plan.md` (this document)

**Requirements:**
- Acceptance Criteria: `/docs/release/Acceptance-Criteria.md`

**Tasks:**
- Backlog: `/docs/tasks/Backlog.md`
- In-Progress: `/docs/tasks/In-Progress.md` (TBD)

**Testing:**
- Smoke Plan: `/docs/tests/Smoke-Plan.md`

**Status:**
- Daily Status: `/docs/status/Daily-Status.md` (TBD)

**Handoffs:**
- Questions to FE: `/handoff/outbox/Questions-to-FE.md` (if needed)
- Questions to ENG: `/handoff/outbox/Questions-to-ENG.md` (if needed)
- Questions to QA: `/handoff/outbox/Questions-to-QA.md` (if needed)

## Phase 2-5 Outlook (Future)

**Phase 2 (Futures):** Week 1
- 5 tasks (T-009 through T-013)
- 8 hours development + 6 hours runtime
- 3 smoke tests (SMK-008, SMK-009, SMK-010)

**Phase 3 (Options):** Week 2
- 6 tasks (T-014 through T-019)
- 20 hours total (IV computation is complex)
- 3 smoke tests (SMK-011, SMK-012, SMK-013)

**Phase 4 (Greeks):** Week 3
- 5 tasks (T-020 through T-024)
- 12 hours total (Black-Scholes + validation)
- 3 smoke tests (SMK-014, SMK-015, SMK-016)

**Phase 5 (Real-time):** Week 4
- 6 tasks (T-025 through T-030)
- 16 hours total (VPS deployment + monitoring)
- 4 smoke tests (SMK-017, SMK-018, SMK-019, SMK-020)

**Total Project Duration:** 4 weeks (62 hours effort)

## Abort Criteria

**Abort Phase 0 if:**
- TimescaleDB installation fails after 3 attempts → Escalate to FE for alternative (InfluxDB?)
- Deribit API is consistently unavailable (>24h downtime) → Wait or pivot to alternative exchange

**Abort Phase 1 if:**
- Data gaps exceed 10% of expected candles → Investigate API issue before proceeding
- OHLCV sanity violations exceed 1% → Data quality too poor for strategies
- Backfill runtime exceeds 12 hours → Re-architect with parallel workers or cloud compute

**Escalation Path:**
- Blocker >24h → PM documents in Questions-to-FE.md with proposed alternatives
- Blocker >48h → PM escalates to user for decision

## Sign-offs Required (End of Phase 1)

- [ ] **FE:** Data quality acceptable, gaps documented and justified
- [ ] **ENG:** All code committed, smoke tests passing, no known bugs
- [ ] **QA:** All smoke tests executed with evidence collected
- [ ] **Orchestrator:** All ACs met, traceability complete, Phase 2 ready to start

---

**End of Orchestrator Plan**

This orchestration output structures work and verification. It is not trading, legal, accounting, or tax advice. Handle secrets securely and follow your organization's policies.
