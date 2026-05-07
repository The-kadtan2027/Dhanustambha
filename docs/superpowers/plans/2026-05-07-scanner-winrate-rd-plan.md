# Stream G — Scanner Win-Rate R&D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a feature bucket analysis pipeline that identifies which signal characteristics predict EP/MB/TI winners, validates them through extended calibration, and promotes proven features to live scanner filters.

**Architecture:** A new standalone analysis script (`analyze_signal_features.py`) reads existing signal-level calibration CSVs and slices each feature column against 5d/10d outcomes to find predictive features. The top features are then validated by extending `calibrate_thresholds.py` with a `--feature-filters` post-filter argument. Features that pass both gates are promoted as hard filters in the scanner code and `config.py`.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. All existing infrastructure (SQLite, calibration scripts) is used as-is. No new dependencies required.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `scripts/analyze_signal_features.py` | CREATE | Core feature bucket analysis script |
| `tests/test_analyze_signal_features.py` | CREATE | Unit tests for the analysis script |
| `scripts/calibrate_thresholds.py` | MODIFY | Add `--feature-filters` post-filter argument |
| `src/scanner/episodic_pivot.py` | MODIFY | Add promoted live filter(s) after G2 validates |
| `src/scanner/momentum_burst.py` | MODIFY | Harden HIGH quality to detection criteria if validated |
| `src/scanner/trend_intensity.py` | MODIFY | Add RS filter if validated |
| `config.py` | MODIFY | New constants for any promoted feature thresholds |
| `tests/test_scanner.py` | MODIFY | Tests for new live filter logic |
| `data/research/` | CREATE DIR | Markdown research reports from analysis runs |

---

## Task 1: Create Feature Analysis Script — Core Logic

**Files:**
- Create: `scripts/analyze_signal_features.py`

This script reads a signals CSV (e.g. `data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv`) and for each feature column computes win rate by bucket. It outputs a ranked table to stdout.

- [ ] **Step 1: Create the script with feature column registry and bucket analysis core**

