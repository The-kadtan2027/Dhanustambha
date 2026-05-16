"""Read-only FastAPI endpoints for the Dhanustambha dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
import math
from typing import Any, AsyncIterator, Dict, List, Optional

from pydantic import BaseModel
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.ingestion.store import (
    get_breadth,
    get_breadth_dates,
    get_watchlist,
    init_db,
)
from src.trade.log import build_open_trade_status, summarize_closed_trades


@asynccontextmanager
async def lifespan(api_app: FastAPI) -> AsyncIterator[None]:
    """Ensure the SQLite schema exists before serving requests."""
    init_db()
    yield


app = FastAPI(
    title="Dhanustambha Dashboard API",
    version="0.1.0",
    description="Read-only API for market monitor, watchlists, and trade status.",
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
    shares: int
    notes: Optional[str] = None
    grade: Optional[str] = None

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
