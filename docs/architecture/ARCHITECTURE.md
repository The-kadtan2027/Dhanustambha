# Architecture — Dhanustambha Trading Platform

**Version:** 1.0  
**Date:** 2026-04-11  
**Author:** Gaju  

---

## Problem Statement

Manual trading is inconsistent. Without a system, a trader is subject to emotion, recency bias, and missed setups. The goal is to build a tool that runs the same process every day, removes emotion from scanning, and gives the trader a clear, ranked shortlist to act on — while they remain in full control of execution.

---

## Guiding Principles

1. **Process over prediction.** The system does not predict the future. It identifies setups that have historically led to profitable outcomes, and lets the trader decide.
2. **Market-first.** No trade is placed unless the Market Monitor says conditions are Offensive. Capital is protected first.
3. **Zero cost infra.** Everything runs on hardware already owned. No cloud, no paid APIs in Phase 1.
4. **Incremental build.** Each phase produces a working, useful tool. Phase 1 alone has immediate trading value.
5. **Human in the loop.** The system scans, alerts, and informs. The human decides. No automated execution, ever, without explicit future decision to build that.

---

## System Overview

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
┌─────────────────────┐
│   daily_briefing.py │  Merges, ranks, prints, saves watchlist
│   (Phase 1 output)  │
└─────────────────────┘
         │
         │  (Phase 2+)
         ▼
┌─────────────────────┐    ┌─────────────────────┐
│   Layer 4           │    │   Layer 5           │
│   Trade Management  │    │   Review Loop       │
│   sizer, log, P&L   │    │   journal, backtest │
└─────────────────────┘    └─────────────────────┘
         │                           │
         └──────────┬────────────────┘
                    ▼
         ┌─────────────────┐
         │  FastAPI + UI   │  (Phase 3+)
         │  Next.js dash   │
         └─────────────────┘
```

---

## Layer 1 — Data Ingestion

### Responsibility
Fetch daily OHLCV (Open, High, Low, Close, Volume) data for all NIFTY 500 symbols from NSE. Store cleanly in SQLite. Handle holidays, retries, and partial failures gracefully.

### Data source strategy
- **Phase 1:** `nsepy` library or direct NSE Bhavcopy CSV download (free, no key)
  - NSE Bhavcopy: `https://www.nseindia.com/api/reports?archives=...` (requires session cookie)
  - Fallback: `yfinance` with `.NS` suffix (data quality is acceptable for EOD)
- **Phase 2+:** Zerodha Kite Connect historical data API (paid subscription, much cleaner)

### SQLite schema

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
```

### Update flow
```
16:30 IST → scheduler.py
  → fetcher.py: download today's Bhavcopy CSV for all NIFTY 500 symbols
  → store.py: upsert into ohlcv table (UNIQUE constraint prevents duplicates)
  → log success/failure per symbol
  → if >10% symbols failed: raise alert, abort downstream processing
```

---

## Layer 2 — Market Monitor

### Responsibility
Compute daily breadth metrics and emit a single verdict that gates all scanning activity.

### Metrics computed

| Metric | Calculation | Offensive threshold |
|---|---|---|
| % above MA20 | Count(close > 20d SMA) / total | > 55% |
| % above MA50 | Count(close > 50d SMA) / total | > 50% |
| New 52w highs | Count(today_high = max(high, 252d)) | > 40 |
| New 52w lows | Count(today_low = min(low, 252d)) | < 20 |
| Up-volume ratio | Sum(volume where close > open) / total volume | > 0.60 |
| Adv/Dec ratio | advancing / declining | > 1.5 |

### Verdict logic

```python
# Simplified decision tree
if pct_above_ma20 > 55 and up_volume_ratio > 0.60 and new_highs > new_lows * 2:
    verdict = "OFFENSIVE"   # Trade aggressively. Full position sizes.
elif pct_above_ma20 > 45 and new_highs > new_lows:
    verdict = "DEFENSIVE"   # Trade small. Reduce position sizes by 50%.
else:
    verdict = "AVOID"       # No new trades. Protect capital.
