"""
Season status — the ONE source of truth for whether a season's player percentiles are
shown on the site (Phase 5). Written into data/index.json under "_seasons" by assemble;
every frontend percentile view reads that flag instead of hard-coding a threshold.

Percentile scales are built from the Tier 1 pool only (games >= 10 AND mpg >= 10, as
p106 assigns `percentile_tier`). Early in a season the pool is empty or tiny, so
percentiles do not appear when a player reaches 5 games: they appear once enough players
league-wide reach 10 games (realistically mid-December).

    percentiles_active = Tier 1 players this season >= POOL_FRACTION x prior season's Tier 1

A proportion of the prior season's complete pool self-calibrates as D1 changes size
(frozen seasons have 2,969-3,288 Tier 1 players; 50% of 2026's 3,288 is 1,644 for 2027).
It is the only knob; the site self-corrects the day the count crosses it.

The first season in the data (2016) has no prior season; it is a complete frozen season,
so it is measured against its own pool (always active).
"""

import math

import pandas as pd

POOL_FRACTION = 0.5


def tier1_count(profiles_csv):
    df = pd.read_csv(profiles_csv, usecols=["percentile_tier"], low_memory=False)
    return int((df["percentile_tier"] == "Tier 1").sum())


def season_status(profiles_csv, prior_profiles_csv=None):
    tier1 = tier1_count(profiles_csv)
    reference = tier1_count(prior_profiles_csv) if prior_profiles_csv is not None else tier1
    min_pool = math.ceil(POOL_FRACTION * reference)
    return {
        "percentiles_active": tier1 >= min_pool,
        "tier1_players": tier1,
        "min_tier1_pool": min_pool,
    }
