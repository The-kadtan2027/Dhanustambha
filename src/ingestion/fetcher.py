"""EOD market data fetching helpers for NSE symbols.

Fetch strategy (fastest to slowest):
  1. nselib bhavcopy  — official NSE CSV, covers all equities in one download, fast.
  2. yfinance batch   — yf.download() for all symbols at once; use for backfill or when
                        nselib is unavailable.  ~3-5 min for 750 symbols vs 20+ min serial.
  3. yfinance serial  — one Ticker per symbol; fallback of last resort for small symbol lists.
"""

import logging
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

import pandas as pd
from nselib import capital_market
import yfinance as yf

import config


logger = logging.getLogger(__name__)


def get_business_day_range(start_date: str, end_date: str) -> List[str]:
    """Return ISO-formatted business days between two inclusive dates."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if start > end:
        return []
    return [timestamp.date().isoformat() for timestamp in pd.bdate_range(start=start, end=end)]


def parse_bhavcopy_rows(rows: List[Dict], date: str) -> List[Dict]:
    """Convert parsed Bhavcopy rows into normalized OHLCV dictionaries."""
    result = []
    for row in rows:
        if row.get("SERIES", "").strip() != "EQ":
            continue
        try:
            result.append(
                {
                    "symbol": row["SYMBOL"].strip(),
                    "date": date,
                    "open": float(row["OPEN"]),
                    "high": float(row["HIGH"]),
                    "low": float(row["LOW"]),
                    "close": float(row["CLOSE"]),
                    "volume": int(float(row["TOTTRDQTY"])),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Skipping malformed row for %s: %s", row.get("SYMBOL", "?"), exc
            )
    return result


def normalize_nselib_bhavcopy(df: pd.DataFrame, fetch_date: str) -> List[Dict]:
    """Normalize an nselib bhavcopy DataFrame into OHLCV dictionaries."""
    result = []
    for _, row in df.iterrows():
        if str(row.get("SctySrs", "")).strip() != "EQ":
            continue
        try:
            result.append(
                {
                    "symbol": str(row["TckrSymb"]).strip(),
                    "date": fetch_date,
                    "open": float(row["OpnPric"]),
                    "high": float(row["HghPric"]),
                    "low": float(row["LwPric"]),
                    "close": float(row["ClsPric"]),
                    "volume": int(float(row["TtlTradgVol"])),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Skipping malformed nselib row for %s: %s",
                row.get("TckrSymb", "?"),
                exc,
            )
    return result


def fetch_via_nselib(symbols: List[str], fetch_date: str) -> List[Dict]:
    """Fetch EOD OHLCV rows from the NSE bhavcopy via nselib."""
    display_date = datetime.strptime(fetch_date, "%Y-%m-%d").strftime("%d-%m-%Y")
    try:
        bhavcopy = capital_market.bhav_copy_equities(display_date)
    except Exception as exc:  # noqa: BLE001 - upstream library can raise several types
        logger.error("nselib bhavcopy fetch failed for %s: %s", fetch_date, exc)
        return []

    if bhavcopy.empty:
        logger.warning("nselib: empty bhavcopy for %s", fetch_date)
        return []

    normalized = normalize_nselib_bhavcopy(bhavcopy, fetch_date)
    if not symbols:
        return normalized

    symbol_set = set(symbols)
    filtered = [row for row in normalized if row["symbol"] in symbol_set]
    missing = sorted(symbol_set - {row["symbol"] for row in filtered})
    if missing:
        logger.warning("nselib: %d requested symbols missing from bhavcopy", len(missing))
    return filtered


def fetch_via_yfinance_batch(
    symbols: List[str],
    fetch_date: str,
    lookback_days: int = 7,
) -> List[Dict]:
    """Fetch EOD OHLCV for many symbols in a single yf.download() call (fast batch mode).

    Recommended for universes > 50 symbols.  Much faster than serial Ticker calls.
    fetch_date is the target date; lookback_days controls the download window.
    """
    if not symbols:
        return []

    target = datetime.strptime(fetch_date, "%Y-%m-%d").date()
    start = (target - timedelta(days=lookback_days)).isoformat()
    end = (target + timedelta(days=1)).isoformat()

    tickers = [f"{s}.NS" for s in symbols]
    logger.info("yfinance batch download: %d symbols, window %s → %s", len(tickers), start, end)

    try:
        raw = yf.download(
            tickers=tickers,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("yfinance batch download failed: %s", exc)
        return []

    if raw.empty:
        logger.warning("yfinance batch: empty result for %s", fetch_date)
        return []

    results: List[Dict] = []
    failed: List[str] = []

    # yf.download with multiple tickers returns a MultiIndex column: (field, ticker)
    for symbol, ticker in zip(symbols, tickers):
        try:
            # Slice columns for this ticker
            if isinstance(raw.columns, pd.MultiIndex):
                sym_df = raw.xs(ticker, axis=1, level=1)
            else:
                sym_df = raw  # single-ticker fallback (shouldn't happen in batch)

            sym_df = sym_df.copy()
            sym_df.index = pd.to_datetime(sym_df.index).date
            if target not in sym_df.index:
                logger.debug("yfinance batch: %s missing for %s", symbol, fetch_date)
                failed.append(symbol)
                continue

            row = sym_df.loc[target]
            # Skip rows with NaN prices (delisted / no-data symbols)
            if pd.isna(row.get("Close", float("nan"))):
                failed.append(symbol)
                continue

            results.append({
                "symbol": symbol,
                "date": fetch_date,
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("yfinance batch: error parsing %s: %s", symbol, exc)
            failed.append(symbol)

    if failed:
        logger.warning("yfinance batch: %d symbols missing/failed: %s", len(failed), failed[:10])
    logger.info("yfinance batch: %d/%d rows collected for %s", len(results), len(symbols), fetch_date)
    return results


def fetch_via_yfinance(symbols: List[str], fetch_date: str) -> List[Dict]:
    """Fetch EOD OHLCV data for symbols via yfinance (serial, one Ticker per symbol).

    Use fetch_via_yfinance_batch() for large universes — it is significantly faster.
    This serial fallback is retained for small symbol lists and targeted retries.
    """
    results: List[Dict] = []
    failed: List[str] = []
    target = datetime.strptime(fetch_date, "%Y-%m-%d").date()
    start_date = target - timedelta(days=7)
    end_date = target + timedelta(days=1)

    for symbol in symbols:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            history = ticker.history(
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                auto_adjust=False,
            )
            if history.empty:
                logger.warning("yfinance: no data for %s", symbol)
                failed.append(symbol)
                continue

            history.index = pd.to_datetime(history.index).date
            if target not in history.index:
                logger.warning("yfinance: date %s not found for %s", fetch_date, symbol)
                failed.append(symbol)
                continue

            row = history.loc[target]
            results.append(
                {
                    "symbol": symbol,
                    "date": fetch_date,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
            )
            time.sleep(0.1)
        except Exception as exc:  # noqa: BLE001 - external API client can raise many types
            logger.error("yfinance fetch failed for %s: %s", symbol, exc)
            failed.append(symbol)

    if failed:
        logger.warning("yfinance: %d symbols failed: %s", len(failed), failed[:10])
    return results


def fetch_eod_data_for_dates(
    symbols: List[str], fetch_dates: Sequence[str], pause_seconds: float = 0.0
) -> List[Dict]:
    """Fetch and combine EOD rows for an explicit sequence of trading dates."""
    combined_rows: List[Dict] = []
    for fetch_date in fetch_dates:
        day_rows = fetch_eod_data(symbols, fetch_date)
        if day_rows:
            combined_rows.extend(day_rows)
        else:
            logger.info("No EOD rows fetched for %s; skipping it in the backfill", fetch_date)

        if pause_seconds > 0:
            time.sleep(pause_seconds)

    return combined_rows


def fetch_eod_data_range(
    symbols: List[str],
    start_date: str,
    end_date: str,
    pause_seconds: float = 0.0,
) -> List[Dict]:
    """Fetch and combine EOD rows for all business days in an inclusive date range."""
    business_dates = get_business_day_range(start_date, end_date)
    return fetch_eod_data_for_dates(symbols, business_dates, pause_seconds=pause_seconds)


def fetch_eod_data(symbols: List[str], fetch_date: Optional[str] = None) -> List[Dict]:
    """Fetch EOD data for symbols on the requested date and report failure rates."""
    if fetch_date is None:
        fetch_date = date.today().isoformat()

    logger.info("Fetching EOD data for %d symbols on %s", len(symbols), fetch_date)
    results = fetch_via_nselib(symbols, fetch_date)
    if not results:
        logger.info("No official NSE data returned for %s; treating it as a holiday or unavailable session", fetch_date)
        return []

    failure_rate = 1 - (len(results) / len(symbols)) if symbols else 0
    if failure_rate > 0.10:
        logger.error(
            "High failure rate: %.0f%% of symbols failed (%d/%d)",
            failure_rate * 100,
            len(symbols) - len(results),
            len(symbols),
        )
    else:
        logger.info("Fetch complete: %d/%d symbols succeeded", len(results), len(symbols))

    return results
