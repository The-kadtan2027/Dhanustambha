"""Check MB signal data availability and run feature analysis."""
import os
import pandas as pd
import numpy as np
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)

# 1. Check which signal files exist and have data
print("=== SIGNAL FILES ===")
for f in sorted(os.listdir('data/calibration')):
    if 'signals' in f:
        sz = os.path.getsize(os.path.join('data/calibration', f))
        print(f"  {f}: {sz/1024/1024:.1f} MB")

# 2. Check the MB signals file for alpha population
print("\n=== MB SIGNAL DATA CHECK ===")
df = pd.read_csv('data/calibration/2026-04-23-momentum_burst-NIFTY500-signals.csv', nrows=500)
for col in ['alpha_5d', 'return_5d', 'close_location_pct', 'nr_count_10d', 'market_verdict']:
    non_null = df[col].notna().sum()
    print(f"  {col}: {non_null}/500 non-null")

# 3. If alpha is empty, use return columns directly and the summary data approach
# Load a sample of the full file to check data patterns
print("\n=== LOADING FULL MB SIGNALS (sample) ===")
# Read in chunks to find rows with valid returns
chunks = pd.read_csv(
    'data/calibration/2026-04-23-momentum_burst-NIFTY500-signals.csv',
    chunksize=50000
)
sample_rows = []
for i, chunk in enumerate(chunks):
    valid = chunk.dropna(subset=['return_5d'])
    if len(valid) > 0:
        sample_rows.append(valid.head(1000))
        print(f"  Chunk {i}: {len(valid)} rows with valid return_5d")
    else:
        print(f"  Chunk {i}: 0 rows with valid return_5d")
    if len(sample_rows) >= 3:
        break

if sample_rows:
    sample = pd.concat(sample_rows, ignore_index=True)
    print(f"\nTotal sample with valid returns: {len(sample)}")
    for col in ['alpha_5d', 'return_5d', 'close_location_pct', 'nr_count_10d']:
        non_null = sample[col].notna().sum()
        print(f"  {col}: {non_null}/{len(sample)} non-null")
else:
    print("\nNo rows with valid return_5d found! Alpha was not backfilled.")
    print("Using the summary data to infer feature importance instead.")
    
    # Alternative: load the EP signals which DO have alpha
    print("\n=== EP SIGNALS (for comparison methodology) ===")
    ep = pd.read_csv('data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv', nrows=500)
    for col in ['alpha_5d', 'return_5d', 'gap_pct', 'market_verdict']:
        non_null = ep[col].notna().sum()
        print(f"  {col}: {non_null}/500 non-null")
