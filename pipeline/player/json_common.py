"""
Shared definitions for the player JSON converters — copied unchanged from the repo's
convert_player_data.py (column lists, column builders, clean_for_json).

One change of mechanism, not of output: the original wrote every file and then ran
scrub_nan_dir() over the folder (NaN -> null). Here the identical replacement is
applied to each file's text before it is written, and every write goes through the
frozen-history guard.
"""

import json

import numpy as np
import pandas as pd

from pipeline import guard

# ============================================================
# COLUMN DEFINITIONS
# ============================================================

# --- LAYER 1: Roster card columns ---
# Frozen identifiers (visible all tabs)
ROSTER_IDENTIFIERS = [
    'player_id', 'name', 'position', 'role', 'class', 'years_in_d1',
    'height_in', 'games', 'minutes_per_game', 'mpg_tier',
    'percentile_tier', 'percentile_eligible',
]

# Tab 1 — Overview stats (raw + national pct)
ROSTER_TAB1_STATS = [
    'ppg', 'rebpg', 'astpg', 'blkpg', 'stlpg',
    'ts', 'usage_pct', 'prpg', 'dprpg', 'bpm', 'obpm', 'dbpm',
]

# Tab 2 — Role/Advanced stats (raw + national pct)
ROSTER_TAB2_STATS = [
    'ortg', 'ortg_delta_team', 'drtg', 'drtg_delta_team', 'ppp_used',
    'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
    'blk_pct', 'stl_pct', 'ast_tov_ratio', 'foul_sensitivity',
]

# Tab 3 — Shooting stats (raw + national pct where applicable)
# Uses per-game made/att for FGM/FGA display strings computed in JS
ROSTER_TAB3_STATS = [
    'ppp_used', 'ts', 'efg', 'total_fg_pct', 'fgm_pg', 'fga_pg',
    'rim_rate', 'rim_fg_pct', 'rim_made_pg', 'rim_att_pg',
    'midrange_rate', 'midrange_fg_pct', 'midrange_made_pg', 'midrange_att_pg',
    'three_rate', 'three_fg_pct', 'three_made_pg', 'three_att_pg',
    'ft_rate', 'ft_pct', 'ft_made_pg', 'ft_att_pg',
]

# String columns — display only, no percentile
ROSTER_STRING_COLS = []

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
    # String display columns
    'fg_made_att_str', 'two_made_att_str', 'three_made_att_str',
    'rim_made_att_str', 'close_two_made_att_str', 'midrange_made_att_str',
    'dunk_made_att_str', 'ft_made_att_str',
]

# Ranked stats for explorer — each with raw + 6 pct contexts
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
    'rim_fg_pct', 'close_two_fg_pct', 'midrange_fg_pct', 'dunk_fg_pct',
    # Shot rates
    'rim_rate', 'close_two_rate', 'midrange_rate', 'dunk_rate', 'three_rate',
    # Ratios
    'close_vs_mid_ratio', 'rim_vs_three_ratio',
    # Per game shooting
    'three_att_pg', 'three_made_pg',
    'rim_att_pg', 'rim_made_pg',
    'close_two_att_pg', 'close_two_made_pg',
    'midrange_att_pg', 'midrange_made_pg',
    'dunk_att_pg', 'dunk_made_pg',
    'ft_att_pg', 'ft_made_pg',
    'fga_pg', 'fgm_pg',
    'two_att_pg', 'two_made_pg',
    # Per 40
    'pts_per_40', 'reb_per_40', 'ast_per_40',
    'stl_per_40', 'blk_per_40', 'stocks_per_40', 'fc_40',
    # Advanced
    'ppp_used', 'tov_sensitivity', 'foul_sensitivity', 'three_p_per_100',
    'recruit_rank_clean',
    # Deltas — team
    'ortg_delta_team', 'drtg_delta_team', 'ts_delta_team',
    'efg_delta_team', 'rim_rate_delta_team', 'three_rate_delta_team',
    # Deltas — conf
    'ortg_delta_conf', 'drtg_delta_conf', 'ts_delta_conf',
    'efg_delta_conf', 'rim_rate_delta_conf', 'three_rate_delta_conf',
    # Deltas — sub
    'ortg_delta_sub', 'drtg_delta_sub', 'ts_delta_sub',
    'efg_delta_sub', 'rim_rate_delta_sub', 'three_rate_delta_sub',
]

EXPLORER_PCT_SUFFIXES = ['_pct', '_conf_pct', '_sub_pct', '_pos_pct', '_pos_conf_pct', '_pos_sub_pct']

def get_explorer_cols(df_cols):
    """Build Layer 2 column list — identifiers + raw + 6 pct contexts per stat."""
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
    # Team context averages — not needed in player JSON
    'conf_team_ts', 'conf_team_efg', 'conf_team_rim_rate', 'conf_team_three_rate',
    'conf_adj_o', 'conf_adj_d',
    'sub_team_ts', 'sub_team_efg', 'sub_team_rim_rate', 'sub_team_three_rate',
    'sub_adj_o', 'sub_adj_d',
    # Sub percentile/rank/z columns — all derived sub context columns
]

def get_profile_cols(df_cols):
    drop_set = set(PROFILE_DROP_COLS)
    cols = []
    for c in df_cols:
        if c in drop_set:
            continue
        keep_delta_sub = c.endswith(('_delta_sub_pct','_delta_sub_rank','_delta_sub_z'))
        keep_sub_pct  = c.endswith(('_sub_pct','_pos_sub_pct'))   # power/mid percentile contexts
        if not keep_delta_sub and not keep_sub_pct and any(c.endswith(s) for s in
                ['_sub_z','_sub_pct','_sub_rank','_pos_sub_z','_pos_sub_pct','_pos_sub_rank']):
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
# HELPERS
# ============================================================

def clean_for_json(df_in):
    """Round numerics, replace NaN/inf with None for JSON serialization."""
    df_out = df_in.copy()
    # Remove any duplicate columns before processing
    df_out = df_out.loc[:, ~df_out.columns.duplicated()]
    # Convert categoricals to string to avoid NaN serialization issues
    for col in df_out.select_dtypes(include='category').columns:
        df_out[col] = df_out[col].astype(str).replace('nan', None)
    numeric_cols = df_out.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df_out[col] = df_out[col].round(4)
    # Replace inf and NaN
    df_out.replace([np.inf, -np.inf], np.nan, inplace=True)
    # Force NaN scrub on all columns
    records = df_out.to_dict(orient='records')
    records = [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in records]
    return pd.DataFrame(records)

def scrub_nan_text(raw):
    """scrub_nan_dir, applied to one file's text before it is written (same replacements)."""
    if 'NaN' in raw:
        raw = raw.replace(':NaN,', ':null,').replace(':NaN}', ':null}')
    return raw

def write_json(path, obj, season, scrub=True):
    """json.dump(obj, f, separators=(',', ':')) + the NaN scrub, written through the guard.

    scrub=False for the files the original never scrubbed: players_index.json (written
    to the base folder, which scrub_nan_dir never visited, so its NaN tokens stay) and
    the team index.json (convert_data.py has no scrub)."""
    text = json.dumps(obj, separators=(',', ':'))
    return guard.write_text(path, scrub_nan_text(text) if scrub else text, season=season)

def write_fragment(path, obj, season):
    """A per-season piece of a multi-season file: raw json (NaN kept), scrubbed on assembly."""
    return guard.write_text(path, json.dumps(obj, separators=(',', ':')), season=season)
