# PROGRESS.md - Project Status Tracker

> Agents: update this file after every completed task. This is the project memory.

**Last updated:** 2026-04-28
**Current phase:** Phase 2 Operationalization + NSE Calibration Tooling
**Active plan:** `docs/plans/implementation_plan.md`

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
- 2026-04-22 - Research/planning update: adopted Stream D in `implementation_plan.md` for research-grade calibration, benchmark-relative scoring, breadth-aware analysis, and scanner feature enrichment before any further threshold changes
- 2026-04-22 - Stream D Task D1-D2 completed: `src/review/backtest.py` now emits richer signal rows (1d/3d/5d/10d/20d returns, MAE/MFE, failure-speed and target-hit fields) plus benchmark-relative NIFTY alpha metrics; `scripts/calibrate_thresholds.py` now persists a signal-level preview alongside the summary report
- 2026-04-22 - Stream D Task D3-D4 completed: backtest rows now join stored breadth context and expose verdict-split summary metrics; all three scanners now emit research-only feature columns for calibration without changing live detection filters
- 2026-04-22 - Stream D Task D5-D6 completed: `scripts/calibrate_thresholds.py` now writes final `-summary.csv` and `-signals.csv` outputs and ranks parameter sets by alpha-aware robustness criteria; parameter grids were widened per Stream D for Momentum Burst, Episodic Pivot, and Trend Intensity
- 2026-04-24 - Benchmark ingestion support added: `scripts/backfill_benchmark.py` and `fetch_benchmark_history()` now allow a NIFTY benchmark proxy (default `^NSEI`) to be stored in `ohlcv`, unblocking benchmark-relative alpha metrics in calibration runs
- 2026-04-24 - Calibration profiling controls added: `scripts/calibrate_thresholds.py` now reports stage timings and supports `--summary-only` plus `--max-param-sets` for fast smoke/profiling runs before full-universe calibration
- 2026-04-24 - Calibration reuse refactor added: `scripts/calibrate_thresholds.py` now preloads scanner-prepared history plus benchmark/breadth context once per run and passes it into `run_backtest()`, cutting the Momentum Burst profiling smoke-test path from ~22s per parameter set to ~5.6s
- 2026-04-24 - Full-grid Momentum Burst calibration rerun completed on the reused-context path for `2025-01-01` to `2025-06-30` (`100` parameter sets, `NIFTY500`) in `5m 34.7s`; this makes single-scanner full-grid reruns practical without deeper refactoring, though regime splits remain incomplete until historical breadth is backfilled
- 2026-04-24 - Historical breadth backfill support added via `scripts/backfill_breadth.py` plus shared `compute_historical_breadth()` logic; `2025-01-01` to `2025-06-30` now has full breadth coverage (`123` rows: `29` OFFENSIVE, `29` DEFENSIVE, `65` AVOID), unblocking meaningful regime-aware calibration reruns
- 2026-04-24 - Momentum Burst calibration rerun completed after breadth backfill for `2025-01-01` to `2025-06-30`; regime splits now populate meaningfully (for the top-ranked set: `1163` OFFENSIVE, `745` DEFENSIVE, `680` AVOID signals) while the overall alpha picture remains weak/negative, so no live default change is justified yet
- 2026-04-24 - Episodic Pivot historical-calibration bug fixed: same-day gap rows are now eligible in `detect_episodic_pivot()`, and the backtest fast path now preserves full prepared EP history up to each evaluation date instead of collapsing it to same-day rows only; smoke calibration on `2025-01-01` to `2025-06-30` immediately recovered non-zero signals (`87` for the loosest parameter set)
- 2026-04-24 - Full-grid Episodic Pivot calibration rerun completed for `2025-01-01` to `2025-06-30` after the historical-fix patch; EP now shows materially stronger alpha than Momentum Burst on several parameter sets, with the best 5-day median-alpha result at `min_gap_pct=8.0`, `min_gap_vol_ratio=6.0`, `max_days_since_gap=3`, though runtime remains heavy at ~`47m 39s` for the full 64-set grid
- 2026-04-24 - Full-grid Trend Intensity calibration rerun completed for `2025-01-01` to `2025-06-30`; runtime was fast (~`1m 50s` for 48 parameter sets), but the top-ranked sets still showed negative 5-day alpha overall, so no Trend Intensity default change is justified from this window
- 2026-04-24 - Cross-scanner calibration review completed for the `2025-01-01` to `2025-06-30` NIFTY500 window: Momentum Burst remained weak/benchmark-lagging, Episodic Pivot emerged as the strongest scanner with a practical default candidate shortlist of `min_gap_pct=6.0`, `min_gap_vol_ratio=3.0`, `max_days_since_gap=2`, and Trend Intensity remained unconvincing despite healthy signal counts
- 2026-04-24 - Signal-level Episodic Pivot review completed for the shortlisted practical candidate (`min_gap_pct=6.0`, `min_gap_vol_ratio=3.0`, `max_days_since_gap=2`): `50` signals, `median_alpha_5d = 1.56`, `OFFENSIVE avg_alpha_5d = 3.67`, `DEFENSIVE avg_alpha_5d = 1.59`, `AVOID avg_alpha_5d = -4.41`; strongest follow-through clustered in `OFFENSIVE`/`DEFENSIVE`, while the worst failures were concentrated in `AVOID`
- 2026-04-24 - Live EP defaults updated in `config.py` to the shortlisted practical calibration candidate: `EP_MIN_GAP_PCT = 6.0`, `EP_MIN_GAP_VOLUME_RATIO = 3.0`, `EP_MAX_DAYS_SINCE_GAP = 2`; Momentum Burst and Trend Intensity defaults remain unchanged pending stronger evidence
- 2026-04-24 - Live-operations EP selectivity check showed `6.0 / 3.0 / 2` was too sparse across recent stored sessions (`0` EP candidates on 2026-04-15/16/17/20/21 in full briefings except unavailable 2026-04-23), so the live observation candidate was loosened to `EP_MIN_GAP_PCT = 5.0` while keeping `EP_MIN_GAP_VOLUME_RATIO = 3.0` and `EP_MAX_DAYS_SINCE_GAP = 2`
- 2026-04-24 - Quick EP-only recheck with the looser live candidate (`5.0 / 3.0 / 2`) recovered actionable selectivity on recent stored sessions: `RAILTEL` appeared as an EP candidate on 2026-04-15/16/17 (`days_since_gap = 0/1/2`) while 2026-04-20 and 2026-04-21 still produced `0` EP candidates, suggesting the looser floor restores some live usefulness without obviously flooding the scanner
- 2026-04-28 - Watchlist interpretation improvement: `merge_and_rank()` now retains a `matched_setups` field plus `setup_match_count` in exported watchlists/briefing output so symbols that qualify under multiple scanners remain interpretable even when a single highest-scoring `setup_type` wins the final row
- 2026-04-28 - EP watchlist review update: April 2026 exported watchlists contained `19` EP rows across `14` sessions, while raw EP detections remained slightly higher because duplicate symbols can still be absorbed by a stronger-scoring Momentum Burst or Trend Intensity row in the final ranked export
- 2026-04-28 - Deep alpha analysis on 2+ years of historical signal data: Episodic Pivot confirmed as the only scanner finding true edge (+5.6% alpha over 10d in OFFENSIVE conditions). Momentum Burst and Trend Intensity generate negative or zero alpha overall. Findings documented in `where_the_money_is.md`.
- 2026-04-28 - Implemented EP Dual-Tier Output: added an `A+` label to Episodic Pivot candidates passing the optimal tight thresholds (gap≥8.0%, vol≥4.0x, 1 day) and `B` for standard detection. Additive label does not eliminate existing signals from the database.
- 2026-04-28 - Implemented MB Quality Redesign: added a `HIGH` quality label to Momentum Burst candidates passing research-validated composite filters (NR_10≥6 + close_location≥70% + 20d_high_breakout), which showed 59.7% win rate and 1.69 MFE/MAE historically.
- 2026-04-28 - Daily briefing UI update: High-tier (`A+`, `HIGH`) setups now sort to the top of scanner sections and are visually marked with a `⭐` in the `daily_briefing.py` console output. Both tiers successfully export to the CSV watchlists.

