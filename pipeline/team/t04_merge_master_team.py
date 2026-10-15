"""
t04 — Merge team stats + shooting splits (one season)
-----------------------------------------------------
Year-scoped port of Scripts/04_merge_master_team_dataset.py. Inner join of the two
t02 outputs on the Team_Year key.

Usage:
    python -m pipeline.team.t04_merge_master_team --year 2018 [--year 2023 ...]
"""

import pandas as pd

from pipeline import guard
from pipeline.stage import stage_main


def run(year, paths):
    # -----------------------------------------------------------------------
    # 1. Load cleaned datasets (FULL SEASON ONLY)
    # -----------------------------------------------------------------------

    teamstats = pd.read_csv(paths.stage_file("team_stats_full_season", year))
    shotsplits = pd.read_csv(paths.stage_file("team_shooting_splits", year))

    # -----------------------------------------------------------------------
    # 2. Merge datasets (FULL SEASON ONLY)
    # -----------------------------------------------------------------------

    merged = pd.merge(
        teamstats,
        shotsplits,
        on="team",
        how="inner",
        suffixes=("", "_splits")   # stats table is primary, splits get suffix
    )

    # Sort for readability
    merged = merged.sort_values("team").reset_index(drop=True)

    # -----------------------------------------------------------------------
    # 3. Sanity checks
    # -----------------------------------------------------------------------

    print(f"\n=== MERGE CHECK ({year}) ===")
    print("Merged rows:", len(merged))
    print("Unique team keys:", merged["team"].nunique())

    if len(merged) != merged["team"].nunique():
        print("[WARNING] Duplicate team-year keys detected.")
    else:
        print("All team-year keys unique.")

    # -----------------------------------------------------------------------
    # 4. Save output
    # -----------------------------------------------------------------------

    out = guard.to_csv(merged, paths.stage_file("master_team", year), season=year,
                       index=False, encoding="utf-8-sig")

    print(f"[DONE] {year}: master dataset saved to:\n{out}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
