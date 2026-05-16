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
