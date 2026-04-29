#!/usr/bin/env python3
"""Calibrate Indian market breadth thresholds (Market Monitor) using historical OHLCV data."""

import os
import sys
import argparse
from datetime import date
import pandas as pd
import sqlite3
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.ingestion.store import get_ohlcv_range
from src.ingestion.symbols import get_universe_symbols

def calculate_historical_breadth(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate breadth metrics for all dates in the OHLCV history."""
    working = ohlcv_df.copy()
    working["date"] = pd.to_datetime(working["date"])
    
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)
    working['ma20'] = working.groupby('symbol')['close'].transform(lambda x: x.rolling(20).mean())
    working['ma50'] = working.groupby('symbol')['close'].transform(lambda x: x.rolling(50).mean())
    working['high_52w'] = working.groupby('symbol')['high'].transform(lambda x: x.rolling(252, min_periods=1).max())
    working['low_52w'] = working.groupby('symbol')['low'].transform(lambda x: x.rolling(252, min_periods=1).min())
    working['prev_close'] = working.groupby('symbol')['close'].shift(1).fillna(working['close'])

    working['above_ma20'] = (working['close'] > working['ma20']).astype(int)
    working['above_ma50'] = (working['close'] > working['ma50']).astype(int)
    working['new_52w_high'] = (working['high'] >= working['high_52w']).astype(int)
    working['new_52w_low'] = (working['low'] <= working['low_52w']).astype(int)
    
    working['up_volume'] = 0
    working.loc[working['close'] >= working['prev_close'], 'up_volume'] = working['volume']

    breadth = working.groupby('date').agg(
        total_symbols=('symbol', 'count'),
        above_ma20=('above_ma20', 'sum'),
        above_ma50=('above_ma50', 'sum'),
        new_highs_52w=('new_52w_high', 'sum'),
        new_lows_52w=('new_52w_low', 'sum'),
        total_volume=('volume', 'sum'),
        up_volume=('up_volume', 'sum'),
    ).reset_index()

    breadth['pct_above_ma20'] = round(breadth['above_ma20'] / breadth['total_symbols'] * 100, 2)
    breadth['pct_above_ma50'] = round(breadth['above_ma50'] / breadth['total_symbols'] * 100, 2)
    breadth['up_volume_ratio'] = round(breadth['up_volume'] / breadth['total_volume'], 4).fillna(0.0)
    
    return breadth

def get_market_returns(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate median universe forward returns to represent market returns."""
    working = ohlcv_df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)
    
    for fwd in [5, 10, 20]:
        working[f'fwd_ret_{fwd}'] = working.groupby('symbol')['close'].transform(lambda x: (x.shift(-fwd) - x) / x * 100)
    
    market = working.groupby('date').agg(
        fwd_ret_5=('fwd_ret_5', 'median'),
        fwd_ret_10=('fwd_ret_10', 'median'),
        fwd_ret_20=('fwd_ret_20', 'median'),
    ).reset_index()
    
    return market.dropna()

def main():
    parser = argparse.ArgumentParser(description="Calibrate market breadth thresholds")
    parser.add_argument("--universe", default=config.UNIVERSE)
    parser.add_argument(
        "--start-date",
        default=(pd.Timestamp.today() - pd.DateOffset(years=config.BACKTEST_YEARS)).date().isoformat(),
    )
    parser.add_argument("--end-date", default=pd.Timestamp.today().date().isoformat())
    args = parser.parse_args()

    symbols = get_universe_symbols(args.universe)
    print(f"Loading OHLCV data for {len(symbols)} symbols...")
    ohlcv_df = get_ohlcv_range(args.start_date, args.end_date, symbols=symbols)
    if ohlcv_df.empty:
        print("No OHLCV history available.")
        return 1
    
    print("Calculating historical breadth metrics...")
    breadth_df = calculate_historical_breadth(ohlcv_df)
    
    print("Calculating median universe forward returns...")
    market_df = get_market_returns(ohlcv_df)
    
    merged = pd.merge(breadth_df, market_df, on='date', how='inner')
    if merged.empty:
        print("No intersecting dates for forward returns calculation.")
        return 1
    
    print("\n--- OFFENSIVE MA20 Threshold Calibration ---")
    results = []
    for thr in [40.0, 45.0, 50.0, 55.0, 60.0]:
        mask = (merged['pct_above_ma20'] >= thr) & (merged['up_volume_ratio'] >= config.MM_OFFENSIVE_UPVOL_RATIO) & (merged['new_highs_52w'] >= merged['new_lows_52w'] * config.MM_OFFENSIVE_HIGHS_VS_LOWS)
        offensive_days = merged[mask]
        
        n_signals = len(offensive_days)
        if n_signals > 0:
            win_rate_10d = (offensive_days['fwd_ret_10'] > 0).mean() * 100
            avg_ret_10d = offensive_days['fwd_ret_10'].mean()
            win_rate_20d = (offensive_days['fwd_ret_20'] > 0).mean() * 100
            avg_ret_20d = offensive_days['fwd_ret_20'].mean()
        else:
            win_rate_10d = avg_ret_10d = win_rate_20d = avg_ret_20d = 0.0
            
        results.append({
            'Threshold_%MA20': thr,
            'Days_Triggered': n_signals,
            'WinRate_10d(%)': round(win_rate_10d, 1),
            'AvgRet_10d(%)': round(avg_ret_10d, 2),
            'WinRate_20d(%)': round(win_rate_20d, 1),
            'AvgRet_20d(%)': round(avg_ret_20d, 2)
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv('data/calibration/offensive_breadth.csv', index=False)
    print("Saved offensive results to data/calibration/offensive_breadth.csv")

    print("\n--- DEFENSIVE MA20 Threshold Calibration ---")
    def_results = []
    for thr in [30.0, 35.0, 40.0, 45.0, 50.0]:
        mask = (merged['pct_above_ma20'] >= thr) & (merged['pct_above_ma20'] < 55.0) & (merged['new_highs_52w'] >= merged['new_lows_52w'])
        defensive_days = merged[mask]
        
        n_signals = len(defensive_days)
        if n_signals > 0:
            avg_ret_10d = defensive_days['fwd_ret_10'].mean()
            win_rate_10d = (defensive_days['fwd_ret_10'] > 0).mean() * 100
        else:
            avg_ret_10d = win_rate_10d = 0.0
            
        def_results.append({
            'Threshold_Floor_%MA20': thr,
            'Days_Triggered': n_signals,
            'WinRate_10d(%)': round(win_rate_10d, 1),
            'AvgRet_10d(%)': round(avg_ret_10d, 2)
        })
    def_res_df = pd.DataFrame(def_results)
    def_res_df.to_csv('data/calibration/defensive_breadth.csv', index=False)
    print("Saved defensive results to data/calibration/defensive_breadth.csv")

if __name__ == '__main__':
    raise SystemExit(main())
