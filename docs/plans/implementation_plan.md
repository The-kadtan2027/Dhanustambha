# Implementation Plan — Operationalization + Research-Grade Backtesting

Covers the completed implementation streams plus the next research-driven calibration
stream. Phase 1 is already fully implemented and validated, and the current focus is
improving the quality of scanner research before making further default-threshold changes.

---

## Stream A — Universe Expansion (do first, ~1 session)

### Context

[src/ingestion/symbols.py](file:///d:/antigravity/Dhanustambha/src/ingestion/symbols.py) currently has `NIFTY500 = NIFTY50` (50 symbols only).
The user wants a broader universe to avoid missing setups.

### Proposed approach: Dynamic NSE index loading

Rather than hand-maintaining 500+ ticker lists, we fetch the official NSE index constituents
from NSE's public CSV endpoints — the same file NSE publishes daily for each index.

**Fetch URLs (no auth required — plain CSV download):**

| Universe | NSE URL |
|---|---|
| NIFTY 50 | `https://nseindia.com/api/equity-stockIndices?index=NIFTY%2050` |
| NIFTY 500 | Download from NSE index constituents CSV |
| NIFTY Midcap 150 | Same pattern |
| NIFTY Smallcap 250 | Same pattern |

**Simpler approach (reliable, static file strategy):**
NSE publishes a daily CSV at:
`https://archives.nseindia.com/content/indices/ind_nifty500list.csv`

This is a plain, unauthenticated download that always reflects the current constituents.
We read this at startup / once per week. If download fails, we fall back to the last saved copy.

**Universe to target:**
- **NIFTY 500** — primary (covers ~95% of market cap, liquid stocks)
- **NIFTY Midcap 150** — already inside NIFTY 500; no extra cost
- **NIFTY Smallcap 250** — adds ~250 more names, including high-momentum small caps that Stockbee setups love

Total: ~750 liquid, exchange-listed stocks. This is the right balance — broad enough to
catch all meaningful setups, tight enough to exclude illiquid penny stocks.

> [!IMPORTANT]
> We do NOT want to scan all 2000+ NSE stocks. The Momentum Burst scanner's
> 20-day avg volume > 200,000 filter already excludes most junk. But fetching 2000
> symbols takes 30-40 minutes on yfinance — impractical for an EOD cron job.
> NIFTY 500 + Smallcap 250 = ~750 symbols. yfinance batch fetch takes ~8-10 minutes.
> That is acceptable for a 16:30 cron job.

### Files changed

#### [MODIFY] [symbols.py](file:///d:/antigravity/Dhanustambha/src/ingestion/symbols.py)
- Replace the hardcoded list approach with a `load_universe_from_nse()` function
  that downloads the NSE constituent CSV for each index
- Cache the result to `data/universe_cache/NIFTY500.csv` (weekly refresh)
- Keep `NIFTY50` hardcoded as the dev/test fallback (fast iteration)
- Keep [get_universe_symbols()](file:///d:/antigravity/Dhanustambha/src/ingestion/symbols.py#77-88) as the public API — callers don't change

#### [NEW] `data/universe_cache/.gitkeep`
- Gitignored directory to store the downloaded constituent CSVs

#### [MODIFY] [config.py](file:///d:/antigravity/Dhanustambha/config.py)
- Add `UNIVERSE_CACHE_DIR`
- Add `UNIVERSE_REFRESH_DAYS = 7` (re-download index CSVs weekly)
- Add `UNIVERSE = 'NIFTY750'` as new default (NIFTY500 + Smallcap250)

#### [MODIFY] [fetcher.py](file:///d:/antigravity/Dhanustambha/src/ingestion/fetcher.py)
- `fetch_eod_data()` already handles a list of symbols — no interface change needed
- Add a yfinance **batch mode**: use `yf.download(tickers=[...], group_by='ticker')`
  for all symbols in one call instead of one call per symbol.
  This cuts fetch time from ~8 min to ~2-3 min for 750 symbols.

#### [MODIFY] [test_fetcher.py](file:///d:/antigravity/Dhanustambha/tests/test_fetcher.py)
- Add a new test: `test_load_universe_returns_expected_size()` — mocks the CSV download,
  verifies we get > 400 symbols and all are clean strings (no `.NS`, no whitespace)

---

## Stream B — Phase 2: Trade Management (~2-3 sessions)

### Context

Architecture defines four components: `sizer.py`, `log.py`, `pnl.py` (in `src/trade/`).
The `trades` table schema is already in [ARCHITECTURE.md](file:///d:/antigravity/Dhanustambha/docs/architecture/ARCHITECTURE.md). No Phase 2 code exists yet.

### Design decisions

**Source of stops:** User enters stop price manually when logging a trade. The system
does not auto-calculate stops — that requires intraday data we don't have. The scanner
output (close price) is the entry reference; the user sets the stop based on chart reading.

**Sizing formula** (from ADR / ARCHITECTURE.md):
```
risk_per_trade = account_size × TRADE_RISK_PCT   (default 1%)
stop_distance  = entry_price − stop_price
shares         = floor(risk_per_trade / stop_distance)
position_value = shares × entry_price

Hard caps:
  position_value ≤ account_size × TRADE_MAX_POSITION_PCT  (10%)
  open trades ≤ TRADE_MAX_OPEN  (5)
  shares × 2 if market == DEFENSIVE (50% size reduction → actually half shares)
```

**P&L:** Computed on close. R-multiple = (exit − entry) / (entry − stop).
A +2R trade means you made 2× your initial risk.

### New files

#### [NEW] `src/trade/__init__.py`

#### [NEW] `src/trade/sizer.py`
- `calculate_position_size(account_size, entry_price, stop_price, market_verdict) → dict`
  Returns: `{shares, position_value, risk_amount, r_unit}`
- Enforces all hard limits, returns `None` with a warning if trade is invalid (stop > entry)

#### [NEW] `src/trade/log.py`
- `open_trade(symbol, setup_type, entry_date, entry_price, shares, stop_price, target_price, notes) → int`
  Inserts into `trades` table, returns trade_id
- `close_trade(trade_id, exit_date, exit_price, notes) → dict`
  Updates the row, computes `pnl` and `status` (`CLOSED_WIN / CLOSED_LOSS / CLOSED_BE`)
- `get_open_trades() → pd.DataFrame`
- `get_closed_trades(last_n_days=90) → pd.DataFrame`

#### [NEW] `src/trade/pnl.py`
- `compute_trade_pnl(entry_price, exit_price, shares) → float`
- `compute_r_multiple(entry_price, exit_price, stop_price) → float`
- `compute_expectancy(closed_trades_df) → dict`
  Returns: `{win_rate, avg_win_r, avg_loss_r, expectancy_r}`

#### [MODIFY] [src/ingestion/store.py](file:///d:/antigravity/Dhanustambha/src/ingestion/store.py)
- Add `CREATE TABLE IF NOT EXISTS trades (...)` to `init_db()`
- Add `save_trade()`, `update_trade()`, `get_trades()` CRUD functions

#### [NEW] `scripts/trade_manager.py`
- CLI entrypoint: `python scripts/trade_manager.py`
- Commands:
  - `open` — prompts for entry details, calls sizer to show position size, confirms, logs trade
  - `close` — lists open trades, prompts for exit price, closes and shows R-multiple
  - `status` — prints open trades with current unrealized P&L (using last close from DB)
  - `summary` — prints closed trade stats (win rate, expectancy)

#### [NEW] `tests/test_trade.py`
- `test_position_sizer_normal_case()` — 1% risk, known prices → verify shares
- `test_position_sizer_defensive_halves_size()` — DEFENSIVE verdict → half shares
- `test_position_sizer_rejects_stop_above_entry()` — stop > entry → returns None
- `test_position_sizer_caps_at_max_position_pct()` — huge shares → capped
- `test_pnl_r_multiple_win()` — entry 100, stop 95, exit 115 → +3R
- `test_pnl_r_multiple_loss()` — entry 100, stop 95, exit 93 → -1.4R
- `test_expectancy_positive()` — synthetic trade log → correct expectancy

---

## Stream C — Backtesting Engine (~3-4 sessions)

### Context

This is the most important stream for answering: *"What are the right thresholds for NSE?"*
ADR-007 explicitly calls this out. The architecture already plans `src/review/backtest.py`.

### Design philosophy

> [!IMPORTANT]
> **We are NOT building a general-purpose backtesting framework.**
> We are building a *parameter calibration tool* for our three specific scanners.
> The question we want to answer is: `"If I had run Momentum Burst with these
> thresholds over the last 3 years, how many signals would it have generated,
> what was the average forward return, and what was the win rate?"`

This is simpler than a full backtester — we don't simulate order execution, slippage,
or portfolio-level capital allocation. We just score historical signals.

### Data requirement: 3 years of NSE history

The free yfinance source supports 3+ years of daily history for NSE symbols.
Once Stream A is done and we have 750 symbols, we run a **one-time historical backfill**:

```bash
python scripts/backfill_history.py --years 3
```

This fills the `ohlcv` table with 3 years × 750 symbols ≈ 562,500 rows (~5 min).
After that, [daily_briefing.py](file:///d:/antigravity/Dhanustambha/tests/test_daily_briefing.py) keeps it current.

### New files

#### [NEW] `scripts/backfill_history.py`
- Fetches 3 years of EOD history for all universe symbols via `yf.download()`
- Writes to `ohlcv` table via `upsert_ohlcv()`
- Skips symbols already having > 600 days of data
- Progress bar via `tqdm`

#### [NEW] `src/review/__init__.py`

#### [NEW] `src/review/backtest.py`
- `run_backtest(scanner_fn, universe, start_date, end_date, params) → BacktestResult`
  - For each trading day in range, applies `scanner_fn(ohlcv_df, params)` to get signals
  - For each signal: records the entry close, and the closes at +5d, +10d, +20d
  - Computes hit rate: % of signals up > X% at each forward horizon
- `BacktestResult` dataclass:
  - `n_signals`, `win_rate_5d`, `win_rate_10d`, `win_rate_20d`
  - `avg_return_5d`, `avg_return_10d`, `avg_return_20d`
  - `best_params_by_win_rate`, `signal_histogram_by_month`

#### [NEW] `scripts/calibrate_thresholds.py`
- Grid search over key parameters for each scanner
- Momentum Burst: `MB_MIN_PCT_CHANGE` (3–8%), `MB_MIN_VOLUME_RATIO` (1.2–2.5)
- Episodic Pivot: `EP_MIN_GAP_PCT` (3–6%), `EP_MIN_GAP_VOLUME_RATIO` (2–5)
- Trend Intensity: `TI_MAX_ATR_PCT` (0.02–0.05), `TI_MIN_DAYS_ABOVE_MA50` (20–40)
- Outputs a ranked table of parameter sets by 10-day win rate (forward returns)
- Saves result to `data/calibration/YYYY-MM-DD-results.csv`

#### [DEFERRED] `src/review/market_regime.py`
- `classify_nifty_regime(date) → str`
  - Uses NIFTY 50 index OHLCV (fetched as `^NSEI` on yfinance) to label each day
    as BULL (NIFTY above 200d MA), BEAR, or SIDEWAYS
  - Allows backtests to be filtered by market regime — crucial for NSE calibration
  - Deferred for now while calibration remains focused on raw forward-return signal quality.
    Revisit only if benchmark-relative or regime-specific analysis becomes necessary.

#### [NEW] `tests/test_backtest.py`
- `test_backtest_runs_on_synthetic_data()` — inject 200 days of synthetic OHLCV for 50 symbols,
  run the MB scanner backtest, verify result dict has expected keys and signal count > 0
- `test_forward_return_correct()` — inject known price sequences, verify +5d return is correct

---

## Sequencing

```
Week 1:  Stream A — Universe expansion + batch yfinance fetch
Week 2:  Stream B — Trade management (sizer + log + pnl)
Week 3:  Stream B — CLI trade_manager.py + integration
Week 4:  Stream C — Historical backfill + backtest engine
Week 5:  Stream C — Calibration script + NSE threshold tuning
```

---

## Verification Plan

### Stream A
```bash
# Unit tests (no network)
pytest tests/test_fetcher.py -v

# Integration smoke test — run with NIFTY50 first (fast), then NIFTY500
python -c "from src.ingestion.symbols import get_universe_symbols; s = get_universe_symbols('NIFTY500'); print(f'{len(s)} symbols loaded'); print(s[:5])"

# Full briefing end-to-end with expanded universe (run after 16:30 IST on a weekday)
python scripts/daily_briefing.py
```

### Stream B
```bash
# Unit tests
pytest tests/test_trade.py -v

# Integration: open a paper trade, close it, check P&L
python scripts/trade_manager.py open
python scripts/trade_manager.py status
python scripts/trade_manager.py close
python scripts/trade_manager.py summary
```

### Stream C
```bash
# Unit tests
pytest tests/test_backtest.py -v

# Historical backfill (run once — takes ~5 min)
python scripts/backfill_history.py --years 3 --universe NIFTY500

# Calibration run (takes ~15 min on 3 years × 500 symbols)
python scripts/calibrate_thresholds.py --scanner momentum_burst --universe NIFTY500
```

---

## Open Questions for User

1. **Universe size confirmation:** NIFTY500 + Smallcap250 ≈ 750 symbols. yfinance batch fetch
   will take ~3-4 minutes per day. Is that acceptable, or do you want to cap at NIFTY500 (500 symbols, ~2 min)?

2. **trade_manager.py interface:** Should `open` / `close` / `status` be interactive CLI
   prompts, or would you prefer a simple CSV-based approach (edit a CSV, system reads it)?
   Interactive CLI is faster to build; CSV is easier to maintain manually.

3. **Backtesting forward return window:** For NSE momentum, Stockbee uses 3–5 day holds for
   Momentum Burst, 2–4 week holds for EP. Should we measure forward returns at +3d, +5d, +10d, +20d?
   Or is there a specific hold period you have in mind?

4. **Backtest benchmark:** When evaluating scanner quality, should we compare signal returns
   against NIFTY 500 buy-and-hold as the benchmark? Or raw % correct (close above entry at +Nd)?

---

## Stream D — Research-Grade Calibration and Methodology Alignment (~3-5 sessions)

### Context

The current calibration engine already measures raw forward returns for Momentum Burst,
Episodic Pivot, and Trend Intensity. That is enough for first-pass tuning, but it is not
yet rich enough to answer the methodology questions raised by Stockbee, Qullamaggie, and
Minervini-style trend/risk rules:

- Are signals outperforming the market, or just rising with a strong tape?
- Which setups work best in `OFFENSIVE` vs `DEFENSIVE` breadth conditions?
- Which setup characteristics actually improve follow-through in NSE names?
- How quickly do failed short-swing setups reveal themselves?

This stream upgrades the calibration flow into a research engine while keeping Phase 2
execution EOD/manual and without introducing intraday order logic.

### Design philosophy

> [!IMPORTANT]
> **We are still not building a general-purpose portfolio backtester.**
> The goal is to make our scanner calibration evidence-based by adding richer signal data,
> benchmark-relative scoring, regime/context analysis, and scanner-specific quality features.

The upgraded research stack must:

- Keep live scanner behavior stable until research validates a better default
- Separate **signal detection** from **trade simulation**
- Rank parameter sets by **alpha and robustness**, not only raw win rate
- Preserve EOD-first architecture and avoid breaking ADR-004 (`EOD only`)

### Scope

#### Task D1 — Upgrade signal-level backtest output

Enhance [src/review/backtest.py](file:///d:/antigravity/Dhanustambha/src/review/backtest.py)
so every historical signal row includes:

- Core metadata: `date`, `symbol`, `setup_type`, `entry_close`, `score`, `scanner_name`, `param_set_id`
- Forward returns: `return_1d`, `return_3d`, `return_5d`, `return_10d`, `return_20d`
- Excursion metrics: `mfe_3d`, `mfe_5d`, `mfe_10d`, `mae_3d`, `mae_5d`, `mae_10d`
- Failure-speed metrics: `failed_to_gain_by_3d`, `failed_to_gain_by_5d`
- Target-hit metrics: `hit_2pct_by_3d`, `hit_5pct_by_5d`, `hit_8pct_by_10d`

Summary output per parameter set should also include:

- `n_signals`
- average + median forward returns
- win rates by horizon
- average MAE/MFE
- failure-speed percentages

#### Task D2 — Add benchmark-relative scoring versus NIFTY

Extend the backtest layer so each signal also records:

- `nifty_return_1d`, `nifty_return_3d`, `nifty_return_5d`, `nifty_return_10d`, `nifty_return_20d`
- `alpha_1d`, `alpha_3d`, `alpha_5d`, `alpha_10d`, `alpha_20d`

Add summary metrics:

- `avg_alpha_3d/5d/10d/20d`
- `median_alpha_3d/5d/10d/20d`
- `alpha_win_rate_3d/5d/10d/20d`

The benchmark can initially be any locally available NIFTY proxy series already supported
by the historical data backend. If benchmark data is missing for a given date/horizon,
alpha fields should remain null rather than aborting the run.

#### Task D3 — Add regime/context joins from breadth history

Attach breadth context to each signal date using the stored `breadth` table:

- `market_verdict`
- `pct_above_ma20_on_day`
- `pct_above_ma50_on_day`
- `new_highs_52w_on_day`
- `new_lows_52w_on_day`
- `up_volume_ratio_on_day`
- `advancing_on_day`
- `declining_on_day`

Add regime split summaries for each parameter set:

- signal counts by verdict
- `offensive_win_rate_5d`, `defensive_win_rate_5d`, `avoid_win_rate_5d`
- `offensive_avg_alpha_5d`, `defensive_avg_alpha_5d`

This is intentionally lighter than the deferred `market_regime.py` concept and uses the
project's existing market monitor definitions first.

#### Task D4 — Add scanner-specific research features

Add research columns to scanner output without making them mandatory live filters yet.

Momentum Burst:

- `close_location_pct`
- `range_expansion_ratio`
- `nr_count_10d`
- `consolidation_days`
- `prior_10d_run_pct`
- `prior_20d_run_pct`
- `distance_from_20d_high_pct`
- `trend_linearity_20d`

Episodic Pivot:

- `days_since_gap`
- `gap_pct`
- `gap_vol_ratio`
- `gap_day_close_location_pct`
- `gap_day_close_vs_open_pct`
- `prior_65d_run_pct`
- `prior_65d_weakness_pct`
- `distance_to_52w_high_before_gap`
- `holding_above_gap_open_days`
- `gap_fill_pct`
- `is_first_gap_in_6m`

Trend Intensity:

- `distance_above_ma50_pct`
- `distance_above_ma150_pct`
- `distance_above_ma200_pct`
- `ma150_above_ma200`
- `ma200_rising_20d`
- `within_25pct_of_52w_high`
- `relative_strength_vs_benchmark_3m`
- `trend_efficiency_ratio`
- `pullback_depth_20d`
- `vol_dryup_ratio_10d`

These are for research and bucketing first. Any future live-filter adoption must be
justified by calibration evidence.

#### Task D5 — Redesign calibration outputs and ranking

Update [scripts/calibrate_thresholds.py](file:///d:/antigravity/Dhanustambha/scripts/calibrate_thresholds.py)
to produce two outputs per run:

- `data/calibration/YYYY-MM-DD-{scanner}-{universe}-summary.csv`
- `data/calibration/YYYY-MM-DD-{scanner}-{universe}-signals.csv`

Change ranking to prioritize:

1. `median_alpha_5d` descending
2. `win_rate_5d` descending
3. `pct_hit_5pct_by_5d` descending
4. `avg_mae_5d` ascending
5. `n_signals` descending

For EP review, also inspect `median_alpha_10d` and `median_alpha_20d` before changing
defaults because catalyst follow-through may be slower than pure momentum bursts.

#### Task D6 — Expand parameter grids only after metric upgrade

Do not widen the search space until Tasks D1-D5 are complete and verified. After that,
expand the grids conservatively:

Momentum Burst:

- `min_pct`: `4.0, 5.0, 6.0, 7.0, 8.0`
- `min_vol_ratio`: `1.3, 1.5, 1.8, 2.0, 2.5`
- `max_prior_run`: `8.0, 10.0, 12.0, 15.0`

Episodic Pivot:

- `min_gap_pct`: `4.0, 5.0, 6.0, 8.0`
- `min_gap_vol_ratio`: `3.0, 4.0, 5.0, 6.0`
- `max_days_since_gap`: `1, 2, 3, 5`

Trend Intensity:

- `max_atr_pct`: `0.02, 0.03, 0.04, 0.05`
- `min_days_above_ma50`: `30, 35, 40, 45`
- `min_vol_ratio`: `1.2, 1.3, 1.5`

### Files changed

#### [MODIFY] [src/review/backtest.py](file:///d:/antigravity/Dhanustambha/src/review/backtest.py)

- Expand `BacktestResult` summary metrics
- Add benchmark-relative return support
- Add MAE/MFE calculation helpers
- Add market breadth context joins
- Add parameter-set identifiers and richer signal output

#### [MODIFY] [scripts/calibrate_thresholds.py](file:///d:/antigravity/Dhanustambha/scripts/calibrate_thresholds.py)

- Save both summary and signal-level calibration reports
- Rank parameter sets by alpha-aware, robustness-aware metrics
- Print clearer run summaries and ranking criteria

#### [MODIFY] [src/scanner/momentum_burst.py](file:///d:/antigravity/Dhanustambha/src/scanner/momentum_burst.py)

- Return research-oriented structure/quality fields alongside existing live fields

#### [MODIFY] [src/scanner/episodic_pivot.py](file:///d:/antigravity/Dhanustambha/src/scanner/episodic_pivot.py)

- Return freshness/gap-quality research fields alongside existing live fields

#### [MODIFY] [src/scanner/trend_intensity.py](file:///d:/antigravity/Dhanustambha/src/scanner/trend_intensity.py)

- Return smoothness/trend-template research fields alongside existing live fields

#### [OPTIONAL NEW] `src/review/reporting.py`

- Helper functions for per-regime summaries and bucket analysis if `backtest.py` grows too large

#### [MODIFY] `tests/test_backtest.py`

- Add assertions for benchmark-relative metrics, excursion metrics, and signal-level output shape

#### [MODIFY] `tests/test_scanner.py`

- Add targeted tests for new scanner feature columns using deterministic synthetic data

### Sequencing

```
Week 1:  Stream D1-D2 — richer backtest rows + benchmark-relative returns
Week 2:  Stream D3 — breadth/regime joins + alpha-aware summaries
Week 3:  Stream D4 — scanner research features
Week 4:  Stream D5-D6 — calibration output redesign + wider parameter grids
Week 5:  Review results and only then consider config default changes
```

### Verification Plan

```bash
# Unit tests
pytest tests/test_backtest.py -v
pytest tests/test_scanner.py -v

# Calibration smoke test with detailed outputs
python scripts/calibrate_thresholds.py --scanner momentum_burst --universe NIFTY500

# Inspect new outputs
dir data/calibration
```

### Expected Outcomes

At the end of Stream D, the repo should be able to answer:

- Which setup has the best alpha versus NIFTY in Indian markets?
- Which setups degrade meaningfully in `DEFENSIVE` breadth?
- Which structure/freshness features improve follow-through?
- Which setups fail fast enough to justify tight time stops?
- Whether further `config.py` changes are supported by evidence rather than raw hit-rate alone

---

## Stream E — Systematic Trade Execution Extension

### Context

After calibrating historical signals for MFE/MAE behavior, we found that fixed preset limits destroy expectancy due to our tight stops, while letting trades ride for 20+ days maximizes alpha. We also found a 20-25% giveback rate, meaning trades that hit +5% will frequently fail to breakeven or stop-loss.

To enforce these rules effortlessly, we will upgrade the Option 1 Execution Tooling (`scripts/trade_manager.py`).

### Design philosophy

The CLI should alert the user when their active trades violate math-validated rules. 
- *Breakeven Trail:* Move stop to entry price when `unrealized_pct_gain >= 5.0%`.
- *Time Exit:* Recommend closure when days held crosses `20` **NSE calendar trading days**.

### Files changed

#### [MODIFY] `src/trade/log.py`
- Modify `build_open_trade_status()` to append three columns:
  - `pct_gain`: `(current_close - entry_price) / entry_price * 100`
  - `days_held`: The number of NSE trading calendar days since `entry_date`. This will require pulling valid dates from the `ohlcv` DB index.
  - `action_required`: `TRAIL_TO_BREAKEVEN`, `TIME_EXIT`, or `NONE`.

#### [MODIFY] `scripts/trade_manager.py`
- Modify `handle_status()` to cleanly format numerical gains and loudly isolate any `action_required` items in a secondary warning print.
- Create a new `handle_update()` CLI command parser to rapidly modify `stop_price` dynamically without digging into the database.

### Expected Outcomes

- A clear terminal execution dashboard that acts as an automated trade manager, pinging the user strictly on MFE/MAE thresholds.
- Prepares the foundation for Phase 4 (Web UI) backend endpoints doing the same status calculations.

---

## Stream F - Phase 4 Dashboard API Foundation

### Context

The user parked live paper trading until the browser dashboard is complete. The most
meaningful next improvement is to expose the existing CLI outputs through a stable
read-only FastAPI contract before building the Next.js frontend.

### Scope

#### Task F1 - Read-only FastAPI dashboard API

Status: Completed on 2026-04-30.

Implemented endpoints:

- `GET /health`
- `GET /briefing/latest`
- `GET /briefing/{date}`
- `GET /watchlist/latest`
- `GET /watchlist/{date}`
- `GET /trades/open`
- `GET /trades/summary`
- `GET /trades/actions`
- `GET /market/breadth/latest`
- `GET /market/breadth/{date}`

Files changed:

- `src/api/main.py`
- `src/api/__init__.py`
- `src/ingestion/store.py`
- `tests/test_api.py`
- `requirements.txt`

Verification:

```bash
python -m pytest tests/ -v
```

Result on 2026-04-30: `76 passed`.

#### Task F2 - Dashboard frontend shell

Status: Completed on 2026-04-30.

Built the first browser dashboard consuming the read-only API. The frontend is focused
on operational views first:

- latest market verdict
- latest watchlist with setup tiers
- open trades and required actions
- closed-trade summary

Files changed:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/layout.tsx`
- `frontend/next.config.ts`
- `frontend/tsconfig.json`
- `.gitignore`

Verification:

```bash
cd frontend
npm run build
npm audit --audit-level=moderate
```

Result on 2026-04-30: production build passed and npm audit found `0` vulnerabilities.

#### Task F3 - Dashboard detail interactions

Status: Completed on 2026-04-30.

Added operational drill-down without changing the trading logic:

- date selector for stored briefing/watchlist days
- watchlist candidate detail panel
- trade action filters
- API error/retry controls in the UI

Files changed:

- `src/api/main.py`
- `src/ingestion/store.py`
- `tests/test_api.py`
- `frontend/app/page.tsx`
- `frontend/app/dashboard-client.tsx`
- `frontend/app/globals.css`

Verification:

```bash
python -m pytest tests/ -v
cd frontend
npm run build
npm audit --audit-level=moderate
```

Result on 2026-04-30: backend tests passed, production dashboard build passed, and npm audit found `0` vulnerabilities.

#### Task F4 - Dashboard E2E Testing (Playwright)

Status: Completed on 2026-05-07.

Added Playwright-based end-to-end smoke tests to verify Next.js page initialization and dashboard rendering reliability. The suite validates the critical user-facing rendering path without requiring live API data.

Files changed:

- `frontend/tests/dashboard.spec.ts`
- `frontend/playwright.config.ts` (if added)

Verification:

```bash
cd frontend
npx playwright test
```

Result on 2026-05-07: Smoke test suite passes, verifying dashboard page initialization and key rendering behaviour.
