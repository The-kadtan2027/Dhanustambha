# PROGRESS.md — Project Status Tracker

> **Agents:** Update this file after every completed task. This is the project memory.

**Last updated:** 2026-04-13  
**Current phase:** Phase 1 Validation — accumulating live NSE data  
**Active plan:** `2026-04-11-phase1-mvp.md` (at project root)

---

## Phase Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | MVP: Data + Market Monitor + Scanner → daily_briefing.py | ✅ Implemented + Validated |
| Phase 2 | Trade Management: position sizer, open trade log, P&L | 🔲 Blocked on Phase 1 |
| Phase 3 | Review Loop: journal, analytics, backtester | 🔲 Blocked on Phase 2 |
| Phase 4 | FastAPI + Next.js UI dashboard | 🔲 Blocked on Phase 3 |

---

## Completed Tasks

- ✅ 2026-04-13 — Task 1: Project scaffold and config
- ✅ 2026-04-13 — Task 2: SQLite schema and store module
- ✅ 2026-04-13 — Task 3: Symbol list and NSE data fetcher
- ✅ 2026-04-13 — Task 4: Market Monitor breadth engine
- ✅ 2026-04-13 — Task 5: Momentum Burst scanner
- ✅ 2026-04-13 — Task 6: Episodic Pivot and Trend Intensity scanners
- ✅ 2026-04-13 — Task 7: Daily briefing orchestrator and watchlist export
- ✅ 2026-04-13 — Phase 1 Validation: symbol universe cleanup (`MM`→`M&M`, `ULTRACEMIN`→`ULTRACEMCO`)
- ✅ 2026-04-13 — Phase 1 Validation: annotated all config.py thresholds with NSE calibration status

---

## In Progress

- Running the briefing live each weekday to accumulate NSE breadth history

---

## Open Questions

- [ ] **Market Monitor thresholds (ADR-007):** Thresholds are Pradeep Bonde's US S&P 500 defaults.
  NSE threshold calibration **requires ~60 trading days of live breadth data** first.
  Until then, treat OFFENSIVE/DEFENSIVE verdicts as directionally useful but not
  NSE-validated. Do not change threshold numbers without an evidence base.
  See `config.py` inline comments for the action plan.

- [ ] **Upper circuit handling in Momentum Burst scanner:** A stock hitting an upper
  circuit limit (20% cap) will be flagged as a Momentum Burst with an anomalously
  high volume ratio. No circuit-limit data source is available in the free tier.
  **Workaround:** `MB_MAX_PCT_CHANGE = 25.0` caps out most circuit events.
  A proper fix requires a circuit-limit feed — Phase 2 enhancement.

---

## Noted Issues

- Active plan file is at repository root as `2026-04-11-phase1-mvp.md` (not under `docs/plans/` as originally intended — low priority to move)
- `NIFTY500` universe is currently a NIFTY50 placeholder. Expanding to full 500 symbols is the next major data-quality improvement, deferred to after Phase 2.

---

## Deviations from Plan

- `requirements.txt` now includes `nselib==2.4.6`; fetcher uses `nselib` bhavcopy as primary live NSE source
- `requirements.txt` uses `nsepy==0.8` (not `0.8.2` — not on PyPI)
- `requirements.txt` uses `pandas-ta-classic==0.3.14b2` (original `pandas-ta==0.3.14b` unavailable; modern releases require NumPy >= 2.2.6 which conflicts on Python 3.12)
- `requirements.txt` uses `numpy==2.2.6` (NumPy 2.x required by the TA library on Python 3.12)
- `fetch_via_yfinance()` queries a date window around `fetch_date` (not `period="5d"`) so historical overrides work during validation
- `fetch_eod_data()` treats empty nselib responses as holidays — no noisy yfinance fallback
- `daily_briefing.py` incrementally backfills missing business-day history before computing breadth and scanners

---

## Next Action

Run `python scripts/daily_briefing.py` every weekday after 16:30 IST.  
After ~60 trading days of breadth data have accumulated, review the
OFFENSIVE/DEFENSIVE verdict history against NIFTY 500 weekly returns and tune
thresholds in `config.py`. See ADR-007 in `docs/architecture/DECISIONS.md`.
