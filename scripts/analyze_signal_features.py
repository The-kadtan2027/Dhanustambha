#!/usr/bin/env python3
"""Analyze which signal features predict winner vs loser outcomes.

Usage:
    python scripts/analyze_signal_features.py \\
        --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \\
        --scanner episodic_pivot \\
        [--regime OFFENSIVE]   # optional: OFFENSIVE | DEFENSIVE | AVOID | all (default)

For each feature column in the signals CSV, computes win rate by quantile bucket
(numeric features) or by True/False (boolean) or by category value (categorical).
Ranks features by win-rate spread to identify which characteristics predict success.
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
    "trend_intensity": [
        "distance_above_ma50_pct",
        "distance_above_ma150_pct",
        "distance_above_ma200_pct",
        "trend_efficiency_ratio",
        "pullback_depth_20d",
        "vol_dryup_ratio_10d",
        "relative_strength_vs_benchmark_3m",
    ],
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

    quantiles = col.quantile([0.25, 0.50, 0.75]).unique()
    bins = [-np.inf] + sorted(quantiles.tolist()) + [np.inf]
    labels = []
    for i in range(len(bins)-1):
        if i == 0:
            labels.append(f"Q1 (<{bins[1]:.1f})")
        elif i == len(bins)-2:
            labels.append(f"Q{i+1} (>{bins[-2]:.1f})")
        else:
            labels.append(f"Q{i+1} ({bins[i]:.1f}-{bins[i+1]:.1f})")
            
    try:
        cuts = pd.cut(df[feature], bins=bins, labels=labels, duplicates="drop")
    except ValueError:
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
    """Return best bucket win_rate_5d minus worst bucket win_rate_5d (pp).

    Only buckets with n >= MIN_N_PER_BUCKET are included in the spread calculation.
    Returns 0.0 if fewer than 2 qualifying buckets exist.
    """
    valid = bucket_df.dropna(subset=["win_rate_5d_pct"])
    valid = valid[valid["n"] >= MIN_N_PER_BUCKET]
    if len(valid) < 2:
        return 0.0
    return round(float(valid["win_rate_5d_pct"].max() - valid["win_rate_5d_pct"].min()), 1)


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser for the feature analysis script."""
    parser = argparse.ArgumentParser(
        description="Analyze signal features vs trade outcomes to identify live filter candidates"
    )
    parser.add_argument(
        "--signals",
        required=True,
        help="Path to signals CSV from data/calibration/ (the -signals.csv files from Stream D)",
    )
    parser.add_argument(
        "--scanner",
        required=True,
        choices=["episodic_pivot", "momentum_burst", "trend_intensity"],
        help="Scanner name matching the signals CSV",
    )
    parser.add_argument(
        "--regime",
        default="all",
        choices=["all", "OFFENSIVE", "DEFENSIVE", "AVOID"],
        help="Filter signals by market_verdict before analysis (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "research"
        ),
        help="Directory to write the markdown research report (default: data/research/)",
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
        "",
        f"**Signals analysed:** {n_signals}  ",
        f"**Promotion threshold:** spread \u2265 {PROMOTION_SPREAD_PP}pp AND n \u2265 {MIN_N_PER_BUCKET} per bucket  ",
        f"**Date:** {date.today().isoformat()}",
        "",
        "---",
        "",
    ]
    for item in results:
        tag = (
            "[CANDIDATE]"
            if item["spread_pp"] >= PROMOTION_SPREAD_PP
            else ("[WEAK]" if item["spread_pp"] >= 8 else "[NOISE]")
        )
        lines.append(f"## {item['feature']} -- spread {item['spread_pp']}pp -- {tag}")
        lines.append("")
        lines.append(item["buckets"].to_markdown(index=False))
        lines.append("")
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    """Run feature analysis and print ranked report to stdout, write markdown report to disk."""
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
    print(f"FEATURE ANALYSIS -- {args.scanner.upper()} | regime={args.regime} | n={len(df)}")
    print(f"{'='*70}")
    print(f"Promotion threshold: spread >= {PROMOTION_SPREAD_PP}pp AND n >= {MIN_N_PER_BUCKET} per bucket\n")

    candidates = []
    for item in results:
        tag = (
            "[CANDIDATE]"
            if item["spread_pp"] >= PROMOTION_SPREAD_PP
            else ("[WEAK]" if item["spread_pp"] >= 8 else "[NOISE]")
        )
        print(f"\n-- {item['feature']} (spread={item['spread_pp']}pp) {tag}")
        print(item["buckets"].to_string(index=False))
        if item["spread_pp"] >= PROMOTION_SPREAD_PP:
            candidates.append(item["feature"])

    print(f"\n{'='*70}")
    if candidates:
        print(f"PROMOTION CANDIDATES ({len(candidates)}): {', '.join(candidates)}")
        print("-> Next step: validate with calibrate_thresholds.py --feature-filters")
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


if __name__ == "__main__":
    raise SystemExit(main())
