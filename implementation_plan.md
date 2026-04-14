# Implementation Plan — Universe Expansion + Phase 2 + Backtesting

Covers three sequential work streams. Each stream builds on the previous one.
Phase 1 is already fully implemented and validated.

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

#### [NEW] `src/review/market_regime.py`
- `classify_nifty_regime(date) → str`
  - Uses NIFTY 50 index OHLCV (fetched as `^NSEI` on yfinance) to label each day
    as BULL (NIFTY above 200d MA), BEAR, or SIDEWAYS
  - Allows backtests to be filtered by market regime — crucial for NSE calibration

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