```python
#!/usr/bin/env python3
"""Analyze which signal features predict winner vs loser outcomes.

Usage:
    python scripts/analyze_signal_features.py \\
        --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \\
        --scanner episodic_pivot \\
        [--regime OFFENSIVE]   # optional: OFFENSIVE | DEFENSIVE | AVOID | all (default)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Feature registries ─────────────────────────────────────────────────────────
# Columns present in the signals CSV for each scanner that are candidate predictors.
# These must NOT include outcome columns (return_*, alpha_*, mfe_*, mae_*, hit_*, failed_*).

NUMERIC_FEATURES: dict[str, list[str]] = {
    "episodic_pivot": [
        "gap_pct",
        "gap_vol_ratio",
        "gap_day_close_location_pct",
        "gap_day_close_vs_open_pct",
        "prior_65d_run_pct",
        "prior_65d_weakness_pct",
        "distance_to_52w_high_before_gap",
        "holding_above_gap_open_days",
        "gap_fill_pct",
        "days_since_gap",
    ],
    "momentum_burst": [
        "pct_change",
        "volume_ratio",
        "close_location_pct",
        "range_expansion_ratio",
        "nr_count_10d",
        "consolidation_days",
        "prior_10d_run_pct",
        "prior_20d_run_pct",
        "distance_from_20d_high_pct",
        "trend_linearity_20d",
    ],
    "trend_intensity": [],
}

BOOLEAN_FEATURES: dict[str, list[str]] = {
    "episodic_pivot": ["is_first_gap_in_6m"],
    "momentum_burst": [],
    "trend_intensity": [],
}

CATEGORICAL_FEATURES: dict[str, list[str]] = {
    "episodic_pivot": ["ep_tier", "market_verdict"],
    "momentum_burst": ["mb_quality", "market_verdict"],
    "trend_intensity": ["market_verdict"],
}

MIN_N_PER_BUCKET = 15   # Minimum signals per bucket for statistical credibility
PROMOTION_SPREAD_PP = 15.0   # Win-rate spread threshold (pp) to flag a feature as predictive


def _win_rate(series: pd.Series) -> float:
    """Return fraction of values > 0, as a percentage."""
    if series.empty:
        return float("nan")
    return round(float((series > 0).mean() * 100), 1)


def _avg_alpha(series: pd.Series) -> float:
    """Return mean value as a percentage, rounded to 2dp."""
    if series.empty:
        return float("nan")
    return round(float(series.mean()), 2)


def _mfe_mae_ratio(mfe: pd.Series, mae: pd.Series) -> float:
    """Return average MFE/|MAE| ratio for the bucket. Excludes zero-MAE rows."""
    mae_abs = mae.abs()
    mask = mae_abs > 0
    if mask.sum() == 0:
        return float("nan")
    return round(float((mfe[mask] / mae_abs[mask]).mean()), 2)


def analyze_numeric_feature(
    df: pd.DataFrame,
    feature: str,
) -> pd.DataFrame | None:
    """Slice df by 4 quantile buckets of feature. Return per-bucket metrics or None if absent."""
    if feature not in df.columns:
        return None
    col = df[feature].dropna()
    if col.empty:
        return None

    quantiles = col.quantile([0.25, 0.50, 0.75])
    p25, p50, p75 = quantiles[0.25], quantiles[0.50], quantiles[0.75]
    labels = [f"Q1 (<{p25:.1f})", f"Q2 ({p25:.1f}-{p50:.1f})", f"Q3 ({p50:.1f}-{p75:.1f})", f"Q4 (>{p75:.1f})"]
    cuts = pd.cut(df[feature], bins=[-np.inf, p25, p50, p75, np.inf], labels=labels, duplicates="drop")
    if cuts.isna().all():
        return None

    records = []
    for label in labels:
        subset = df[cuts == label]
        records.append({
            "bucket": label,
            "n": len(subset),
            "win_rate_5d_pct": _win_rate(subset.get("return_5d", pd.Series(dtype=float))),
            "win_rate_10d_pct": _win_rate(subset.get("return_10d", pd.Series(dtype=float))),
            "avg_alpha_5d_pct": _avg_alpha(subset.get("alpha_5d", pd.Series(dtype=float))),
            "avg_alpha_10d_pct": _avg_alpha(subset.get("alpha_10d", pd.Series(dtype=float))),
            "mfe_mae_ratio_5d": _mfe_mae_ratio(
                subset.get("mfe_5d", pd.Series(dtype=float)),
                subset.get("mae_5d", pd.Series(dtype=float)),
            ),
        })
    return pd.DataFrame(records)


def analyze_boolean_feature(df: pd.DataFrame, feature: str) -> pd.DataFrame | None:
    """Split df by True/False value of a boolean feature. Return metrics or None if absent."""
    if feature not in df.columns:
        return None
    records = []
    for val in [True, False]:
        subset = df[df[feature] == val]
        records.append({
            "bucket": str(val),
            "n": len(subset),
            "win_rate_5d_pct": _win_rate(subset.get("return_5d", pd.Series(dtype=float))),
            "win_rate_10d_pct": _win_rate(subset.get("return_10d", pd.Series(dtype=float))),
            "avg_alpha_5d_pct": _avg_alpha(subset.get("alpha_5d", pd.Series(dtype=float))),
            "avg_alpha_10d_pct": _avg_alpha(subset.get("alpha_10d", pd.Series(dtype=float))),
            "mfe_mae_ratio_5d": _mfe_mae_ratio(
                subset.get("mfe_5d", pd.Series(dtype=float)),
                subset.get("mae_5d", pd.Series(dtype=float)),
            ),
        })
    return pd.DataFrame(records)


def analyze_categorical_feature(df: pd.DataFrame, feature: str) -> pd.DataFrame | None:
    """Split df by each unique value of a categorical feature. Return metrics or None if absent."""
    if feature not in df.columns:
        return None
    records = []
    for val in sorted(df[feature].dropna().unique()):
        subset = df[df[feature] == val]
        records.append({
            "bucket": str(val),
            "n": len(subset),
            "win_rate_5d_pct": _win_rate(subset.get("return_5d", pd.Series(dtype=float))),
            "win_rate_10d_pct": _win_rate(subset.get("return_10d", pd.Series(dtype=float))),
            "avg_alpha_5d_pct": _avg_alpha(subset.get("alpha_5d", pd.Series(dtype=float))),
            "avg_alpha_10d_pct": _avg_alpha(subset.get("alpha_10d", pd.Series(dtype=float))),
            "mfe_mae_ratio_5d": _mfe_mae_ratio(
                subset.get("mfe_5d", pd.Series(dtype=float)),
                subset.get("mae_5d", pd.Series(dtype=float)),
            ),
        })
    return pd.DataFrame(records)


def compute_win_rate_spread(bucket_df: pd.DataFrame) -> float:
    """Return best bucket win_rate_5d minus worst bucket win_rate_5d (pp)."""
    valid = bucket_df.dropna(subset=["win_rate_5d_pct"])
    valid = valid[valid["n"] >= MIN_N_PER_BUCKET]
    if len(valid) < 2:
        return 0.0
    return round(float(valid["win_rate_5d_pct"].max() - valid["win_rate_5d_pct"].min()), 1)


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser for the feature analysis script."""
    parser = argparse.ArgumentParser(description="Analyze signal features vs trade outcomes")
    parser.add_argument("--signals", required=True, help="Path to signals CSV from data/calibration/")
    parser.add_argument(
        "--scanner",
        required=True,
        choices=["episodic_pivot", "momentum_burst", "trend_intensity"],
    )
    parser.add_argument(
        "--regime",
        default="all",
        choices=["all", "OFFENSIVE", "DEFENSIVE", "AVOID"],
        help="Filter signals by market_verdict before analysis",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "research"),
    )
    return parser


def run_feature_analysis(
    df: pd.DataFrame,
    scanner: str,
) -> list[dict]:
    """Run all feature analyses on df. Return list of result dicts sorted by win_rate_spread desc."""
    results = []

    for feature in NUMERIC_FEATURES.get(scanner, []):
        bucket_df = analyze_numeric_feature(df, feature)
        if bucket_df is None:
            continue
        spread = compute_win_rate_spread(bucket_df)
        results.append({"feature": feature, "type": "numeric", "spread_pp": spread, "buckets": bucket_df})

    for feature in BOOLEAN_FEATURES.get(scanner, []):
        bucket_df = analyze_boolean_feature(df, feature)
        if bucket_df is None:
            continue
        spread = compute_win_rate_spread(bucket_df)
        results.append({"feature": feature, "type": "boolean", "spread_pp": spread, "buckets": bucket_df})

    for feature in CATEGORICAL_FEATURES.get(scanner, []):
        bucket_df = analyze_categorical_feature(df, feature)
        if bucket_df is None:
            continue
        spread = compute_win_rate_spread(bucket_df)
        results.append({"feature": feature, "type": "categorical", "spread_pp": spread, "buckets": bucket_df})

    return sorted(results, key=lambda x: x["spread_pp"], reverse=True)


def main() -> int:
    """Run feature analysis and print ranked report."""
    parser = build_parser()
    args = parser.parse_args()

    if not os.path.exists(args.signals):
        print(f"ERROR: signals file not found: {args.signals}", file=sys.stderr)
        return 1

    df = pd.read_csv(args.signals)
    print(f"Loaded {len(df)} signals from {args.signals}")

    if args.regime != "all" and "market_verdict" in df.columns:
        df = df[df["market_verdict"] == args.regime].reset_index(drop=True)
        print(f"Filtered to {len(df)} signals with verdict={args.regime}")

    if df.empty:
        print("No signals remaining after filter. Exiting.")
        return 1

    results = run_feature_analysis(df, args.scanner)

    print(f"\n{'='*70}")
    print(f"FEATURE ANALYSIS — {args.scanner.upper()} | regime={args.regime} | n={len(df)}")
    print(f"{'='*70}")
    print(f"Promotion threshold: spread >= {PROMOTION_SPREAD_PP}pp AND n >= {MIN_N_PER_BUCKET} per bucket\n")

    candidates = []
    for item in results:
        tag = "✅ CANDIDATE" if item["spread_pp"] >= PROMOTION_SPREAD_PP else ("⚠️  WEAK" if item["spread_pp"] >= 8 else "❌ NOISE")
        print(f"\n── {item['feature']} (spread={item['spread_pp']}pp) {tag}")
        print(item["buckets"].to_string(index=False))
        if item["spread_pp"] >= PROMOTION_SPREAD_PP:
            candidates.append(item["feature"])

    print(f"\n{'='*70}")
    if candidates:
        print(f"PROMOTION CANDIDATES ({len(candidates)}): {', '.join(candidates)}")
        print("→ Next step: validate with calibrate_thresholds.py --feature-filters")
    else:
        print("No features cleared the promotion threshold. No live filter changes warranted.")
    print(f"{'='*70}\n")

    os.makedirs(args.output_dir, exist_ok=True)
    report_path = os.path.join(
        args.output_dir,
        f"{date.today().isoformat()}-{args.scanner}-feature-analysis.md",
    )
    _write_markdown_report(results, args.scanner, args.regime, len(df), report_path)
    print(f"Report saved to {report_path}")
    return 0


def _write_markdown_report(
    results: list[dict],
    scanner: str,
    regime: str,
    n_signals: int,
    output_path: str,
) -> None:
    """Write ranked feature analysis to a markdown file."""
    lines = [
        f"# Feature Analysis — {scanner} | regime={regime}",
        f"",
        f"**Signals analysed:** {n_signals}  ",
        f"**Promotion threshold:** spread ≥ {PROMOTION_SPREAD_PP}pp AND n ≥ {MIN_N_PER_BUCKET} per bucket  ",
        f"**Date:** {date.today().isoformat()}",
        f"",
        f"---",
        f"",
    ]
    for item in results:
        tag = "✅ PROMOTION CANDIDATE" if item["spread_pp"] >= PROMOTION_SPREAD_PP else ("⚠️ WEAK" if item["spread_pp"] >= 8 else "❌ NOISE")
        lines.append(f"## {item['feature']} — spread {item['spread_pp']}pp — {tag}")
        lines.append("")
        lines.append(item["buckets"].to_markdown(index=False))
        lines.append("")
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create `data/research/.gitkeep`** so the output directory exists in git

```bash
mkdir data\research
type nul > data\research\.gitkeep
```

- [ ] **Step 3: Run smoke test against an existing signals CSV**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \
  --scanner episodic_pivot --regime OFFENSIVE
```

