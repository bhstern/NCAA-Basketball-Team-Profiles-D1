"""
Player identifiers — the single definition used by p105 AND the player-history index.

Copied unchanged from Scripts/105_master_player_dataset_feature_engineering.py. Both
callers must build IDs from the same code, or the history index would silently stop
matching the season being built.
"""

import hashlib

import pandas as pd

# ------------------------------------------------------------
# PLAYER IDENTIFIERS — HYBRID FORMAT (FINAL)
# ------------------------------------------------------------
# player_id:
#   Stable across seasons
#   NAME + BIRTHDAY + short hash
#
# player_season_id:
#   Unique per player per season
#   NAME + BIRTHDAY + TEAM + YEAR + short hash
#
# Birthday is cleaned BEFORE ID creation.


def clean_birthday(series):
    # Clean birthday first (remove timestamp, handle errors)
    return pd.to_datetime(series, errors="coerce").dt.date


def make_player_id(r):
    base = (
        r["name"].upper().replace(" ", "") +
        "_" +
        str(r["birthday"])
    )
    h = hashlib.md5(base.encode()).hexdigest()[:6]
    return base + "_" + h


def make_player_season_id(r):
    base = (
        r["name"].upper().replace(" ", "") +
        "_" +
        str(r["birthday"]) +
        "_" +
        r["team"].upper().replace(" ", "") +
        "_" +
        str(r["year"])
    )
    h = hashlib.md5(base.encode()).hexdigest()[:6]
    return base + "_" + h


def add_player_ids(player):
    """Clean birthday, then add player_id and player_season_id (in place, as the original)."""
    player["birthday"] = clean_birthday(player["birthday"])
    player["player_id"] = player.apply(make_player_id, axis=1)
    player["player_season_id"] = player.apply(make_player_season_id, axis=1)
    return player
