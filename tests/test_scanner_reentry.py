import pandas as pd
import pytest
from src.scanner.reentry import detect_ep_reentry

def test_detect_ep_reentry_returns_empty_when_no_closed_trades(monkeypatch):
    monkeypatch.setattr("src.scanner.reentry.get_closed_trades", lambda **kw: pd.DataFrame())
    df = pd.DataFrame()
    result = detect_ep_reentry(df)
    assert result.empty

def test_detect_ep_reentry_identifies_valid_reentry(monkeypatch):
    closed_trades = pd.DataFrame([{
        "symbol": "EP_WINNER",
        "setup_type": "EPISODIC_PIVOT",
        "exit_date": "2026-05-01"
    }])
    monkeypatch.setattr("src.scanner.reentry.get_closed_trades", lambda **kw: closed_trades)

    # Let's mock OHLCV so it touches MA10
    # To have MA10 we need 10 days of data at least, or we can just supply enough data
    rows = []
    # 20 days around 100 for standard MA
    for i in range(20):
        rows.append({"symbol": "EP_WINNER", "date": f"2026-05-0{i+1:02d}", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1000})
        
    # Day 21: High is 105, Low is 101, Close is 102
    rows.append({"symbol": "EP_WINNER", "date": "2026-05-21", "open": 100, "high": 105, "low": 101, "close": 102, "volume": 1000})
    
    # Day 22: Pullback touching MA10. MA10 is around 100. Low goes to 99, High 101.
    rows.append({"symbol": "EP_WINNER", "date": "2026-05-22", "open": 101, "high": 101, "low": 99, "close": 100, "volume": 1000})
    
    # Day 23: Breakout above Day 22 high (101). Low 100, High 104, Close 103 
    rows.append({"symbol": "EP_WINNER", "date": "2026-05-23", "open": 100, "high": 104, "low": 100, "close": 103, "volume": 2000})

    ohlcv = pd.DataFrame(rows)
    # The last row should have a previous high of 101 (from Day 22), and close of 103 (which is > 101).
    # Since low of Day 22 (99) <= ma10 (~100.2) <= high of Day 22 (101), condition 2 is met.
    
    result = detect_ep_reentry(ohlcv)
    assert not result.empty
    assert result.iloc[0]["symbol"] == "EP_WINNER"
    assert result.iloc[0]["setup_type"] == "EP_REENTRY"
