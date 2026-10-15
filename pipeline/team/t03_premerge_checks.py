"""
t03 — Pre-merge data integrity checks (one season) — ADVISORY GATE
------------------------------------------------------------------
Year-scoped port of Scripts/03_premerge_data_checks.py. Prints everything the
original printed and returns pass/fail on team-key alignment.

KNOWN BUG, REPRODUCED ON PURPOSE (spec §6 item 4): the original compares the shooting
splits against the DEPRECATED regular-season team stats, not the full-season file
that t04 actually merges. For frozen seasons this reads that season's rows out of
the existing regular-season baseline (read-only). The current season has no
regular-season source, so the check is reported as NOT EVALUATED.

PHASE 5: retire this check or repoint it at t02's full-season output.

Usage:
    python -m pipeline.team.t03_premerge_checks --year 2018 [--year 2023 ...]
"""

import pandas as pd

from pipeline import config
from pipeline.paths import LEGACY_REGULAR_SEASON
from pipeline.stage import GateResult, stage_main

NAME = "t03_premerge_checks"


def normalize_team_format(s):
    if isinstance(s, str):
        s = s.replace("\xa0", " ").strip()  # remove non-breaking spaces
        parts = s.split(" ")
        team = " ".join(parts[:-1])
        year = parts[-1]
        return f"{team}_{year}"
    return s


def run(year, paths):
    if year not in config.FROZEN_SEASONS:
        print(f"\n[t03] {year}: no regular-season source for the current season — check not evaluated.")
        return GateResult(NAME, year, passed=None, messages=[
            "Original check reads the deprecated regular-season file, which does not exist "
            "for the current season (retire/repoint candidate, Phase 5)."
        ])

    # -----------------------------------------------------------------------
    # 1. Load cleaned datasets
    # -----------------------------------------------------------------------

    team_key = "team"

    teamstats = pd.read_csv(paths.baseline_root / LEGACY_REGULAR_SEASON)
    teamstats = teamstats[teamstats[team_key].astype(str).str.endswith(f"_{year}")]

    shotsplits = pd.read_csv(paths.stage_file("team_shooting_splits", year))

    # -----------------------------------------------------------------------
    # 2. Normalize team names (fix Unicode, enforce Team_Year format)
    # -----------------------------------------------------------------------

    teamstats[team_key] = teamstats[team_key].apply(normalize_team_format)
    shotsplits[team_key] = shotsplits[team_key].apply(normalize_team_format)

    # -----------------------------------------------------------------------
    # 3. Check for missing teams between datasets
    # -----------------------------------------------------------------------

    ts_not_in_ss = set(teamstats[team_key]) - set(shotsplits[team_key])
    ss_not_in_ts = set(shotsplits[team_key]) - set(teamstats[team_key])

    print(f"\n=== TEAM ALIGNMENT CHECK ({year}) ===")
    print(f"Teams in TeamStats but not ShootingSplits: {len(ts_not_in_ss)}")
    if len(ts_not_in_ss) > 0:
        print(sorted(ts_not_in_ss))

    print(f"\nTeams in ShootingSplits but not TeamStats: {len(ss_not_in_ts)}")
    if len(ss_not_in_ts) > 0:
        print(sorted(ss_not_in_ts))

    # -----------------------------------------------------------------------
    # 4. Check for duplicate team-year keys
    # -----------------------------------------------------------------------

    print("\n=== DUPLICATE KEY CHECK ===")

    ts_dupes = teamstats[teamstats.duplicated(team_key, keep=False)]
    ss_dupes = shotsplits[shotsplits.duplicated(team_key, keep=False)]

    print(f"Duplicate keys in TeamStats: {len(ts_dupes)}")
    print(f"Duplicate keys in ShootingSplits: {len(ss_dupes)}")

    if len(ts_dupes) > 0:
        print("\nTeamStats duplicates:")
        print(ts_dupes[team_key].unique())

    if len(ss_dupes) > 0:
        print("\nShootingSplits duplicates:")
        print(ss_dupes[team_key].unique())

    # -----------------------------------------------------------------------
    # 5. Basic schema validation
    # -----------------------------------------------------------------------

    print("\n=== SCHEMA CHECK ===")
    print("TeamStats columns:", len(teamstats.columns))
    print("ShootingSplits columns:", len(shotsplits.columns))

    print("\nTeamStats sample columns:")
    print(teamstats.columns[:12].tolist())

    print("\nShootingSplits sample columns:")
    print(shotsplits.columns[:12].tolist())

    # -----------------------------------------------------------------------
    # 6. Final status
    # -----------------------------------------------------------------------

    print("\n=== STATUS ===")
    aligned = len(ts_not_in_ss) == 0 and len(ss_not_in_ts) == 0
    if aligned:
        print("All team-year keys align. Ready for merge.")
    else:
        print("Mismatches detected. Review before merging.")

    messages = ["Checks the deprecated regular-season file, not the file t04 merges (known bug)."]
    if not aligned:
        messages.append(f"{len(ts_not_in_ss)} team(s) only in TeamStats, "
                        f"{len(ss_not_in_ts)} only in ShootingSplits")
    return GateResult(NAME, year, passed=aligned, messages=messages)


if __name__ == "__main__":
    stage_main(run, __doc__)
