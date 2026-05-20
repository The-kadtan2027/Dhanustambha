"""Central configuration for the Dhanustambha trading platform."""

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market.db")
WATCHLIST_DIR = os.path.join(BASE_DIR, "data", "watchlists")
UNIVERSE_CACHE_DIR = os.path.join(BASE_DIR, "data", "universe_cache")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Universe: 'NIFTY50' (fast/dev), 'NIFTY500' (~500 symbols), 'NIFTY750' (NIFTY500+Smallcap250)
UNIVERSE = "NIFTY500"
MAX_WATCHLIST_SIZE = 20
BRIEFING_HISTORY_DAYS = 60
# How many days before re-downloading NSE constituent CSVs from NSE archives
UNIVERSE_REFRESH_DAYS = 7

# ---------------------------------------------------------------------------
# Market Monitor thresholds
# ---------------------------------------------------------------------------
# SOURCE: Pradeep Bonde (Stockbee) — calibrated on the US S&P 500 universe.
# NSE STATUS: ✅ VALIDATED FOR NSE (via 3-year NIFTY500 median return backtest).
# Empirical calibration shows >55% MA20 yields 70%+ WinRates over 20-day horizons.
# 45% floor correctly segregates underperforming regimes.
MM_OFFENSIVE_MA20_PCT = 55.0      # % of universe above 20-day SMA → OFFENSIVE
MM_OFFENSIVE_UPVOL_RATIO = 0.60   # Up-volume / total-volume ratio → OFFENSIVE
MM_OFFENSIVE_HIGHS_VS_LOWS = 2.0  # new_highs >= new_lows * this → OFFENSIVE
MM_DEFENSIVE_MA20_PCT = 35.0      # % above MA20 floor for DEFENSIVE (vs AVOID)

# ---------------------------------------------------------------------------
# Momentum Burst scanner thresholds
# ---------------------------------------------------------------------------
MB_MIN_PCT_CHANGE = 5.0      # Minimum % gain over lookback window
MB_MAX_PCT_CHANGE = 20.0     # Cap — above this is likely a circuit-limit event
MB_MIN_VOLUME_RATIO = 1.5    # Today's volume / 20d avg volume
MB_LOOKBACK_DAYS = 3         # Look back N days for the % change calculation
MB_MIN_PRICE = 50.0          # Minimum price ₹ to exclude penny stocks
MB_MIN_AVG_VOLUME = 200_000  # Minimum 20d average daily volume (liquidity filter)
MB_MAX_PRIOR_RUN = -2.3      # Skip stocks already up >this% in the prior 10 days (G2 validation limit)

# MB Quality filters — additive labels, not detection gates
# Calibration: combo G = 59.7% wr, 1.69 MFE/MAE, 1.6% fail-by-3d (vs 50.6% baseline)
MB_QUALITY_MIN_NR_COUNT = 6          # Narrow-range days in prior 10 (tight base)
MB_QUALITY_MIN_CLOSE_LOC_PCT = 70.0  # Close in top 30% of day's range (strong close)
MB_QUALITY_MIN_DIST_20D_HIGH = 0.0   # Must be at or above 20-day high (breakout)

# ---------------------------------------------------------------------------
# Episodic Pivot scanner thresholds
# ---------------------------------------------------------------------------
# Tier B — standard live detection (current params)
EP_MIN_GAP_PCT = 5.0           # Loosened live observation candidate after sparse recent sessions
EP_MIN_GAP_VOLUME_RATIO = 3.0  # Shortlisted live candidate from 2025 H1 NSE calibration
EP_MAX_DAYS_SINCE_GAP = 2      # Shortlisted live candidate from 2025 H1 NSE calibration
EP_MAX_GAP_VOLUME_RATIO = 0.0  # Disabled by default; set to 4.9 to enable research quality filter

# Tier A+ — high-conviction subset (calibration: 61% wr, 1.50 MFE/MAE, 95 signals/2yr)
EP_TIER_A_MIN_GAP_PCT = 8.0
EP_TIER_A_MIN_GAP_VOLUME_RATIO = 4.0
EP_TIER_A_MAX_DAYS_SINCE_GAP = 1

