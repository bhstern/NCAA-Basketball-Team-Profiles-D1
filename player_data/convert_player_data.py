"""
convert_player_data.py
----------------------
Converts the player profiles CSV into JSON files for the site.

Outputs:
    layer1_rosters/
        rosters_{year}.json      — roster cards per team, embedded stats for
                                   team profile roster tab (~60 cols per player)

    layer2_explorer/
        players_{year}.json      — full explorer + profile data per year
                                   (~316 cols, powers Views 2, 3, 5, 6)

    layer2_profiles/
        player_{player_id}.json  — full career file per player, all seasons
                                   (powers View 2 career timeline)

    layer3_positional/
        team_positional.json     — minutes-weighted position group averages
                                   per team per year + benchmarks
                                   (powers Views 4, 7, 8)

    players_index.json           — lightweight player lookup for search/autocomplete

Run this after 106_master_player_profiles.py produces the profiles CSV.
Re-run whenever player data is updated.
"""

import pandas as pd
import numpy as np
import json
import os

# ============================================================
# PATHS
# ============================================================

INPUT_PATH = (
    "/Users/benjstern/Documents/CBB Analytics/Data/Master Datasets/"
    "2016-2026 CBB Dataset Player Profiles.csv"
)

BASE_OUTPUT = (
    "/Users/benjstern/Documents/CBB Analytics/"
    "NCAA-Basketball-Team-Profiles-D1/player_data"
)

ROSTERS_DIR    = os.path.join(BASE_OUTPUT, "layer1_rosters")
EXPLORER_DIR   = os.path.join(BASE_OUTPUT, "layer2_explorer")
PROFILES_DIR   = os.path.join(BASE_OUTPUT, "layer2_profiles")
POSITIONAL_DIR = os.path.join(BASE_OUTPUT, "layer3_positional")

