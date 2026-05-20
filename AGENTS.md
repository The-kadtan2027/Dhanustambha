# AGENTS.md — Single Source of Truth
# Dhanustambha Trading Platform

> *धनुस्तंभ — "the arrow at full draw, before release"*
> A systematic, developer-built trading platform for NSE/BSE markets, following Stockbee/Pradeep Bonde's momentum methodology.

> **This file is the single source of truth for every coding agent working on this project.**
> Read this entire file before writing a single line of code. No exceptions.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Tech Stack & Infrastructure](#2-tech-stack--infrastructure)
3. [System Architecture](#3-system-architecture)
4. [SQLite Schema](#4-sqlite-schema)
5. [Configuration — config.py](#5-configuration--configpy)
6. [Architecture Decision Records (ADRs)](#6-architecture-decision-records-adrs)
7. [Agent Rules — Behavioral Contract](#7-agent-rules--behavioral-contract)
8. [Phase History & Build Order](#8-phase-history--build-order)
9. [Current Status & Active Plan](#9-current-status--active-plan)
10. [Completed Tasks Log](#10-completed-tasks-log)
11. [Open Questions](#11-open-questions)
12. [Noted Issues & Deviations](#12-noted-issues--deviations)

---

## 1. What This Project Is

A personal, zero-cost trading toolbox implementing the Stockbee momentum methodology for Indian markets (NSE/BSE). Built by a developer-trader. Runs on homelab hardware — WSL2 on an HP Pavilion or Termux on a rooted Android device.

**This is NOT:**
- An automated trading bot. All execution is manual.
- A real-time/intraday system. EOD data only.
- Connected to a broker (yet). Free NSE data only through Phase 3.

### Core Methodology (Stockbee / Pradeep Bonde)

| Setup | Description |
|---|---|
| **Momentum Burst** | Stocks that explode 5–25% in 3–5 days due to a catalyst. Buy the burst, ride the follow-through, exit quickly. |
| **Episodic Pivot (EP)** | Earnings/news-driven structural breakouts that reset a stock's range. Can run for weeks. |
| **Trend Intensity** | Stocks in persistent, low-volatility uptrends breaking to new highs. |
| **Market Monitor** | Breadth-based market health check. Only trade aggressively when OFFENSIVE. Go to cash when DEFENSIVE/AVOID. |

---

## 2. Tech Stack & Infrastructure

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ (3.12 locally) | Native trading/data ecosystem |
| Data store | SQLite | Zero cost, zero infra, sufficient for EOD data on 2000 stocks |
| API layer | FastAPI | Lightweight, async, auto-generates OpenAPI docs |
| Frontend | Next.js | Browser-based dashboard |
| Scheduler | cron (WSL) / Termux:Boot | Runs daily at 16:30 IST after NSE market close |
| Data source | nselib (primary), yfinance (fallback) | Free, no API key needed |
| Testing | pytest | Standard, works on WSL and Termux |
| Dependency mgmt | pip + requirements.txt | Simple, no venv complexity on homelab |

### Infrastructure

```
HP Pavilion Gaming Laptop (AMD Ryzen 5 3550H, 16 GB RAM)
  └── WSL2 (Ubuntu 22.04)
        ├── Python 3.11 environment
        ├── SQLite DB: ~/dhanustambha/data/market.db
        ├── cron job: daily 16:30 IST pull
        └── FastAPI server (optional, for UI)

Rooted Android (backup / mobile use)
  └── Termux + TermuxAlpine
        └── Same Python environment, same codebase via git
```

**Local PowerShell note:** Use `C:\Program Files\Python312\python.exe` — there is no default `python`/`py` on PATH in this environment.

### How to Run the Trading GUI

To interactively test GUI features or evaluate the system locally, you need to spin up both the FastAPI backend and Next.js frontend in separate terminal windows:

**Terminal 1 — FastAPI Backend**
```powershell
python -m uvicorn src.api.main:app --reload
```
*(Runs on `http://127.0.0.1:8000`)*

**Terminal 2 — Next.js Frontend Dashboard**
```powershell
cd frontend
npm run dev
```
*(Runs on `http://localhost:3000`)*

### Repository Layout

```
dhanustambha/
├── AGENTS.md                   ← YOU ARE HERE — single source of truth
├── README.md                   ← Project overview (kept for GitHub)
├── AGENT_RULES.md              ← Superseded by AGENTS.md; kept for legacy reference
├── requirements.txt            ← Python dependencies
├── config.py                   ← Central config (paths, constants, thresholds)
│
├── data/                       ← SQLite DB lives here (gitignored)
│   ├── market.db
│   ├── calibration/            ← Calibration run CSVs (summary + signals)
│   ├── research/               ← FINDINGS.md and feature analysis reports
│   └── watchlists/             ← Daily exported watchlist CSVs
│
├── src/
│   ├── ingestion/              ← Layer 1: data pull and storage
│   │   ├── fetcher.py
│   │   ├── store.py
│   │   └── scheduler.py
│   ├── monitor/                ← Layer 2: market breadth engine
│   │   ├── breadth.py
│   │   ├── verdict.py
│   │   └── history.py
│   ├── scanner/                ← Layer 3: setup detection
│   │   ├── momentum_burst.py
│   │   ├── episodic_pivot.py
│   │   ├── trend_intensity.py
│   │   └── watchlist.py
│   ├── trade/                  ← Layer 4: trade management
│   │   ├── sizer.py
│   │   ├── log.py
│   │   └── pnl.py
│   ├── review/                 ← Layer 5: journal and analytics
│   │   ├── journal.py
│   │   ├── analytics.py
│   │   └── backtest.py
│   └── api/                    ← FastAPI server
│       └── main.py
│
├── frontend/                   ← Next.js dashboard
│   └── app/
│       └── components/
│           ├── LiveScanController.tsx ← Reusable async scan UI
│           ├── BreadthGauges.tsx
│           └── CandleChart.tsx
│
├── scripts/
│   ├── daily_briefing.py       ← Main entry point (run every weekday evening)
│   ├── calibrate_thresholds.py ← Scanner calibration runner
│   ├── analyze_signal_features.py ← Win-rate feature analysis
│   ├── backfill_benchmark.py   ← NIFTY benchmark OHLCV backfill
│   └── backfill_breadth.py     ← Historical breadth backfill
│
└── docs/
    ├── architecture/           ← Kept for historical context (superseded by AGENTS.md)
    ├── plans/
    │   └── PROGRESS.md         ← Kept for historical log
    └── superpowers/
        ├── specs/              ← Research design specs
        └── plans/              ← Active implementation plans
```

---

## 3. System Architecture

### Five Layers

| Layer | Purpose | Status |
|---|---|---|
| 1 — Data ingestion | Pull NSE EOD OHLCV + Live LTP/OHLCV | ✅ Complete (Tiered) |
| 2 — Market monitor | Breadth engine → Offensive/Defensive verdict | ✅ Complete (EOD/Live) |
| 3 — Setup scanner | Momentum Burst + EP + Trend Intensity scans | ✅ Complete (EOD/Live) |
| 4 — Trade management | Position sizing, open trade log, P&L | ✅ Complete |
| 5 — Review loop | Trade journal, setup analytics, backtester | ✅ Complete |
| 6 — Live Stream | Async progress scans + real-time LTP polling | ✅ Complete |

### Data Flow

```
NSE/BSE Market (3:30 PM close)
       │
       ▼  [16:30 cron]
┌─────────────────────┐
│   Layer 1           │  Fetches OHLCV for ~500 symbols
│   Data Ingestion    │  Stores to SQLite (market.db)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Layer 2           │  Computes daily breadth metrics
│   Market Monitor    │  Emits: OFFENSIVE / DEFENSIVE / AVOID
└────────┬────────────┘
         │  (if OFFENSIVE or DEFENSIVE, continue)
         ▼
┌─────────────────────┐
│   Layer 3           │  Runs 3 scans in parallel
│   Setup Scanner     │  Momentum Burst + EP + Trend Intensity
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐  ┌─────────────────────┐
│   daily_briefing.py │  │   Live Scan Worker  │
│   (Phase 1 output)  │  │   (Async/Progress)  │
└────────┬────────────┘  └────────┬────────────┘
         │                        │
         ▼                        ▼
┌─────────────────────┐    ┌─────────────────────┐
│   Layer 4           │    │   Layer 5           │
│   Trade Management  │    │   Review Loop       │
│   sizer, log, P&L   │    │   journal, backtest │
└────────┬────────────┘    └────────┬────────────┘
         │                           │
         └──────────┬────────────────┘
                    ▼
         ┌─────────────────┐
         │  FastAPI + UI   │
         │  Next.js dash   │
         └────────┬────────┘
                  │
                  ▼ [Stream H/I]
         ┌─────────────────────┐
         │  Live Price Cache   │  (60s TTL)
         │  yfinance -> Google  │  (Tiered Fetcher)
         └─────────────────────┘
```

### Scanner Detection Logic

#### Setup 1: Momentum Burst
```
- Today's close is 5–25% above the close N days ago (N = 1, 2, or 3)
- Today's volume >= 1.5x the 20-day average volume
- Prior 10-day run < -2.3% (stock was slightly down/flat — NOT already extended) [G2-promoted filter]
- Price > ₹50 (avoid penny stocks)
- 20-day average daily volume > 200,000 shares (minimum liquidity)
- Score: pct_change * volume_ratio
- Quality label: HIGH if NR_10>=6 + close_location>=70% + 20d_high_breakout
```

#### Setup 2: Episodic Pivot (EP)
```
- Stock gapped up > 5% from previous close at open [live: 5.0%]
- Gap happened 0–2 trading days ago [live: max_days=2]
- Stock is currently trading above the gap-open price (holding the gap)
- Volume on gap day was >= 3x the 20-day average [live: 3.0x]
- EP tier: A+ if gap>=8%, vol>=4x, days=1; otherwise B
- Disabled research filter: EP_MAX_GAP_VOLUME_RATIO = 0.0 (set to 4.9 for paper-trading observation)
```

#### Setup 3: Trend Intensity
```
- 50-day SMA is rising (today's MA50 > MA50 20 days ago)
- Today's close is a new 10-week (50-day) high
- The stock has been above MA50 for >= 30 of the last 50 days
- Volume today >= 1.3x 20-day average
- ATR(14) / close < 0.05 (low volatility — the "quiet" trend)
- MA50 persistence: >= 40 of last 50 days above MA50
- Pullback depth < 16.0% from 20d high [G2-promoted filter]
- Research field: relative_strength_vs_benchmark_3m (not a live filter — RS band failed G2)
```

### Market Monitor Verdict Logic

```python
if pct_above_ma20 > 55 and up_volume_ratio > 0.60 and new_highs > new_lows * 2:
    verdict = "OFFENSIVE"   # Trade aggressively. Full position sizes.
elif pct_above_ma20 > 45 and new_highs > new_lows:
    verdict = "DEFENSIVE"   # Trade small. Reduce position sizes by 50%.
else:
    verdict = "AVOID"       # No new trades. Protect capital.
```

### Trade Management

```
risk_per_trade = account_size * risk_pct  (default 1%)
stop_distance = entry_price - stop_price
shares = risk_per_trade / stop_distance
position_value = shares * entry_price

Hard limits:
- No single position > 10% of account
- Max 5 open positions simultaneously
- Reduce all sizes by 50% in DEFENSIVE conditions

Stop-loss config (from MAE research):
- EP: 4.0% fixed stop
- MB: 2.5% fixed stop
- TI: 1.5% fixed stop

Exit rules (from MFE research):
- Hold up to 20 stored trading days for maximum alpha
- Aggressive Trailing Tiers:
  1. +3.0% gain -> trail stop to Breakeven
  2. +7.5% gain -> trail stop to +3.0%
  3. +10.0% gain -> trail stop to +7.5%
- EP Runner Re-Entry: closed EP winners are automatically tracked for PB to MA10/MA20 breakouts filter over next 30 days
```

---

## 4. SQLite Schema

```sql
-- Master symbol list
CREATE TABLE symbols (
    symbol      TEXT PRIMARY KEY,
    name        TEXT,
    sector      TEXT,
    index_name  TEXT,   -- 'NIFTY500', 'NIFTY50', etc.
    active      INTEGER DEFAULT 1
);

-- Daily OHLCV — one row per symbol per trading day
CREATE TABLE ohlcv (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,   -- ISO format: '2026-04-11'
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    UNIQUE(symbol, date),
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

CREATE INDEX idx_ohlcv_symbol_date ON ohlcv(symbol, date);
CREATE INDEX idx_ohlcv_date ON ohlcv(date);

-- Daily breadth metrics (one row per trading day)
CREATE TABLE breadth (
    date                TEXT PRIMARY KEY,
    pct_above_ma20      REAL,
    pct_above_ma50      REAL,
    new_highs_52w       INTEGER,
    new_lows_52w        INTEGER,
    up_volume_ratio     REAL,
    advancing           INTEGER,
    declining           INTEGER,
    verdict             TEXT    -- 'OFFENSIVE', 'DEFENSIVE', 'AVOID'
);

-- Scanner output (watchlist candidates per day)
CREATE TABLE watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    setup_type      TEXT NOT NULL,  -- 'MOMENTUM_BURST', 'EP', 'TREND_INTENSITY'
    score           REAL,
    pct_change      REAL,
    volume_ratio    REAL,
    close           REAL,
    notes           TEXT
);

-- Trade log
CREATE TABLE trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    setup_type      TEXT NOT NULL,
    entry_date      TEXT,
    entry_price     REAL,
    shares          INTEGER,
    stop_price      REAL,
    target_price    REAL,
    exit_date       TEXT,
    exit_price      REAL,
    status          TEXT,   -- 'OPEN', 'CLOSED_WIN', 'CLOSED_LOSS', 'CLOSED_BE'
    pnl             REAL,
    notes           TEXT,
    grade           TEXT    -- 'A', 'B', 'C' (setup quality at entry)
);
```

---

## 5. Configuration — config.py

All tunable parameters live in `config.py`. **Never hardcode thresholds, paths, or ticker lists inside source files.**

```python
# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'market.db')
WATCHLIST_DIR = os.path.join(BASE_DIR, 'data', 'watchlists')

# Universe
UNIVERSE = 'NIFTY500'
MAX_WATCHLIST_SIZE = 10

# Market Monitor thresholds (NSE-validated 2026-04-13)
MM_OFFENSIVE_MA20_PCT = 55.0
MM_OFFENSIVE_UPVOL_RATIO = 0.60
MM_OFFENSIVE_HIGHS_VS_LOWS = 2.0
MM_DEFENSIVE_MA20_PCT = 45.0

# Momentum Burst (live defaults; MB_MAX_PRIOR_RUN promoted 2026-05-08)
MB_MIN_PCT_CHANGE = 5.0
MB_MAX_PCT_CHANGE = 20.0
MB_MIN_VOLUME_RATIO = 1.5
MB_LOOKBACK_DAYS = 3
MB_MIN_PRICE = 50.0
MB_MIN_AVG_VOLUME = 200_000
MB_MAX_PRIOR_RUN = -2.3     # G2-validated: stock must not be extended (prior 10d run < -2.3%)

# Episodic Pivot (live defaults; calibration-validated 2026-04-24, loosened 2026-04-24)
EP_MIN_GAP_PCT = 5.0
EP_MIN_GAP_VOLUME_RATIO = 3.0
EP_MAX_DAYS_SINCE_GAP = 2
EP_MAX_GAP_VOLUME_RATIO = 0.0  # 0.0 = disabled; set to 4.9 for paper-trading observation only

# Trend Intensity (live defaults; TI_MAX_PULLBACK_DEPTH_PCT promoted 2026-05-08)
TI_HIGH_LOOKBACK_DAYS = 50
TI_MA50_TREND_LOOKBACK = 20
TI_MIN_DAYS_ABOVE_MA50 = 40
TI_MIN_VOLUME_RATIO = 1.3
TI_MAX_ATR_PCT = 0.05
TI_MAX_PULLBACK_DEPTH_PCT = 16.0  # G2-validated: deep pullbacks excluded

# Stop-loss by scanner (MAE-optimized 2026-04-29)
EP_STOP_LOSS_PCT = 4.0
MB_STOP_LOSS_PCT = 2.5
TI_STOP_LOSS_PCT = 1.5

# Trade management
TRADE_RISK_PCT = 0.01
TRADE_MAX_POSITION_PCT = 0.10
TRADE_MAX_OPEN = 5
TRADE_DEFENSIVE_SIZE_FACTOR = 0.5
TRADE_TRAIL_TRIGGER_PCT = 5.0   # Trail stop to breakeven after +5%
TRADE_TIME_EXIT_DAYS = 20       # Time-based exit after 20 stored trading days

# Data fetch
DATA_FETCH_RETRY_ATTEMPTS = 3
DATA_FETCH_TIMEOUT_SECONDS = 30
NSE_MARKET_CLOSE_TIME = "15:30"
DATA_PULL_TIME = "16:30"
```

---

## 6. Architecture Decision Records (ADRs)

### ADR-001 — Python over Java
**Status:** Accepted permanently.
Every meaningful Indian market library (nsepy, jugaad-trader, nsetools, kiteconnect) is Python-first. pandas/numpy/ta-lib make OHLCV analysis idiomatic. FastAPI gives zero-boilerplate REST.

### ADR-002 — SQLite over PostgreSQL
**Status:** Accepted.
Zero infra. Runs identically on WSL2 and Termux. 630K rows is small for SQLite. Single `.db` file, trivial backup.
**Revisit when:** Adding intraday data (~47M rows/year) → switch to TimescaleDB.

### ADR-003 — Free NSE data first, Zerodha Kite later
**Status:** Accepted.
`nselib` bhavcopy is primary (live). `yfinance` is fallback. `fetch_ohlcv()` interface is data-source agnostic — switching to Kite is a one-file change.
**Caveats:** Neither source provides adjusted prices. Backtests must flag this.

### ADR-004 — EOD data only; no intraday
**Status:** Accepted through Phase 5.
Pradeep Bonde's methodology is explicitly EOD-based — scan after close, build watchlist, enter next morning. Intraday is a future architecture decision (would break this ADR).

### ADR-005 — No automated order execution
**Status:** Accepted permanently for Phase 1–5.
All execution is manual. A bug in scanner + auto-execution = real financial loss. SEBI automated trading rules apply.

### ADR-006 — NIFTY 500 as primary universe
**Status:** Accepted.
Covers ~95% of total NSE market cap. Best momentum setups are almost always here. 500 symbols = manageable on SQLite.
**Expansion path:** NIFTY 1000 or mid-cap sub-scan after Phase 5 stabilises.

### ADR-007 — Market Monitor thresholds need NSE calibration
**Status:** Accepted and validated (2026-04-13).
3-year historical breadth run on NIFTY 500 confirmed Pradeep's 55% Offensive / 45% Defensive MA20 thresholds correlate optimally with NSE forward returns. Thresholds are NSE-validated.

### ADR-008 — cron over persistent scheduler
**Status:** Accepted.
No persistent process to manage. No memory leak. If the laptop is off at 16:30, job doesn't run — acceptable. Trader runs manually if needed.

```cron
30 16 * * 1-5 cd /home/gaju/dhanustambha && python scripts/daily_briefing.py >> logs/briefing.log 2>&1
```

### ADR-009 — Tiered Live Data Fetching
**Status:** Accepted.
To ensure "Somewhat Live" availability during market hours without expensive API keys, use a tiered approach:
1. `yfinance` (Batch) — Primary choice for speed.
2. `Google Finance Scraper` — Fallback for missing/throttled symbols (Parallelized @ 50 threads).
3. `SQLite DB` — Last resort (previous EOD close) ensuring the scanner never crashes due to partial API failures.

---

## 7. Agent Rules — Behavioral Contract

> Every agent must read and follow all rules below. These exist because this project is built incrementally across many sessions by different agent instances with no shared memory.

### Rule 1 — Orientation Protocol (Every Session)

At the start of every session, before writing any code:

1. Read `AGENTS.md` (this file) completely
2. Read the active plan in `docs/superpowers/plans/`
3. Read `data/research/FINDINGS.md` if doing scanner/calibration work
4. State any open questions before starting work

**Never skip this step.** If you skip and start coding, you will likely contradict something already decided.

### Rule 2 — Scope Discipline

- Work **only** the task assigned in the current plan.
- Do not add features not in the plan. Do not refactor what you weren't asked to refactor.
- If you see something broken outside your task: note it as a `# TODO:` comment and add it to the **Noted Issues** section of this file. Do not fix it unless told to.
- If the plan seems wrong or incomplete, stop and ask. Do not improvise.

> **The enemy of incremental progress is scope creep — even well-intentioned scope creep.**

### Rule 3 — File and Naming Conventions

**Python:**
- All source files live under `src/`. Match the module structure exactly as shown in the repository layout above.
- Tests live under `tests/`. Test file names mirror source: `src/monitor/breadth.py` → `tests/test_monitor_breadth.py`.
- Follow PEP 8. Max line length: 100 characters.
- All functions must have a docstring. No exceptions.
- Use type hints on all function signatures.

**Constants and configuration:**
- **Never hardcode** thresholds, paths, or ticker lists inside source files.
- All constants go in `config.py`. Import from there.
- The SQLite DB path is always `config.DB_PATH`. Never construct it inline.

**Imports:** Standard library → third-party → local, separated by blank lines. No wildcard imports.

### Rule 4 — Testing Rules

- Every function containing business logic must have a test.
- Tests use `pytest`. Run with `pytest tests/ -v` from project root.
- Never mark a task complete without running tests and confirming they pass.
- Tests must be deterministic. No network calls in unit tests — mock them.
- For scanner and breadth logic: use small, in-memory pandas DataFrames with known values.

```python
# Good test pattern
def test_momentum_burst_detects_5_percent_move():
    df = pd.DataFrame({
        'close': [100, 100, 100, 100, 105],
        'volume': [1000, 1000, 1000, 1000, 2500],
        'symbol': ['TEST'] * 5,
        'date': pd.date_range('2024-01-01', periods=5)
    })
    result = detect_momentum_burst(df, min_pct=5.0, min_vol_ratio=1.5)
    assert len(result) == 1
    assert result.iloc[0]['symbol'] == 'TEST'
```

### Rule 5 — Data and Database Rules

- The SQLite schema is defined in `src/ingestion/store.py`. Do not create tables anywhere else.
- Never run raw SQL strings with f-strings. Use parameterized queries: `cursor.execute("SELECT * FROM ohlcv WHERE symbol = ?", (symbol,))`
- All database operations must handle `sqlite3.OperationalError` gracefully with a logged error.
- The `data/` directory is gitignored. Never commit `.db` files.

### Rule 6 — NSE Data Specifics

- NSE market hours: 9:15 AM – 3:30 PM IST (Monday–Friday)
- Data pull runs at **16:30 IST** to allow NSE to publish final EOD data
- NSE holidays must be handled — skip pull on exchange holidays, do not treat a missing day as an error
- Symbol format: `RELIANCE`, `TCS`, `INFY` — **no `.NS` suffix** in the DB
- NIFTY 500 is the primary universe (~500 large/mid cap stocks)
- Corporate actions (splits, bonuses, dividends) affect historical prices. Flag this in any backtest.
- `NIFTY750` is implemented as `NIFTY500 + MICROCAP250` (SMALLCAP250 overlaps fully with NIFTY500)

### Rule 7 — Commit Discipline

- Commit after every completed task step, not after a large batch of work.
- Commit message format: `type(scope): description`
  - Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
  - Examples: `feat(ingestion): add NSE EOD fetch for NIFTY 500` | `fix(scanner): correct volume ratio threshold`
- Never commit broken code. If tests fail, fix them before committing.

### Rule 8 — Updating This File

After completing each task, update the **Completed Tasks Log** section (Section 10) of this file:
- Mark with date: `✅ 2026-05-16 — Task N: Description`
- Note any deviations from the plan and why
- Note any follow-up items discovered

**Also update Section 9** (Current Status & Active Plan) to reflect:
- The current phase
- The active plan file path
- Next actions

### Rule 9 — When Uncertain

If anything in the plan is unclear, ambiguous, or seems wrong:
1. State your assumption explicitly in a comment: `# ASSUMPTION: treating 0 volume as market holiday`
2. Add it to **Open Questions** (Section 11) in this file
3. Continue with the stated assumption rather than blocking

Do not silently make a decision that changes architecture or data models. Those need human review.

### Rule 10 — Error Handling Philosophy

- **Data fetch failures:** Log the symbol, continue with the rest. If >10% fail, abort and alert.
- **SQLite errors:** Always wrap in try/except. Log with full context. Never silently swallow.
- **Scanner errors:** A crash in one scanner should not stop the others. Run each independently.
- **Missing data:** If a symbol has <60 days of history, skip it for any scan requiring a 50-day lookback. Log at DEBUG level.
- **No data for today:** If it's a market holiday, the fetcher gets no data. Expected. Log at INFO and exit cleanly.

---

## 8. Phase History & Build Order

| Phase | Description | Status |
|---|---|---|
| Phase 1 | MVP: Data + Market Monitor + Scanner → `daily_briefing.py` | ✅ Complete + live validation ongoing |
| Phase 2 | Trade Management: position sizer, open trade log, P&L | ✅ Complete |
| Phase 3 | Review Loop: journal, analytics, calibration backtester | ✅ Complete (calibration active) |
| Phase 4 | FastAPI + Next.js UI dashboard | ✅ Complete through F4 |
| Phase 5 / Stream G | Scanner Win-Rate R&D: feature analysis, validation, promotion/demotion gates | ✅ Complete |
| Phase 6 | Live Price Feed & "Somewhat Live" Scanners (Stream H & I) | ✅ Complete |
| Phase 7 | Paper Trading & Exit Mechanics Execution | 🔄 In progress |

**Phase 1** is complete when `python scripts/daily_briefing.py` runs and produces:

```
=== Dhanustambha Daily Briefing — 2026-05-16 ===

MARKET MONITOR
  Stocks above MA20:     58%
  New 52w highs:         47  |  New 52w lows: 12
  Verdict:               OFFENSIVE ✅

TOP MOMENTUM BURST CANDIDATES (5)
  ⭐ HIGH  DIXON    +8.2   3.4x   ...
  ...

TOP EPISODIC PIVOT CANDIDATES (3)
  ⭐ A+    POLYCAB  +6.1   5.2x   2 days
  ...

Watchlist saved to: data/watchlists/2026-05-16.csv
```

---

## 9. Current Status & Active Plan

**Last updated:** 2026-05-20
**Current phase:** Phase 6 — Paper Trading

**Active plan file:** `docs/superpowers/plans/2026-05-16-interactive-trade-book.md`

**Research findings file:** `data/research/FINDINGS.md`

### Stream G Summary

Stream G is a research pipeline to improve scanner signal quality by identifying predictive features and promoting proven filters to live detection code.

**Research pipeline:**
1. **G1** — Feature bucket analysis: run `analyze_signal_features.py` on historical calibration signal CSVs; identify features with win-rate spread ≥ 15pp across quartile buckets
2. **G2** — Extended calibration validation: run the feature as a `--feature-filters` post-filter in `calibrate_thresholds.py` across a rolling window; gate passes if OFFENSIVE win rate >50% and signal count is sufficient
3. **G3** — Live promotion: add the validated filter to scanner code + `config.py`; write an explicit rejection test

**Promotion gate (G2 → G3):**
- Filtered OFFENSIVE win rate > the baseline by a meaningful margin
- At least 30 OFFENSIVE signals remain in the calibration window after filtering
- Result must generalise across temporal windows (H1 + H2 of a year, not just one period)

**G2 results so far:**

| Scanner | Feature | Result | Action |
|---|---|---|---|
| MB | `prior_10d_run_pct < -2.3` | ✅ VALIDATED | Promoted to live in `config.py` + `detect_momentum_burst()` |
| MB | `consolidation_days < 4` | ❌ FAILED | Single-day artifact; did not generalise |
| TI | `pullback_depth_20d < 16.0` | ✅ VALIDATED | Promoted to live in `config.py` + `detect_trend_intensity()` |
| TI | `trend_efficiency_ratio < 0.3` | ❌ FAILED | Defensive regimes failed completely |
| TI | `relative_strength_vs_benchmark_3m:2.4..6.7` | ❌ FAILED | Signal count choked (6–12 signals), no generalisation |
| EP | `prior_65d_weakness_pct >= 37` | ❌ FAILED | 2025-H2 out-of-sample failure |
| EP | `gap_vol_ratio <= 4.9` | ⚠️ OBSERVATION | Survived rolling validation; H2 OFFENSIVE count too small for hard default |

### Next Actions

1. **Resolve Phase 6 risk policy:** Decide whether live paper trading should use current config (`TRADE_RISK_PCT = 0.025`, `TRADE_MAX_POSITION_PCT = 0.25`) or the handoff-stated 1% risk / max-position cap, then update `config.py` and docs if needed.
2. **Continue Trade Book live testing** by opening a controlled paper trade only after the risk policy is confirmed.
3. **Keep EP quality filtering in observation mode** until a longer window justifies promoting `EP_MAX_GAP_VOLUME_RATIO = 4.9` to a live default.

---

## 10. Completed Tasks Log

```
✅ 2026-04-13 — Task 1: Project scaffold and config
✅ 2026-04-13 — Task 2: SQLite schema and store module
✅ 2026-04-13 — Task 3: Symbol list and NSE data fetcher
✅ 2026-04-13 — Task 4: Market Monitor breadth engine
✅ 2026-04-13 — Task 5: Momentum Burst scanner
✅ 2026-04-13 — Task 6: Episodic Pivot and Trend Intensity scanners
✅ 2026-04-13 — Task 7: Daily briefing orchestrator and watchlist export
✅ 2026-04-13 — Phase 1 Validation: symbol universe cleanup (MM → M&M, ULTRACEMIN → ULTRACEMCO)
✅ 2026-04-13 — Phase 1 Validation: annotated all config.py thresholds with NSE calibration status
✅ 2026-04-13 — Stream A: dynamic NSE constituent loading (NIFTY500 default, NIFTY750 optional)
✅ 2026-04-13 — Stream B: manual trade workflow (trade/log.py, trade_manager.py CLI)
✅ 2026-04-13 — Stream C: 3-year NIFTY500 historical backfill (342,283 OHLCV rows; nselib primary)
✅ 2026-04-14 — Stream C: Momentum Burst calibration for NIFTY500
✅ 2026-04-15 — Stream C: Episodic Pivot calibration for NIFTY500
✅ 2026-04-15 — Stream C: Trend Intensity calibration for NIFTY500; defaults updated
✅ 2026-04-22 — Stream D (D1-D2): backtest.py emits richer signal rows (1d/3d/5d/10d/20d returns, MAE/MFE, alpha)
✅ 2026-04-22 — Stream D (D3-D4): breadth context joined to backtest rows; scanner research-only feature columns added
✅ 2026-04-22 — Stream D (D5-D6): calibrate_thresholds.py writes -summary.csv and -signals.csv; alpha-aware ranking
✅ 2026-04-24 — Benchmark ingestion: backfill_benchmark.py added; NIFTY proxy stored in ohlcv
✅ 2026-04-24 — Calibration profiling: --summary-only, --max-param-sets controls added
✅ 2026-04-24 — Calibration reuse refactor: history preloaded once per run (22s → 5.6s per parameter set)
✅ 2026-04-24 — Historical breadth backfill: backfill_breadth.py; 123 rows covering Jan-Jun 2025
✅ 2026-04-24 — Full-grid calibration reruns: MB, EP, TI on Jan-Jun 2025 NIFTY500 window
✅ 2026-04-24 — EP historical-calibration bug fixed: same-day gap rows now eligible (days_since_gap=0)
✅ 2026-04-24 — Cross-scanner calibration review: EP confirmed as strongest scanner
✅ 2026-04-24 — Live EP defaults updated: EP_MIN_GAP_PCT=5.0, EP_MIN_GAP_VOLUME_RATIO=3.0, EP_MAX_DAYS_SINCE_GAP=2
✅ 2026-04-28 — Watchlist improvement: matched_setups + setup_match_count fields retained in export
✅ 2026-04-28 — Deep alpha analysis (2+ years): EP confirmed as only scanner with true edge
✅ 2026-04-28 — EP Dual-Tier Output: A+ (tight thresholds) and B labels implemented
✅ 2026-04-28 — MB Quality Redesign: HIGH label implemented
✅ 2026-04-28 — Daily briefing UI: HIGH/A+ sort to top, marked with ⭐
✅ 2026-05-17 — UX Refinements: enlarged charts to 400px, CSS breadth progress bars, and manual briefing trigger UI/API added
✅ 2026-04-29 — Stop-Loss Optimization (MAE): EP=4.0%, MB=2.5%, TI=1.5% fixed stops added to config.py
✅ 2026-04-29 — Target & Exit Strategy (MFE): hold 20d, trail to breakeven at +5%
✅ 2026-04-29 — Daily briefing UI: STOP_LOSS dynamic column added to output table
✅ 2026-04-29 — Stream E: trade_manager.py status shows pct_gain, days_held, action_required; update command added
✅ 2026-04-30 — Phase 4 Task 1: read-only FastAPI API (health, briefing, watchlist, breadth, trades endpoints)
✅ 2026-04-30 — Phase 4 Task 2: Next.js dashboard shell consuming FastAPI endpoints
✅ 2026-04-30 — Phase 4 Task 3: dashboard detail interactions; GET /briefing/dates endpoint
✅ 2026-04-30 — Phase 4 validation fix: CORS headers added to FastAPI
✅ 2026-04-30 — Phase 4 validation fix: duplicate watchlist rows collapsed in API response
✅ 2026-05-07 — Phase 4 Task F4: Playwright E2E smoke test suite added (dashboard.spec.ts)
✅ 2026-05-07 — Stream G planning: design spec + plan documents created
✅ 2026-05-07 — Stream G Tasks 1-2: analyze_signal_features.py + tests created
✅ 2026-05-07 — Stream G Tasks 3-5: EP feature analysis run; findings in FINDINGS.md
✅ 2026-05-07 — Stream G: disabled-by-default EP quality filter added (EP_MAX_GAP_VOLUME_RATIO)
✅ 2026-05-07 — Stream G: TI exposes relative_strength_vs_benchmark_3m
✅ 2026-05-07 — Stream G Task 7: MB HIGH-tier smoke validation recorded (did not pass hardening gate)
✅ 2026-05-07 — Stream G Task 10: TI RS benchmark history bug fixed; 10-set RS smoke recorded
✅ 2026-05-08 — Stream G G1 (MB): consolidation_days, prior_10d_run_pct, nr_count_10d, others cleared 15pp gate
✅ 2026-05-08 — Stream G G1 (TI): trend_efficiency_ratio, pullback_depth_20d, others cleared 15pp gate
✅ 2026-05-08 — Stream G G2 (MB): prior_10d_run_pct<-2.3 VALIDATED; MB_MAX_PRIOR_RUN promoted to live
✅ 2026-05-08 — Stream G G2 (TI): pullback_depth_20d<16.0 VALIDATED; TI_MAX_PULLBACK_DEPTH_PCT promoted to live
✅ 2026-05-08 — Stream G Task 10: TI RS full-grid FAILED; RS not promoted
✅ 2026-05-08 — Stream G G3 tests: test_mb_prior_run_filter_rejects_extended_stock + test_ti_pullback_filter_rejects_deep_pullback added
✅ 2026-05-16 — AGENTS.md created: single source of truth consolidating all project docs
✅ 2026-05-16 — Stream G Task 9 (Demotion Review): TI demoted to REFERENCE_ONLY; MB retained ACTIVE with G2 filter
✅ 2026-05-16 — Phase 6 Target Analysis: Validated deep edge of Aggressive Trailing ladders over standard Fixed Exits 
✅ 2026-05-16 — Phase 6 Exits: Implemented 3-Tier Aggressive Trailing exit logic in `determine_action_required` 
✅ 2026-05-16 — Phase 6 Reentry: Built and integrated EP Re-Entry scanner into `daily_briefing.py` 
✅ 2026-05-16 — Phase 6 Validation: Proven Microcaps/NIFTY750 drastically decays EP win rate; NIFTY500 confirmed ideal
✅ 2026-05-16 — Task 18: Phase 6 Paper Trading Execution (Aggressive Trailing, EP Re-Entry, NIFTY750 Research) 
✅ 2026-05-16 — Task 19: Interactive Trade Book Implementation
✅ 2026-05-16 — Task 20: Embedded Charts (Sub-Project 2)
✅ 2026-05-16 — Task 21: Breadth Dashboard (Sub-Project 3)
✅ 2026-05-17 — Backtest handoff verification
✅ 2026-05-17 — Trade ticket live validation fix
✅ 2026-05-17 — Valvo Dashboard Visual Upgrade (Sub-Projects A, B, C, D)
✅ 2026-05-17 — Dedicated Market Monitor page
✅ 2026-05-20 — Bug fix: EP scanner tab showed 0 candidates
   - Root cause: `scanner-client.tsx` filter tab used the alias `'EP'` as the filter value; DB stores `setup_type = 'EPISODIC_PIVOT'`
   - Fix: segmented control now uses `'EPISODIC_PIVOT'` as value with `'EP'` as display label
   - Added `test_ep_watchlist_setup_type_is_episodic_pivot_not_ep` to `tests/test_api.py` to lock in the contract
✅ 2026-05-20 — Bug fix: trade modal shares field was read-only
    - Root cause: the execute form displayed computed shares as a `<Metric>` display-only component; user had no way to override the server-computed quantity
    - Fix: replaced `<Metric>` with an editable `<input type="number">` seeded from `quote.shares`; user override is wired into the `/trades/open` payload
    - `Confirm Trade` button remains disabled until a valid quote exists and shares > 0
✅ 2026-05-20 — Stream H: Live Price Feed (LTP)
    - Implemented `LivePriceCache` with 60s TTL and Tiered Fetcher (yfinance -> Google).
    - Integrated real-time LTP polling in Scanners Table and Trade Book P&L.
✅ 2026-05-20 — Stream I: Somewhat Live Market Scanner
    - Built async briefing pipeline (`/briefing/live/start`) with background worker and job/progress tracking.
    - Optimized DB queries to use 60-day lookback instead of full history (drastic speedup).
    - Created reusable `LiveScanController` with progress bar UI.
    - Integrated "Live Briefing" button directly into the main Dashboard.
✅ 2026-05-20 — Bug fix: yfinance throttling caused noisy JSON decode errors logs; suppressed yfinance internal logger.
✅ 2026-05-20 — UX: Added Execute button directly to watchlist table rows in `scanner-client.tsx`.
✅ 2026-05-20 — Bug fix: Live scanner timeouts resolved by switching yfinance interval from 1m to 1d.
✅ 2026-05-20 — Bug fix: Watchlist UI duplicates prevented by adding date-based clear before insertion in DB.
```

---

## 11. Open Questions

- [ ] **Intraday/opening alerts (future phase):** User wants help reducing market-open FOMO and missed entries. Deferred — would break ADR-004 (EOD only) and requires an explicit architecture decision. Capture as future enhancement: "opening-plan alerts" for next-day entry planning before true intraday signal generation.

- [ ] **EP quality filter live promotion:** `EP_MAX_GAP_VOLUME_RATIO = 4.9` survived rolling 2025 validation but H2 OFFENSIVE signal count was too small. Remains a disabled-by-default paper-trading observation filter. Needs a longer window or a richer H2 signal pool before a hard live default is warranted.

- [ ] **MB/TI reference-only demotion (Task 9):** Both scanners now have one validated live filter each. The open question is whether their remaining signal quality justifies a spot in the main watchlist, or whether a formal `REFERENCE_ONLY_SCANNERS` demotion gate should be used.

---

## 12. Noted Issues & Deviations

### Active Issues

- No active test failure is currently noted from the Phase 6 handoff. The previous `tests/test_backtest.py::test_backtest_runs_on_synthetic_data` item was verified passing on 2026-05-17.

- ~~EP scanner tab showed 0 candidates on 2026-05-20~~ **RESOLVED 2026-05-20** — filter value corrected from `'EP'` alias to `'EPISODIC_PIVOT'` in `scanner-client.tsx`.

- ~~Trade modal shares field was read-only~~ **RESOLVED 2026-05-20** — editable `<input>` field with server-computed default added to `CandidateDetailPanel`.

- ~~yfinance throttling caused noisy JSON errors in terminal~~ **RESOLVED 2026-05-20** — set yfinance logger to CRITICAL to suppress non-fatal parsing errors.

- ~~Execute ⚡ button only available in detail panel~~ **RESOLVED 2026-05-20** — added Execute button directly in watchlist table rows and wired `isExecuting` state.

- ~~Live scanner briefing takes several minutes due to heavy rate throttling~~ **RESOLVED 2026-05-20** — changed `yfinance` download interval from `1m` to `1d` to fetch single daily candles without throttling.

- ~~Live scanner appends duplicated watchlist records when run multiple times~~ **RESOLVED 2026-05-20** — modified `save_watchlist` to delete the given date's entries before inserting new ones.

- Phase 6 risk config needs an explicit decision before real paper-trade entry: current `config.py` uses `TRADE_RISK_PCT = 0.025` and `TRADE_MAX_POSITION_PCT = 0.25`, while the handoff language expected 1% risk and a max-position cap. The UI correctly reflects backend config, but the intended risk policy must be confirmed.

- `src/review/market_regime.py` from a follow-on plan is intentionally deferred; calibration proceeds without market-regime classification until explicitly prioritised.

### Deviations from Original Plan

- `requirements.txt` uses: `nselib==2.4.6`, `nsepy==0.8`, `pandas-ta-classic==0.3.14b2`, `numpy==2.2.6`
- Historical backfill uses `nselib.capital_market.price_volume_data()` as primary (yfinance returned empty/no-timezone responses for many NSE tickers)
- `fetch_via_yfinance()` queries an explicit date window for historical overrides to work
- `daily_briefing.py` incrementally backfills missing business-day history before computing breadth and scanners
- `NIFTY750` = `NIFTY500 + MICROCAP250` (SMALLCAP250 overlaps fully with NIFTY500)
- `trade_manager.py` is an interactive CLI rather than a CSV-driven workflow
- `calibrate_thresholds.py` ranks parameter sets by 10-day forward win rate first, then avg 10-day return and signal count
- `detect_episodic_pivot()` treats qualifying latest-row gap as `days_since_gap = 0` (matches architecture intent)
- `detect_momentum_burst()` evaluates the "already extended" rule over the immediate prior 10 trading days (not older history)
- The backtest layer falls back to a local equal-weight benchmark proxy from stored universe history when no external benchmark series is present
- Live EP defaults were loosened from the strict calibrated `6.0/3.0/2` to `5.0/3.0/2` after live selectivity check showed zero candidates on most sessions
- Final exported watchlists record one winning `setup_type` per symbol by design; use `matched_setups` column when validating whether multiple scanners triggered on the same symbol
- `TATAMOTORS` legacy OHLCV rows have been mapped and aliased to `TMCV` in the historical backend