Expected: ranked feature table printed to console, no errors, report file created in `data/research/`.

- [ ] **Step 4: Commit**

```bash
git add scripts/analyze_signal_features.py data/research/.gitkeep
git commit -m "feat(research): add analyze_signal_features.py for EP/MB/TI win-rate analysis"
```

---

## Task 2: Tests for Feature Analysis Script

**Files:**
- Create: `tests/test_analyze_signal_features.py`

- [ ] **Step 1: Write tests covering bucket analysis, spread calculation, and regime filter**

```python
"""Tests for scripts/analyze_signal_features.py feature bucket analysis."""
import os
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.analyze_signal_features import (
    analyze_boolean_feature,
    analyze_categorical_feature,
    analyze_numeric_feature,
    compute_win_rate_spread,
    run_feature_analysis,
    MIN_N_PER_BUCKET,
    PROMOTION_SPREAD_PP,
)


def _make_signals(n: int = 60) -> pd.DataFrame:
    """Return a synthetic signals DataFrame with known outcome patterns."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "return_5d": rng.normal(0.5, 3.0, n),
        "return_10d": rng.normal(1.0, 4.0, n),
        "alpha_5d": rng.normal(0.2, 2.0, n),
        "alpha_10d": rng.normal(0.5, 3.0, n),
        "mfe_5d": rng.uniform(0, 8, n),
        "mae_5d": rng.uniform(-5, 0, n),
        "market_verdict": rng.choice(["OFFENSIVE", "DEFENSIVE", "AVOID"], n),
        # numeric feature — high values should "win" more (we'll encode this below)
        "gap_pct": rng.uniform(4, 15, n),
        # boolean feature
        "is_first_gap_in_6m": rng.choice([True, False], n),
        # categorical feature
        "ep_tier": rng.choice(["A+", "B"], n),
    })
    # Force a strong pattern: high gap_pct → winner (to test spread detection)
    high_gap_mask = df["gap_pct"] > df["gap_pct"].median()
    df.loc[high_gap_mask, "return_5d"] = rng.uniform(2, 8, high_gap_mask.sum())
    df.loc[~high_gap_mask, "return_5d"] = rng.uniform(-5, -1, (~high_gap_mask).sum())
    return df


def test_analyze_numeric_feature_returns_4_buckets():
    df = _make_signals(80)
    result = analyze_numeric_feature(df, "gap_pct")
    assert result is not None
    assert len(result) == 4
    assert "bucket" in result.columns
    assert "win_rate_5d_pct" in result.columns
    assert "n" in result.columns


def test_compute_win_rate_spread_detects_strong_feature():
    df = _make_signals(80)
    bucket_df = analyze_numeric_feature(df, "gap_pct")
    spread = compute_win_rate_spread(bucket_df)
    # With the forced pattern in _make_signals, spread should be large
    assert spread >= PROMOTION_SPREAD_PP, f"Expected spread >= {PROMOTION_SPREAD_PP}pp, got {spread}"


def test_compute_win_rate_spread_ignores_small_n_buckets():
    """Buckets with fewer than MIN_N_PER_BUCKET signals should not count toward spread."""
    bucket_df = pd.DataFrame({
        "bucket": ["Q1", "Q2", "Q3", "Q4"],
        "n": [MIN_N_PER_BUCKET - 1, 30, 30, 30],
        "win_rate_5d_pct": [90.0, 50.0, 50.0, 50.0],
    })
    spread = compute_win_rate_spread(bucket_df)
    # Q1 has too few signals; spread over the remaining 3 is 0
    assert spread == 0.0


def test_analyze_boolean_feature_returns_two_rows():
    df = _make_signals(60)
    result = analyze_boolean_feature(df, "is_first_gap_in_6m")
    assert result is not None
    assert len(result) == 2
    assert set(result["bucket"].astype(str)) == {"True", "False"}


def test_analyze_categorical_feature_returns_all_values():
    df = _make_signals(60)
    result = analyze_categorical_feature(df, "ep_tier")
    assert result is not None
    assert set(result["bucket"]) == {"A+", "B"}


def test_analyze_numeric_feature_returns_none_for_missing_column():
    df = _make_signals(20)
    result = analyze_numeric_feature(df, "nonexistent_column")
    assert result is None


def test_run_feature_analysis_returns_sorted_by_spread():
    df = _make_signals(80)
    results = run_feature_analysis(df, "episodic_pivot")
    spreads = [r["spread_pp"] for r in results]
    assert spreads == sorted(spreads, reverse=True)


def test_run_feature_analysis_handles_missing_alpha_columns():
    """Should not crash if alpha_* columns are missing (older signal CSVs)."""
    df = _make_signals(60)
    df = df.drop(columns=["alpha_5d", "alpha_10d"])
    results = run_feature_analysis(df, "episodic_pivot")
    assert isinstance(results, list)
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/test_analyze_signal_features.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_analyze_signal_features.py
git commit -m "test(research): add unit tests for analyze_signal_features.py"
```