## In Progress

- Running the briefing live each weekday to accumulate NSE breadth history
- Monitoring the calibrated scanner defaults in live daily briefings
- Monitoring the updated live EP defaults (`5.0 / 3.0 / 2`) in daily briefings to confirm they surface timely candidates without degrading quality; initial raw EP checks recovered `RAILTEL` across 2026-04-15/16/17 while still staying selective on 2026-04-20/21, and exported April watchlists now distinguish the winning `setup_type` from `matched_setups`
- Keeping Momentum Burst and Trend Intensity live defaults unchanged until a longer-window or signal-level review produces stronger evidence than the Jan-Jun 2025 window alone
- 2026-04-15 monitoring checkpoint: reran `daily_briefing.py --date 2026-04-13` against the local DB after adopting calibrated EP/TI defaults; verdict was `DEFENSIVE` with `21` Momentum Burst, `4` Episodic Pivot, and `3` Trend Intensity candidates, and the saved top-10 watchlist remained Momentum Burst-heavy (`6` MB, `3` EP, `1` TI candidate was filtered out of the top list)
- 2026-04-16 monitoring checkpoint: ran `daily_briefing.py --date 2026-04-16` against the local DB; verdict was `OFFENSIVE` with `37` Momentum Burst, `5` Episodic Pivot, and `8` Trend Intensity candidates, and the saved top-20 watchlist was well balanced (`7` MB, `5` EP, `8` TI), suggesting the calibrated EP/TI defaults are surfacing alongside Momentum Burst rather than being crowded out
- 2026-04-17 monitoring checkpoint: latest breadth row saved `OFFENSIVE` with `% above MA20 = 95.18`, `% above MA50 = 73.29`, `33` new highs, `0` new lows, `up-volume ratio = 0.8176`, and `399 / 98` advancers/decliners; the saved top-20 watchlist in `data/watchlists/2026-04-17.csv` split `9` Momentum Burst, `2` Episodic Pivot, and `9` Trend Intensity candidates, indicating Trend Intensity remained strong while Episodic Pivot was lighter on this session

