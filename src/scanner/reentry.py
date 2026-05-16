"""Scanner for Episodic Pivot re-entry setups."""

import pandas as pd
from src.trade.log import get_closed_trades

def detect_ep_reentry(ohlcv: pd.DataFrame, days_since_close: int = 30) -> pd.DataFrame:
    """Find EP re-entry candidates: previous EP trades that pulled back to touching MA10/MA20 and broken out."""
    closed_trades = get_closed_trades(last_n_days=days_since_close)
    if closed_trades.empty:
        return pd.DataFrame()
        
    ep_trades = closed_trades[closed_trades["setup_type"] == "EPISODIC_PIVOT"]
    if ep_trades.empty:
        # Fallback to check generic EP if setup_type got recorded differently
        ep_trades = closed_trades[closed_trades["setup_type"].str.contains("EP", na=False)]
        if ep_trades.empty:
            return pd.DataFrame()

    ep_symbols = ep_trades["symbol"].unique()
    df = ohlcv[ohlcv["symbol"].isin(ep_symbols)].copy()
    if df.empty:
        return pd.DataFrame()

    # Calculate MAs and Vol ratio
    df["ma10"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(10).mean())
    df["ma20"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20).mean())
    df["vol20"] = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20).mean())
    df["vol_ratio"] = df["volume"] / df["vol20"]
    df["prev_high"] = df.groupby("symbol")["high"].shift(1)

    latest_date = df["date"].max()
    today_df = df[df["date"] == latest_date].copy()
    
    candidates = []
    for _, row in today_df.iterrows():
        # Condition 1: Close is above prev high
        if row["close"] <= row["prev_high"]:
            continue
            
        # Condition 2: Touch or cross MA10 or MA20 in the last 2 days
        sym = row["symbol"]
        recent = df[(df["symbol"] == sym) & (df["date"] <= latest_date)].tail(3)
        if len(recent) < 2:
            continue
            
        touched_ma = False
        for _, rev_row in recent.iterrows():
            if (rev_row["low"] <= rev_row["ma10"] <= rev_row["high"]) or \
               (rev_row["low"] <= rev_row["ma20"] <= rev_row["high"]):
                touched_ma = True
                break
                
        if not touched_ma:
            continue
            
        res = row.to_dict()
        res["score"] = row["vol_ratio"]
        res["setup_type"] = "EP_REENTRY"
        # Avoid division by zero
        prev_high = row["prev_high"] if row["prev_high"] else row["open"]
        res["pct_change"] = ((row["close"] / prev_high) - 1.0) * 100 if prev_high else 0.0
        res["volume_ratio"] = row["vol_ratio"]
        
        # Mark matched setups for daily briefing format
        res["matched_setups"] = "EP_REENTRY"
        candidates.append(res)
        
    return pd.DataFrame(candidates)
