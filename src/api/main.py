"""FastAPI endpoints for the Dhanustambha dashboard and manual trade workflow."""

from __future__ import annotations
from datetime import datetime
from contextlib import asynccontextmanager
import math
import sys
from typing import Any, AsyncIterator, Dict, List, Optional
import subprocess

import threading
import uuid
import logging
from pydantic import BaseModel
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
from src.ingestion.store import (
    get_breadth,
    get_breadth_dates,
    get_breadth_history,
    get_ohlcv,
    get_watchlist,
    init_db,
)
from src.trade.log import (
    build_open_trade_status,
    build_portfolio_summary,
    close_trade,
    open_trade,
    summarize_closed_trades,
    update_stop_price,
)
from src.trade.sizer import calculate_position_size
import time

logger = logging.getLogger(__name__)

# Stream I: Live Scan Job Store
# job_id -> {status: "running"|"completed"|"failed", progress: int, candidates: int, error: str, start_time: str}
LIVE_SCAN_JOBS: Dict[str, Dict[str, Any]] = {}

class LiveScanStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    candidates: int
    error: Optional[str] = None
    start_time: str
    finish_time: Optional[str] = None


class LivePriceCache:
    """In-memory cache for live prices to avoid redundant external calls.

    Refreshes data only if the last fetch was more than config.LIVE_PRICE_REFRESH_SECONDS ago.
    """
    def __init__(self):
        self.data: Dict[str, Dict[str, Any]] = {}
        self.last_fetch_time: float = 0

    def get_prices(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        now = time.time()
        # If cache is young, return from cache for available symbols
        if now - self.last_fetch_time < config.LIVE_PRICE_REFRESH_SECONDS:
            if all(s in self.data for s in symbols):
                return {s: {**self.data[s], "is_cached": True} for s in symbols}

        # Fetch fresh for requested symbols
        from src.ingestion.fetcher import fetch_live_prices
        fresh = fetch_live_prices(symbols)
        self.data.update(fresh)
        self.last_fetch_time = now
        # Mark fresh results as not cached
        return {s: {**self.data[s], "is_cached": False} for s in symbols if s in self.data}

_price_cache = LivePriceCache()
import asyncio

async def _scheduled_scan_loop():
    """Background task to run live scans periodically during market hours."""
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    last_run_time = None

    while True:
        try:
            if getattr(config, "LIVE_SCAN_SCHEDULE_ENABLED", False):
                now = datetime.now(IST)
                
                # Only run on market days (Monday - Friday)
                if now.weekday() < 5:
                    start_hour, start_minute = [int(p) for p in getattr(config, "LIVE_SCAN_START_TIME", "14:00").split(":")]
                    end_hour, end_minute = [int(p) for p in getattr(config, "LIVE_SCAN_END_TIME", "15:30").split(":")]
                    interval = getattr(config, "LIVE_SCAN_INTERVAL_MINUTES", 30)

                    start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                    end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

                    if start_time <= now <= end_time:
                        # Ensures scans happen at intervals (e.g. xx:00 and xx:30)
                        if now.minute % interval == 0:
                            # Prevent multiple triggers within the same minute
                            if last_run_time is None or (now - last_run_time).total_seconds() > 60:
                                logger.info("Triggering scheduled live scan at %s", now.strftime("%H:%M:%S"))
                                # Call the existing background worker trigger
                                start_live_scan()
                                last_run_time = now
        except Exception:
            logger.exception("Scheduled scan loop encountered an error")
        
        await asyncio.sleep(10)  # Check every 10 seconds

@asynccontextmanager
async def lifespan(api_app: FastAPI) -> AsyncIterator[None]:
    """Ensure the SQLite schema exists before serving requests and start background tasks."""
    init_db()
    
    scan_task = None
    if getattr(config, "LIVE_SCAN_SCHEDULE_ENABLED", False):
        scan_task = asyncio.create_task(_scheduled_scan_loop())
        
    yield

    if scan_task:
        scan_task.cancel()


app = FastAPI(
    title="Dhanustambha Dashboard API",
    version="0.1.0",
    description="API for market monitor, watchlists, trade status, and manual trade workflow.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

class TradeOpenRequest(BaseModel):
    symbol: str
    setup_type: str
    entry_date: str
    entry_price: float
    stop_price: float
    shares: Optional[int] = None
    account_size: Optional[float] = None
    notes: Optional[str] = None
    grade: Optional[str] = None

class TradeQuoteRequest(BaseModel):
    symbol: str
    setup_type: str
    entry_date: str
    entry_price: float
    stop_price: float
    account_size: float

class TradeUpdateStopRequest(BaseModel):
    stop_price: float

class TradeCloseRequest(BaseModel):
    exit_date: str
    exit_price: float



def _clean_value(value: Any) -> Any:
    """Convert pandas/numpy values into JSON-safe Python primitives."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _records_from_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records."""
    if df.empty:
        return []
    cleaned = df.astype(object).where(pd.notna(df), None)
    return [
        {key: _clean_value(value) for key, value in row.items()}
        for row in cleaned.to_dict(orient="records")
    ]


def _float_or_none(value: Any) -> Optional[float]:
    """Return a finite float for numeric values, otherwise None."""
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _build_live_ohlcv_row(
    symbol: str,
    row_date: str,
    live_data: Dict[str, Any],
    existing_today: Optional[Dict[str, Any]] = None,
    previous_row: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Build a same-day OHLCV row without collapsing an existing candle range."""
    price = _float_or_none(live_data.get("price"))
    if price is None:
        return None

    existing_today = existing_today or {}
    previous_row = previous_row or {}
    prior_close = _float_or_none(previous_row.get("close"))
    open_price = _float_or_none(live_data.get("open"))
    high_price = _float_or_none(live_data.get("high"))
    low_price = _float_or_none(live_data.get("low"))

    if open_price is None:
        open_price = _float_or_none(existing_today.get("open")) or prior_close or price
    if high_price is None:
        high_price = _float_or_none(existing_today.get("high")) or open_price
    if low_price is None:
        low_price = _float_or_none(existing_today.get("low")) or open_price

    # Live LTP snapshots may not include the full day range. Preserve any stored
    # same-day range and expand it only when the latest price breaks that range.
    high_price = max(high_price, open_price, price)
    low_price = min(low_price, open_price, price)

    live_volume = live_data.get("volume")
    existing_volume = existing_today.get("volume")
    volume = live_volume if live_volume is not None else existing_volume

    return {
        "symbol": symbol,
        "date": row_date,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": price,
        "volume": int(volume or 0),
    }


def _build_trade_quote(req: TradeQuoteRequest) -> Dict[str, Any]:
    """Calculate a server-side trade quote or raise a validation error."""
    if req.account_size <= 0:
        raise HTTPException(status_code=422, detail="Account size must be positive.")

    if req.entry_price <= 0:
        raise HTTPException(status_code=422, detail="Entry price must be positive.")

    if req.stop_price <= 0:
        raise HTTPException(status_code=422, detail="Stop price must be positive.")

    if req.stop_price >= req.entry_price:
        raise HTTPException(
            status_code=422,
            detail="Stop price must be below entry price.",
        )

    market_verdict = "OFFENSIVE"
    try:
        market_verdict = str(_require_breadth(req.entry_date).get("verdict", "OFFENSIVE"))
    except HTTPException:
        market_verdict = "OFFENSIVE"

    sizing = calculate_position_size(
        account_size=req.account_size,
        entry_price=req.entry_price,
        stop_price=req.stop_price,
        market_verdict=market_verdict,
    )
    if sizing is None:
        raise HTTPException(
            status_code=422,
            detail="Position size is invalid for the account, entry, and stop.",
        )

    risk_pct = config.TRADE_RISK_PCT * 100
    max_position_value = req.account_size * config.TRADE_MAX_POSITION_PCT
    return {
        "valid": True,
        "symbol": req.symbol.strip().upper(),
        "setup_type": req.setup_type.strip().upper(),
        "entry_date": req.entry_date,
        "entry_price": req.entry_price,
        "stop_price": req.stop_price,
        "account_size": req.account_size,
        "market_verdict": market_verdict.upper(),
        "risk_pct": round(risk_pct, 2),
        "max_position_value": round(max_position_value, 2),
        "shares": int(sizing["shares"]),
        "position_value": sizing["position_value"],
        "risk_amount": sizing["risk_amount"],
        "r_unit": sizing["r_unit"],
    }


def _require_breadth(date: Optional[str] = None) -> Dict[str, Any]:
    """Return a breadth row or raise a 404 when none is available."""
    breadth = get_breadth(date)
    if not breadth:
        target = date or "latest"
        raise HTTPException(status_code=404, detail=f"No breadth data found for {target}.")
    return {key: _clean_value(value) for key, value in breadth.items()}


def _watchlist_payload(date: Optional[str] = None) -> Dict[str, Any]:
    """Return watchlist payload for one date or the latest saved watchlist."""
    watchlist = get_watchlist(date)
    if watchlist.empty:
        target = date or "latest"
        raise HTTPException(status_code=404, detail=f"No watchlist found for {target}.")

    resolved_date = str(watchlist.iloc[0]["date"])
    return {
        "date": resolved_date,
        "count": int(len(watchlist)),
        "items": _records_from_dataframe(watchlist),
    }


def _optional_watchlist_payload(date: str) -> Dict[str, Any]:
    """Return watchlist rows for a date, allowing no-candidate market days."""
    watchlist = get_watchlist(date)
    return {
        "date": date,
        "count": int(len(watchlist)),
        "items": _records_from_dataframe(watchlist),
    }


@app.get("/health")
def health() -> Dict[str, str]:
    """Return a basic service health response."""
    return {"status": "ok"}


@app.get("/market/breadth/latest")
def latest_breadth() -> Dict[str, Any]:
    """Return the latest stored Market Monitor breadth reading."""
    return _require_breadth()


@app.get("/market/breadth/history")
def breadth_history(days: int = 60) -> Dict[str, Any]:
    """Return the last N days of stored breadth readings, oldest first."""
    rows = get_breadth_history(days=days)
    return {"count": len(rows), "items": rows}


@app.get("/market/breadth/{date}")
def breadth_by_date(date: str) -> Dict[str, Any]:
    """Return the stored Market Monitor breadth reading for a date."""
    return _require_breadth(date)


@app.get("/watchlist/latest")
def latest_watchlist() -> Dict[str, Any]:
    """Return the latest saved watchlist."""
    return _watchlist_payload()


@app.get("/watchlist/{date}")
def watchlist_by_date(date: str) -> Dict[str, Any]:
    """Return the saved watchlist for a date."""
    return _watchlist_payload(date)


@app.get("/market/prices")
def market_prices(symbols: str) -> Dict[str, Any]:
    """Return 'live' prices for a comma-separated list of symbols.

    Tiered fallback: yfinance -> Scraper -> DB close.
    """
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        return {"items": {}}
    
    prices = _price_cache.get_prices(sym_list)
    return {
        "items": prices,
        "timestamp": datetime.now().isoformat(),
        "refresh_interval": config.LIVE_PRICE_REFRESH_SECONDS
    }


@app.get("/briefing/latest")
def latest_briefing() -> Dict[str, Any]:
    """Return the latest stored briefing summary."""
    breadth = _require_breadth()
    return briefing_by_date(str(breadth["date"]))


@app.get("/briefing/dates")
def briefing_dates() -> Dict[str, Any]:
    """Return stored briefing dates newest first."""
    dates = get_breadth_dates()
    return {
        "count": len(dates),
        "items": dates,
    }


@app.get("/briefing/{date}")
def briefing_by_date(date: str) -> Dict[str, Any]:
    """Return stored breadth and watchlist data for one briefing date."""
    breadth = _require_breadth(date)
    watchlist = _optional_watchlist_payload(date)
    return {
        "date": date,
        "market": breadth,
        "watchlist": watchlist["items"],
        "watchlist_count": watchlist["count"],
    }


@app.post("/trades/quote")
def api_trade_quote(req: TradeQuoteRequest) -> Dict[str, Any]:
    """Return server-side position sizing for a proposed manual trade."""
    return _build_trade_quote(req)


@app.post("/trades/open")
def api_open_trade(req: TradeOpenRequest) -> Dict[str, Any]:
    try:
        if req.account_size is not None:
            quote = _build_trade_quote(
                TradeQuoteRequest(
                    symbol=req.symbol,
                    setup_type=req.setup_type,
                    entry_date=req.entry_date,
                    entry_price=req.entry_price,
                    stop_price=req.stop_price,
                    account_size=req.account_size,
                )
            )
            shares = int(quote["shares"])
        elif req.shares is not None:
            shares = int(req.shares)
        else:
            raise HTTPException(
                status_code=422,
                detail="Either account_size or shares must be provided.",
            )

        trade_id = open_trade(
            symbol=req.symbol,
            setup_type=req.setup_type,
            entry_date=req.entry_date,
            entry_price=req.entry_price,
            stop_price=req.stop_price,
            shares=shares,
            notes=req.notes or "",
            grade=req.grade or ""
        )
        from src.ingestion.store import get_connection

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            cols = [description[0] for description in cursor.description]
            row = dict(zip(cols, cursor.fetchone()))
        finally:
            conn.close()
        return row
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/trades/{trade_id}/update-stop")
def api_update_stop(trade_id: int, req: TradeUpdateStopRequest) -> Dict[str, Any]:
    try:
        update_stop_price(trade_id, req.stop_price)
        return {"status": "success", "id": trade_id, "new_stop": req.stop_price}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/trades/{trade_id}/close")
def api_close_trade(trade_id: int, req: TradeCloseRequest) -> Dict[str, Any]:
    try:
        close_trade(trade_id, req.exit_date, req.exit_price)
        return {"status": "success", "id": trade_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/ohlcv/{symbol}")
def ohlcv_chart(symbol: str, days: int = 90) -> Dict[str, Any]:
    """Return OHLCV candles with rolling MA20/MA50 for the chart component."""
    df = get_ohlcv(symbol.upper(), days=days)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")

    df = df.sort_values("date").reset_index(drop=True)
    df["ma20"] = df["close"].rolling(20, min_periods=20).mean()
    df["ma50"] = df["close"].rolling(50, min_periods=50).mean()

    candles: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        date_val = row["date"]
        date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
        candles.append({
            "time": date_str,
            "open": _clean_value(row["open"]),
            "high": _clean_value(row["high"]),
            "low": _clean_value(row["low"]),
            "close": _clean_value(row["close"]),
            "volume": _clean_value(row["volume"]),
            "ma20": _clean_value(row["ma20"]),
            "ma50": _clean_value(row["ma50"]),
        })

    return {"symbol": symbol.upper(), "days": days, "candles": candles}


@app.get("/trades/open")
def open_trades(live: bool = True) -> Dict[str, Any]:
    """Return open trades with current P&L and action flags.

    If live=True, fetches current prices to show real-time P&L and persists them
    as today's OHLCV candle so the chart always has a live bar without a full scan.
    """
    current_prices = None
    if live:
        from src.ingestion.store import get_trades, upsert_ohlcv, get_all_symbols_ohlcv
        from datetime import date as _date

        active_symbols = get_trades(status=config.TRADE_DEFAULT_STATUS_OPEN)["symbol"].unique().tolist()
        if active_symbols:
            live_data = _price_cache.get_prices(active_symbols)
            current_prices = {s: d["price"] for s, d in live_data.items() if "price" in d}

            # --- Persist live prices as today's OHLCV candle ---
            # Uses the same _build_live_ohlcv_row logic as the full live-scan worker.
            # INSERT OR REPLACE is idempotent; EOD fetcher at 16:30 overwrites with actual close.
            today_str = _date.today().isoformat()
            try:
                existing_df = get_all_symbols_ohlcv(today_str, lookback_days=1)
                existing_today: Dict[str, Any] = {}
                previous_rows: Dict[str, Any] = {}
                if not existing_df.empty:
                    today_mask = existing_df["date"].dt.strftime("%Y-%m-%d") == today_str
                    existing_today = {
                        str(r["symbol"]): r.to_dict()
                        for _, r in existing_df.loc[today_mask].iterrows()
                    }
                    previous_rows = {
                        str(r["symbol"]): r.to_dict()
                        for _, r in existing_df.loc[~today_mask]
                        .sort_values(["symbol", "date"])
                        .groupby("symbol")
                        .tail(1)
                        .iterrows()
                    }
                rows = []
                for s, d in live_data.items():
                    row = _build_live_ohlcv_row(
                        s, today_str, d,
                        existing_today=existing_today.get(s),
                        previous_row=previous_rows.get(s),
                    )
                    if row:
                        rows.append(row)
                if rows:
                    upsert_ohlcv(rows)
            except Exception:
                logger.exception("Failed to persist live OHLCV for open positions — skipping")

    trades = build_open_trade_status(current_prices=current_prices)
    return {
        "count": int(len(trades)),
        "items": _records_from_dataframe(trades),
    }


@app.get("/trades/actions")
def trade_actions(live: bool = True) -> Dict[str, Any]:
    """Return open trades that require management action."""
    current_prices = None
    if live:
        from src.ingestion.store import get_trades
        active_symbols = get_trades(status=config.TRADE_DEFAULT_STATUS_OPEN)["symbol"].unique().tolist()
        if active_symbols:
            live_data = _price_cache.get_prices(active_symbols)
            current_prices = {s: d["price"] for s, d in live_data.items() if "price" in d}

    trades = build_open_trade_status(current_prices=current_prices)
    if not trades.empty and "action_required" in trades.columns:
        trades = trades[trades["action_required"] != "NONE"]
    return {
        "count": int(len(trades)),
        "items": _records_from_dataframe(trades),
    }

@app.get("/trades/by-symbol/{symbol}")
def trades_by_symbol(symbol: str) -> Dict[str, Any]:
    """Return all trades (open and closed) for a given symbol."""
    from src.ingestion.store import get_trades
    all_trades = get_trades()
    if not all_trades.empty:
        filtered = all_trades[all_trades["symbol"] == symbol.upper()]
    else:
        filtered = all_trades
    return {
        "symbol": symbol.upper(),
        "count": int(len(filtered)),
        "trades": _records_from_dataframe(filtered),
    }


@app.get("/trades/portfolio")
def trade_portfolio(live: bool = True) -> Dict[str, Any]:
    """Return portfolio-level aggregates across all open trades."""
    current_prices = None
    if live:
        from src.ingestion.store import get_trades
        active_symbols = get_trades(status=config.TRADE_DEFAULT_STATUS_OPEN)["symbol"].unique().tolist()
        if active_symbols:
            live_data = _price_cache.get_prices(active_symbols)
            current_prices = {s: d["price"] for s, d in live_data.items() if "price" in d}

    return build_portfolio_summary(current_prices=current_prices)


@app.get("/trades/summary")
def trade_summary() -> Dict[str, Any]:
    """Return expectancy-style closed-trade summary metrics."""
    summary = summarize_closed_trades()
    return {key: _clean_value(value) for key, value in summary.items()}

class TradeReviewRequest(BaseModel):
    entry_rule_followed: bool
    exit_rule_followed: bool
    what_to_improve: str
    review_date: str

@app.get("/trades/closed")
def closed_trades() -> Dict[str, Any]:
    """Return closed trades with optional reviews."""
    from src.ingestion.store import get_closed_trades
    rows = get_closed_trades()
    return {"count": len(rows), "items": rows}

@app.post("/trades/{trade_id}/review")
def api_save_review(trade_id: int, req: TradeReviewRequest) -> Dict[str, Any]:
    """Save a qualitative review for a closed trade."""
    from src.ingestion.store import save_trade_review, get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE id = ?", (trade_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Trade not found.")
    finally:
        conn.close()
        
    save_trade_review(
        trade_id=trade_id,
        entry_rule_followed=int(req.entry_rule_followed),
        exit_rule_followed=int(req.exit_rule_followed),
        what_to_improve=req.what_to_improve,
        review_date=req.review_date
    )
    return {"status": "saved", "trade_id": trade_id}


@app.post("/briefing/run")
def api_run_briefing() -> Dict[str, Any]:
    """Manually trigger the daily briefing script."""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/daily_briefing.py"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Script failed: {result.stderr}")

        return {
            "status": "success",
            "output": result.stdout,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Script execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Stream I: Live Market Scanner Endpoints

def _run_live_scan_worker(job_id: str):
    """Background worker to run the full briefing pipeline with live data."""
    from src.ingestion.store import upsert_ohlcv, get_all_symbols_ohlcv, save_breadth, save_watchlist
    from src.ingestion.symbols import get_universe_symbols
    from src.ingestion.fetcher import fetch_live_ohlcv
    from src.monitor.breadth import compute_breadth
    from src.monitor.verdict import compute_verdict
    from src.scanner.momentum_burst import detect_momentum_burst
    from src.scanner.episodic_pivot import detect_episodic_pivot
    from src.scanner.trend_intensity import detect_trend_intensity
    from src.scanner.watchlist import merge_and_rank, export_watchlist
    from datetime import date
    
    job = LIVE_SCAN_JOBS[job_id]
    today = date.today().isoformat()
    
    try:
        # 1. Discover active symbols for the configured universe
        symbols = get_universe_symbols(config.UNIVERSE)
        if not symbols:
            job["status"] = "failed"
            job["error"] = f"No active symbols found for universe '{config.UNIVERSE}'."
            return

        # 2. Fetch Live OHLCV (with progress)
        def progress_cb(c, t):
            job["progress"] = int((c / t) * 80)  # Scan is 80% of total work
            
        ohlcv_map = fetch_live_ohlcv(symbols, progress_callback=progress_cb)
        
        # 3. Upsert into DB for today
        existing_today: Dict[str, Dict[str, Any]] = {}
        previous_rows: Dict[str, Dict[str, Any]] = {}
        existing_df = get_all_symbols_ohlcv(today, lookback_days=1)
        if not existing_df.empty:
            today_mask = existing_df["date"].dt.strftime("%Y-%m-%d") == today
            existing_today = {
                str(row["symbol"]): row.to_dict()
                for _, row in existing_df.loc[today_mask].iterrows()
            }
            previous_rows = {
                str(row["symbol"]): row.to_dict()
                for _, row in existing_df.loc[~today_mask]
                .sort_values(["symbol", "date"])
                .groupby("symbol")
                .tail(1)
                .iterrows()
            }

        rows = []
        for s, d in ohlcv_map.items():
            row = _build_live_ohlcv_row(
                s,
                today,
                d,
                existing_today=existing_today.get(s),
                previous_row=previous_rows.get(s),
            )
            if row is not None:
                rows.append(row)
        
        if rows:
            upsert_ohlcv(rows)
        
        # 4. Compute Breadth
        job["status"] = "processing_breadth"
        job["progress"] = 85
        
        # Fetch full history for today to calculate MAs and 52w highs (260 business days = 52 weeks)
        full_df = get_all_symbols_ohlcv(today, lookback_days=260)
        breadth_record = compute_breadth(full_df)
        if breadth_record:
            breadth_record["verdict"] = compute_verdict(breadth_record)
            save_breadth(breadth_record)
        
        # 5. Run Scanners
        job["status"] = "scanning"
        job["progress"] = 90
        
        # Limit data to recent history for scanners to avoid massive Pandas groupBy slowdowns
        scanner_df = full_df.groupby("symbol").tail(70).reset_index(drop=True)
        
        mb_results = detect_momentum_burst(scanner_df)
        ep_results = detect_episodic_pivot(scanner_df)
        ti_results = detect_trend_intensity(scanner_df)
        
        # 6. Build and Export Watchlist
        # This ranks and saves to both CSV and SQLite
        watchlist_df = merge_and_rank([mb_results, ep_results, ti_results], today)
        export_watchlist(watchlist_df, today)
        
        # 7. Finalize
        job["status"] = "completed"
        job["progress"] = 100
        job["candidates"] = len(watchlist_df)
        job["finish_time"] = datetime.now().isoformat()
        
    except Exception as e:
        logger.exception("Live scan worker failed for job %s", job_id)
        job["status"] = "failed"
        job["error"] = str(e)
        job["finish_time"] = datetime.now().isoformat()


@app.post("/briefing/live/start")
def start_live_scan() -> Dict[str, str]:
    """Start a background live scan job and return its ID."""
    job_id = str(uuid.uuid4())
    LIVE_SCAN_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress": 0,
        "candidates": 0,
        "error": None,
        "start_time": datetime.now().isoformat(),
        "finish_time": None
    }
    
    thread = threading.Thread(target=_run_live_scan_worker, args=(job_id,), daemon=True)
    thread.start()
    
    return {"job_id": job_id}


@app.get("/briefing/live/status/{job_id}", response_model=LiveScanStatusResponse)
def get_live_scan_status(job_id: str):
    """Return the current status of a live scan job."""
    if job_id not in LIVE_SCAN_JOBS:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return LIVE_SCAN_JOBS[job_id]