---

## Task 3: Run EP Feature Analysis and Document Findings

This task is a research run, not code. Its output determines which features move to Task 4.

- [ ] **Step 1: Run analysis on EP signals CSV — all regimes first**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \
  --scanner episodic_pivot --regime all
```

- [ ] **Step 2: Run again for OFFENSIVE regime only**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \
  --scanner episodic_pivot --regime OFFENSIVE
```

- [ ] **Step 3: Record findings in `data/research/FINDINGS.md`**

Create `data/research/FINDINGS.md` and record which features had spread ≥ 15pp, their best/worst bucket win rates, and which 1-2 features will be taken forward to Task 4 extended calibration. Format:

```markdown
# Stream G Research Findings

## EP Feature Analysis — 2026-05-07

### Promotion Candidates (spread ≥ 15pp)
| Feature | Best Bucket | Worst Bucket | Spread |
|---|---|---|---|
| [feature_name] | [bucket_label] ([win_rate]%) | [bucket_label] ([win_rate]%) | [spread]pp |

### Selected for G2 Extended Calibration
- [feature_name]: filter value = [threshold from best bucket boundary]

### Noise Features (spread < 5pp)
- [list them]
```

- [ ] **Step 4: Commit findings**

```bash
git add data/research/
git commit -m "docs(research): EP feature analysis findings from G1 run"
```

