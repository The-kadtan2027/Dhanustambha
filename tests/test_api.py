"""Tests for the read-only FastAPI dashboard endpoints."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Return a TestClient backed by a temporary SQLite database."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "api_test.db"))

    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.ingestion.store import init_db

    init_db()
    return TestClient(app)


def test_health_endpoint(api_client):
    """Health endpoint should return a simple OK response."""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_latest_briefing_returns_breadth_and_watchlist(api_client):
    """Briefing endpoint should combine stored breadth and watchlist rows."""
    from src.ingestion.store import save_breadth, save_watchlist

    save_breadth(
        {
            "date": "2026-04-29",
            "pct_above_ma20": 62.0,
            "pct_above_ma50": 55.0,
            "new_highs_52w": 42,
            "new_lows_52w": 8,
            "up_volume_ratio": 0.66,
            "advancing": 310,
            "declining": 180,
            "verdict": "OFFENSIVE",
        }
    )
    save_watchlist(
        [
            {
                "date": "2026-04-29",
                "symbol": "RELIANCE",
                "setup_type": "EPISODIC_PIVOT",
                "score": 25.0,
                "pct_change": 8.0,
                "volume_ratio": 4.0,
                "close": 100.0,
                "notes": "A+",
            }
        ]
    )

    response = api_client.get("/briefing/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-04-29"
    assert payload["market"]["verdict"] == "OFFENSIVE"
    assert payload["watchlist_count"] == 1
    assert payload["watchlist"][0]["symbol"] == "RELIANCE"


def test_latest_briefing_collapses_duplicate_watchlist_rows(api_client):
    """Briefing payload should not repeat exact duplicate saved watchlist rows."""
    from src.ingestion.store import save_breadth, save_watchlist

    save_breadth(
        {
            "date": "2026-04-29",
            "pct_above_ma20": 62.0,
            "pct_above_ma50": 55.0,
            "new_highs_52w": 42,
            "new_lows_52w": 8,
            "up_volume_ratio": 0.66,
            "advancing": 310,
            "declining": 180,
            "verdict": "OFFENSIVE",
        }
    )
    duplicate_row = {
        "date": "2026-04-29",
        "symbol": "RELIANCE",
        "setup_type": "EPISODIC_PIVOT",
        "score": 25.0,
        "pct_change": 8.0,
        "volume_ratio": 4.0,
        "close": 100.0,
        "notes": "A+",
    }
    save_watchlist([duplicate_row, duplicate_row.copy()])

    response = api_client.get("/briefing/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["watchlist_count"] == 1
    assert payload["watchlist"] == [duplicate_row]


def test_briefing_allows_market_day_without_watchlist(api_client):
    """Briefing endpoint should return market data when no candidates were saved."""
    from src.ingestion.store import save_breadth

    save_breadth(
        {
            "date": "2026-04-30",
            "pct_above_ma20": 32.0,
            "pct_above_ma50": 35.0,
            "new_highs_52w": 5,
            "new_lows_52w": 40,
            "up_volume_ratio": 0.31,
            "advancing": 110,
            "declining": 390,
            "verdict": "AVOID",
        }
    )

    response = api_client.get("/briefing/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-04-30"
    assert payload["market"]["verdict"] == "AVOID"
    assert payload["watchlist_count"] == 0
    assert payload["watchlist"] == []


def test_briefing_dates_returns_stored_breadth_dates_desc(api_client):
    """Briefing dates endpoint should list available stored briefing dates newest first."""
    from src.ingestion.store import save_breadth

    for date in ("2026-04-28", "2026-04-30", "2026-04-29"):
        save_breadth(
            {
                "date": date,
                "pct_above_ma20": 62.0,
                "pct_above_ma50": 55.0,
                "new_highs_52w": 42,
                "new_lows_52w": 8,
                "up_volume_ratio": 0.66,
                "advancing": 310,
                "declining": 180,
                "verdict": "OFFENSIVE",
            }
        )

    response = api_client.get("/briefing/dates")

    assert response.status_code == 200
    assert response.json() == {
        "count": 3,
        "items": ["2026-04-30", "2026-04-29", "2026-04-28"],
    }


def test_briefing_dates_allows_dashboard_origin(api_client):
    """Briefing dates should allow the local dashboard origin to fetch data."""
    response = api_client.get(
        "/briefing/dates",
        headers={"Origin": "http://127.0.0.1:3000"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_trade_actions_filters_none_actions(api_client):
    """Trade actions endpoint should return only trades with required actions."""
    from src.ingestion.store import upsert_ohlcv
    from src.trade.log import open_trade

    upsert_ohlcv(
        [
            {
                "symbol": "INFY",
                "date": "2026-04-28",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 500000,
            },
            {
                "symbol": "INFY",
                "date": "2026-04-29",
                "open": 102.0,
                "high": 108.0,
                "low": 101.0,
                "close": 106.0,
                "volume": 600000,
            },
        ]
    )
    open_trade(
        symbol="INFY",
        setup_type="EPISODIC_PIVOT",
        entry_date="2026-04-28",
        entry_price=100.0,
        shares=10,
        stop_price=96.0,
    )

    response = api_client.get("/trades/actions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["action_required"] == "TRAIL_TO_BREAKEVEN"


def test_api_allows_post_methods(api_client):
    """API should allow POST methods for frontend trade execution."""
    response = api_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert "POST" in response.headers.get("access-control-allow-methods", "")

def test_api_open_trade(api_client):
    """API should allow opening a new trade."""
    payload = {
        "symbol": "FOO",
        "setup_type": "MOMENTUM_BURST",
        "entry_date": "2026-05-16",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "shares": 10,
        "grade": "B"
    }
    res = api_client.post("/trades/open", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "OPEN"
    assert data["symbol"] == "FOO"
    assert data["shares"] == 10


def test_api_trade_quote_returns_server_sizing(api_client):
    """Trade quote should calculate server-side sizing from account risk."""
    response = api_client.post(
        "/trades/quote",
        json={
            "symbol": "FOO",
            "setup_type": "MOMENTUM_BURST",
            "entry_date": "2026-05-16",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "account_size": 500_000.0,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["valid"] is True
    assert payload["shares"] == 1250
    assert payload["risk_amount"] == 6250.0
    assert payload["position_value"] == 125000.0
    assert payload["r_unit"] == 5.0
    assert payload["market_verdict"] == "OFFENSIVE"


def test_api_trade_quote_rejects_invalid_stop(api_client):
    """Trade quote should reject a stop that is not below entry."""
    response = api_client.post(
        "/trades/quote",
        json={
            "symbol": "FOO",
            "setup_type": "MOMENTUM_BURST",
            "entry_date": "2026-05-16",
            "entry_price": 100.0,
            "stop_price": 101.0,
            "account_size": 500_000.0,
        },
    )

    assert response.status_code == 422
    assert "Stop price must be below entry price" in response.json()["detail"]


def test_api_trade_quote_uses_defensive_sizing(api_client):
    """Trade quote should apply defensive size reduction for DEFENSIVE sessions."""
    from src.ingestion.store import save_breadth

    save_breadth(
        {
            "date": "2026-05-16",
            "pct_above_ma20": 50.0,
            "pct_above_ma50": 45.0,
            "new_highs_52w": 20,
            "new_lows_52w": 10,
            "up_volume_ratio": 0.51,
            "advancing": 260,
            "declining": 240,
            "verdict": "DEFENSIVE",
        }
    )

    response = api_client.post(
        "/trades/quote",
        json={
            "symbol": "FOO",
            "setup_type": "MOMENTUM_BURST",
            "entry_date": "2026-05-16",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "account_size": 500_000.0,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["market_verdict"] == "DEFENSIVE"
    assert payload["shares"] == 625
    assert payload["position_value"] == 62500.0


def test_api_open_trade_uses_server_calculated_shares(api_client):
    """Opening a trade should ignore stale browser share math and store server sizing."""
    response = api_client.post(
        "/trades/open",
        json={
            "symbol": "FOO",
            "setup_type": "MOMENTUM_BURST",
            "entry_date": "2026-05-16",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "shares": 1,
            "account_size": 500_000.0,
            "grade": "B",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["symbol"] == "FOO"
    assert payload["shares"] == 1250


def test_api_open_trade_rejects_invalid_quote(api_client):
    """Opening a trade should reject invalid risk inputs before writing a trade."""
    response = api_client.post(
        "/trades/open",
        json={
            "symbol": "FOO",
            "setup_type": "MOMENTUM_BURST",
            "entry_date": "2026-05-16",
            "entry_price": 100.0,
            "stop_price": 101.0,
            "shares": 1,
            "account_size": 500_000.0,
            "grade": "B",
        },
    )

    assert response.status_code == 422
    assert "Stop price must be below entry price" in response.json()["detail"]

def test_api_update_and_close_trade(api_client):
    """API should allow updating the stop price and closing the trade."""
    res = api_client.post("/trades/open", json={
        "symbol": "BAR", "setup_type": "EP", "entry_date": "2026-05-16",
        "entry_price": 200.0, "stop_price": 190.0, "shares": 5, "grade": "A"
    })
    assert res.status_code == 200
    trade_id = res.json()["id"]

    res = api_client.put(f"/trades/{trade_id}/update-stop", json={"stop_price": 195.0})
    assert res.status_code == 200
    
    res = api_client.put(f"/trades/{trade_id}/close", json={"exit_date": "2026-05-17", "exit_price": 210.0})
    assert res.status_code == 200


def test_ohlcv_endpoint_returns_candles_and_ma(api_client):
    """OHLCV endpoint should return candle rows with MA20 and MA50 columns."""
    import sqlite3

    conn = sqlite3.connect(__import__("config").DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO symbols (symbol, name, active) VALUES (?, ?, ?)",
        ("DEMO", "Demo Stock", 1),
    )
    conn.commit()
    conn.close()

    from src.ingestion.store import upsert_ohlcv

    rows = [
        {
            "symbol": "DEMO",
            "date": f"2026-0{1 if i < 9 else 2}-{(i % 28) + 1:02d}",
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 98.0 + i,
            "close": 102.0 + i,
            "volume": 500_000,
        }
        for i in range(30)
    ]
    upsert_ohlcv(rows)

    response = api_client.get("/ohlcv/DEMO?days=90")
    assert response.status_code == 200
    payload = response.json()
    assert "candles" in payload
    assert payload["symbol"] == "DEMO"
    assert len(payload["candles"]) >= 1
    first = payload["candles"][0]
    for key in ("time", "open", "high", "low", "close", "volume", "ma20", "ma50"):
        assert key in first, f"Missing key: {key}"

def test_breadth_history_endpoint_returns_rows(api_client):
    """GET /market/breadth/history should return a list of breadth rows."""
    import sqlite3
    conn = sqlite3.connect(__import__("config").DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO breadth
          (date, pct_above_ma20, pct_above_ma50, new_highs_52w, new_lows_52w,
           up_volume_ratio, advancing, declining, verdict)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("2026-05-01", 60.0, 55.0, 80, 10, 0.65, 300, 200, "OFFENSIVE"))
    conn.commit()
    conn.close()

    response = api_client.get("/market/breadth/history?days=60")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 1
    first = payload["items"][0]
    for key in ("date", "pct_above_ma20", "up_volume_ratio", "verdict"):
        assert key in first, f"Missing key: {key}"

def test_closed_trades_and_review(api_client):
    """Test fetching closed trades and saving reviews."""
    res_closed = api_client.get("/trades/closed")
    assert res_closed.status_code == 200
    
    review_data = {
        "entry_rule_followed": True,
        "exit_rule_followed": True,
        "what_to_improve": "Solid exit.",
        "review_date": "2026-05-17"
    }
    # Assume trade 9999 doesn't exist
    res_review = api_client.post("/trades/9999/review", json=review_data)
    assert res_review.status_code == 404
