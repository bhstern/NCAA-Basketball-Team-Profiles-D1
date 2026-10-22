"""
Player history index — the read-only stand-in for "every other season" in p105.
-------------------------------------------------------------------------------
The original 105 processed 2016-2026 in one frame, and three things in it depend on
seasons other than the one being built:

    player_id_collision  same player_id on two teams in one year, in ANY year
    years_in_d1          how many earlier season-rows the player_id has
    row order            `df.sort_values('year')` is an UNSTABLE sort, so it shuffles
                         rows inside every season; the shuffle depends on the row
                         counts of all 11 seasons

The index holds one row per frozen player-season:

    player_season_id, player_id, year, team, legacy_pos

`legacy_pos` is the row's position within its season after the original's sort. It is
computed here by running the very same `sort_values('year')` over the 11 frozen
seasons stacked in the original's order, and is replayed in p105 keyed on
player_season_id.

Build once from the frozen seasons' p102 output; p105 only ever reads it.

    python -m pipeline.player.history --build            (refuses to overwrite)
    python -m pipeline.player.history --build --force
"""

import argparse

import numpy as np
import pandas as pd

from pipeline import config, guard
from pipeline.paths import Paths
from pipeline.player.ids import add_player_ids

COLUMNS = ["player_season_id", "player_id", "year", "team", "legacy_pos"]


class PlayerHistoryError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Build (once, frozen seasons only)
# ---------------------------------------------------------------------------

def build(paths=None, force=False, source=None):
    """Write the index under `paths`; read the frozen seasons' p102 output from
    `source` (default: `paths`)."""
    paths = paths or Paths()
    source = source or paths
    out = paths.player_history_file
    if out.exists() and not force:
        raise PlayerHistoryError(f"History index already exists (use --force to rebuild): {out}")

    frames = []
    for year in sorted(config.FROZEN_SEASONS):
        player = pd.read_csv(source.stage_file("player_stats", year))
        player = add_player_ids(player)
        wrong = sorted(set(player["year"]) - {year})
        if wrong:
            raise PlayerHistoryError(f"{year}: p102 output contains other seasons {wrong}")
        frames.append(player[["player_season_id", "player_id", "year", "team"]])

    # Same stacking as the original (102 concatenated seasons in year order)
    index = pd.concat(frames, ignore_index=True)

    if not index["player_season_id"].is_unique:
        dupes = index.loc[index["player_season_id"].duplicated(), "player_season_id"].tolist()
        raise PlayerHistoryError(f"player_season_id is not unique, cannot key the order replay: {dupes[:5]}")

    # The original's exact call. Unstable, so rows inside a season come out shuffled;
    # record where each row landed within its season.
    shuffled = index.sort_values("year")
    index.loc[shuffled.index, "legacy_pos"] = shuffled.groupby("year").cumcount().to_numpy()
    index["legacy_pos"] = index["legacy_pos"].astype("int64")

    guard.to_csv(index[COLUMNS], out, season=None, index=False)
    moved = int((index["legacy_pos"] != index.groupby("year").cumcount()).sum())
    print(f"Player history index: {len(index):,} rows, {index['year'].nunique()} seasons, "
          f"{moved:,} rows moved by the original's unstable sort -> {out}")
    return out


# ---------------------------------------------------------------------------
# Read (p105)
# ---------------------------------------------------------------------------

def load(paths):
    path = paths.player_history_file
    if not path.exists():
        raise PlayerHistoryError(
            f"Player history index not found: {path}\n"
            f"Build it once with: python -m pipeline.player.history --build"
        )
    index = pd.read_csv(path)
    if list(index.columns) != COLUMNS:
        raise PlayerHistoryError(f"Unexpected history index columns: {list(index.columns)}")
    return index


def _other_seasons(index, year):
    return index[index["year"] != year]


def check_frozen_season_matches(index, df, year):
    """A frozen season being rebuilt must be exactly the season the index was built from."""
    expected = index.loc[index["year"] == year, "player_season_id"]
    got = df["player_season_id"]
    if len(got) != len(expected) or not got.is_unique or set(got) != set(expected):
        missing = sorted(set(expected) - set(got))[:5]
        extra = sorted(set(got) - set(expected))[:5]
        raise PlayerHistoryError(
            f"{year}: player rows do not match the history index "
            f"({len(got)} rows vs {len(expected)} indexed; not in frame {missing}; not in index {extra})"
        )


def collision_flags(index, player, year):
    """
    TRUE if the same player_id appears on multiple teams in the SAME year, in any
    season: the frozen seasons from the index plus the season being built.
    Returns a boolean Series for the season's rows only.
    """
    seen = pd.concat(
        [_other_seasons(index, year)[["player_id", "year", "team"]],
         player[["player_id", "year", "team"]]],
        ignore_index=True,
    )
    teams_per_year = seen.groupby(["player_id", "year"])["team"].nunique()
    collided = set(teams_per_year[teams_per_year > 1].index.get_level_values("player_id"))
    return player["player_id"].isin(collided)


def order_rows(index, df, year):
    """
    Stand-in for the original's `df = df.sort_values('year')`.

    Frozen season  -> replay the original's shuffle: rows go to their recorded
                      legacy_pos, matched on player_season_id.
    Current season -> an explicit STABLE sort, i.e. raw input order, so the nightly
                      build is bit-reproducible on any machine.
    """
    if year not in config.FROZEN_SEASONS:
        return df.sort_values("year", kind="stable")

    check_frozen_season_matches(index, df, year)
    season = index[index["year"] == year]
    pos = df["player_season_id"].map(season.set_index("player_season_id")["legacy_pos"])
    if pos.isna().any() or sorted(pos.astype("int64")) != list(range(len(df))):
        raise PlayerHistoryError(f"{year}: legacy_pos is not a complete 0..n-1 ordering for this season")
    return df.iloc[np.argsort(pos.to_numpy(dtype="int64"), kind="stable")]


def prior_season_rows(index, df, year):
    """Number of rows each player_id has in seasons BEFORE this one (int64, df-aligned)."""
    earlier = index[index["year"] < year]
    counts = earlier.groupby("player_id").size()
    return df["player_id"].map(counts).fillna(0).astype("int64")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", required=True)
    ap.add_argument("--force", action="store_true", help="overwrite an existing index")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()
    build(Paths(out_root=args.out_root), force=args.force)


if __name__ == "__main__":
    main()