```

**Thresholds are configurable in `config.py`.** They will need tuning against NSE historical data — Indian market breadth behaves differently from US markets that Pradeep originally calibrated for.

### Output
- Writes one row to `breadth` table
- Returns verdict string to `daily_briefing.py`

---

## Layer 3 — Setup Scanner

### Responsibility
Given the universe of stocks and their OHLCV history, identify stocks that match one of three setup templates.

### Setup 1: Momentum Burst

**What it is:** A stock that has been quiet/consolidating, then suddenly explodes in price AND volume over 1–3 days. The burst indicates institutional or informed buying.

**Detection criteria:**
```
- Today's close is 5–25% above the close N days ago (N = 1, 2, or 3)
- Today's volume is >= 1.5x the 20-day average volume
- The stock was NOT already up > 15% in the prior 10 days (avoid extended stocks)
- Price > ₹50 (avoid penny stocks)
- 20-day average daily volume > 200,000 shares (minimum liquidity)
```

**Score:** `pct_change * volume_ratio` — higher is better

### Setup 2: Episodic Pivot (EP)

**What it is:** A stock that has gapped up significantly on an earnings announcement or major news event, and is holding/building above the gap. These can run for weeks.

**Detection criteria:**
```
- Stock gapped up > 4% from previous close at open
- Gap happened 0–5 trading days ago
- Stock is currently trading above the gap-open price (holding the gap)
- Volume on gap day was >= 3x the 20-day average
- The stock was NOT extended before the gap (close < 1.10 * 52w high before gap)
```

**Data dependency:** Requires earnings calendar. In Phase 1, EP detection is purely price/volume based (no earnings date lookup). A news/earnings calendar integration is a Phase 2 enhancement.

### Setup 3: Trend Intensity Breakout

**What it is:** A stock in a persistent, steady uptrend (low volatility, consistent higher highs/lows) breaking to a new N-week high with above-average volume.

**Detection criteria:**
```
- 50-day SMA is rising (today's MA50 > MA50 20 days ago)
- Today's close is a new 10-week (50-day) high
- The stock has been above MA50 for >= 30 of the last 50 days
- Volume today >= 1.3x 20-day average
- ATR(14) / close < 0.03 (low volatility — the "quiet" trend)
```

### Watchlist output
All three scans run and their results are merged. The final watchlist is sorted by score descending. The top N candidates (configurable, default 10) are written to:
- `data/watchlists/YYYY-MM-DD.csv`
- `watchlist` table in SQLite

---

## Layer 4 — Trade Management (Phase 2)

### Position sizing: Fixed Fractional Risk
```
risk_per_trade = account_size * risk_pct  (default 1%)
stop_distance = entry_price - stop_price
shares = risk_per_trade / stop_distance
position_value = shares * entry_price
```

**Hard limits:**
- No single position > 10% of account (even if risk model allows it)
- Max 5 open positions simultaneously (Phase 2 default)
- Reduce all sizes by 50% in DEFENSIVE market conditions

### Trade log schema
```sql
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

## Layer 5 — Review Loop (Phase 3)

### Trade journal
After closing a trade, the trader fills in:
- Setup grade at entry (A/B/C)
- Was the entry rule followed?
- Was the exit rule followed?
- What would you do differently?

### Analytics computed weekly
- Win rate by setup type
- Average R-multiple (profit / initial risk) by setup type
- Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
- Best and worst performing sectors
- Compliance rate (did you follow your rules?)

### Backtester (Phase 3)
Runs a setup's detection logic over 2 years of historical data. Reports:
- Number of signals generated
- Win rate
- Average hold period
- Max drawdown of the strategy
- Comparison to NIFTY 500 buy-and-hold

---

## Configuration — config.py

All tunable parameters live here. Agents must never hardcode these values.

```python
# config.py
import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'market.db')
WATCHLIST_DIR = os.path.join(BASE_DIR, 'data', 'watchlists')

# Universe
UNIVERSE = 'NIFTY500'       # or 'NIFTY50' for faster dev testing
MAX_WATCHLIST_SIZE = 10

# Market Monitor thresholds
MM_OFFENSIVE_MA20_PCT = 55.0
MM_OFFENSIVE_UPVOL_RATIO = 0.60
MM_OFFENSIVE_HIGHS_VS_LOWS = 2.0
MM_DEFENSIVE_MA20_PCT = 45.0

# Momentum Burst thresholds
MB_MIN_PCT_CHANGE = 5.0
MB_MAX_PCT_CHANGE = 25.0
MB_MIN_VOLUME_RATIO = 1.5
MB_LOOKBACK_DAYS = 3
MB_MIN_PRICE = 50.0
MB_MIN_AVG_VOLUME = 200_000
MB_MAX_PRIOR_RUN = 15.0     # Avoid stocks already up >15% in prior 10 days

# Episodic Pivot thresholds
EP_MIN_GAP_PCT = 4.0
EP_MIN_GAP_VOLUME_RATIO = 3.0
EP_MAX_DAYS_SINCE_GAP = 5

# Trend Intensity thresholds
TI_HIGH_LOOKBACK_DAYS = 50  # 10-week high
TI_MA50_TREND_LOOKBACK = 20
TI_MIN_DAYS_ABOVE_MA50 = 30
TI_MIN_VOLUME_RATIO = 1.3
TI_MAX_ATR_PCT = 0.03

# Trade management
TRADE_RISK_PCT = 0.01        # Risk 1% of account per trade
TRADE_MAX_POSITION_PCT = 0.10
TRADE_MAX_OPEN = 5
TRADE_DEFENSIVE_SIZE_FACTOR = 0.5

# Data fetch
DATA_FETCH_RETRY_ATTEMPTS = 3
DATA_FETCH_TIMEOUT_SECONDS = 30
NSE_MARKET_CLOSE_TIME = "15:30"
DATA_PULL_TIME = "16:30"
```

---

## Error Handling Philosophy

- **Data fetch failures:** Log the symbol, continue with the rest. If > 10% fail, abort and alert.
- **SQLite errors:** Always wrap in try/except. Log with full context. Never silently swallow.
- **Scanner errors:** A crash in one scanner should not stop the others. Run each independently.
- **Missing data:** If a symbol has < 60 days of history, skip it for any scan that requires a 50-day lookback. Log it at DEBUG level.
- **No data for today:** If it's a market holiday, the fetcher gets no data. This is expected. Log at INFO and exit cleanly.