for d in [ROSTERS_DIR, EXPLORER_DIR, PROFILES_DIR, POSITIONAL_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# LOAD
# ============================================================

print("Loading player profiles dataset...")
df = pd.read_csv(INPUT_PATH, low_memory=False)
print(f"  {len(df):,} rows, {len(df.columns):,} columns")

# ============================================================
# COLUMN DEFINITIONS
# ============================================================

# --- LAYER 1: Roster card columns ---
# Frozen identifiers (visible all tabs)
ROSTER_IDENTIFIERS = [
    'player_id', 'name', 'position', 'class', 'years_in_d1',
    'height_in', 'games', 'minutes_per_game', 'mpg_tier',
    'percentile_tier', 'percentile_eligible',
]

# Tab 1 — Overview stats (raw + national pct)
ROSTER_TAB1_STATS = [
    'ppg', 'rebpg', 'astpg', 'blkpg', 'stlpg',
    'ts', 'usage_pct', 'prpg', 'bpm', 'obpm', 'dbpm',
]

# Tab 2 — Role/Advanced stats (raw + national pct)
ROSTER_TAB2_STATS = [
    'ortg', 'ortg_delta_team', 'drtg', 'drtg_delta_team', 'ppp_used',
    'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
    'blk_pct', 'stl_pct', 'ast_tov_ratio', 'foul_sensitivity',
]

# Tab 3 — Shooting stats (raw + national pct where applicable)
ROSTER_TAB3_STATS = [
    'ts',
    'rim_rate', 'rim_fg_pct', 'rim_made_pg', 'rim_att_pg',
    'midrange_rate', 'midrange_fg_pct', 'midrange_made_pg', 'midrange_att_pg',
    'three_rate', 'three_fg_pct', 'three_made_pg', 'three_att_pg',
    'ft_rate', 'ft_pct', 'ft_made_pg', 'ft_att_pg',
]

# String columns — display only, no percentile
ROSTER_STRING_COLS = [
    'rim_made_pg', 'rim_att_pg',
    'midrange_made_pg', 'midrange_att_pg',
    'three_made_pg', 'three_att_pg',
    'ft_made_pg', 'ft_att_pg',
]

ALL_ROSTER_STATS = list(dict.fromkeys(
    ROSTER_TAB1_STATS + ROSTER_TAB2_STATS + ROSTER_TAB3_STATS
))

def get_roster_cols(df_cols):
    """Build full Layer 1 column list — raw + national pct for ranked stats."""
    cols = list(ROSTER_IDENTIFIERS)
    for stat in ALL_ROSTER_STATS:
        if stat in df_cols:
            cols.append(stat)
        pct_col = f'{stat}_pct'
        if pct_col in df_cols and stat not in ROSTER_STRING_COLS:
            cols.append(pct_col)
    return [c for c in cols if c in df_cols]

# --- LAYER 2: Explorer columns ---
# Identifiers
EXPLORER_IDENTIFIERS = [
    'player_id', 'player_season_id', 'player_id_collision',
    'name', 'team', 'conference', 'power_mid', 'year',
    'position', 'role', 'class', 'years_in_d1',
    'height_in', 'age', 'games',
    'minutes_per_game', 'mpg_tier', 'usage_tier', 'games_tier',
    'percentile_tier', 'percentile_eligible',
    'hometown_city', 'hometown_state',
]

# Ranked stats for explorer — 59 stats, each with raw + 4 pct contexts
EXPLORER_RANKED_STATS = [
    # Playing time
    'minutes_per_game', 'usage_pct',
    # Core impact
    'ortg', 'drtg', 'bpm', 'obpm', 'dbpm', 'prpg', 'oprpg', 'dprpg',
    # Rate/role
    'efg', 'ts', 'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
    'blk_pct', 'stl_pct', 'ft_rate', 'ast_tov_ratio',
    # Per game box score
    'ppg', 'rebpg', 'astpg', 'stlpg', 'blkpg',
    # Shooting %s
    'total_fg_pct', 'two_fg_pct', 'three_fg_pct', 'ft_pct',
    'rim_fg_pct', 'midrange_fg_pct',
    # Shot rates
    'rim_rate', 'midrange_rate', 'three_rate',
    # Per game shooting
    'three_att_pg', 'three_made_pg',
    'rim_att_pg', 'rim_made_pg',
    'midrange_att_pg', 'midrange_made_pg',
    'ft_att_pg', 'ft_made_pg',
    # Per 40
    'pts_per_40', 'reb_per_40', 'ast_per_40',
    'stl_per_40', 'blk_per_40', 'stocks_per_40', 'fc_40',
    # Advanced
    'ppp_used', 'tov_sensitivity', 'foul_sensitivity', 'three_p_per_100',
    # Deltas
    'ortg_delta_team', 'drtg_delta_team', 'ts_delta_team',
    'ortg_delta_conf', 'drtg_delta_conf', 'ts_delta_conf',
]

EXPLORER_PCT_SUFFIXES = ['_pct', '_sub_pct', '_pos_pct', '_pos_sub_pct']

def get_explorer_cols(df_cols):
    """Build Layer 2 column list — identifiers + raw + 4 pct contexts per stat."""
    seen = set()
    cols = []
    for c in EXPLORER_IDENTIFIERS:
        if c in df_cols and c not in seen:
            cols.append(c)
            seen.add(c)
    for stat in EXPLORER_RANKED_STATS:
        if stat in df_cols and stat not in seen:
            cols.append(stat)
            seen.add(stat)
        for suffix in EXPLORER_PCT_SUFFIXES:
            col = f'{stat}{suffix}'
            if col in df_cols and col not in seen:
                cols.append(col)
                seen.add(col)
    return cols

# --- LAYER 2 PROFILES: Full profile columns ---
# Everything EXCEPT dropped columns
PROFILE_DROP_COLS = [
    'height_str',        # JS formats height_in
    'minutes_pct',       # redundant with minutes_per_game
    'class_num',         # numeric encoding of class, not needed in JS
    'total_points',      # games-dependent, ppg covers it
    'total_reb',         # same
    'total_ast',         # same
    'ast_to_ratio',      # exact duplicate of ast_tov_ratio
    # Sub deltas — not meaningful for any view
    'ortg_delta_sub', 'drtg_delta_sub', 'ts_delta_sub',
    'efg_delta_sub', 'rim_rate_delta_sub', 'three_rate_delta_sub',
    # Redundant delta variants
    'efg_delta_team', 'efg_delta_conf',
    'rim_rate_delta_team', 'rim_rate_delta_conf',
    'three_rate_delta_team', 'three_rate_delta_conf',
    # Team context averages — not needed in player JSON
    'conf_team_ts', 'conf_team_efg', 'conf_team_rim_rate', 'conf_team_three_rate',
    'conf_adj_o', 'conf_adj_d',
    'sub_team_ts', 'sub_team_efg', 'sub_team_rim_rate', 'sub_team_three_rate',
    'sub_adj_o', 'sub_adj_d',
    # Sub percentile/rank/z columns — all derived sub context columns
]

def get_profile_cols(df_cols):
    """Build full profile column list — everything minus dropped cols and sub derived."""
    drop_set = set(PROFILE_DROP_COLS)
    cols = []
    for c in df_cols:
        if c in drop_set:
            continue
        # Drop all sub-derived columns (sub z/pct/rank and pos_sub z/pct/rank)
        if any(c.endswith(s) for s in ['_sub_z', '_sub_pct', '_sub_rank',
                                        '_pos_sub_z', '_pos_sub_pct', '_pos_sub_rank']):
            continue
        cols.append(c)
    return cols

# --- LAYER 3: Positional averages stats ---
POSITIONAL_STATS = [
    'ortg', 'drtg', 'bpm', 'obpm', 'dbpm', 'prpg', 'oprpg', 'dprpg',
    'efg', 'ts', 'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
    'blk_pct', 'stl_pct', 'ft_rate', 'ast_tov_ratio',
    'ppg', 'rebpg', 'astpg', 'stlpg', 'blkpg',
    'total_fg_pct', 'two_fg_pct', 'three_fg_pct', 'ft_pct',
    'rim_fg_pct', 'midrange_fg_pct',
    'rim_rate', 'midrange_rate', 'three_rate',
    'three_att_pg', 'rim_att_pg', 'ft_att_pg',
    'pts_per_40', 'reb_per_40', 'ast_per_40',
    'ppp_used', 'tov_sensitivity', 'foul_sensitivity',
    'ortg_delta_team', 'drtg_delta_team', 'ts_delta_team',
]

# ============================================================
# HELPER: CLEAN FOR JSON
# ============================================================

def clean_for_json(df_in):
    """Round numerics, replace NaN/inf with None for JSON serialization."""
    df_out = df_in.copy()
    # Remove any duplicate columns before processing
    df_out = df_out.loc[:, ~df_out.columns.duplicated()]
    numeric_cols = df_out.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df_out[col] = df_out[col].round(4)
    # Replace inf
    df_out.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df_out.where(pd.notnull(df_out), other=None)

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
            'Primary Rotation (18–26 MPG)': 1,
            'Bench Rotation (10–18 MPG)': 2,
            'Fringe Rotation (5–10 MPG)': 3,
            'End of Bench (0–5 MPG)': 4,
        }
        team_df = team_df.copy()
        team_df['_tier_sort'] = team_df['mpg_tier'].map(tier_order).fillna(5)
        team_df = team_df.sort_values(['_tier_sort', 'minutes_per_game'],
                                       ascending=[True, False])
        team_df = team_df.drop(columns=['_tier_sort'])
        records = team_df.to_dict(orient='records')
        roster_dict[team] = [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in records]

    filepath = os.path.join(ROSTERS_DIR, f'rosters_{year}.json')
    with open(filepath, 'w') as f:
        json.dump(roster_dict, f, separators=(',', ':'))

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
    records = [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in records]
    filepath = os.path.join(EXPLORER_DIR, f'players_{year}.json')
    with open(filepath, 'w') as f:
        json.dump(records, f, separators=(',', ':'))

    size_kb = os.path.getsize(filepath) / 1024
    print(f"  players_{year}.json — {len(records):,} players, {size_kb:.0f} KB")

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

    filepath = os.path.join(PROFILES_DIR, f'player_{player_id}.json')
    with open(filepath, 'w') as f:
        json.dump(career, f, separators=(',', ':'))

    player_count += 1
    if player_count % 2000 == 0:
        print(f"  {player_count:,} player files written...")

