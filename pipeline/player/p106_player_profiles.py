"""
p106 — Player profiles dataset (one season)
-------------------------------------------
Year-scoped port of Scripts/106_master_player_descriptive_profiles.py. The body below
is the original, unchanged apart from where it reads and writes. The original already
computed everything inside a per-year loop, so the loop is kept and runs once.

Pipeline:
    1. Load trimmed 158-column dataset
    2. Drop 5 redundant columns
    3. Fix class and power_mid values
    4. Add percentile_tier and percentile_eligible flags
    5. Reorder columns into logical groups
    6. Compute descriptive stats across 6 comparison contexts, within the season:
         - National (z, pct, rank)
         - Conference (pct, rank)
         - Power vs Mid-Major (z, pct, rank)
         - Position national (z, pct, rank)
         - Position within conference (pct, rank)
         - Position within sub (z, pct, rank)
    7. Save output

Tier system (as coded): Tier 1 = games >= 10 AND mpg >= 10; Tier 2 = games >= 5 AND
mpg >= 5; everyone else gets no percentile. Dunk exception: dunk_fg_pct requires
dunk_att >= 10 regardless of tier.

KNOWN ISSUES, REPRODUCED ON PURPOSE (spec §6 item 1): the original docstring says
Tier 2 needs games >= 10 but the code uses games >= 5; Tier 2 gets
percentile_eligible = True, which 106B's Check 7 contradicts.

Usage:
    python -m pipeline.player.p106_player_profiles --year 2018 [--year 2023 ...]
"""

import pandas as pd
import numpy as np

from pipeline import guard
from pipeline.stage import stage_main


