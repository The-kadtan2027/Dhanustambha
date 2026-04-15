# PROGRESS.md - Project Status Tracker

> Agents: update this file after every completed task. This is the project memory.

**Last updated:** 2026-04-15
**Current phase:** Phase 2 Operationalization + NSE Calibration Tooling
**Active plan:** `implementation_plan.md` (at project root)

## Phase Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | MVP: Data + Market Monitor + Scanner -> `daily_briefing.py` | Implemented + live validation ongoing |
| Phase 2 | Trade Management: position sizer, open trade log, P&L | Core workflow implemented |
| Phase 3 | Review Loop: journal, analytics, backtester | Backtesting/calibration scaffolding implemented |
| Phase 4 | FastAPI + Next.js UI dashboard | Blocked on Phase 3 |

## Completed Tasks

- 2026-04-13 - Task 1: Project scaffold and config
- 2026-04-13 - Task 2: SQLite schema and store module
- 2026-04-13 - Task 3: Symbol list and NSE data fetcher
- 2026-04-13 - Task 4: Market Monitor breadth engine
- 2026-04-13 - Task 5: Momentum Burst scanner
- 2026-04-13 - Task 6: Episodic Pivot and Trend Intensity scanners
- 2026-04-13 - Task 7: Daily briefing orchestrator and watchlist export
- 2026-04-13 - Phase 1 Validation: symbol universe cleanup (`MM` -> `M&M`, `ULTRACEMIN` -> `ULTRACEMCO`)
- 2026-04-13 - Phase 1 Validation: annotated all `config.py` thresholds with NSE calibration status
- 2026-04-13 - Stream A: dynamic NSE constituent loading finalized (`NIFTY500` default, `NIFTY750` optional via `MICROCAP250`)
- 2026-04-13 - Stream B: manual trade workflow implemented (`trade/log.py`, `trade_manager.py`, trade status/summary)
- 2026-04-13 - Stream C: historical backfill + scanner calibration scaffolding implemented
- 2026-04-13 - Stream C: 3-year NIFTY500 historical backfill completed (`342,283` OHLCV rows stored; `nselib` history primary, `yfinance` fallback retained)
- 2026-04-14 - Stream C: Momentum Burst calibration completed for `NIFTY500`; report saved to `data/calibration/2026-04-14-momentum_burst-NIFTY500.csv`
- 2026-04-15 - Stream C: Episodic Pivot calibration completed for `NIFTY500`; report saved to `data/calibration/2026-04-15-episodic_pivot-NIFTY500.csv`
- 2026-04-15 - Stream C: Trend Intensity calibration completed for `NIFTY500`; report saved to `data/calibration/2026-04-15-trend_intensity-NIFTY500.csv`
- 2026-04-15 - Scanner defaults updated from calibration review: `EP_MIN_GAP_VOLUME_RATIO=5.0`, `TI_MAX_ATR_PCT=0.05`, `TI_MIN_DAYS_ABOVE_MA50=40`

## In Progress

- Running the briefing live each weekday to accumulate NSE breadth history
- Reviewing scanner calibration rankings and deciding whether to tune thresholds in `config.py`
- Monitoring the calibrated scanner defaults in live daily briefings
- 2026-04-15 monitoring checkpoint: reran `daily_briefing.py --date 2026-04-13` against the local DB after adopting calibrated EP/TI defaults; verdict was `DEFENSIVE` with `21` Momentum Burst, `4` Episodic Pivot, and `3` Trend Intensity candidates, and the saved top-10 watchlist remained Momentum Burst-heavy (`6` MB, `3` EP, `1` TI candidate was filtered out of the top list)

## Open Questions

- [ ] **Market Monitor thresholds (ADR-007):** Thresholds are Pradeep Bonde's US S&P 500 defaults. NSE threshold calibration still requires about 60 trading days of live breadth data. Until then, treat `OFFENSIVE` and `DEFENSIVE` as directionally useful but not NSE-validated.

- [ ] **Upper circuit handling in Momentum Burst:** A stock hitting an upper circuit can still look like a strong burst on free EOD data. The current mitigation is `MB_MAX_PCT_CHANGE = 25.0`. A cleaner fix needs circuit-limit data.

- [ ] **Calibration objective:** Backtesting currently optimizes for forward-return hit rate at `+5d`, `+10d`, and `+20d`. Benchmark-relative scoring versus NIFTY can be added later if raw signal quality is not enough.

- [ ] **Intraday/opening alerts as a future phase:** User wants help reducing market-open FOMO and missed entries. Keep Phase 2 on the current EOD/manual workflow, but capture a future enhancement for "opening-plan" alerts first, and only consider true intraday signal generation after an explicit architecture decision because it would break ADR-004 (`EOD only`) and increase data/infrastructure complexity.

## Noted Issues

- The active plan file remains at repository root instead of under `docs/plans/`.
- `implementation_plan.md` is now the active multi-stream follow-on plan and should be kept aligned with this tracker.
- Legacy OHLCV rows still exist for `TATAMOTORS`, while the current NSE constituent universe resolves that company as `TMCV`. Treat this as a symbol-alias cleanup follow-up, not a calibration blocker.
- The current environment has no default `python`/`py` command on `PATH`; use `C:\Program Files\Python312\python.exe` for manual local runs from PowerShell unless the shell environment is updated.

## Deviations from Plan

- `requirements.txt` includes `nselib==2.4.6`; fetcher uses `nselib` bhavcopy as the primary live NSE source.
- Historical backfill now uses `nselib.capital_market.price_volume_data()` as the primary source because `yfinance` batch history returned empty/no-timezone responses for many NSE tickers during calibration backfill.
- `requirements.txt` uses `nsepy==0.8` (not `0.8.2`, which is unavailable on PyPI).
- `requirements.txt` uses `pandas-ta-classic==0.3.14b2`.
- `requirements.txt` uses `numpy==2.2.6`.
- `fetch_via_yfinance()` queries an explicit date window around `fetch_date` so historical overrides work during validation.
- `daily_briefing.py` incrementally backfills missing business-day history before computing breadth and scanners.
- `NIFTY750` is implemented as `NIFTY500 + MICROCAP250` because official NSE constituent data shows `SMALLCAP250` overlaps fully with `NIFTY500`.
- `trade_manager.py` is an interactive CLI rather than a CSV-driven workflow.
- `calibrate_thresholds.py` ranks parameter sets by 10-day forward win rate first, then average 10-day return and signal count.
- `calibrate_thresholds.py` now preloads OHLCV history once per run to avoid repeated SQLite reads per parameter set, and prints per-parameter progress for long calibration jobs.
- `detect_momentum_burst()` now evaluates the "already extended" rule over the immediate prior 10 trading days, matching the architecture/config intent rather than scanning the entire older history.
- Adopted calibration changes so far keep Momentum Burst defaults unchanged, tighten EP volume confirmation, and relax Trend Intensity's ATR ceiling while requiring stronger MA50 persistence.

## Next Action

1. Run `python scripts/daily_briefing.py` every weekday after `16:30 IST`.
2. Use `python scripts/trade_manager.py` for manual paper/live trade logging and review.
3. Monitor live briefing/watchlist quality using the newly calibrated EP and Trend Intensity defaults before making any further threshold changes.
4. If watchlist quality is acceptable, leave Momentum Burst at `5.0 / 1.5` and keep the adopted EP/TI calibration changes as the new baseline.
5. After about 60 trading days of live breadth data have accumulated, review verdict history against subsequent NIFTY 500 returns and tune Market Monitor thresholds in `config.py`.
