"""
p105B — Player feature-engineering QA suite (one season) — ADVISORY GATE
------------------------------------------------------------------------
Year-scoped port of Scripts/105B_master_player_dataset_data_checks.py. Runs and prints
the full original QA suite for the one season.

The only explicit PASS/FAIL in the original is player_season_id uniqueness; that is
what the gate reports. Everything else is printed for review, as before.

Usage:
    python -m pipeline.player.p105b_player_fe_checks --year 2018 [--year 2023 ...]
"""

import numpy as np
import pandas as pd

from pipeline.stage import GateResult, stage_main

NAME = "p105b_player_fe_checks"


def run(year, paths):
    pd.set_option("display.max_rows", None)

    print("\n============================================================")
    print("  LOADING MASTER DATASET")
    print("============================================================")

    df = pd.read_csv(paths.stage_file("player_fe", year))
    print(f"Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns.")


    # ============================================================
    # 1. SCHEMA CHECKS
    # ============================================================

    def check_columns():
        print("\n==============================")
        print("COLUMNS IN DATASET")
        print("==============================")
        for col in df.columns:
            print(col)


    def check_dtypes():
        print("\n==============================")
        print("COLUMN DTYPES")
        print("==============================")
        print(df.dtypes)


    def check_duplicate_columns():
        print("\n==============================")
        print("DUPLICATE COLUMN CHECK")
        print("==============================")
        dupes = df.columns[df.columns.duplicated()].tolist()
        if dupes:
            print("Duplicate columns found:", dupes)
        else:
            print("No duplicate columns.")


    # ============================================================
    # 2. ROW-LEVEL INTEGRITY
    # ============================================================

    def check_row_count():
        print("\n==============================")
        print("ROW COUNT")
        print("==============================")
        print(f"Rows: {df.shape[0]}")


    def check_unique_player_season_ids():
        print("\n==============================")
        print("PLAYER-SEASON ID UNIQUENESS")
        print("==============================")
        if "player_season_id" not in df.columns:
            print("player_season_id column missing!")
            return
        print("Unique IDs:", df["player_season_id"].nunique())
        print("Total rows:", df.shape[0])
        if df["player_season_id"].nunique() == df.shape[0]:
            print("PASS — all player-season IDs are unique.")
        else:
            print("FAIL — duplicate player-season IDs detected.")


    def check_duplicate_rows():
        print("\n==============================")
        print("DUPLICATE ROW CHECK")
        print("==============================")
        dups = df.duplicated().sum()
        print(f"Duplicate rows: {dups}")


    # ============================================================
    # 3. MERGE INTEGRITY
    # ============================================================

    def check_team_merge_success():
        print("\n==============================")
        print("TEAM MERGE INTEGRITY")
        print("==============================")
        required_cols = [
            "team_adj_o", "team_adj_d",
            "team_ts", "team_efg",
            "team_rim_rate", "team_three_rate"
        ]
        for col in required_cols:
            if col not in df.columns:
                print(f"Missing column: {col}")
            else:
                print(f"{col}: nulls = {df[col].isna().sum()}")


    def check_conference_column():
        print("\n==============================")
        print("CONFERENCE COLUMN CHECK")
        print("==============================")
        if "conference" not in df.columns:
            print("ERROR — conference column missing!")
        else:
            print("conference column exists.")
            print("Nulls:", df["conference"].isna().sum())

        leftovers = [c for c in df.columns if "conference_" in c]
        if leftovers:
            print("WARNING — leftover conference columns:", leftovers)
        else:
            print("No leftover conference_x or conference_y columns.")


    def check_team_year_coverage():
        print("\n==============================")
        print("TEAM-YEAR COVERAGE CHECK")
        print("==============================")
        print(df.groupby(["team", "year"]).size().head(20))


    # ============================================================
    # 4. MISSINGNESS
    # ============================================================

    def null_summary():
        print("\n==============================")
        print("NULL SUMMARY")
        print("==============================")
        print(df.isna().sum().sort_values(ascending=False).head(40))


    def players_with_extreme_missingness():
        print("\n==============================")
        print("PLAYERS WITH EXTREME MISSINGNESS")
        print("==============================")
        df["null_count"] = df.isna().sum(axis=1)
        print(df.sort_values("null_count", ascending=False).head(20)[["name", "team", "year", "null_count"]])


    # ============================================================
    # 5. DISTRIBUTION CHECKS
    # ============================================================

    def check_minutes_distribution():
        print("\n==============================")
        print("MINUTES DISTRIBUTION")
        print("==============================")
        print(df["minutes_per_game"].describe())


    def check_minutes_pct():
        print("\n==============================")
        print("MINUTES_PCT DISTRIBUTION")
        print("==============================")
        print(df["minutes_pct"].describe())


    def check_height_distribution():
        print("\n==============================")
        print("HEIGHT DISTRIBUTION")
        print("==============================")
        print(df["height_in"].describe())


    def check_usage_distribution():
        print("\n==============================")
        print("USAGE DISTRIBUTION")
        print("==============================")
        print(df["usage_pct"].describe())


    def check_ts_distribution():
        print("\n==============================")
        print("TS% DISTRIBUTION")
        print("==============================")
        print(df["ts"].describe())


    def check_fg_distribution():
        print("\n==============================")
        print("FG% DISTRIBUTION")
        print("==============================")
        print(df["total_fg_pct"].describe())


    def check_rim_fg_distribution():
        print("\n==============================")
        print("RIM FG% DISTRIBUTION")
        print("==============================")
        print(df["rim_fg_pct"].describe())


    def check_midrange_fg_distribution():
        print("\n==============================")
        print("MIDRANGE FG% DISTRIBUTION")
        print("==============================")
        print(df["midrange_fg_pct"].describe())


    def check_ft_distribution():
        print("\n==============================")
        print("FT% DISTRIBUTION")
        print("==============================")
        print(df["ft_pct"].describe())


    def check_shot_profile_rates():
        print("\n==============================")
        print("SHOT PROFILE RATE CHECKS")
        print("==============================")
        rate_cols = [
            "close_two_rate", "midrange_rate", "dunk_rate",
            "rim_rate", "three_rate", "ft_rate"
        ]
        for col in rate_cols:
            print(f"{col}: {df[col].describe()}")


    def check_totals_and_per_game():
        print("\n==============================")
        print("TOTALS + PER-GAME CHECK")
        print("==============================")
        cols = [
            "total_fga", "total_fgm", "total_fg_pct",
            "fga_pg", "fgm_pg",
            "two_att_pg", "two_made_pg",
            "three_att_pg", "three_made_pg",
            "close_two_att_pg", "close_two_made_pg",
            "midrange_att_pg", "midrange_made_pg",
            "dunk_att_pg", "dunk_made_pg",
            "rim_att_pg", "rim_made_pg",
            "ft_att_pg", "ft_made_pg"
        ]
        for col in cols:
            print(f"{col}: {df[col].describe()}")


    def check_string_fields():
        print("\n==============================")
        print("MADE/ATTEMPT STRING CHECK")
        print("==============================")
        str_cols = [
            "two_made_att_str", "three_made_att_str",
            "close_two_made_att_str", "midrange_made_att_str",
            "dunk_made_att_str", "rim_made_att_str",
            "fg_made_att_str", "ft_made_att_str"
        ]
        for col in str_cols:
            print(f"{col}: nulls = {df[col].isna().sum()}")


    def check_midrange_and_rim_raw():
        print("\n==============================")
        print("MIDRANGE + RIM RAW CHECK")
        print("==============================")
        cols = [
            "midrange_att", "midrange_made", "midrange_fg_pct",
            "rim_att", "rim_made", "rim_fg_pct"
        ]
        for col in cols:
            print(f"{col}: {df[col].describe()}")


    # ============================================================
    # 6. CONTEXTUAL DELTAS
    # ============================================================

    def check_contextual_deltas():
        print("\n==============================")
        print("CONTEXTUAL DELTAS CHECK")
        print("==============================")
        delta_cols = [
            "ts_delta_team", "efg_delta_team", "rim_rate_delta_team", "three_rate_delta_team",
            "ts_delta_conf", "efg_delta_conf", "rim_rate_delta_conf", "three_rate_delta_conf",
            "ts_delta_sub", "efg_delta_sub", "rim_rate_delta_sub", "three_rate_delta_sub",
            "ts_delta_nat", "efg_delta_nat", "rim_rate_delta_nat", "three_rate_delta_nat",
            "ortg_delta_team", "drtg_delta_team",
            "ortg_delta_conf", "drtg_delta_conf",
            "ortg_delta_sub", "drtg_delta_sub",
            "ortg_delta_nat", "drtg_delta_nat"
        ]
        for col in delta_cols:
            print(f"{col}: {df[col].describe()}")


    # ============================================================
    # 7. STABILITY FEATURES
    # ============================================================

    def check_stability_features():
        print("\n==============================")
        print("STABILITY FEATURES CHECK")
        print("==============================")
        stab_cols = [c for c in df.columns if "tier" in c]
        for col in stab_cols:
            print(f"{col}: nulls = {df[col].isna().sum()}")


    # ============================================================
    # 8. POSITION MAPPING
    # ============================================================

    def check_position_mapping():
        print("\n==============================")
        print("POSITION MAPPING CHECK")
        print("==============================")
        print(df["position"].value_counts(dropna=False))


    # ============================================================
    # 9. OUTLIERS
    # ============================================================

    def find_numeric_outliers():
        print("\n==============================")
        print("NUMERIC OUTLIERS")
        print("==============================")
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            upper = q3 + 3 * iqr
            lower = q1 - 3 * iqr
            outliers = df[(df[col] < lower) | (df[col] > upper)]
            if len(outliers) > 0:
                print(f"{col}: {len(outliers)} outliers")


    # ============================================================
    # 10. YEAR / SEASON ALIGNMENT
    # ============================================================

    def check_year_range():
        print("\n==============================")
        print("YEAR RANGE")
        print("==============================")
        print(df["year"].min(), "to", df["year"].max())


    def check_games_minutes_consistency():
        print("\n==============================")
        print("GAMES vs MINUTES CONSISTENCY")
        print("==============================")
        print(df[["games", "minutes_per_game"]].describe())


    # ============================================================
    # 11. TRUE PLAYER ID COLLISION CHECK
    # ============================================================

    def check_true_player_id_collisions():
        print("\n==============================")
        print("TRUE PLAYER ID COLLISION CHECK")
        print("==============================")

        groups = df.groupby("player_id")
        true_collisions = []

        for pid, g in groups:
            if len(g) == 1:
                continue
            multi_team_same_year = (g.groupby("year")["team"].nunique() > 1).any()
            if multi_team_same_year:
                true_collisions.append(pid)

        print(f"Total TRUE collisions: {len(true_collisions)}")


    # ============================================================
    # RUN ALL CHECKS
    # ============================================================

    print("\n============================================================")
    print("  RUNNING FULL QA SUITE")
    print("============================================================")

    # 1. Schema
    check_columns()
    check_dtypes()
    check_duplicate_columns()

    # 2. Row-level integrity
    check_row_count()
    check_unique_player_season_ids()
    check_duplicate_rows()

    # 3. Merge integrity
    check_team_merge_success()
    check_conference_column()
    check_team_year_coverage()

    # 4. Missingness
    null_summary()
    players_with_extreme_missingness()

    # 5. Distributions
    check_minutes_distribution()
    check_minutes_pct()
    check_height_distribution()
    check_usage_distribution()
    check_ts_distribution()
    check_fg_distribution()
    check_rim_fg_distribution()
    check_midrange_fg_distribution()
    check_ft_distribution()
    check_shot_profile_rates()
    check_totals_and_per_game()
    check_string_fields()
    check_midrange_and_rim_raw()

    # 6. Contextual deltas
    check_contextual_deltas()

    # 7. Stability features
    check_stability_features()

    # 8. Position mapping
    check_position_mapping()

    # 9. Outliers
    find_numeric_outliers()

    # 10. Year / season alignment
    check_year_range()
    check_games_minutes_consistency()

    # 11. Player ID Duplicates
    check_true_player_id_collisions()

    unique_ids = df["player_season_id"].nunique() == df.shape[0]
    return GateResult(NAME, year, passed=bool(unique_ids), messages=[
        "player_season_id unique" if unique_ids else "duplicate player_season_id detected"
    ])


if __name__ == "__main__":
    stage_main(run, __doc__)
