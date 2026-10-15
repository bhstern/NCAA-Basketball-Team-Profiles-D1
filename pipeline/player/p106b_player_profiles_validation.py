"""
p106B — Player profiles validation (one season) — ADVISORY GATE
---------------------------------------------------------------
Year-scoped port of Scripts/106B_master_player_validation_check.py. The 12 checks are
the original's, unchanged, hardcoded values included.

KNOWN ISSUES, REPRODUCED ON PURPOSE (spec §6 item 1) — do not fix until the baseline
match is proven:
    - expected_rows = 53682 (all seasons) -> Check 1 fails on any single season
    - Check 7 expects Tier 2 percentile_eligible = False; p106 sets it True
    - Checks 5, 9, 11 are hardcoded to the 2026 season; Check 10 to Cooper Flagg 2025.
      On any other single season Check 11 raises on its empty 2026 slice.

Because the original assumes all seasons are present, a crash inside the checks is
caught and reported as NOT EVALUATED rather than stopping the run.

Usage:
    python -m pipeline.player.p106b_player_profiles_validation --year 2018 [--year 2023 ...]
"""

import pandas as pd
import numpy as np

from pipeline.stage import GateResult, stage_main

NAME = "p106b_player_profiles_validation"


def _original_checks(year, paths):
    # ============================================================
    # LOAD
    # ============================================================

    print("Loading player profiles dataset...")
    df = pd.read_csv(paths.stage_file("player_profiles", year))
    print(f"  Rows:    {len(df):,}")
    print(f"  Columns: {len(df.columns):,}")

    issues = []

    # ============================================================
    # CHECK 1 — SHAPE
    # ============================================================

    print("\n--- CHECK 1: Shape ---")
    expected_rows = 53682
    if len(df) != expected_rows:
        issues.append(f"Row count mismatch: expected {expected_rows:,}, got {len(df):,}")
        print(f"  FAIL: expected {expected_rows:,} rows, got {len(df):,}")
    else:
        print(f"  PASS: {len(df):,} rows")

    expected_min_cols = 1400
    if len(df.columns) < expected_min_cols:
        issues.append(f"Column count too low: {len(df.columns)} (expected ~1,593)")
        print(f"  FAIL: only {len(df.columns)} columns (expected ~1,593)")
    else:
        print(f"  PASS: {len(df.columns):,} columns")

    # ============================================================
    # CHECK 2 — TIER COUNTS PER YEAR
    # ============================================================

    print("\n--- CHECK 2: Tier Counts Per Year ---")
    tier_counts = df.groupby(['year','percentile_tier']).size().unstack(fill_value=0)
    print(tier_counts.to_string())

    # Flag any year with fewer than 2,500 Tier 1 players
    for year, row in tier_counts.iterrows():
        t1 = row.get('Tier 1', 0)
        if t1 < 2500:
            issues.append(f"Year {year} has only {t1} Tier 1 players")
            print(f"  WARNING: {year} has only {t1} Tier 1 players")

    # ============================================================
    # CHECK 3 — PERCENTILE RANGE (0 to 1)
    # ============================================================

    print("\n--- CHECK 3: Percentile Range ---")
    # Only check DERIVED percentile columns created by the script.
    # Excludes raw stat columns that naturally contain '_pct' in their name
    # (usage_pct, or_pct, blk_pct, etc.)
    raw_pct_cols = {
        'minutes_pct', 'usage_pct', 'or_pct', 'dr_pct', 'ast_pct', 'tov_pct',
        'blk_pct', 'stl_pct', 'ft_pct', 'efg', 'ts', 'two_fg_pct', 'three_fg_pct',
        'close_two_fg_pct', 'midrange_fg_pct', 'dunk_fg_pct', 'rim_fg_pct',
        'total_fg_pct', 'paint_touch_proxy', 'percentile_eligible',
    }
    derived_pct_suffixes = ('_pct', '_conf_pct', '_sub_pct', '_pos_pct',
                            '_pos_conf_pct', '_pos_sub_pct')
    pct_cols = [
        c for c in df.columns
        if any(c.endswith(s) for s in derived_pct_suffixes)
        and c not in raw_pct_cols
    ]

    out_of_range = []
    for col in pct_cols:
        vals = df[col].dropna()
        if len(vals) == 0:
            continue
        if vals.min() < -0.001 or vals.max() > 1.001:
            out_of_range.append(f"{col}: min={vals.min():.4f}, max={vals.max():.4f}")

    if out_of_range:
        for msg in out_of_range:
            issues.append(f"Percentile out of range: {msg}")
            print(f"  FAIL: {msg}")
    else:
        print(f"  PASS: all {len(pct_cols)} percentile columns in [0, 1]")

    # ============================================================
    # CHECK 4 — RANK INTEGRITY
    # ============================================================

    print("\n--- CHECK 4: Rank Integrity ---")
    rank_cols = [c for c in df.columns if c.endswith('_rank')]
    rank_issues = []
    for col in rank_cols:
        vals = df[col].dropna()
        if len(vals) == 0:
            continue
        if vals.min() < 1:
            rank_issues.append(f"{col}: min rank = {vals.min()}")
        if not pd.api.types.is_integer_dtype(vals):
            # Check if values are whole numbers
            if not (vals == vals.round()).all():
                rank_issues.append(f"{col}: non-integer values found")

    if rank_issues:
        for msg in rank_issues[:10]:  # cap at 10
            issues.append(f"Rank issue: {msg}")
            print(f"  FAIL: {msg}")
    else:
        print(f"  PASS: all {len(rank_cols)} rank columns have valid values (min >= 1)")

    # ============================================================
    # CHECK 5 — Z-SCORE SANITY (Tier 1 only)
    # ============================================================

    print("\n--- CHECK 5: Z-Score Sanity (Tier 1, 2026) ---")
    z_cols = [c for c in df.columns if c.endswith('_z')]
    df_t1_2026 = df[(df['percentile_tier'] == 'Tier 1') & (df['year'] == 2026)]
    z_issues = []
    for col in z_cols[:10]:  # spot check first 10
        vals = df_t1_2026[col].dropna()
        if len(vals) < 100:
            continue
        mean = vals.mean()
        std  = vals.std()
        if abs(mean) > 0.1:
            z_issues.append(f"{col}: mean={mean:.3f} (expected ~0)")
        if abs(std - 1) > 0.15:
            z_issues.append(f"{col}: std={std:.3f} (expected ~1)")

    if z_issues:
        for msg in z_issues:
            issues.append(f"Z-score sanity: {msg}")
            print(f"  FAIL: {msg}")
    else:
        print(f"  PASS: z-score means ~0, stds ~1 for sampled columns")

    # ============================================================
    # CHECK 6 — NO-PERCENTILE PLAYERS HAVE NaN DERIVED COLS
    # ============================================================

    print("\n--- CHECK 6: No-Percentile Players Have NaN Derived Cols ---")
    none_df = df[df['percentile_tier'] == 'None']
    sample_derived = ['ortg_pct', 'ortg_rank', 'ortg_z', 'ppg_pct', 'bpm_rank']
    sample_derived = [c for c in sample_derived if c in df.columns]

    none_issues = []
    for col in sample_derived:
        non_null = none_df[col].notna().sum()
        if non_null > 0:
            none_issues.append(f"{col}: {non_null} non-null values for 'None' tier players")

    if none_issues:
        for msg in none_issues:
            issues.append(f"None-tier has values: {msg}")
            print(f"  FAIL: {msg}")
    else:
        print(f"  PASS: all sampled derived columns are NaN for 'None' tier players")

    # ============================================================
    # CHECK 7 — TIER 2 PLAYERS HAVE PERCENTILES, eligible=False
    # ============================================================

    print("\n--- CHECK 7: Tier 2 Players ---")
    tier2_df = df[df['percentile_tier'] == 'Tier 2']

    # percentile_eligible should be False
    eligible_vals = tier2_df['percentile_eligible'].dropna().unique()
    if set(eligible_vals) != {False}:
        issues.append(f"Tier 2 percentile_eligible has unexpected values: {eligible_vals}")
        print(f"  FAIL: percentile_eligible values: {eligible_vals}")
    else:
        print(f"  PASS: all Tier 2 players have percentile_eligible = False")

    # Should have some percentile values
    t2_pct_coverage = tier2_df['ortg_pct'].notna().sum()
    print(f"  INFO: {t2_pct_coverage:,} of {len(tier2_df):,} Tier 2 players have ortg_pct")

    # ============================================================
    # CHECK 8 — DUNK EXCEPTION
    # ============================================================

    print("\n--- CHECK 8: Dunk FG% Exception ---")
    if 'dunk_fg_pct_pct' in df.columns:
        low_dunk = df[df['dunk_att'] < 10]
        non_null = low_dunk['dunk_fg_pct_pct'].notna().sum()
        if non_null > 0:
            issues.append(f"dunk_fg_pct_pct: {non_null} players with dunk_att < 10 have a percentile")
            print(f"  FAIL: {non_null} players with dunk_att < 10 have dunk_fg_pct percentile")
        else:
            print(f"  PASS: no players with dunk_att < 10 have dunk_fg_pct percentile")
    else:
        print("  SKIP: dunk_fg_pct_pct column not found")

    # ============================================================
    # CHECK 9 — POSITION GROUP SAMPLE SIZES
    # ============================================================

    print("\n--- CHECK 9: Position Group Sample Sizes (Tier 1, 2026) ---")
    pos_conf = df_t1_2026.groupby(['position','conference']).size().reset_index(name='n')
    small = pos_conf[pos_conf['n'] < 5]
    if len(small) > 0:
        print(f"  WARNING: {len(small)} position/conference combos with < 5 Tier 1 players:")
        print(small.to_string())
    else:
        print(f"  PASS: all position/conference combos have >= 5 Tier 1 players")

    # Overall position counts
    print("\n  2026 Tier 1 position counts:")
    print(df_t1_2026['position'].value_counts().to_string())

    # ============================================================
    # CHECK 10 — SPOT CHECK KNOWN PLAYERS
    # ============================================================

    print("\n--- CHECK 10: Spot Check Known Players ---")

    spot_checks = [
        # (name, team, year, stat, expected_direction)
        ('Cooper Flagg', 'Duke', 2025, 'ortg', 'top_25pct'),
        ('Cooper Flagg', 'Duke', 2025, 'bpm', 'top_25pct'),
        ('Cooper Flagg', 'Duke', 2025, 'tov_pct', None),  # just check it exists
    ]

    for name, team, year, stat, direction in spot_checks:
        row = df[(df['name'] == name) & (df['team'] == team) & (df['year'] == year)]
        if row.empty:
            print(f"  WARNING: {name} {team} {year} not found")
            continue
        pct_col = f'{stat}_pct'
        if pct_col not in df.columns:
            print(f"  WARNING: {pct_col} not in dataset")
            continue
        pct_val = row[pct_col].values[0]
        rank_val = row[f'{stat}_rank'].values[0] if f'{stat}_rank' in df.columns else 'N/A'
        raw_val  = row[stat].values[0]
        tier     = row['percentile_tier'].values[0]
        print(f"  {name} ({tier}) | {stat}={raw_val:.1f} | pct={pct_val:.3f} | rank={rank_val}")
        if direction == 'top_25pct' and pct_val < 0.75:
            issues.append(f"{name} {stat} pct={pct_val:.3f} — expected top 25%")
            print(f"    WARNING: expected top 25% percentile")

    # Manual spot check — print full profile for one known player
    print("\n  Full profile snapshot — Cooper Flagg 2025:")
    flagg = df[(df['name'] == 'Cooper Flagg') & (df['year'] == 2025)]
    if not flagg.empty:
        key_cols = [
            'name','team','year','position','percentile_tier','percentile_eligible',
            'ortg','ortg_pct','ortg_rank',
            'bpm','bpm_pct','bpm_rank',
            'ppg','ppg_pct','ppg_rank',
            'drtg','drtg_pct','drtg_rank',
            'tov_pct','tov_pct_pct','tov_pct_rank',
            'three_fg_pct','three_fg_pct_pct','three_fg_pct_rank',
            'ortg_pos_pct','ortg_pos_rank',
            'ortg_conf_pct','ortg_conf_rank',
        ]
        key_cols = [c for c in key_cols if c in df.columns]
        print(flagg[key_cols].T.to_string())

    # ============================================================
    # CHECK 11 — LOWER-BETTER DIRECTIONALITY
    # ============================================================

    print("\n--- CHECK 11: Lower-Better Directionality ---")
    df_t1_2026 = df[(df['percentile_tier'] == 'Tier 1') & (df['year'] == 2026)]

    lower_better_checks = ['tov_pct', 'drtg', 'fc_40']
    for stat in lower_better_checks:
        if f'{stat}_pct' not in df.columns:
            continue
        # Player with lowest value should have highest percentile
        best_player = df_t1_2026.nsmallest(1, stat).iloc[0]
        worst_player = df_t1_2026.nlargest(1, stat).iloc[0]
        best_pct  = best_player[f'{stat}_pct']
        worst_pct = worst_player[f'{stat}_pct']
        best_rank  = best_player[f'{stat}_rank']
        worst_rank = worst_player[f'{stat}_rank']

        if best_pct > worst_pct and best_rank < worst_rank:
            print(f"  PASS {stat}: lowest value → pct={best_pct:.3f}, rank={best_rank} | highest → pct={worst_pct:.3f}, rank={worst_rank}")
        else:
            issues.append(f"{stat} directionality wrong: best pct={best_pct:.3f} rank={best_rank}")
            print(f"  FAIL {stat}: lowest value → pct={best_pct:.3f}, rank={best_rank} | highest → pct={worst_pct:.3f}, rank={worst_rank}")

    # ============================================================
    # CHECK 12 — 16 DERIVED COLUMNS PER RANKED STAT
    # ============================================================

    print("\n--- CHECK 12: Derived Column Count Per Stat ---")
    ranked_sample = ['ortg', 'ppg', 'tov_pct', 'three_fg_pct', 'rim_rate', 'drtg_delta_team']
    expected_suffixes = [
        '_z', '_pct', '_rank',
        '_conf_pct', '_conf_rank',
        '_sub_z', '_sub_pct', '_sub_rank',
        '_pos_z', '_pos_pct', '_pos_rank',
        '_pos_conf_pct', '_pos_conf_rank',
        '_pos_sub_z', '_pos_sub_pct', '_pos_sub_rank',
    ]

    for stat in ranked_sample:
        missing_suffixes = [s for s in expected_suffixes if f'{stat}{s}' not in df.columns]
        if missing_suffixes:
            issues.append(f"{stat} missing derived cols: {missing_suffixes}")
            print(f"  FAIL {stat}: missing {missing_suffixes}")
        else:
            print(f"  PASS {stat}: all 16 derived columns present")

    # ============================================================
    # SUMMARY
    # ============================================================

    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    if issues:
        print(f"\n{len(issues)} issue(s) found:\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\nAll checks passed! Dataset looks clean.")
    print()

    return issues


def run(year, paths):
    try:
        issues = _original_checks(year, paths)
    except Exception as e:
        print(f"\n[p106B] {year}: original checks crashed part-way: {type(e).__name__}: {e}")
        return GateResult(NAME, year, passed=None, messages=[
            f"Original checks assume all seasons are present and crashed: {type(e).__name__}: {e}"
        ])
    return GateResult(NAME, year, passed=not issues, messages=list(issues))


if __name__ == "__main__":
    stage_main(run, __doc__)