---

## Task 4: Extended Calibration — Add `--feature-filters` to `calibrate_thresholds.py`

**Files:**
- Modify: `scripts/calibrate_thresholds.py`

The `--feature-filters` argument takes one or more `feature_name:threshold_value` pairs. After each backtest parameter set generates signal rows, the script applies the filter to the signal DataFrame before computing summary metrics. This lets us measure "how much does filtering by this feature improve alpha?" without touching the scanner detection code.

- [ ] **Step 1: Add `--feature-filters` argument and `apply_feature_filters()` helper to `calibrate_thresholds.py`**

In `build_parser()`, add this argument after `--max-param-sets`:

```python
parser.add_argument(
    "--feature-filters",
    nargs="*",
    default=None,
    metavar="FEATURE:THRESHOLD",
    help=(
        "Post-filter signals by feature threshold before computing summary metrics. "
        "Format: feature_name:min_value (numeric) or feature_name:True (boolean). "
        "E.g.: --feature-filters gap_day_close_location_pct:60 is_first_gap_in_6m:True"
    ),
)
```

Add this function before `main()`:

```python
def apply_feature_filters(
    signals_df: pd.DataFrame,
    feature_filters: list[str] | None,
) -> pd.DataFrame:
    """Apply feature threshold filters to a signals DataFrame.

    Each filter is a string of the form 'feature_name:value'.
    For numeric features, keeps rows where feature >= value.
    For boolean features, keeps rows where feature == value (True/False).
    Missing columns are silently skipped.
    """
    if not feature_filters or signals_df.empty:
        return signals_df

    result = signals_df.copy()
    for spec in feature_filters:
        if ":" not in spec:
            continue
        feature, raw_value = spec.split(":", 1)
        if feature not in result.columns:
            continue
        if raw_value.lower() in ("true", "false"):
            bool_val = raw_value.lower() == "true"
            result = result[result[feature].astype(bool) == bool_val]
        else:
            try:
                threshold = float(raw_value)
                result = result[result[feature] >= threshold]
            except ValueError:
                continue
    return result.reset_index(drop=True)
```

- [ ] **Step 2: Apply the filter inside the calibration loop**

In `main()`, locate the line that starts `if not args.summary_only and not result.signal_results.empty:` (around line 163) and add the filter application just above it:

```python
        filtered_signals = apply_feature_filters(result.signal_results, args.feature_filters)
        if not args.summary_only and not filtered_signals.empty:
            signal_frames.append(filtered_signals.copy())
```

Also update signal count display to show both raw and filtered:

```python
        filtered_n = len(filtered_signals) if args.feature_filters else result.n_signals
        print(
            f"      Completed in {_format_seconds(param_duration)} "
            f"with {result.n_signals} raw signals"
            + (f" → {filtered_n} after feature filter" if args.feature_filters else "")
        )
```

- [ ] **Step 3: Write a test for `apply_feature_filters()`**

Add to `tests/test_analyze_signal_features.py`:

```python
from scripts.calibrate_thresholds import apply_feature_filters

def test_apply_feature_filters_numeric():
    df = pd.DataFrame({
        "gap_day_close_location_pct": [40.0, 55.0, 70.0, 80.0],
        "return_5d": [1.0, 2.0, 3.0, 4.0],
    })
    result = apply_feature_filters(df, ["gap_day_close_location_pct:60"])
    assert len(result) == 2
    assert result["gap_day_close_location_pct"].min() >= 60.0


def test_apply_feature_filters_boolean():
    df = pd.DataFrame({
        "is_first_gap_in_6m": [True, False, True, False],
        "return_5d": [1.0, 2.0, 3.0, 4.0],
    })
    result = apply_feature_filters(df, ["is_first_gap_in_6m:True"])
    assert len(result) == 2
    assert result["is_first_gap_in_6m"].all()


def test_apply_feature_filters_missing_column_skipped():
    df = pd.DataFrame({"return_5d": [1.0, 2.0]})
    result = apply_feature_filters(df, ["nonexistent_col:50"])
    assert len(result) == 2  # unchanged


def test_apply_feature_filters_none_returns_unchanged():
    df = pd.DataFrame({"return_5d": [1.0, 2.0, 3.0]})
    result = apply_feature_filters(df, None)
    assert len(result) == 3
```

- [ ] **Step 4: Run tests**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/test_analyze_signal_features.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Smoke run — extended calibration with feature filter**

Using the feature(s) identified in Task 3 findings (replace `gap_day_close_location_pct:60` with the actual chosen feature and threshold):

```bash
C:\Program Files\Python312\python.exe scripts/calibrate_thresholds.py \
  --scanner episodic_pivot --universe NIFTY500 \
  --max-param-sets 5 \
  --feature-filters gap_day_close_location_pct:60
```

Expected: runs without error, signal counts show both raw and filtered n, output CSV saves to `data/calibration/`.

- [ ] **Step 6: Commit**

