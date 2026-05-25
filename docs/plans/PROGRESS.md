# PROGRESS.md - Project Status Tracker

> Agents: update this file after every completed task. This is the project memory.

**Last updated:** 2026-05-21
**Current phase:** Phase 6 - Paper Trading
**Active plan:** `docs/superpowers/plans/2026-05-16-interactive-trade-book.md`

## Phase Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | MVP: Data + Market Monitor + Scanner -> `daily_briefing.py` | Implemented + live validation ongoing |
| Phase 2 | Trade Management: position sizer, open trade log, P&L | Core workflow implemented |
| Phase 3 | Review Loop: journal, analytics, backtester | Backtesting/calibration scaffolding implemented |
| Phase 4 | FastAPI + Next.js UI dashboard | Completed through F4; live validation ongoing |
| Phase 5 / Stream G | Scanner Win-Rate R&D: feature analysis, validation, and scanner-quality promotion gates | Complete |
| Phase 6 | Paper Trading & Exit Mechanics Execution | In progress |

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
- 2026-04-29 - Stop-Loss Optimization Research (MAE): analyzed 700K historical signals to find optimal stop losses. Found fixed % stops consistently outperform ATR-based stops. Applied findings to `config.py` (EP: 4.0%, MB: 2.5%, TI: 1.5%).
- 2026-04-29 - Target & Exit Strategy Research (MFE): ran simulations comparing fixed % targets, trailing stops, and pure time holds. Concluded that taking profits before 15%+ mathematically destroys expectancy due to tight stops. Optimal exit design identified as: hold 20+ days for maximum alpha, trailing stop to breakeven after a +5% gain.
- 2026-04-29 - Daily Briefing UI Update: added `STOP_LOSS` dynamic calculation column to `daily_briefing.py` output table based on the new scanner-specific stop-loss configurations.
- 2026-04-29 - Stream E execution tooling implemented: `trade_manager.py status` now shows `pct_gain`, stored NSE-session `days_held`, and `action_required` (`TRAIL_TO_BREAKEVEN` at +5% with stop below entry, `TIME_EXIT` after 20 stored trading days); added `trade_manager.py update` to modify open-trade stop prices quickly.
- 2026-04-30 - Phase 4 Task 1 completed: read-only FastAPI dashboard API added in `src/api/main.py` with health, briefing, watchlist, breadth, open-trade, trade-action, and trade-summary endpoints; `requirements.txt` now includes FastAPI/Uvicorn/HTTPX and API tests cover the new contract.
- 2026-04-30 - Phase 4 Task 2 completed: Next.js dashboard shell added under `frontend/`, consuming the read-only FastAPI endpoints and rendering latest market verdict, watchlist candidates, open trades, action-required queue, and closed-trade summary.
- 2026-04-30 - Phase 4 Task 3 completed: dashboard detail interactions added with stored briefing date selection, watchlist candidate drill-down, trade-action filters, and API retry/error controls; FastAPI now exposes `GET /briefing/dates` for available stored briefing dates.
- 2026-04-30 - Phase 4 validation fix: dashboard client-side date switching/retry requests were blocked by missing FastAPI CORS headers; `src/api/main.py` now allows the local dashboard origins (`127.0.0.1` / `localhost` on ports `3000` and `3001`), and API tests cover the browser fetch contract.
- 2026-04-30 - Phase 4 validation fix: stored watchlist rows for some dates contained exact duplicate entries, which inflated dashboard candidate counts and triggered React duplicate-key warnings during date changes; `get_watchlist()` now returns distinct rows, and API tests cover duplicate collapse in briefing payloads.
- 2026-05-07 - Phase 4 Task F4 completed: Dashboard UI E2E Testing integrated with Playwright. A smoke test suite `dashboard.spec.ts` was added to verify Next.js page initialization and rendering reliability.
- 2026-05-07 - Stream G planning completed: `docs/superpowers/specs/2026-05-07-scanner-winrate-rd-design.md` and `docs/superpowers/plans/2026-05-07-scanner-winrate-rd-plan.md` define the scanner win-rate R&D pipeline.
- 2026-05-07 - Stream G Task 1-2 completed: `scripts/analyze_signal_features.py` plus feature-analysis tests were added to bucket scanner signal features by outcome and rank predictive candidates by win-rate spread.
- 2026-05-07 - Stream G Task 3-5 progressed: EP feature analysis and extended `--feature-filters` validation were run; findings are recorded in `data/research/FINDINGS.md`.
- 2026-05-07 - Stream G EP validation checkpoint: `prior_65d_weakness_pct>=37` was rejected after 2025-H2 out-of-sample failure; `gap_vol_ratio<=4.9` survived a rolling 2025 sanity check but is not yet justified as a live default.
- 2026-05-07 - Stream G implementation checkpoint: a disabled-by-default EP quality filter was added via `EP_MAX_GAP_VOLUME_RATIO = 0.0`; setting it to `4.9` can be used for research or paper-trading observation without changing normal live behavior.
- 2026-05-07 - Stream G TI checkpoint: Trend Intensity now exposes `relative_strength_vs_benchmark_3m` for future feature analysis.
- 2026-05-07 - Stream G Task 7 MB smoke validation completed: `mb_quality=HIGH` improved OFFENSIVE hit rate/alpha in a 10-set Jan-Jun 2025 smoke, but only produced `28` OFFENSIVE signals and stayed below the `15pp` spread gate, so MB HIGH is not promoted to live detection from this evidence.
- 2026-05-07 - Stream G Task 10 TI RS bug fixed and smoke validation completed: Trend Intensity prepared-history now receives benchmark history, populating `relative_strength_vs_benchmark_3m`; the `2.4..6.7` RS band improved the 10-set smoke but remains too small for live promotion.
- 2026-05-08 - Stream G G1 (MB): `consolidation_days`, `prior_10d_run_pct`, `nr_count_10d`, `prior_20d_run_pct`, `distance_from_20d_high_pct` all exceeded the 15pp promotion spread gate on the full MB signal set (OFFENSIVE regime); `prior_10d_run_pct < -2.3` and `consolidation_days < 4` selected for G2 validation.
- 2026-05-08 - Stream G G1 (TI): `trend_efficiency_ratio`, `pullback_depth_20d`, `distance_above_ma50_pct`, `vol_dryup_ratio_10d` all exceeded 15pp; `trend_efficiency_ratio < 0.3` and `pullback_depth_20d < 16.0` selected for G2 validation.
- 2026-05-08 - Stream G G2 (MB): `prior_10d_run_pct < -2.3` **VALIDATED** (offensive win rate >60% across parameter grid); `consolidation_days < 4` **FAILED** (artifact of single-day cross-section, did not generalise over temporal horizon). MB G3 live filter promoted: `MB_MAX_PRIOR_RUN = -2.3` in `config.py`, enforced in `detect_momentum_burst()`.
- 2026-05-08 - Stream G G2 (TI): `pullback_depth_20d < 16.0` **VALIDATED** (offensive win rate >50%, significantly mitigated median alpha); `trend_efficiency_ratio < 0.3` **FAILED** (defensive regimes failed completely). TI G3 live filter promoted: `TI_MAX_PULLBACK_DEPTH_PCT = 16.0` in `config.py`, enforced in `detect_trend_intensity()`.
- 2026-05-08 - Stream G Task 10 TI RS-band full-grid validation completed: `relative_strength_vs_benchmark_3m:2.4..6.7` **FAILED** full-grid — signal count choked (6–12 signals over H1 window), no generalisation beyond smoke sample. TI RS live filter **not promoted**.
- 2026-05-08 - Stream G G3 tests added: `test_mb_prior_run_filter_rejects_extended_stock` and `test_ti_pullback_filter_rejects_deep_pullback` added to scanner test suite to explicitly verify G2-validated live filter rejection behaviour.
- 2026-05-16 - Dashboard production-grade execution slice: added backend `/trades/quote` risk sizing, enforced server-calculated shares in `/trades/open` when `account_size` is supplied, and updated the dashboard trade ticket to display backend-derived risk, position value, R unit, max position, and market regime before confirmation.
- 2026-05-17 - Backtest handoff verification: `tests/test_backtest.py::test_backtest_runs_on_synthetic_data` already uses a test-local `MB_MAX_PRIOR_RUN` monkeypatch, and the focused test plus full `tests/test_backtest.py` suite pass. No source-code fix was required; the stale "must fix next" handoff was removed.
- 2026-05-17 - Trade ticket live validation fix: scanner execution now seeds a setup-aware default stop loss before requesting `/trades/quote`, so the backend quote populates and `Confirm Trade` enables only after valid server sizing. Added Playwright coverage for the quote path and cancelled the live validation ticket without creating an open trade.
- 2026-05-17 - Dedicated Market Monitor page: added `/market` as a full-width market breadth view with regime summary, MA/up-volume/net-high-low metrics, advance/decline panels, corrected green/red net A/D bars, timeframe controls, and dashboard/sidebar navigation links.
- 2026-05-20 - Stream H: Live Price Feed (LTP) implemented with `LivePriceCache` and Tiered Fetcher.
- 2026-05-20 - Stream I: "Somewhat Live" Market Scanner implemented with async briefing pipeline and Dashboard integration.
- 2026-05-20 - Performance: Optimized DB queries (60-day lookback) and increased fetcher concurrency (50 threads).
- 2026-05-21 - Trade Book live-price refresh fix: `/trades/open`, `/trades/actions`, and `/trades/portfolio` now default to live quotes so a page reload or in-app refresh no longer regresses to stale DB closes; regression coverage added in `tests/test_api.py`.
- 2026-05-24 - Chart usability upgrade: shared candlestick charts now expose richer price context, scanner detail gained timeframe and resize controls, dashboard breadth panels gained resize controls, and the dedicated market page now shows threshold-aware breadth charts plus resize controls.

