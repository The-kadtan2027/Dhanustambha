"""Central configuration for the Dhanustambha Phase 1 MVP."""

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market.db")
WATCHLIST_DIR = os.path.join(BASE_DIR, "data", "watchlists")
LOG_DIR = os.path.join(BASE_DIR, "logs")

UNIVERSE = "NIFTY500"
MAX_WATCHLIST_SIZE = 10
BRIEFING_HISTORY_DAYS = 60

# ---------------------------------------------------------------------------
# Market Monitor thresholds
# ---------------------------------------------------------------------------
# SOURCE: Pradeep Bonde (Stockbee) — calibrated on the US S&P 500 universe.
# NSE STATUS: ⚠️  NOT YET VALIDATED FOR NSE (see ADR-007 in DECISIONS.md).
# These are used as starting-point defaults.  After ~60 trading days of live
# NSE breadth data have accumulated, compare the OFFENSIVE/DEFENSIVE verdicts
# against the NIFTY 500 returns in the following week and retune.
# DO NOT change these numbers without that evidence base.
# ---------------------------------------------------------------------------
MM_OFFENSIVE_MA20_PCT = 55.0      # % of universe above 20-day SMA → OFFENSIVE
MM_OFFENSIVE_UPVOL_RATIO = 0.60   # Up-volume / total-volume ratio → OFFENSIVE
MM_OFFENSIVE_HIGHS_VS_LOWS = 2.0  # new_highs >= new_lows * this → OFFENSIVE
MM_DEFENSIVE_MA20_PCT = 45.0      # % above MA20 floor for DEFENSIVE (vs AVOID)

# ---------------------------------------------------------------------------
# Momentum Burst scanner thresholds
# ---------------------------------------------------------------------------
MB_MIN_PCT_CHANGE = 5.0      # Minimum % gain over lookback window
MB_MAX_PCT_CHANGE = 25.0     # Cap — above this is likely a circuit-limit event
MB_MIN_VOLUME_RATIO = 1.5    # Today's volume / 20d avg volume
MB_LOOKBACK_DAYS = 3         # Look back N days for the % change calculation
MB_MIN_PRICE = 50.0          # Minimum price ₹ to exclude penny stocks
MB_MIN_AVG_VOLUME = 200_000  # Minimum 20d average daily volume (liquidity filter)
MB_MAX_PRIOR_RUN = 15.0      # Skip stocks already up >this% in the prior 10 days

# ---------------------------------------------------------------------------
# Episodic Pivot scanner thresholds
# ---------------------------------------------------------------------------
EP_MIN_GAP_PCT = 4.0           # Minimum gap-up % from previous close at open
EP_MIN_GAP_VOLUME_RATIO = 3.0  # Gap-day volume / 20d avg volume
EP_MAX_DAYS_SINCE_GAP = 5      # Only flag if gap happened within N trading days

# ---------------------------------------------------------------------------
# Trend Intensity scanner thresholds
# ---------------------------------------------------------------------------
TI_HIGH_LOOKBACK_DAYS = 50    # N-day high used as breakout reference (≈10 weeks)
TI_MA50_TREND_LOOKBACK = 20   # MA50 must be rising vs N days ago
TI_MIN_DAYS_ABOVE_MA50 = 30   # Stock must be above MA50 for >= N of last 50 days
TI_MIN_VOLUME_RATIO = 1.3     # Breakout-day volume / 20d avg volume
TI_MAX_ATR_PCT = 0.03         # ATR(14)/close < this → "quiet" low-volatility trend

TRADE_RISK_PCT = 0.01
TRADE_MAX_POSITION_PCT = 0.10
TRADE_MAX_OPEN = 5
TRADE_DEFENSIVE_SIZE_FACTOR = 0.5

DATA_FETCH_RETRY_ATTEMPTS = 3
DATA_FETCH_TIMEOUT_SECONDS = 30