```bash
git add scripts/calibrate_thresholds.py tests/test_analyze_signal_features.py
git commit -m "feat(calibration): add --feature-filters post-filter to calibrate_thresholds.py"
```

---

## Task 5: Run Full Extended EP Calibration and Validate Features

This is a research run. Decision gate: does the filtered calibration show improved `median_alpha_5d` vs the baseline?

- [ ] **Step 1: Run full extended calibration for EP with the top candidate feature(s) from Task 3**

Replace `FEATURE:THRESHOLD` below with the actual values from FINDINGS.md:

```bash
C:\Program Files\Python312\python.exe scripts/calibrate_thresholds.py \
  --scanner episodic_pivot --universe NIFTY500 \
  --feature-filters FEATURE:THRESHOLD
```

This will take ~47min for the full 64-set grid. Use `--max-param-sets 10` first as a smoke check.

- [ ] **Step 2: Compare results vs baseline**

Open the new `data/calibration/*-episodic_pivot-NIFTY500-summary.csv` and compare top-ranked `median_alpha_5d` and `n_signals` against the baseline from `2026-04-25-episodic_pivot-NIFTY500-summary.csv`.

**Promotion gate passes if:**
- Filtered `median_alpha_5d` (OFFENSIVE) > baseline `median_alpha_5d` (OFFENSIVE)
- At least 5 OFFENSIVE signals remain in the calibration window after filtering

**If gate passes:** proceed to Task 6 (live filter promotion).
**If gate fails:** update FINDINGS.md with the result and skip to Task 7 (MB analysis).

- [ ] **Step 3: Update FINDINGS.md with G2 result**

```bash
git add data/calibration/ data/research/FINDINGS.md
git commit -m "docs(research): EP G2 extended calibration results"
```

---

## Task 6: Promote Validated EP Feature to Live Filter

**Only run this task if Task 5's promotion gate passed.**

**Files:**
- Modify: `config.py`
- Modify: `src/scanner/episodic_pivot.py`
- Modify: `tests/test_scanner.py`

- [ ] **Step 1: Add config constant**

In `config.py`, add the new constant in the EP thresholds section. Example for gap close location (use the actual threshold from FINDINGS.md):

```python
# Episodic Pivot — G2-validated live quality filter
# Set to 0.0 to disable (no filter applied).
EP_MIN_GAP_CLOSE_LOCATION_PCT = 60.0   # G2-validated: 2026-05-07
```

- [ ] **Step 2: Apply the filter in `detect_episodic_pivot()` in `src/scanner/episodic_pivot.py`**

In the candidate loop, after the `today["close"] >= gap_row["open"]` check, add:

```python
                    # G2-validated quality filter: require strong close on gap day
                    if config.EP_MIN_GAP_CLOSE_LOCATION_PCT > 0:
                        loc = gap_row.get("gap_day_close_location_pct", 100.0)
                        if pd.isna(loc) or loc < config.EP_MIN_GAP_CLOSE_LOCATION_PCT:
                            break
```

*(Replace `gap_day_close_location_pct` and the config constant name with the actual feature promoted from FINDINGS.md.)*

- [ ] **Step 3: Write failing test first**

In `tests/test_scanner.py`, add:

```python
def test_ep_live_filter_rejects_weak_close_location():
    """detect_episodic_pivot() must reject gaps where close is < EP_MIN_GAP_CLOSE_LOCATION_PCT."""
    import config
    original_threshold = config.EP_MIN_GAP_CLOSE_LOCATION_PCT
    config.EP_MIN_GAP_CLOSE_LOCATION_PCT = 70.0
    try:
        # Build a minimal OHLCV history: gap-up on day 25 but close at bottom of range
        n = 30
        dates = pd.date_range("2025-01-01", periods=n, freq="B")
        closes = [100.0] * (n - 1) + [106.0]
        opens  = [100.0] * (n - 1) + [104.0]   # +4% gap
        highs  = [101.0] * (n - 1) + [110.0]
        # close (106) is near LOW (104), close_location = (106-104)/(110-104) = 33%
        lows   = [99.0]  * (n - 1) + [104.0]
        vols   = [200_000] * (n - 1) + [700_000]  # 3.5x average
        df = pd.DataFrame({
            "symbol": ["TEST"] * n,
            "date": dates,
            "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols,
        })
        result = detect_episodic_pivot(df)
        assert result.empty, "Should reject gap with close_location < 70%"
    finally:
        config.EP_MIN_GAP_CLOSE_LOCATION_PCT = original_threshold
```

- [ ] **Step 4: Run test to verify it fails before implementation**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/test_scanner.py::test_ep_live_filter_rejects_weak_close_location -v
```

Expected: FAIL (filter not implemented yet).

- [ ] **Step 5: Implement the filter (Step 2 above), then run tests**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/ -v
```

Expected: ALL tests PASS, including the new one.

- [ ] **Step 6: Commit**

```bash
git add config.py src/scanner/episodic_pivot.py tests/test_scanner.py
git commit -m "feat(scanner): promote G2-validated EP quality filter to live detection"
```

---

## Task 7: MB Feature Analysis and Quality Tier Validation