## In Progress

- Running the briefing live each weekday to accumulate NSE breadth history
- Monitoring the calibrated scanner defaults in live daily briefings
- Validating the Phase 4 dashboard against live daily briefing data after each market close
- Phase 6 paper trading validation with the interactive Trade Book and backend-enforced risk sizing.
- Observing the disabled-by-default EP quality filter candidate (`EP_MAX_GAP_VOLUME_RATIO = 4.9` when enabled manually) before deciding whether it should become a live default.
- Monitoring the updated live EP defaults (`5.0 / 3.0 / 2`) in daily briefings to confirm they surface timely candidates without degrading quality; initial raw EP checks recovered `RAILTEL` across 2026-04-15/16/17 while still staying selective on 2026-04-20/21, and exported April watchlists now distinguish the winning `setup_type` from `matched_setups`
- Keeping Momentum Burst and Trend Intensity live defaults unchanged until a longer-window or signal-level review produces stronger evidence than the Jan-Jun 2025 window alone
- 2026-04-15 monitoring checkpoint: reran `daily_briefing.py --date 2026-04-13` against the local DB after adopting calibrated EP/TI defaults; verdict was `DEFENSIVE` with `21` Momentum Burst, `4` Episodic Pivot, and `3` Trend Intensity candidates, and the saved top-10 watchlist remained Momentum Burst-heavy (`6` MB, `3` EP, `1` TI candidate was filtered out of the top list)
- 2026-04-16 monitoring checkpoint: ran `daily_briefing.py --date 2026-04-16` against the local DB; verdict was `OFFENSIVE` with `37` Momentum Burst, `5` Episodic Pivot, and `8` Trend Intensity candidates, and the saved top-20 watchlist was well balanced (`7` MB, `5` EP, `8` TI), suggesting the calibrated EP/TI defaults are surfacing alongside Momentum Burst rather than being crowded out
- 2026-04-17 monitoring checkpoint: latest breadth row saved `OFFENSIVE` with `% above MA20 = 95.18`, `% above MA50 = 73.29`, `33` new highs, `0` new lows, `up-volume ratio = 0.8176`, and `399 / 98` advancers/decliners; the saved top-20 watchlist in `data/watchlists/2026-04-17.csv` split `9` Momentum Burst, `2` Episodic Pivot, and `9` Trend Intensity candidates, indicating Trend Intensity remained strong while Episodic Pivot was lighter on this session

