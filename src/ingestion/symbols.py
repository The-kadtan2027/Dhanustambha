"""Symbol universe definitions for Phase 1 development and scanning.

Sources and caveats:
- NIFTY 50 composition as of April 2026 (NSE official).
- NSE uses 'M&M' (with ampersand) for Mahindra & Mahindra.  Both nselib and
  yfinance (.NS suffix) accept this ticker correctly.
- NIFTY500 is a placeholder — it mirrors NIFTY50 for Phase 1. Expand to the
  full 500-symbol universe once the pipeline is validated end-to-end.
"""

import logging
from typing import List


logger = logging.getLogger(__name__)


NIFTY50 = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
    "HINDUNILVR",
    "ITC",
    "SBIN",
    "BHARTIARTL",
    "KOTAKBANK",
    "LT",
    "AXISBANK",
    "ASIANPAINT",
    "MARUTI",
    "SUNPHARMA",
    "TITAN",
    "BAJFINANCE",
    "NTPC",
    "POWERGRID",
    "ULTRACEMCO",    # UltraTech Cement — corrected from erroneous 'ULTRACEMIN'
    "NESTLEIND",
    "WIPRO",
    "HCLTECH",
    "TECHM",
    "ONGC",
    "JSWSTEEL",
    "TATAMOTORS",
    "TATASTEEL",
    "ADANIPORTS",
    "GRASIM",
    "CIPLA",
    "DIVISLAB",
    "DRREDDY",
    "EICHERMOT",
    "BAJAJFINSV",
    "BAJAJ-AUTO",
    "BPCL",
    "BRITANNIA",
    "COALINDIA",
    "HEROMOTOCO",
    "HINDALCO",
    "INDUSINDBK",
    "M&M",           # Mahindra & Mahindra — corrected from erroneous 'MM'
    "SBILIFE",
    "SHRIRAMFIN",
    "TATACONSUM",
    "UPL",
    "VEDL",
    "ADANIENT",
    "APOLLOHOSP",
]

NIFTY50_TEST = NIFTY50[:10]

# Phase 1 placeholder. The full NIFTY 500 universe can replace this later.
NIFTY500 = NIFTY50


def get_universe_symbols(universe: str = "NIFTY500") -> List[str]:
    """Return the symbol list for the requested configured universe."""
    universes = {
        "NIFTY50": NIFTY50,
        "NIFTY50_TEST": NIFTY50_TEST,
        "NIFTY500": NIFTY500,
    }
    if universe not in universes:
        logger.warning("Unknown universe '%s', defaulting to NIFTY50", universe)
        return NIFTY50
    return universes[universe]
