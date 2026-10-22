"""
Assemble the multi-season site JSON from per-season outputs (validation path).
------------------------------------------------------------------------------
Some site files cover every season at once. This step builds them inside the
sandbox from what the per-season stages produced:

    data/index.json                              merged from t07's per-season fragments
    player_data/layer3_positional/
        team_positional.json                     merged from p107's per-season fragments
        positional_benchmarks.json               merged from p107's per-season fragments
    player_data/layer2_profiles/player_*.json    convert_player_data.py Part 3, unchanged
    player_data/players_index.json               convert_player_data.py Part 5, unchanged

Parts 3 and 5 are cross-season by nature (a career file holds every season of a
player; the index takes each player's latest season, and the original's unstable
`sort_values('year')` over all rows decides ties). They run unchanged on the
per-season player_profiles files stitched back together at text level, so they see
exactly the frame the original saw. The nightly current-season design for career
files (per-team shards) is deferred; this assembly is for proving the rebuild.

Writes ONLY inside the _rebuild sandbox: every write passes season=None, which the
frozen-history guard allows in a sandbox and refuses everywhere else.

Usage:
    python -m pipeline.assemble_json                 (all frozen seasons)
"""

import argparse
import json
import os
import shutil

import pandas as pd
import numpy as np

from pipeline import config, guard
from pipeline.dev.stitch import stitch
from pipeline.paths import Paths
from pipeline.player.json_common import clean_for_json, get_profile_cols, write_json


def merge_fragments(name, years, source):
    """Per-season dict fragments -> one dict, seasons in year order (as the original built it)."""
    merged = {}
    for year in sorted(years):
        merged.update(json.loads(source(year).json_fragment(year, name).read_text(encoding="utf-8")))
    return merged


def assemble_team_index(years, paths, source):
    out = write_json(paths.json_file("data", "index.json"), merge_fragments("team_index.json", years, source), None,
                     scrub=False)   # convert_data.py has no NaN scrub
    print(f"  index.json saved -> {out}")


def assemble_positional(years, paths, source):
    for name in ("team_positional.json", "positional_benchmarks.json"):
        out = write_json(paths.json_file("player_data", "layer3_positional", name),
                         merge_fragments(name, years, source), None)
        print(f"  {name} — {os.path.getsize(out) / 1024 / 1024:.1f} MB -> {out}")


def fresh_profiles_dir(paths):
    """Career files are rebuilt from scratch so no stale file from an earlier run survives."""
    target = guard.check(paths.json_file("player_data", "layer2_profiles"), season=None)
    if os.path.realpath(config.REBUILD_ROOT) not in [str(p) for p in target.parents]:
        raise PermissionError(f"Refusing to clear a folder outside the _rebuild sandbox: {target}")
    if target.exists():
        shutil.rmtree(target)
    return target


def assemble_player_cross_season(years, paths, source):
    profiles_csv = stitch("player_profiles", years, paths, source)
    fresh_profiles_dir(paths)

    print("Loading player profiles dataset (stitched)...")
    df = pd.read_csv(profiles_csv, low_memory=False)
    print(f"  {len(df):,} rows, {len(df.columns):,} columns")

    # ============================================================
    # PART 3 — LAYER 2 PROFILES: PER-PLAYER CAREER FILES
    # ============================================================

    print("\n--- PART 3: Layer 2 Profile Files (per player) ---")

    profile_cols = get_profile_cols(df.columns)
    df_profiles = clean_for_json(df[profile_cols].copy())

    # Separate collision players
    collision_ids = set(
        df[df['player_id_collision'] == True]['player_id'].unique()
    )
    print(f"  Collision players excluded from career files: {len(collision_ids)}")

    df_clean    = df_profiles[~df_profiles['player_id'].isin(collision_ids)]
    df_collide  = df_profiles[df_profiles['player_id'].isin(collision_ids)]

    # Write per-player career files
    player_count = 0
    for player_id, player_df in df_clean.groupby('player_id'):
        # Sort seasons chronologically
        player_df = player_df.sort_values('year')
        seasons = player_df.to_dict(orient='records')

        # Build career file
        career = {
            'player_id': player_id,
            'name': seasons[0].get('name'),
            'seasons': seasons,
        }

        write_json(paths.json_file("player_data", "layer2_profiles", f'player_{player_id}.json'),
                   career, None)

        player_count += 1
        if player_count % 2000 == 0:
            print(f"  {player_count:,} player files written...")

    # Write collision players as individual season files (no career grouping)
    collision_count = 0
    for _, row in df_collide.iterrows():
        season_id = row.get('player_season_id', f"collision_{collision_count}")
        write_json(paths.json_file("player_data", "layer2_profiles", f'player_{season_id}_collision.json'),
                   row.to_dict(), None)
        collision_count += 1

    print(f"  {player_count:,} career files written")
    print(f"  {collision_count} collision season files written")

    # ============================================================
    # PART 5 — PLAYER SEARCH INDEX
    # ============================================================

    print("\n--- PART 5: Player Search Index ---")

    # Lightweight lookup — most recent season per player
    index_cols = ['player_id', 'name', 'position', 'team', 'conference',
                  'power_mid', 'year', 'class', 'height_in']
    index_cols = [c for c in index_cols if c in df.columns]

    # Get most recent season per player (for search display)
    df_latest = (df.sort_values('year')
                   .groupby('player_id')
                   .last()
                   .reset_index()[index_cols])

    # Also include all team/year combos for each player (for search routing)
    team_history = (df.groupby('player_id')
                      .apply(lambda x: [
                          {'year': int(r['year']), 'team': r['team']}
                          for _, r in x.sort_values('year').iterrows()
                      ], include_groups=False)
                      .reset_index()
                      .rename(columns={0: 'history'}))

    df_index = df_latest.merge(team_history, on='player_id', how='left')
    df_index = clean_for_json(df_index)

    index_records = df_index.to_dict(orient='records')

    index_path = write_json(paths.json_file("player_data", "players_index.json"), index_records, None,
                            scrub=False)   # never scrubbed by the original

    size_kb = os.path.getsize(index_path) / 1024
    print(f"  players_index.json — {len(index_records):,} players, {size_kb:.0f} KB")


def run(years, paths=None, source=None):
    """Assemble into `paths`. `source(year) -> Paths` says where each season's per-season
    outputs live (default: `paths`) — e.g. the frozen seasons from the main sandbox and
    the season just built from the run's own output root."""
    paths = paths or Paths()
    source = source or (lambda year: paths)
    print("\n--- Team index ---")
    assemble_team_index(years, paths, source)
    print("\n--- Positional files ---")
    assemble_positional(years, paths, source)
    print("\n--- Career files + players index ---")
    assemble_player_cross_season(years, paths, source)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, action="append", help="default: all frozen seasons")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()
    run(sorted(args.year or config.FROZEN_SEASONS), Paths(out_root=args.out_root))


if __name__ == "__main__":
    main()
