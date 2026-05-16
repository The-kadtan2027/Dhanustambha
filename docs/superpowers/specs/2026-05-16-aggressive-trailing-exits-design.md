# Spec: Aggressive Trailing Exits & EP Runner Re-Entry

**Date:** 2026-05-16
**Status:** DRAFT (Pending User Review)
**Scope:** Trade exit management (`src/trade/trade_manager.py`) and Scanner (`src/scanner/`) for newly-added re-entry logic.

## Goal
To implement a high-conviction "Never go red" profit-taking system that locks in gains aggressively on Momentum Burst (MB) and Episodic Pivot (EP) trades, while creating a formal re-entry window for high-relative-strength EP runners that shake us out.

## Context
Target analysis on our historical MFE data shows:
- EPs can push to >30% gains over 20+ day holds, but normal drawdowns mean static stops cut winners short.
- MBs pop quickly (often bleeding back half their gains within 5-10 days), causing a major "giveback" penalty if left unmanaged.
- The user requested "Approach 2: Aggressive Trailing" combined with a method to re-enter monster EP setups after being "wiggled out".

## 1. Trade Management Rules (The Aggressive Trail)

All trades tracked in the SQLite `trades` table will be managed via the `trade_manager.py` daily process. The management script will apply the following trailing tier logic sequentially:

**For BOTH Episodic Pivots and Momentum Bursts:**
1. **Level 1 (Breakeven):** When a trade hits `+3%` from its entry price, the stop loss is adjusted up to `Entry Price` (Breakeven).
2. **Level 2 (Lock Win):** When a trade hits `+7.5%`, the stop loss is adjusted up to `Entry Price + 3%`.
3. **Level 3 (Runner):** When a trade hits `+10%`, the stop loss is adjusted up to `Entry Price + 7.5%`.
4. **Subsequent:** (Optional later addition) Trail by 10-day low / moving average. For now, hard mechanical targets.
5. **Time Exit:** Unchanged. The daily monitor will flag `action_required="TIME_EXIT"` if a position is held for 20 trading days and hasn't hit its trail or hard stop.

### Configuration updates needed in `config.py`:
```python
TRADE_TRAIL_TIER_1_TRIGGER_PCT = 3.0
TRADE_TRAIL_TIER_1_STOP_PCT = 0.0      # +0% (Break Even)

TRADE_TRAIL_TIER_2_TRIGGER_PCT = 7.5
TRADE_TRAIL_TIER_2_STOP_PCT = 3.0      # +3% locked in

TRADE_TRAIL_TIER_3_TRIGGER_PCT = 10.0
TRADE_TRAIL_TIER_3_STOP_PCT = 7.5      # +7.5% locked in
```

## 2. EP Re-Entry System ("The Runner Watchlist")

When an Episodic Pivot trade is closed for a profit (meaning it hit a trailing stop for a BE, 3%, or 7.5% win), we don't forget about it. Instead, the stock enters a 30-day "Runner Watchlist".

**Detecting Re-Entry Candidates:**
A new scanner module or function (`detect_ep_reentry`) will run daily against symbols in the EP Runner Watchlist.

**Re-Entry Buy Triggers (Pullback to MA):**
1. **Pre-condition:** Stock was a previously captured EP.
2. **Pullback Test:** Price touches or closes near the rising 10-day or 20-day Simple Moving Average (SMA).
3. **Trigger:** Price breaks *above* the previous day's high (a classic 10-day high breakout or moving average bounce).
4. **Volume:** Today's volume > 10-day average volume (or relative volume > 1.2x).

**Execution:**
- The symbol appears in the daily briefing under a new section: **⭐ EP RUNNER RE-ENTRY**.
- It is traded exactly like a normal EP entry: full size, with a standard hard stop (e.g. 4.0% or placed under the pullback cycle low).

## 3. Data Flow and Architecture Changes

- **Trade Table (`data/market.db`):** No schema change required. The `trade_manager.update` logic already handles modifying `stop_price`.
- **`trade_manager.py`:** We will replace the single `TRADE_TRAIL_TRIGGER_PCT` logic with the new 3-tier trigger logic. The `status` command will instruct the trader to move the stop to specific new threshold prices.
- **`src/scanner/reentry.py` (NEW):** We will create a new scanner. It will read the `trades` table, find `CLOSED_WIN` or `CLOSED_BE` setups originally tagged `EP`, check if they closed within the last 30 days, and query their OHLCV data to detect moving average bounces.
- **`scripts/daily_briefing.py`:** Add a block to fetch symbols from the new `reentry.py` scanner and print them below the standard scanner output.

## 4. Testing Plan

1. **Trade Manager Tests:** Create unit tests in `pytest` supplying synthetic trade histories that hit +3%, +8%, and +11% to verify the trailing stop is correctly bumped to BE, +3%, and +7.5% respectively.
2. **Re-Entry Scanner Tests:** Provide mocked DataFrame OHLCV demonstrating a stock hitting a 20-day high, falling back to touch a 10-day SMA, then breaking the prior day's high. Verify the scanner catches this.
3. **Daily Briefing Integration:** Verify the mock runner appears in the briefing CLI output.

## 5. User Review Required
Please review formatting, threshold percentages, and the definition of the "Re-Entry Trigger". Let me know if any logic needs adjustment before implementation!