def run(year, paths):
    season = year   # the original's per-year loop reuses the name `year`

    # ============================================================
    # LOAD TRIMMED DATASET
    # ============================================================

    df = pd.read_csv(paths.stage_file("player_trimmed", season))

    # ============================================================
    # DROP REDUNDANT COLUMNS
    # ============================================================

    drop_cols = ['possessions', 'ast_to_ratio', 'close_two_pct', 'dunk_pct', 'height']
    df = df.drop(columns=drop_cols)

    # ============================================================
    # FIX VALUES
    # ============================================================

    df['class'] = df['class'].replace('--', pd.NA)
    df['power_mid'] = df['power_mid'].replace('Mid', 'Mid-Major')

    # ============================================================
    # PERCENTILE TIER FLAGS
    # ============================================================

    def assign_tier(row):
        if row['games'] >= 10 and row['minutes_per_game'] >= 10:
            return 'Tier 1'
        elif row['games'] >= 5 and row['minutes_per_game'] >= 5:
            return 'Tier 2'
        else:
            return 'None'

    df['percentile_tier'] = df.apply(assign_tier, axis=1)
    df['percentile_eligible'] = df['percentile_tier'].map({
        'Tier 1': True,
        'Tier 2': True,
        'None': False
    })

    # ============================================================
    # REORDER BASE COLUMNS
    # ============================================================

    ordered_cols = [

        # --- Group 1: Identifiers ---
        'player_id', 'player_season_id', 'player_id_collision',
        'name', 'team', 'conference', 'power_mid', 'year',
        'percentile_tier', 'percentile_eligible',

        # --- Group 2: Bio / Physical ---
        'position', 'role', 'class', 'years_in_d1', 'class_num',
        'age', 'height_str', 'height_in',
        'hometown_city', 'hometown_state', 'recruit_rank_clean',

        # --- Group 3: Playing Time ---
        'games', 'games_tier',
        'minutes_played', 'minutes_per_game', 'mpg_tier',
        'minutes_pct', 'usage_pct', 'usage_tier',

        # --- Group 4: Core Impact ---
        'ortg', 'drtg', 'bpm', 'obpm', 'dbpm',
        'prpg', 'oprpg', 'dprpg',

        # --- Group 5: Rate / Role Stats ---
        'efg', 'ts',
        'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
        'blk_pct', 'stl_pct', 'ft_rate', 'ast_tov_ratio',

        # --- Group 6: Per-Game Box Score ---
        'ppg', 'rebpg', 'astpg', 'stlpg', 'blkpg',
        'total_points', 'total_reb', 'total_ast', 'total_stl', 'total_blk',

        # --- Group 7: Shooting ---
        'total_fga', 'total_fgm', 'total_fg_pct', 'fga_pg', 'fgm_pg', 'fg_made_att_str',
        'two_pa', 'two_pm', 'two_fg_pct', 'two_att_pg', 'two_made_pg', 'two_made_att_str',
        'dunk_att', 'dunk_made', 'dunk_fg_pct', 'dunk_att_pg', 'dunk_made_pg', 'dunk_made_att_str', 'dunk_rate',
        'close_two_att', 'close_two_made', 'close_two_fg_pct', 'close_two_att_pg', 'close_two_made_pg', 'close_two_made_att_str', 'close_two_rate',
        'rim_att', 'rim_made', 'rim_fg_pct', 'rim_att_pg', 'rim_made_pg', 'rim_made_att_str', 'rim_rate',
        'midrange_att', 'midrange_made', 'midrange_fg_pct', 'midrange_att_pg', 'midrange_made_pg', 'midrange_made_att_str', 'midrange_rate',
        'three_pa', 'three_pm', 'three_fg_pct', 'three_att_pg', 'three_made_pg', 'three_made_att_str', 'three_rate', 'three_p_per_100',
        'fta', 'ftm', 'ft_pct', 'ft_att_pg', 'ft_made_pg', 'ft_made_att_str',
        'paint_touch_proxy', 'close_vs_mid_ratio', 'rim_vs_three_ratio',

        # --- Group 8: Per-40 ---
        'pts_per_40', 'reb_per_40', 'ast_per_40', 'stl_per_40', 'blk_per_40', 'stocks_per_40', 'fc_40',

        # --- Group 9: Advanced ---
        'ppp_used', 'tov_sensitivity', 'foul_sensitivity',

        # --- Group 10: Contextual Deltas ---
        'ortg_delta_team', 'drtg_delta_team', 'ts_delta_team', 'efg_delta_team', 'rim_rate_delta_team', 'three_rate_delta_team',
        'ortg_delta_conf', 'drtg_delta_conf', 'ts_delta_conf', 'efg_delta_conf', 'rim_rate_delta_conf', 'three_rate_delta_conf',
        'ortg_delta_sub',  'drtg_delta_sub',  'ts_delta_sub',  'efg_delta_sub',  'rim_rate_delta_sub',  'three_rate_delta_sub',

        # --- Group 11: Team Context ---
        'team_ts',
        'conf_team_ts', 'conf_team_efg', 'conf_team_rim_rate', 'conf_team_three_rate',
        'conf_adj_o', 'conf_adj_d',
        'sub_team_ts', 'sub_team_efg', 'sub_team_rim_rate', 'sub_team_three_rate',
        'sub_adj_o', 'sub_adj_d',
    ]

    df = df[ordered_cols].copy()

    # ============================================================
    # DIRECTIONALITY
    # ============================================================

    lower_better = [
        'drtg', 'tov_pct', 'fc_40',
        'tov_sensitivity', 'foul_sensitivity',
        'drtg_delta_team', 'drtg_delta_conf', 'drtg_delta_sub',
    ]

    ranked_stats = [
        # Group 2
        'height_in', 'age',
        # Group 3
        'minutes_played', 'minutes_per_game', 'minutes_pct', 'usage_pct',
        # Group 4
        'ortg', 'drtg', 'bpm', 'obpm', 'dbpm', 'prpg', 'oprpg', 'dprpg',
        # Group 5
        'efg', 'ts', 'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
        'blk_pct', 'stl_pct', 'ft_rate', 'ast_tov_ratio',
        # Group 6
        'ppg', 'rebpg', 'astpg', 'stlpg', 'blkpg',
        # Group 7 - FG%
        'total_fg_pct', 'two_fg_pct', 'three_fg_pct', 'ft_pct',
        'close_two_fg_pct', 'midrange_fg_pct', 'dunk_fg_pct', 'rim_fg_pct',
        # Group 7 - per game makes + attempts
        'fga_pg', 'fgm_pg',
        'two_att_pg', 'two_made_pg',
        'three_att_pg', 'three_made_pg',
        'rim_att_pg', 'rim_made_pg',
        'close_two_att_pg', 'close_two_made_pg',
        'midrange_att_pg', 'midrange_made_pg',
        'dunk_att_pg', 'dunk_made_pg',
        'ft_att_pg', 'ft_made_pg',
        # Group 7 - rates + ratios
        'dunk_rate', 'close_two_rate', 'rim_rate', 'midrange_rate', 'three_rate',
        'paint_touch_proxy', 'three_p_per_100', 'close_vs_mid_ratio', 'rim_vs_three_ratio',
        # Group 8
        'pts_per_40', 'reb_per_40', 'ast_per_40', 'stl_per_40', 'blk_per_40', 'stocks_per_40', 'fc_40',
        # Group 9
        'ppp_used', 'tov_sensitivity', 'foul_sensitivity',
        # Group 10
        'ortg_delta_team', 'drtg_delta_team', 'ts_delta_team', 'efg_delta_team',
        'rim_rate_delta_team', 'three_rate_delta_team',
        'ortg_delta_conf', 'drtg_delta_conf', 'ts_delta_conf', 'efg_delta_conf',
        'rim_rate_delta_conf', 'three_rate_delta_conf',
        'ortg_delta_sub', 'drtg_delta_sub', 'ts_delta_sub', 'efg_delta_sub',
        'rim_rate_delta_sub', 'three_rate_delta_sub',
    ]

    DUNK_MIN_ATT = 10

    # ============================================================
    # HELPER: VECTORIZED TIER 2 PLACEMENT VIA searchsorted
    # ============================================================

    def place_on_scale(t1_clean, t2_vals, direction):
        """
        Given sorted Tier 1 values and Tier 2 values,
        return (pct, rank) arrays using np.searchsorted.
        All Tier 2 players placed simultaneously — no Python loop.
        """
        t1_sorted = np.sort(t1_clean)
        n = len(t1_sorted)

        if direction == 'higher':
            # Position = number of T1 values below this T2 value
            positions = np.searchsorted(t1_sorted, t2_vals, side='left')
            pct  = positions / n
            rank = n - positions + 1
        else:
            # For lower-better, flip: position = number of T1 values above
            positions = np.searchsorted(t1_sorted, t2_vals, side='right')
            pct  = (n - positions) / n
            rank = positions + 1

        return pct, rank

    # ============================================================
    # HELPER: COMPUTE Z, PCT, RANK FOR A GROUP
    # ============================================================

    def compute_group_stats(t1_vals, all_vals, direction, compute_z=True):
        """
        t1_vals  : Tier 1 values (define the scale)
        all_vals : Tier 1 + Tier 2 values (receive z-scores)
        Returns dict of arrays keyed by suffix.
        """
        results = {}
        t1_clean = t1_vals.dropna().values
        n = len(t1_clean)

        if n == 0:
            return results

        # Z-score (optional, only for national + sub)
        if compute_z:
            mean = t1_clean.mean()
            std  = t1_clean.std(ddof=0)
            if std > 0:
                z = (all_vals.values - mean) / std
                if direction == 'lower':
                    z = -z
            else:
                z = np.zeros(len(all_vals))
            results['z'] = pd.Series(z, index=all_vals.index)

        # Pct + rank for Tier 1
        # rank 1 = best always
        t1_idx = t1_vals.index
        if direction == 'higher':
            pct  = t1_vals.rank(pct=True)
            rank = t1_vals.rank(ascending=False, method='min')  # highest value = rank 1
        else:
            pct  = 1 - t1_vals.rank(pct=True) + (1 / n)
            rank = t1_vals.rank(ascending=True, method='min')   # lowest value = rank 1

        results['pct_t1']  = pct
        results['rank_t1'] = rank

        # Pct + rank for Tier 2 via searchsorted
        t2_idx = all_vals.index.difference(t1_idx)
        if len(t2_idx) > 0:
            t2_vals_clean = all_vals.loc[t2_idx].dropna()
            if len(t2_vals_clean) > 0:
                t2_pct, t2_rank = place_on_scale(t1_clean, t2_vals_clean.values, direction)
                results['pct_t2']  = pd.Series(t2_pct,  index=t2_vals_clean.index)
                results['rank_t2'] = pd.Series(t2_rank, index=t2_vals_clean.index)

        return results

    # ============================================================
    # MAIN LOOP — PER YEAR
    # ============================================================

    output_frames = []

    for year, year_df in df.groupby('year'):

        year_df = year_df.copy()

        tier1_mask    = year_df['percentile_tier'] == 'Tier 1'
        tier2_mask    = year_df['percentile_tier'] == 'Tier 2'
        eligible_mask = tier1_mask | tier2_mask

        for stat in ranked_stats:

            direction = 'lower' if stat in lower_better else 'higher'

            # Dunk FG% exception
            if stat == 'dunk_fg_pct':
                dunk_ok   = year_df['dunk_att'] >= DUNK_MIN_ATT
                t1_mask   = tier1_mask & dunk_ok
                t12_mask  = eligible_mask & dunk_ok
            else:
                t1_mask  = tier1_mask
                t12_mask = eligible_mask

            t1_vals  = year_df.loc[t1_mask,  stat].astype(float)
            all_vals = year_df.loc[t12_mask, stat].astype(float)

            if t1_vals.dropna().empty:
                continue

            # ---- NATIONAL ----
            res = compute_group_stats(t1_vals, all_vals, direction, compute_z=True)
            if 'z' in res:
                year_df.loc[t12_mask, f'{stat}_z']    = res['z']
            if 'pct_t1' in res:
                year_df.loc[t1_mask,  f'{stat}_pct']  = res['pct_t1']
                year_df.loc[t1_mask,  f'{stat}_rank'] = res['rank_t1']
            if 'pct_t2' in res:
                year_df.loc[res['pct_t2'].index,  f'{stat}_pct']  = res['pct_t2']
                year_df.loc[res['rank_t2'].index, f'{stat}_rank'] = res['rank_t2']

            # ---- CONFERENCE ----
            for conf, conf_df in year_df[t1_mask].groupby('conference'):
                conf_t1_mask  = t1_mask  & (year_df['conference'] == conf)
                conf_all_mask = t12_mask & (year_df['conference'] == conf)
                conf_t1_vals  = year_df.loc[conf_t1_mask, stat].astype(float)
                conf_all_vals = year_df.loc[conf_all_mask, stat].astype(float)

                if conf_t1_vals.dropna().empty:
                    continue

                res = compute_group_stats(conf_t1_vals, conf_all_vals, direction, compute_z=False)
                if 'pct_t1' in res:
                    year_df.loc[conf_t1_mask, f'{stat}_conf_pct']  = res['pct_t1']
                    year_df.loc[conf_t1_mask, f'{stat}_conf_rank'] = res['rank_t1']
                if 'pct_t2' in res:
                    year_df.loc[res['pct_t2'].index,  f'{stat}_conf_pct']  = res['pct_t2']
                    year_df.loc[res['rank_t2'].index, f'{stat}_conf_rank'] = res['rank_t2']

            # ---- SUBGROUP ----
            for sub, sub_df in year_df[t1_mask].groupby('power_mid'):
                sub_t1_mask  = t1_mask  & (year_df['power_mid'] == sub)
                sub_all_mask = t12_mask & (year_df['power_mid'] == sub)
                sub_t1_vals  = year_df.loc[sub_t1_mask, stat].astype(float)
                sub_all_vals = year_df.loc[sub_all_mask, stat].astype(float)

                if sub_t1_vals.dropna().empty:
                    continue

                res = compute_group_stats(sub_t1_vals, sub_all_vals, direction, compute_z=True)
                if 'z' in res:
                    year_df.loc[sub_all_mask, f'{stat}_sub_z']    = res['z']
                if 'pct_t1' in res:
                    year_df.loc[sub_t1_mask,  f'{stat}_sub_pct']  = res['pct_t1']
                    year_df.loc[sub_t1_mask,  f'{stat}_sub_rank'] = res['rank_t1']
                if 'pct_t2' in res:
                    year_df.loc[res['pct_t2'].index,  f'{stat}_sub_pct']  = res['pct_t2']
                    year_df.loc[res['rank_t2'].index, f'{stat}_sub_rank'] = res['rank_t2']

            # ---- POSITION NATIONAL ----
            for pos, pos_df in year_df[t1_mask].groupby('position'):
                if pd.isna(pos) or pos in ['NA', 'None']:
                    continue

                pos_t1_mask  = t1_mask  & (year_df['position'] == pos)
                pos_all_mask = t12_mask & (year_df['position'] == pos)
                pos_t1_vals  = year_df.loc[pos_t1_mask, stat].astype(float)
                pos_all_vals = year_df.loc[pos_all_mask, stat].astype(float)

                if pos_t1_vals.dropna().empty:
                    continue

                res = compute_group_stats(pos_t1_vals, pos_all_vals, direction, compute_z=True)
                if 'z' in res:
                    year_df.loc[pos_all_mask, f'{stat}_pos_z']    = res['z']
                if 'pct_t1' in res:
                    year_df.loc[pos_t1_mask,  f'{stat}_pos_pct']  = res['pct_t1']
                    year_df.loc[pos_t1_mask,  f'{stat}_pos_rank'] = res['rank_t1']
                if 'pct_t2' in res:
                    year_df.loc[res['pct_t2'].index,  f'{stat}_pos_pct']  = res['pct_t2']
                    year_df.loc[res['rank_t2'].index, f'{stat}_pos_rank'] = res['rank_t2']

            # ---- POSITION WITHIN CONFERENCE ----
            for (pos, conf), grp in year_df[t1_mask].groupby(['position', 'conference']):
                if pd.isna(pos) or pos in ['NA', 'None']:
                    continue

                pc_t1_mask  = t1_mask  & (year_df['position'] == pos) & (year_df['conference'] == conf)
                pc_all_mask = t12_mask & (year_df['position'] == pos) & (year_df['conference'] == conf)
                pc_t1_vals  = year_df.loc[pc_t1_mask, stat].astype(float)
                pc_all_vals = year_df.loc[pc_all_mask, stat].astype(float)

                if pc_t1_vals.dropna().empty:
                    continue

                res = compute_group_stats(pc_t1_vals, pc_all_vals, direction, compute_z=False)
                if 'pct_t1' in res:
                    year_df.loc[pc_t1_mask, f'{stat}_pos_conf_pct']  = res['pct_t1']
                    year_df.loc[pc_t1_mask, f'{stat}_pos_conf_rank'] = res['rank_t1']
                if 'pct_t2' in res:
                    year_df.loc[res['pct_t2'].index,  f'{stat}_pos_conf_pct']  = res['pct_t2']
                    year_df.loc[res['rank_t2'].index, f'{stat}_pos_conf_rank'] = res['rank_t2']

            # ---- POSITION WITHIN SUBGROUP ----
            for (pos, sub), grp in year_df[t1_mask].groupby(['position', 'power_mid']):
                if pd.isna(pos) or pos in ['NA', 'None']:
                    continue

                ps_t1_mask  = t1_mask  & (year_df['position'] == pos) & (year_df['power_mid'] == sub)
                ps_all_mask = t12_mask & (year_df['position'] == pos) & (year_df['power_mid'] == sub)
                ps_t1_vals  = year_df.loc[ps_t1_mask, stat].astype(float)
                ps_all_vals = year_df.loc[ps_all_mask, stat].astype(float)

                if ps_t1_vals.dropna().empty:
                    continue

                res = compute_group_stats(ps_t1_vals, ps_all_vals, direction, compute_z=True)
                if 'z' in res:
                    year_df.loc[ps_all_mask, f'{stat}_pos_sub_z']    = res['z']
                if 'pct_t1' in res:
                    year_df.loc[ps_t1_mask,  f'{stat}_pos_sub_pct']  = res['pct_t1']
                    year_df.loc[ps_t1_mask,  f'{stat}_pos_sub_rank'] = res['rank_t1']
                if 'pct_t2' in res:
                    year_df.loc[res['pct_t2'].index,  f'{stat}_pos_sub_pct']  = res['pct_t2']
                    year_df.loc[res['rank_t2'].index, f'{stat}_pos_sub_rank'] = res['rank_t2']

        output_frames.append(year_df)
        print(f"  Year {year} complete")

    # ============================================================
    # COMBINE ALL YEARS
    # ============================================================

    print("\nCombining all years...")
    df_out = pd.concat(output_frames, ignore_index=True)

    # ============================================================
    # FINAL COLUMN ORDERING
    # ============================================================

    print("Ordering columns...")

    final_cols = []
    for col in ordered_cols:
        final_cols.append(col)
        if col in ranked_stats:
            final_cols.extend([
                f'{col}_z',
                f'{col}_pct',
                f'{col}_rank',
                f'{col}_conf_pct',
                f'{col}_conf_rank',
                f'{col}_sub_z',
                f'{col}_sub_pct',
                f'{col}_sub_rank',
                f'{col}_pos_z',
                f'{col}_pos_pct',
                f'{col}_pos_rank',
                f'{col}_pos_conf_pct',
                f'{col}_pos_conf_rank',
                f'{col}_pos_sub_z',
                f'{col}_pos_sub_pct',
                f'{col}_pos_sub_rank',
            ])

    final_cols = [c for c in final_cols if c in df_out.columns]
    df_out = df_out[final_cols].copy()

    # ============================================================
    # CAST RANK COLUMNS TO INTEGER
    # ============================================================

    rank_cols = [c for c in df_out.columns if c.endswith('_rank')]
    for col in rank_cols:
        df_out[col] = pd.to_numeric(df_out[col], errors='coerce').astype('Int64')

    # ============================================================
    # SAVE OUTPUT
    # ============================================================

    output_path = guard.to_csv(df_out, paths.stage_file("player_profiles", season), season=season, index=False)

    print("\n=== PLAYER PROFILES DATASET SAVED ===")
    print(f"Rows:    {len(df_out):,}")
    print(f"Columns: {len(df_out.columns):,}")
    print(output_path)
    return output_path


if __name__ == "__main__":
    stage_main(run, __doc__)