**Files:**
- Run `analyze_signal_features.py` on the latest MB signals CSV

- [ ] **Step 1: Run MB feature analysis**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-momentum_burst-NIFTY500-signals.csv \
  --scanner momentum_burst --regime all
```

- [ ] **Step 2: Run with OFFENSIVE regime filter**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-momentum_burst-NIFTY500-signals.csv \
  --scanner momentum_burst --regime OFFENSIVE
```

- [ ] **Step 3: Run with feature filter `mb_quality:HIGH` to check if HIGH tier has better alpha**

```bash
C:\Program Files\Python312\python.exe scripts/calibrate_thresholds.py \
  --scanner momentum_burst --universe NIFTY500 \
  --max-param-sets 10 \
  --feature-filters mb_quality:HIGH
```

- [ ] **Step 4: Decision gate — is MB HIGH tier viable?**

Compare `median_alpha_5d` (OFFENSIVE) for `mb_quality=HIGH` vs unfiltered.

**If HIGH shows ≥ 15pp win-rate spread AND improved alpha:** proceed to Task 8 (harden HIGH to detection criteria).
**If HIGH shows no improvement:** update FINDINGS.md with result. MB is demoted to reference-only. Add a note to `daily_briefing.py` output (see Task 9).

- [ ] **Step 5: Update FINDINGS.md**

```bash
git add data/research/FINDINGS.md
git commit -m "docs(research): MB feature analysis findings from G1/G2 runs"
```

---

## Task 8: Harden MB HIGH Quality to Detection Criteria (if Task 7 gate passes)

**Only run if Task 7 confirms HIGH tier has meaningful alpha improvement.**

**Files:**
- Modify: `config.py`
- Modify: `src/scanner/momentum_burst.py`
- Modify: `tests/test_scanner.py`

- [ ] **Step 1: The three HIGH criteria are already in config. Make them default-active detection filters.**

In `config.py`, the existing constants are:
```python
MB_QUALITY_MIN_NR_COUNT = 6
MB_QUALITY_MIN_CLOSE_LOC_PCT = 70.0
MB_QUALITY_MIN_DIST_20D_HIGH = 0.0
```

Add a flag:
```python
MB_REQUIRE_HIGH_QUALITY = True   # Set False to restore pre-G2 behavior for research
```

- [ ] **Step 2: Apply detection-time filter in `detect_momentum_burst()`**

After the existing filter block in `detect_momentum_burst()`, before returning `candidates`, add:

```python
    if config.MB_REQUIRE_HIGH_QUALITY:
        filtered = filtered[
            filtered["nr_count_10d"].ge(config.MB_QUALITY_MIN_NR_COUNT)
            & filtered["close_location_pct"].ge(config.MB_QUALITY_MIN_CLOSE_LOC_PCT)
            & filtered["distance_from_20d_high_pct"].ge(config.MB_QUALITY_MIN_DIST_20D_HIGH)
        ]
```

- [ ] **Step 3: Write failing test**

In `tests/test_scanner.py`, add:
```python
def test_mb_high_quality_filter_rejects_weak_close():
    """When MB_REQUIRE_HIGH_QUALITY=True, low close_location candidates are rejected."""
    import config
    original = config.MB_REQUIRE_HIGH_QUALITY
    config.MB_REQUIRE_HIGH_QUALITY = True
    config.MB_QUALITY_MIN_CLOSE_LOC_PCT = 70.0
    try:
        n = 30
        dates = pd.date_range("2025-01-01", periods=n, freq="B")
        closes = [100.0] * (n - 1) + [106.0]
        highs  = [101.0] * (n - 1) + [115.0]
        lows   = [99.0]  * (n - 1) + [104.5]
        # close_location = (106-104.5)/(115-104.5) = 14.3% ← below 70% threshold
        opens  = closes
        vols   = [200_000] * (n - 1) + [500_000]
        df = pd.DataFrame({
            "symbol": ["TEST"] * n,
            "date": dates,
            "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols,
        })
        result = detect_momentum_burst(df)
        assert result.empty, "Should reject MB candidate with low close_location"
    finally:
        config.MB_REQUIRE_HIGH_QUALITY = original
```

- [ ] **Step 4: Run failing test, then implement, then run full suite**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/test_scanner.py::test_mb_high_quality_filter_rejects_weak_close -v
# Expect: FAIL
# ... implement filter in detect_momentum_burst() ...
C:\Program Files\Python312\python.exe -m pytest tests/ -v
# Expect: ALL PASS
```

- [ ] **Step 5: Commit**

```bash
git add config.py src/scanner/momentum_burst.py tests/test_scanner.py
git commit -m "feat(scanner): harden MB HIGH quality tier to live detection criteria"
```

---

## Task 9: Reference-Only Demotion for Scanners Without Edge

**Run this task for any scanner that failed its G2 gate (no alpha improvement found).**

**Files:**
- Modify: `scripts/daily_briefing.py`

The "reference-only" demotion means: the scanner still runs and its results still appear in the daily output, but they are printed in a separate section below the main watchlist and are never written to the top-N watchlist CSV.

- [ ] **Step 1: Review `daily_briefing.py` to find where scanner results are printed and exported**

Find the section that constructs the top-N watchlist (sorted by score) and the CSV export. Understand which variables hold scanner results.

- [ ] **Step 2: Add a `REFERENCE_ONLY_SCANNERS` constant to `config.py`**

```python
# Scanners demoted to reference-only based on Stream G feature analysis findings.
# Set to [] to show all scanners in the main watchlist.
REFERENCE_ONLY_SCANNERS: list[str] = []   # e.g. ["MOMENTUM_BURST", "TREND_INTENSITY"]
```

- [ ] **Step 3: Modify watchlist merge to exclude reference-only scanners from top-N CSV**

In `src/scanner/watchlist.py` (or wherever `merge_and_rank()` lives), add:

```python
import config