## Open Questions

- [x] **Market Monitor thresholds (ADR-007):** Evaluated and calibrated! A 3-year historical breadth script run on NIFTY500 confirmed that Pradeep Bonde's 55% Offensive and 45% Defensive thresholds correlate optimally with median forward returns. They have now been marked as NSE-validated in `config.py`.

- [x] **Upper circuit handling in Momentum Burst:** `MB_MAX_PCT_CHANGE` was lowered to `20.0` in `config.py` to match the exact maximum NSE circuit limit.

- [x] **Calibration objective:** Stream D completed (D1-D6). Richer backtest signal rows (MAE/MFE, benchmark-relative alpha, regime splits, scanner quality features) are implemented. Calibration outputs now rank by alpha-aware, robustness-aware criteria. All calibration reruns completed for Momentum Burst, Episodic Pivot, and Trend Intensity on the Jan–Jun 2025 NIFTY500 window.

- [ ] **Intraday/opening alerts as a future phase:** User wants help reducing market-open FOMO and missed entries. Keep Phase 2 on the current EOD/manual workflow, but capture a future enhancement for "opening-plan" alerts first, and only consider true intraday signal generation after an explicit architecture decision because it would break ADR-004 (`EOD only`) and increase data/infrastructure complexity.

## Noted Issues

