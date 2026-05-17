"""FastAPI endpoints for the Dhanustambha dashboard and manual trade workflow."""

from __future__ import annotations

from contextlib import asynccontextmanager
import math
from typing import Any, AsyncIterator, Dict, List, Optional

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
    close_trade,
    open_trade,
    summarize_closed_trades,
    update_stop_price,
)
from src.trade.sizer import calculate_position_size


@asynccontextmanager
async def lifespan(api_app: FastAPI) -> AsyncIterator[None]:
    """Ensure the SQLite schema exists before serving requests."""
    init_db()
    yield


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
    df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
    df["ma50"] = df["close"].rolling(50, min_periods=1).mean()

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
def open_trades() -> Dict[str, Any]:
    """Return open trades with current P&L and action flags."""
    trades = build_open_trade_status()
    return {
        "count": int(len(trades)),
        "items": _records_from_dataframe(trades),
    }


@app.get("/trades/actions")
def trade_actions() -> Dict[str, Any]:
    """Return open trades that require management action."""
    trades = build_open_trade_status()
    if not trades.empty and "action_required" in trades.columns:
        trades = trades[trades["action_required"] != "NONE"]
    return {
        "count": int(len(trades)),
        "items": _records_from_dataframe(trades),
    }


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