## Open Questions

- [x] **Market Monitor thresholds (ADR-007):** Evaluated and calibrated! A 3-year historical breadth script run on NIFTY500 confirmed that Pradeep Bonde's 55% Offensive and 45% Defensive thresholds correlate optimally with median forward returns. They have now been marked as NSE-validated in `config.py`.

- [x] **Upper circuit handling in Momentum Burst:** `MB_MAX_PCT_CHANGE` was lowered to `20.0` in `config.py` to match the exact maximum NSE circuit limit.

- [ ] **Calibration objective:** Stream D now prioritizes benchmark-relative scoring versus NIFTY, breadth-aware regime splits, and MAE/MFE plus time-stop style analysis before any additional scanner default changes are made.

- [ ] **Intraday/opening alerts as a future phase:** User wants help reducing market-open FOMO and missed entries. Keep Phase 2 on the current EOD/manual workflow, but capture a future enhancement for "opening-plan" alerts first, and only consider true intraday signal generation after an explicit architecture decision because it would break ADR-004 (`EOD only`) and increase data/infrastructure complexity.

## Noted Issues

- `src/review/market_regime.py` from the follow-on plan is intentionally deferred for now; current calibration/backtesting work proceeds without market-regime classification until regime-aware analysis is explicitly prioritized.
- The active multi-stream follow-on plan has been moved under `docs/plans/implementation_plan.md` and should be kept aligned with this tracker.
- Stream D intentionally stops short of intraday ORB execution modelling; EP research remains EOD-first until a future architecture decision explicitly expands the data model beyond ADR-004.
- [x] Legacy OHLCV rows for `TATAMOTORS` have been mapped and aliased cleanly to `TMCV` in the historical backend.
- The current environment has no default `python`/`py` command on `PATH`; use `C:\Program Files\Python312\python.exe` for manual local runs from PowerShell unless the shell environment is updated.
- Final exported watchlists record one winning `setup_type` per symbol by design; use the `matched_setups` column in CSV/briefing output when validating whether EP or another scanner also triggered on the same symbol.

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
- Stream D plans to replace raw-win-rate-first calibration ranking with alpha-aware, regime-aware ranking once the richer signal outputs are implemented.
- Current April 2026 calibration outputs completed end-to-end, but `alpha_*` columns remained null because no benchmark proxy rows were yet stored in `ohlcv`; use `scripts/backfill_benchmark.py` before interpreting the new rankings as true alpha-aware results.
- The backtest layer now falls back to a local equal-weight benchmark proxy built from stored universe history when no external benchmark series is present, so alpha-aware calibration no longer depends on yfinance/NSE index access in this environment.
- `detect_episodic_pivot()` now treats a qualifying latest-row gap as `days_since_gap = 0`, which matches the architecture's intended "gap happened 0-5 trading days ago" rule and is required for historical calibration correctness.

## Next Action

1. Run `python scripts/daily_briefing.py` every weekday after `16:30 IST`.
2. Paper trade the new `⭐ A+` Episodic Pivot signals in OFFENSIVE markets via `python scripts/trade_manager.py` for 2-4 weeks to validate edge.
3. Observe how often `⭐ HIGH` Momentum Burst candidates trigger in live sessions before deciding on final MB scanner removal or retirement.
4. With only EP demonstrating proven alpha so far, revisit position sizing defaults (`TRADE_RISK_PCT`, `TRADE_MAX_POSITION_PCT`) once live/paper trading builds sufficient confidence in concentrated EP holding logic.