# Write collision players as individual season files (no career grouping)
collision_count = 0
for _, row in df_collide.iterrows():
    season_id = row.get('player_season_id', f"collision_{collision_count}")
    filepath = os.path.join(PROFILES_DIR, f'player_{season_id}_collision.json')
    with open(filepath, 'w') as f:
        json.dump(row.to_dict(), f, separators=(',', ':'))
    collision_count += 1

print(f"  {player_count:,} career files written")
print(f"  {collision_count} collision season files written")

# ============================================================
# PART 4 — LAYER 3: POSITIONAL AVERAGES
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

# Save team averages
team_pos_path = os.path.join(POSITIONAL_DIR, 'team_positional.json')
with open(team_pos_path, 'w') as f:
    json.dump(team_positional, f, separators=(',', ':'))
size_mb = os.path.getsize(team_pos_path) / 1024 / 1024
print(f"  team_positional.json — {size_mb:.1f} MB")

# Save benchmarks separately
bench_path = os.path.join(POSITIONAL_DIR, 'positional_benchmarks.json')
with open(bench_path, 'w') as f:
    json.dump(benchmarks_out, f, separators=(',', ':'))
size_mb = os.path.getsize(bench_path) / 1024 / 1024
print(f"  positional_benchmarks.json — {size_mb:.1f} MB")

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
                  ])
                  .reset_index()
                  .rename(columns={0: 'history'}))

df_index = df_latest.merge(team_history, on='player_id', how='left')
df_index = clean_for_json(df_index)

index_records = df_index.to_dict(orient='records')

index_path = os.path.join(BASE_OUTPUT, 'players_index.json')
with open(index_path, 'w') as f:
    json.dump(index_records, f, separators=(',', ':'))

size_kb = os.path.getsize(index_path) / 1024
print(f"  players_index.json — {len(index_records):,} players, {size_kb:.0f} KB")

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "="*60)
print("CONVERT PLAYER DATA COMPLETE")
print("="*60)
print(f"\nLayer 1  — {len(years)} roster files → {ROSTERS_DIR}")
print(f"Layer 2  — {len(years)} explorer files → {EXPLORER_DIR}")
print(f"Layer 2  — {player_count:,} player profile files → {PROFILES_DIR}")
print(f"Layer 3  — 1 positional file → {POSITIONAL_DIR}")
print(f"Index    — 1 search index → {BASE_OUTPUT}")
print(f"\nAll files saved to: {BASE_OUTPUT}")