- `src/review/market_regime.py` from the follow-on plan is intentionally deferred for now; current calibration/backtesting work proceeds without market-regime classification until regime-aware analysis is explicitly prioritized.
- The older multi-stream follow-on plan remains in `docs/plans/implementation_plan.md` for historical context; the active implementation plan is now Phase 6 under `docs/superpowers/plans/2026-05-16-interactive-trade-book.md`.
- Stream D intentionally stops short of intraday ORB execution modelling; EP research remains EOD-first until a future architecture decision explicitly expands the data model beyond ADR-004.
- Stream G must not hard-code `gap_vol_ratio<=4.9` as a live EP default yet. Current evidence supports a disabled-by-default research/paper-trading observation filter only.
- [x] Legacy OHLCV rows for `TATAMOTORS` have been mapped and aliased cleanly to `TMCV` in the historical backend.
- The current environment has no default `python`/`py` command on `PATH`; use `C:\Program Files\Python312\python.exe` for manual local runs from PowerShell unless the shell environment is updated.
- Final exported watchlists record one winning `setup_type` per symbol by design; use the `matched_setups` column in CSV/briefing output when validating whether EP or another scanner also triggered on the same symbol.
- Phase 6 risk config needs an explicit decision before real paper-trade entry: current `config.py` uses `TRADE_RISK_PCT = 0.025` and `TRADE_MAX_POSITION_PCT = 0.25`, while the handoff language expected 1% risk and a max-position cap. The UI correctly reflects backend config, but the intended risk policy must be confirmed.
- [x] Trade Book stale-price regression on page refresh resolved on 2026-05-21: trade status endpoints now default to live quotes instead of falling back to stored closes on initial reload.

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

1. **Resolve Phase 6 risk policy:** Decide whether live paper trading should use current config (`TRADE_RISK_PCT = 0.025`, `TRADE_MAX_POSITION_PCT = 0.25`) or the handoff-stated 1% risk / max-position cap, then update `config.py` and docs if needed.
2. Continue Trade Book live testing by opening a controlled paper trade only after the risk policy is confirmed.
3. Continue daily live monitoring and keep `EP_MAX_GAP_VOLUME_RATIO = 4.9` as a disabled-by-default observation filter until a longer window justifies promotion.
