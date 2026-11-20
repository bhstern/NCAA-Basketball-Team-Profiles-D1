"""
Row-count invariants — BLOCKING checks after every fetch and every merge (Phase 5).
------------------------------------------------------------------------------------
Why: on the first live 2026-27 fetch, t04's inner join merged 0 rows without raising
(Torvik had added a 🎯 link to the shooting-splits team names, so no key matched), and
the run carried on. Row counts must never silently collapse again.

What is checked (all raise RowCountError, which stops the run):

    1. NOT ZERO        every checked file has at least one row.
    2. JOIN RETENTION  a join keeps nearly every row it should:
                         t04 inner join  >= 98% of the smaller input
                         p105 team join  >= 98% of player rows matched to a team
                       (every frozen season is 100%; this catches a key mismatch even
                       on a first run that has no history to compare against)
    3. ROW-PRESERVING  stages that must not add or drop rows keep the count exactly:
                         t04 -> t05 -> t06 (teams), p102 -> p105 -> p105C -> p106 (players)
    4. NO SHARP DROP   versus the previous SUCCESSFUL run of the same season, a count may
                       grow freely (early season: ~280 teams -> 365 as teams tip off)
                       but may not fall by more than MAX_DROP. Counts are recorded only
                       when a run completes, so a failed run never becomes the baseline.

There is deliberately no "equals an expected constant" check.
"""

import json
from pathlib import Path

import pandas as pd

from pipeline import guard

MAX_DROP = 0.10            # a count may fall at most 10% vs the previous successful run
MIN_JOIN_RETENTION = 0.98  # frozen seasons: 1.000 for every join


class RowCountError(RuntimeError):
    pass


def _rows(path, header=True):
    path = Path(path)
    if not path.exists():
        raise RowCountError(f"expected output is missing: {path}")
    return len(pd.read_csv(path, header=0 if header else None, usecols=[0], low_memory=False))


# ---------------------------------------------------------------------------
# What each step produces
# ---------------------------------------------------------------------------

def _fetch_counts(year, paths):
    return {
        "raw_team_tables": _rows(paths.raw_team_tables(year)),
        "raw_shooting_splits": _rows(paths.raw_shooting_splits(year)),
        "raw_player_stats": _rows(paths.raw_player(year), header=False),
    }


STAGE_OUTPUTS = {
    "t02_clean_shooting_splits": "team_shooting_splits",
    "t02_clean_team_stats": "team_stats_full_season",
    "t04_merge_master_team": "master_team",
    "t05_feature_engineering": "master_team_fe",
    "t06_team_profiles": "team_profiles",
    "p102_clean_player_stats": "player_stats",
    "p105_feature_engineering": "player_fe",
    "p105c_column_trim": "player_trimmed",
    "p106_player_profiles": "player_profiles",
}

# stage output -> the earlier output whose row count it must equal exactly
ROW_PRESERVING = {
    "master_team_fe": "master_team",
    "team_profiles": "master_team_fe",
    "player_fe": "player_stats",
    "player_trimmed": "player_fe",
    "player_profiles": "player_trimmed",
}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_join_retention(step, year, paths, counts):
    if step == "t04_merge_master_team":
        smaller = min(counts["team_stats_full_season"], counts["team_shooting_splits"])
        kept = counts["master_team"]
        if smaller and kept / smaller < MIN_JOIN_RETENTION:
            raise RowCountError(
                f"{year} t04: inner join kept {kept} of {smaller} rows "
                f"(team_stats={counts['team_stats_full_season']}, "
                f"shooting_splits={counts['team_shooting_splits']}) — team keys no longer match?"
            )
    if step == "p105_feature_engineering":
        fe = pd.read_csv(paths.stage_file("player_fe", year), usecols=["full_season_games"])
        matched = fe["full_season_games"].notna().mean() if len(fe) else 0.0
        if matched < MIN_JOIN_RETENTION:
            raise RowCountError(
                f"{year} p105: only {matched:.1%} of player rows matched a team in the team "
                f"profiles (left join on team+year) — team keys no longer match?"
            )


def check_after(step, year, paths, counts, previous):
    """Run the invariants for `step`. `counts` (this run so far) is updated in place.
    `previous` is the last successful run's counts for this season (or {})."""
    if step == "fetch_current":
        new = _fetch_counts(year, paths)
    elif step in STAGE_OUTPUTS:
        key = STAGE_OUTPUTS[step]
        new = {key: _rows(paths.stage_file(key, year))}
    else:
        return {}
    counts.update(new)

    for label, n in new.items():
        if n == 0:
            raise RowCountError(f"{year} {step}: {label} has 0 rows")
        before = previous.get(label)
        if before and n < before * (1 - MAX_DROP):
            raise RowCountError(
                f"{year} {step}: {label} fell from {before} (previous successful run) to {n} "
                f"(> {MAX_DROP:.0%} drop)"
            )
        must_equal = ROW_PRESERVING.get(label)
        if must_equal and must_equal in counts and n != counts[must_equal]:
            raise RowCountError(
                f"{year} {step}: {label} has {n} rows but {must_equal} had {counts[must_equal]} "
                f"— this stage must not add or drop rows"
            )

    _check_join_retention(step, year, paths, counts)
    return new


# ---------------------------------------------------------------------------
# Previous-successful-run baseline (lives next to the run reports, in the out root)
# ---------------------------------------------------------------------------

def history_file(paths, year):
    return Path(paths.out_root) / "run_state" / f"row_counts_{year}.json"


def load_previous(paths, year):
    f = history_file(paths, year)
    if not f.exists():
        return {}
    return json.loads(f.read_text()).get("counts", {})


def record_success(paths, year, counts, finished):
    payload = {"year": year, "finished": finished, "counts": counts}
    return guard.write_text(history_file(paths, year), json.dumps(payload, indent=2), season=None)