# ---------------------------------------------------------------------------
# Trend Intensity scanner thresholds
# ---------------------------------------------------------------------------
TI_HIGH_LOOKBACK_DAYS = 50    # N-day high used as breakout reference (≈10 weeks)
TI_MA50_TREND_LOOKBACK = 20   # MA50 must be rising vs N days ago
TI_MIN_DAYS_ABOVE_MA50 = 40   # Stock must be above MA50 for >= N of last 50 days
TI_MIN_VOLUME_RATIO = 1.3     # Breakout-day volume / 20d avg volume
TI_MAX_ATR_PCT = 0.05         # ATR(14)/close < this → "quiet" low-volatility trend
TI_MAX_PULLBACK_DEPTH_PCT = 16.0 # Max pullback depth within recent 20 days

# ---------------------------------------------------------------------------
# Trade management (Phase 2)
# ---------------------------------------------------------------------------
# Set ACCOUNT_SIZE to your actual trading capital in INR before using the sizer.
ACCOUNT_SIZE = 100_000          # ₹5 lakh default — override per your actual capital
TRADE_RISK_PCT = 0.025          # Risk 2.5% of account per trade as per user preference constraint
# Validated fixed % stop losses per setup type (from MAE optimization)
TRADE_EP_STOP_PCT = 4.0         # 4.0% for Episodic Pivot (winners routinely dip 3-4%)
TRADE_MB_STOP_PCT = 2.5         # 2.5% for Momentum Burst
TRADE_TI_STOP_PCT = 1.5         # 1.5% for Trend Intensity

TRADE_MAX_POSITION_PCT = 0.25   # No single position > 10% of account
TRADE_MAX_OPEN = 5              # Max 5 concurrent open trades
TRADE_DEFENSIVE_SIZE_FACTOR = 0.5  # Halve position size in DEFENSIVE market conditions
TRADE_DEFAULT_STATUS_OPEN = "OPEN"
TRADE_STATUS_CLOSED_WIN = "CLOSED_WIN"
TRADE_STATUS_CLOSED_LOSS = "CLOSED_LOSS"
TRADE_STATUS_CLOSED_BE = "CLOSED_BE"
TRADE_TRAIL_TIER_1_TRIGGER_PCT = 3.0
TRADE_TRAIL_TIER_1_STOP_PCT = 0.0

TRADE_TRAIL_TIER_2_TRIGGER_PCT = 7.5
TRADE_TRAIL_TIER_2_STOP_PCT = 3.0

TRADE_TRAIL_TIER_3_TRIGGER_PCT = 10.0
TRADE_TRAIL_TIER_3_STOP_PCT = 7.5

TRADE_TIME_EXIT_DAYS = 20

BACKTEST_FORWARD_DAYS = (3, 5, 10, 20)
BACKTEST_OUTPUT_DIR = os.path.join(BASE_DIR, "data", "calibration")
BACKTEST_YEARS = 3
BACKTEST_SIGNAL_HORIZONS = (1, 3, 5, 10, 20)
BACKTEST_EXCURSION_HORIZONS = (3, 5, 10)
BACKTEST_BENCHMARK_CANDIDATES = ("^NSEI", "NIFTY50", "NIFTY", "NIFTYBEES")
BACKTEST_BENCHMARK_SYMBOL = "^NSEI"
BACKTEST_BENCHMARK_SOURCE_TICKERS = ("^NSEI", "NIFTYBEES.NS", "SETFNIF50.NS")

DATA_FETCH_RETRY_ATTEMPTS = 3
DATA_FETCH_TIMEOUT_SECONDS = 30
DATA_PULL_TIME = "16:30"
DATA_PULL_GRACE_MINUTES = 30

# ---------------------------------------------------------------------------
# Live Price Feed (Stream H)
# ---------------------------------------------------------------------------
LIVE_PRICE_REFRESH_SECONDS = 60  # Default 1 minute for dashboard polling
LIVE_PRICE_CACHE_TTL = 300      # 5 minute hard expiration for backend safety