def merge_and_rank(mb_df, ep_df, ti_df, max_candidates=None):
    """Merge scanner results. Reference-only scanners are excluded from top-N export."""
    # ... existing merge logic ...

    # Exclude reference-only scanners from the ranked export
    reference_only = set(config.REFERENCE_ONLY_SCANNERS)
    export_df = merged[~merged["setup_type"].isin(reference_only)].copy()
    reference_df = merged[merged["setup_type"].isin(reference_only)].copy()

    # Return both for separate display in daily_briefing.py
    return export_df, reference_df
```

- [ ] **Step 4: Update `daily_briefing.py` to print the reference section separately**

After the main watchlist print block, add:

```python
if not reference_df.empty:
    print("\n── FOR REFERENCE ONLY (no alpha evidence — do not trade) ──")
    for _, row in reference_df.iterrows():
        print(f"  {row['symbol']:12s}  {row['setup_type']:18s}  score={row['score']:.1f}")
```

- [ ] **Step 5: Run tests and smoke run**

```bash
C:\Program Files\Python312\python.exe -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add config.py src/scanner/watchlist.py scripts/daily_briefing.py
git commit -m "feat(briefing): add reference-only scanner demotion based on G2 validation"
```

---

## Task 10: TI Relative Strength Feature (if capacity remains)

**Files:**
- Modify: `src/scanner/trend_intensity.py`

The hypothesis: TI works for stocks already outperforming NIFTY. We need to add `relative_strength_vs_benchmark_3m` to the TI feature set.

- [ ] **Step 1: Add RS feature to `prepare_trend_intensity_features()` in `src/scanner/trend_intensity.py`**

After the existing feature calculations, add:

```python
        # Relative strength vs benchmark: stock 3m return minus benchmark 3m return
        stock_3m_return = (ordered["close"] / ordered["close"].shift(63) - 1) * 100
        # Benchmark returns must be joined from the stored benchmark series.
        # For now, compute stock-only 3m percentile rank vs universe as a proxy.
        ordered["rs_3m_pct"] = stock_3m_return  # raw 3m return; percentile rank computed at analysis time
```

Note: Full RS vs benchmark requires joining benchmark OHLCV, which is not available in the per-symbol prepare loop. For Phase G4, use the raw 3m return percentile rank across the universe at analysis time in the feature analysis script. Add a note in the code:

```python
        # ASSUMPTION: rs_3m_pct is the stock's raw 3m return. Percentile ranking vs
        # universe is computed externally in analyze_signal_features.py at analysis time.
        # This is sufficient for bucket analysis; a live filter would use config.TI_MIN_RS_3M_PCT_RANK.
```

- [ ] **Step 2: Run TI feature analysis**

```bash
C:\Program Files\Python312\python.exe scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-24-trend_intensity-NIFTY500-signals.csv \
  --scanner trend_intensity --regime OFFENSIVE
```

- [ ] **Step 3: Update FINDINGS.md with TI result and commit**

```bash
git add src/scanner/trend_intensity.py data/research/FINDINGS.md
git commit -m "docs(research): TI RS feature analysis findings from G1 run"
```

---

## Self-Review

**Spec coverage:**
- G1 feature analysis script → Task 1 ✅
- Tests for analysis script → Task 2 ✅
- EP feature analysis research run → Task 3 ✅
- Extended calibration `--feature-filters` → Task 4 ✅
- Full EP extended calibration run → Task 5 ✅
- EP live filter promotion → Task 6 ✅
- MB feature analysis + HIGH tier validation → Task 7 ✅
- MB HIGH tier hardening → Task 8 ✅
- Reference-only demotion for scanners without edge → Task 9 ✅
- TI RS feature → Task 10 ✅

**Placeholder scan:** All tasks have concrete code. Gate conditions in Tasks 5, 7, and 8 have explicit pass/fail criteria. Task 9 depends on prior tasks' outcomes — the agent should check FINDINGS.md for the list of scanners to demote.

**Type consistency:** `apply_feature_filters()` returns `pd.DataFrame`, used as `filtered_signals` → passed to `signal_frames.append()` ✅. `run_feature_analysis()` returns `list[dict]` ✅. `merge_and_rank()` now returns a tuple `(export_df, reference_df)` — callers in `daily_briefing.py` must be updated to unpack the tuple (this is flagged in Task 9 Step 4).

> [!IMPORTANT]
> `merge_and_rank()` return signature changes in Task 9. Any existing caller that expects a single DataFrame must be updated. Check all callers before committing Task 9.
