"""
p103 — Player stats data checks (one season) — ADVISORY GATE
------------------------------------------------------------
Year-scoped port of Scripts/103_Torvik_player_stats_data_checks.py. Prints everything
the original printed, for the one season.

The original is print-only and defines no pass/fail rule, so the gate reports
NOT EVALUATED. Pass/fail thresholds are a Phase 5 decision (and must be blocking
before the Phase 6 cron).

Usage:
    python -m pipeline.player.p103_player_stats_checks --year 2018 [--year 2023 ...]
"""

import numpy as np
import pandas as pd

from pipeline.stage import GateResult, stage_main

NAME = "p103_player_stats_checks"


def run(year, paths):
    # ---------------------------------------------------------
    # Load dataset
    # ---------------------------------------------------------
    df = pd.read_csv(paths.stage_file("player_stats", year))
    print(f"Loaded dataset: rows={df.shape[0]}, cols={df.shape[1]}")
    print("-" * 60)

    # ---------------------------------------------------------
    # 1. Basic structural checks
    # ---------------------------------------------------------
    print("COLUMN CHECK:")
    print(df.columns.tolist())
    print("-" * 60)

    print("MISSING VALUES (Top 20):")
    print(df.isna().sum().sort_values(ascending=False).head(20))
    print("-" * 60)

    # ---------------------------------------------------------
    # 2. Players per year
    # ---------------------------------------------------------
    print("PLAYERS PER YEAR:")
    print(df.groupby("year")["name"].count())
    print("-" * 60)

    # ---------------------------------------------------------
    # 3. Teams per year
    # ---------------------------------------------------------
    print("TEAMS PER YEAR:")
    print(df.groupby("year")["team"].nunique())
    print("-" * 60)

    # ---------------------------------------------------------
    # 4. Conferences per year
    # ---------------------------------------------------------
    print("CONFERENCES PER YEAR:")
    print(df.groupby("year")["conference"].nunique())
    print("-" * 60)

    # ---------------------------------------------------------
    # 5. Height sanity check
    # ---------------------------------------------------------
    print("HEIGHT SUMMARY (inches):")
    print(df["height"].describe())
    print("-" * 60)

    # ---------------------------------------------------------
    # 6. Key stat ranges
    # ---------------------------------------------------------
    STAT_COLS = [
        "ortg", "raw_ortg", "drtg", "raw_drtg", "usage_pct", "efg", "ts",
        "blk_pct", "stl_pct", "ast_pct", "tov_pct", "ft_rate",
        "two_p_pct", "three_p_pct", "close_two_pct", "far_two_pct",
        "dunk_pct", "bpm", "obpm", "dbpm", "ppg"
    ]

    print("KEY STAT RANGES:")
    for col in STAT_COLS:
        if col in df.columns:
            print(f"{col:15} min={df[col].min():8.3f}   max={df[col].max():8.3f}")
    print("-" * 60)

    # ---------------------------------------------------------
    # 7. Outlier detection (simple z-score > 5)
    # ---------------------------------------------------------
    def zscore_outliers(series, threshold=5):
        if series.dtype not in [np.float64, np.int64, float, int]:
            return 0
        z = (series - series.mean()) / series.std(ddof=0)
        return (np.abs(z) > threshold).sum()

    print("OUTLIER COUNTS (|z| > 5):")
    for col in STAT_COLS:
        if col in df.columns:
            print(f"{col:15} outliers={zscore_outliers(df[col])}")
    print("-" * 60)

    return GateResult(NAME, year, passed=None, messages=[
        "Print-only in the original: no pass/fail rule defined yet (Phase 5)."
    ])


if __name__ == "__main__":
    stage_main(run, __doc__)
