"""
p107 — Player profiles CSV -> site JSON (one season)
----------------------------------------------------
Year-scoped port of the repo's convert_player_data.py, Parts 1, 2 and 4:

    layer1_rosters/rosters_{Y}.json      written for the season
    layer2_explorer/players_{Y}.json     written for the season
    layer3_positional/*                  this season's slice saved as a fragment

Parts 3 (per-player career files) and 5 (players_index.json) span every season by
nature; they are built by pipeline.assemble_json. Output goes to <out_root>/json/,
mirroring the repo layout — never into the repo.

Usage:
    python -m pipeline.player.p107_convert_player_json --year 2018 [--year 2023 ...]
"""

import os

import pandas as pd
import numpy as np

from pipeline.player.json_common import (
    clean_for_json, get_explorer_cols, get_roster_cols, POSITIONAL_STATS,
    write_fragment, write_json,
)
from pipeline.stage import stage_main


def run(year, paths):
    season = year   # the original's loops reuse the name `year`

    print("Loading player profiles dataset...")
    df = pd.read_csv(paths.stage_file("player_profiles", season), low_memory=False)
    print(f"  {len(df):,} rows, {len(df.columns):,} columns")

    # ============================================================
    # PART 1 — LAYER 1: ROSTER FILES
    # ============================================================

    print("\n--- PART 1: Layer 1 Roster Files ---")

    roster_cols = get_roster_cols(df.columns)
    df_roster = clean_for_json(df[roster_cols + ['team', 'year']].copy())

    years = sorted(df['year'].unique())
    for year in years:
        yr_df = df_roster[df_roster['year'] == year].drop(columns=['year'])
        roster_dict = {}

        for team, team_df in yr_df.groupby('team'):
            # Sort by mpg_tier order then minutes_per_game desc
            tier_order = {
                'Core Player (26+ MPG)': 0,
                'Primary Rotation (18\u201326 MPG)': 1,
                'Bench Rotation (10\u201318 MPG)': 2,
                'Fringe Rotation (5\u201310 MPG)': 3,
                'End of Bench (0\u20135 MPG)': 4,
            }
            team_df = team_df.copy()
            team_df['_tier_sort'] = team_df['mpg_tier'].map(tier_order).fillna(5)
            team_df = team_df.sort_values(['_tier_sort', 'minutes_per_game'],
                                           ascending=[True, False])
            team_df = team_df.drop(columns=['_tier_sort'])
            roster_dict[team] = team_df.to_dict(orient='records')

        filepath = write_json(paths.json_file("player_data", "layer1_rosters", f'rosters_{year}.json'),
                              roster_dict, season)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  rosters_{year}.json — {yr_df['team'].nunique()} teams, {size_kb:.0f} KB")

    # ============================================================
    # PART 2 — LAYER 2: EXPLORER FILES
    # ============================================================

    print("\n--- PART 2: Layer 2 Explorer Files ---")

    explorer_cols = get_explorer_cols(df.columns)
    df_explorer = clean_for_json(df[explorer_cols].copy())

    for year in years:
        yr_df = df_explorer[df_explorer['year'] == year]
        records = yr_df.to_dict(orient='records')

        filepath = write_json(paths.json_file("player_data", "layer2_explorer", f'players_{year}.json'),
                              records, season)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  players_{year}.json — {len(records):,} players, {size_kb:.0f} KB")

    # ============================================================
    # PART 4 — LAYER 3: POSITIONAL AVERAGES (this season's slice)
    # ============================================================

    print("\n--- PART 4: Layer 3 Positional Averages ---")

    # Only use Tier 1 players for benchmark calculations
    df_t1 = df[df['percentile_tier'] == 'Tier 1'].copy()

    team_positional = {}   # team averages only
    benchmarks_out  = {}   # benchmarks separate — national/conf/power/mid

    for year in years:
        year_str = str(year)
        team_positional[year_str] = {}
        benchmarks_out[year_str]  = {}

        yr_df = df[df['year'] == year].copy()
        yr_t1 = df_t1[df_t1['year'] == year].copy()

        # --- BENCHMARKS (Tier 1 only, stored separately) ---
        for pos in ['Guard', 'Wing', 'Big']:
            pos_t1 = yr_t1[yr_t1['position'] == pos]
            if pos_t1.empty:
                continue

            nat_avg   = {}
            pow_avg   = {}
            mid_avg   = {}
            conf_avgs = {}

            for stat in POSITIONAL_STATS:
                if stat not in pos_t1.columns:
                    continue
                vals = pos_t1[stat].dropna()
                nat_avg[stat] = round(float(vals.mean()), 4) if len(vals) > 0 else None

                pow_vals = pos_t1[pos_t1['power_mid'] == 'Power'][stat].dropna()
                pow_avg[stat] = round(float(pow_vals.mean()), 4) if len(pow_vals) > 0 else None

                mid_vals = pos_t1[pos_t1['power_mid'] == 'Mid-Major'][stat].dropna()
                mid_avg[stat] = round(float(mid_vals.mean()), 4) if len(mid_vals) > 0 else None

            for conf in pos_t1['conference'].unique():
                conf_pos = pos_t1[pos_t1['conference'] == conf]
                conf_avgs[conf] = {}
                for stat in POSITIONAL_STATS:
                    if stat not in conf_pos.columns:
                        continue
                    vals = conf_pos[stat].dropna()
                    conf_avgs[conf][stat] = round(float(vals.mean()), 4) if len(vals) > 0 else None

            benchmarks_out[year_str][pos] = {
                'national':   nat_avg,
                'power':      pow_avg,
                'mid_major':  mid_avg,
                'conference': conf_avgs,
            }

        # --- TEAM AVERAGES (minutes-weighted, all players) ---
        for team, team_df in yr_df.groupby('team'):
            team_positional[year_str][team] = {}

            for pos in ['Guard', 'Wing', 'Big']:
                pos_df = team_df[team_df['position'] == pos].copy()
                if pos_df.empty:
                    team_positional[year_str][team][pos] = None
                    continue

                pos_df    = pos_df.dropna(subset=['minutes_played'])
                total_min = pos_df['minutes_played'].sum()

                if total_min == 0:
                    team_positional[year_str][team][pos] = None
                    continue

                team_pos_avgs = {}
                for stat in POSITIONAL_STATS:
                    if stat not in pos_df.columns:
                        continue
                    stat_vals = pos_df[stat].fillna(0)
                    weighted  = (stat_vals * pos_df['minutes_played']).sum() / total_min
                    team_pos_avgs[stat] = round(float(weighted), 4)

                team_pos_avgs['player_count']   = len(pos_df)
                team_pos_avgs['total_minutes']  = round(float(total_min), 1)

                team_positional[year_str][team][pos] = team_pos_avgs

    # ONE-SEASON PORT: this season's slice of team_positional.json and
    # positional_benchmarks.json, saved as fragments; pipeline.assemble_json merges the
    # seasons in year order and applies the NaN scrub, as the original's single write did.
    write_fragment(paths.json_fragment(season, "team_positional.json"), team_positional, season)
    write_fragment(paths.json_fragment(season, "positional_benchmarks.json"), benchmarks_out, season)
    print(f"  {season}: positional fragments written")


if __name__ == "__main__":
    stage_main(run, __doc__)
