# Aggressive Trailing Exits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the new 3-tier aggressive trailing stop system and an Episodic Pivot re-entry scanner.

**Architecture:** We will update `config.py` constants, alter `determine_action_required` in `src/trade/log.py` to prompt the 3 different trail tiers, add a new scanner module `src/scanner/reentry.py` that queries closed EP trades and matches them against `ohlcv` to spot pullbacks, and surface these in `scripts/daily_briefing.py`.

**Tech Stack:** Python 3.11, pandas, sqlite3, pytest

---

### Task 1: Update Configuration Constants

**Files:**
- Modify: `config.py:88-92`

- [ ] **Step 1: Replace old trail trigger with tier configs**

```python
# Replace TRADE_BREAKEVEN_TRIGGER_PCT = 5.0 with:
TRADE_TRAIL_TIER_1_TRIGGER_PCT = 3.0
TRADE_TRAIL_TIER_1_STOP_PCT = 0.0

TRADE_TRAIL_TIER_2_TRIGGER_PCT = 7.5
TRADE_TRAIL_TIER_2_STOP_PCT = 3.0

TRADE_TRAIL_TIER_3_TRIGGER_PCT = 10.0
TRADE_TRAIL_TIER_3_STOP_PCT = 7.5

TRADE_TIME_EXIT_DAYS = 20
```

- [ ] **Step 2: Commit changes**

```bash
git add config.py
git commit -m "feat(config): add aggressive trailing stop tier constants"
```

---

### Task 2: Implement 3-Tier Rule in Trade Log

**Files:**
- Modify: `src/trade/log.py:182-200`
- Modify: `tests/test_trade_log.py` (Assuming tests exist here, or we will patch it. Actually, verify `tests/test_trade_log.py` exists during execution).

- [ ] **Step 1: Update `determine_action_required` logic**

Replace `determine_action_required` in `src/trade/log.py` to check thresholds top-down:

```python
def determine_action_required(
    entry_price: float,
    stop_price: float,
    pct_gain: Optional[float],
    days_held: int,
) -> str:
    """Return the trade-management action required by current gain and holding age."""
    if days_held >= config.TRADE_TIME_EXIT_DAYS:
        return "TIME_EXIT"

    if pct_gain is not None:
        if pct_gain >= config.TRADE_TRAIL_TIER_3_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_3_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_7_5PCT"
                
        if pct_gain >= config.TRADE_TRAIL_TIER_2_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_2_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_3PCT"
                
        if pct_gain >= config.TRADE_TRAIL_TIER_1_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_1_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_BREAKEVEN"

    return "NONE"
```

- [ ] **Step 2: Update unit tests for action triggers**

Update `tests/test_trade_log.py` to fix old tests and add tests for Tiers 1-3. Run pytest until passing.

- [ ] **Step 3: Commit**

```bash
git add src/trade/log.py tests/test_trade_log.py
git commit -m "feat(trade): implement 3-tier aggressive trailing action triggers"
```

---

### Task 3: Build the EP Re-Entry Scanner

**Files:**
- Create: `src/scanner/reentry.py`
- Create: `tests/test_scanner_reentry.py`

- [ ] **Step 1: Write `reentry.py` logic**

```python
"""Scanner for Episodic Pivot re-entry setups."""

import pandas as pd
from src.trade.log import get_closed_trades

def detect_ep_reentry(ohlcv: pd.DataFrame, days_since_close: int = 30) -> pd.DataFrame:
    """Find EP re-entry candidates: previous EP trades that pulled back to touching MA10/MA20 and broken out."""
    closed_trades = get_closed_trades(last_n_days=days_since_close)
    if closed_trades.empty:
        return pd.DataFrame()
        
    ep_trades = closed_trades[closed_trades["setup_type"] == "EPISODIC_PIVOT"]
    if ep_trades.empty:
        return pd.DataFrame()

    ep_symbols = ep_trades["symbol"].unique()
    df = ohlcv[ohlcv["symbol"].isin(ep_symbols)].copy()
    if df.empty:
        return pd.DataFrame()

    # Calculate MAs and Vol ratio
    df["ma10"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(10).mean())
    df["ma20"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20).mean())
    df["vol20"] = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20).mean())
    df["vol_ratio"] = df["volume"] / df["vol20"]
    df["prev_high"] = df.groupby("symbol")["high"].shift(1)

    latest_date = df["date"].max()
    today_df = df[df["date"] == latest_date].copy()
    
    candidates = []
    for _, row in today_df.iterrows():
        # Condition 1: Close is above prev high
        if row["close"] <= row["prev_high"]:
            continue
            
        # Condition 2: Touch or cross MA10 or MA20 in the last 2 days
        sym = row["symbol"]
        recent = df[(df["symbol"] == sym) & (df["date"] <= latest_date)].tail(3)
        if len(recent) < 2:
            continue
            
        touched_ma = False
        for _, rev_row in recent.iterrows():
            if (rev_row["low"] <= rev_row["ma10"] <= rev_row["high"]) or \
               (rev_row["low"] <= rev_row["ma20"] <= rev_row["high"]):
                touched_ma = True
                break
                
        if not touched_ma:
            continue
            
        res = row.to_dict()
        res["score"] = row["vol_ratio"]
        res["setup_type"] = "EP_REENTRY"
        res["pct_change"] = ((row["close"] / row["prev_high"]) - 1.0) * 100
        res["volume_ratio"] = row["vol_ratio"]
        candidates.append(res)
        
    return pd.DataFrame(candidates)
```

- [ ] **Step 2: Write tests in `test_scanner_reentry.py`**
Verify the fallback behavior and basic SMA triggering logic. (You'll need a mocked `get_closed_trades` via monkeypatch). Follow standard Dhanustambha test patterns. 

- [ ] **Step 3: Commit**

```bash
git add src/scanner/reentry.py tests/test_scanner_reentry.py
git commit -m "feat(scanner): add episodic pivot runner re-entry scanner"
```

---

### Task 4: Integrate Re-Entry to Daily Briefing

**Files:**
- Modify: `scripts/daily_briefing.py`

- [ ] **Step 1: Import scanner and process results**

In `scripts/daily_briefing.py`:
- Add `from src.scanner.reentry import detect_ep_reentry`
- Inside `run_briefing` after calling the 3 main scanners around line 231, add:

```python
    reentry_results = detect_ep_reentry(all_data)
    print(f"      EP Re-Entry:       {len(reentry_results)} candidates")
```

And around line 279 (where it prints the layout tables):

```python
    _print_setup_table("TOP TREND INTENSITY", ti_results)
    
    if not reentry_results.empty:
        _print_setup_table("⭐ EP RUNNER RE-ENTRY", reentry_results)
```

- [ ] **Step 2: Verify and Commit**
Run `pytest` to make sure you didn't break layout functions.

```bash
git add scripts/daily_briefing.py
git commit -m "feat(briefing): print EP re-entry candidates in daily report"
```
