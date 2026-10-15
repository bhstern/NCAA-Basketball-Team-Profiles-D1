"""
t05 — Team-level feature engineering (one season)
-------------------------------------------------
Year-scoped port of Scripts/05_master_team_dataset_feature_engineering.py.

Transforms merged Torvik team stats + shooting splits into a complete,
model-ready dataset including:

    • Four Factors (rate conversions)
    • Shot profile (attempts, FG%, rates)
    • Rim metrics (rate + FG%)
    • PPP, xPPP, residuals
    • Per-possession shot metrics
    • Correct offensive/defensive block % mapping

League averages were already per-year in the original, so one season is self-contained.

KNOWN RISK, REPRODUCED ON PURPOSE (spec §6 item 2): the made-attempt parse uses
`.astype(int)` and will crash on a missing split (early-season sparse data).

Usage:
    python -m pipeline.team.t05_feature_engineering --year 2018 [--year 2023 ...]
"""

import pandas as pd

from pipeline import guard
from pipeline.stage import stage_main


def parse_made_att(df, col):
    made_col = col + "_made"
    att_col = col + "_att"
    df[[made_col, att_col]] = df[col].str.split("-", expand=True).astype(int)
    return df


def run(year, paths):
    # ============================================================
    # LOAD MERGED FULL-SEASON MASTER DATASET
    # ============================================================

    merged = pd.read_csv(paths.stage_file("master_team", year))

    # ============================================================
    # FULL-SEASON GAMES / WINS / LOSSES
    # ============================================================

    merged["full_season_losses"] = merged["games"] - merged["wins"]

    merged = merged.rename(
        columns={
            "games": "full_season_games",
            "wins": "full_season_wins",
            "record": "full_season_record",
        }
    )

    # ============================================================
    # FOUR FACTORS (PERCENT → RATE CONVERSIONS)
    # ============================================================

    merged["tov_rate_off"] = merged["tovpct"] / 100
    merged["tov_rate_def"] = merged["tovpct_d"] / 100

    merged["orb_rate_off"] = merged["o_rebpct"] / 100
    merged["orb_rate_def"] = merged["op_orebpct"] / 100

    merged["efg_rate_off"] = merged["efg"] / 100
    merged["efg_rate_def"] = merged["efg_d."] / 100

    merged["ft_rate_off"] = merged["ft_rate"] / 100
    merged["ft_rate_def"] = merged["ft_rate_d"] / 100

    merged["2pt_pct_off"] = merged["2p_pct"] / 100
    merged["2pt_pct_def"] = merged["2p_pct_d."] / 100

    merged["3pt_pct_off"] = merged["3p_pct"] / 100
    merged["3pt_pct_def"] = merged["3p_pct_d."] / 100

    # ⭐ FIXED: Torvik block % mapping
    # blk_pct     = DEFENSIVE block rate (% of opponent 2PA you block)
    # blked_pct   = OFFENSIVE block rate (% of your 2PA that get blocked)

    merged["blk_pct_def"] = merged["blk_pct"] / 100
    merged["blk_pct_off"] = merged["blked_pct"] / 100

    merged["ast_pct_off"] = merged["ast_pct"] / 100
    merged["ast_pct_def"] = merged["op_ast_pct"] / 100

    merged["three_rate_off"] = merged["3p_rate"] / 100
    merged["three_rate_def"] = merged["3p_rate_d"] / 100

    merged["ft_pct_off"] = merged["ftpct"] / 100
    merged["ft_pct_def"] = merged["op._ftpct"] / 100

    merged["elite_sos_rate"] = merged["elite_sos"] / 100

    # Drop original percent-style columns
    merged = merged.drop(
        columns=[
            "efg", "efg_d.", "ft_rate", "ft_rate_d", "tovpct", "tovpct_d",
            "o_rebpct", "op_orebpct", "2p_pct", "2p_pct_d.", "3p_pct", "3p_pct_d.",
            "blk_pct", "blked_pct", "ast_pct", "op_ast_pct",
            "3p_rate", "3p_rate_d", "ftpct", "op._ftpct", "elite_sos"
        ]
    )

    # ============================================================
    # PARSE MADE–ATTEMPT STRINGS INTO NUMERIC COLUMNS
    # ============================================================

    locations = ["dunks", "close_twos", "long_twos", "threes"]
    sides = ["off", "def"]

    for side in sides:
        for loc in locations:
            merged = parse_made_att(merged, f"{side}_{loc}")

    # ============================================================
    # ADJUST CLOSE TWOS TO EXCLUDE DUNKS
    # ============================================================

    for side in sides:
        merged[f"{side}_close_twos_made"] -= merged[f"{side}_dunks_made"]
        merged[f"{side}_close_twos_att"] -= merged[f"{side}_dunks_att"]

    # ============================================================
    # TOTAL 2PA AND TOTAL FGA
    # ============================================================

    for side in sides:
        merged[f"{side}_two_att"] = (
            merged[f"{side}_dunks_att"]
            + merged[f"{side}_close_twos_att"]
            + merged[f"{side}_long_twos_att"]
        )
        merged[f"{side}_fga"] = merged[f"{side}_two_att"] + merged[f"{side}_threes_att"]

    # ============================================================
    # FG% BY LOCATION
    # ============================================================

    for side in sides:
        for loc in locations:
            merged[f"{side}_{loc}_fg"] = (
                merged[f"{side}_{loc}_made"] / merged[f"{side}_{loc}_att"]
            )

    # ============================================================
    # RATE AS % OF TOTAL FGA
    # ============================================================

    for side in sides:
        for loc in locations:
            merged[f"{side}_{loc}_rate_total"] = (
                merged[f"{side}_{loc}_att"] / merged[f"{side}_fga"]
            )

    # ============================================================
    # RATE AS % OF 2PA
    # ============================================================

    two_point_locs = ["dunks", "close_twos", "long_twos"]

    for side in sides:
        for loc in two_point_locs:
            merged[f"{side}_{loc}_rate_two"] = (
                merged[f"{side}_{loc}_att"] / merged[f"{side}_two_att"]
            )

    # ============================================================
    # FULL-SEASON POSSESSIONS + PER-POSSESSION SHOT METRICS
    # ============================================================

    merged["full_season_possessions"] = (
        merged["adj._t"] * merged["full_season_games"]
    ).replace(0, 1)

    for side in sides:
        for loc in locations:
            merged[f"{side}_{loc}_att_per_poss"] = (
                merged[f"{side}_{loc}_att"] / merged["full_season_possessions"]
            )
            pts = 3 if loc == "threes" else 2
            merged[f"{side}_{loc}_ppp"] = (
                merged[f"{side}_{loc}_made"] * pts / merged["full_season_possessions"]
            )

    # ============================================================
    # ESTIMATE FREE THROWS + TOTAL POINTS + FULL-SEASON PPP
    # ============================================================

    merged["fta_off_est"] = merged["ft_rate_off"] * merged["off_fga"]
    merged["fta_def_est"] = merged["ft_rate_def"] * merged["def_fga"]

    merged["ftm_off_est"] = merged["fta_off_est"] * merged["ft_pct_off"]
    merged["ftm_def_est"] = merged["fta_def_est"] * merged["ft_pct_def"]

    merged["pts_off_est"] = (
        2 * (merged["off_dunks_made"] + merged["off_close_twos_made"] + merged["off_long_twos_made"])
        + 3 * merged["off_threes_made"]
        + merged["ftm_off_est"]
    )

    merged["pts_def_est"] = (
        2 * (merged["def_dunks_made"] + merged["def_close_twos_made"] + merged["def_long_twos_made"])
        + 3 * merged["def_threes_made"]
        + merged["ftm_def_est"]
    )

    merged["ppp_off_full"] = merged["pts_off_est"] / merged["full_season_possessions"]
    merged["ppp_def_full"] = merged["pts_def_est"] / merged["full_season_possessions"]

    # ============================================================
    # LEAGUE AVERAGES BY LOCATION (PER YEAR)
    # ============================================================

    league_avgs = (
        merged.groupby("year")
        .agg({
            "off_dunks_made": "sum", "off_dunks_att": "sum",
            "off_close_twos_made": "sum", "off_close_twos_att": "sum",
            "off_long_twos_made": "sum", "off_long_twos_att": "sum",
            "off_threes_made": "sum", "off_threes_att": "sum",
        })
        .reset_index()
    )

    league_avgs["lg_fg_dunks"] = league_avgs["off_dunks_made"] / league_avgs["off_dunks_att"]
    league_avgs["lg_fg_close_twos"] = league_avgs["off_close_twos_made"] / league_avgs["off_close_twos_att"]
    league_avgs["lg_fg_long_twos"] = league_avgs["off_long_twos_made"] / league_avgs["off_long_twos_att"]
    league_avgs["lg_fg_threes"] = league_avgs["off_threes_made"] / league_avgs["off_threes_att"]

    league_avgs["lg_xpts_dunks"] = league_avgs["lg_fg_dunks"] * 2
    league_avgs["lg_xpts_close_twos"] = league_avgs["lg_fg_close_twos"] * 2
    league_avgs["lg_xpts_long_twos"] = league_avgs["lg_fg_long_twos"] * 2
    league_avgs["lg_xpts_threes"] = league_avgs["lg_fg_threes"] * 3

    merged = merged.merge(
        league_avgs[
            ["year", "lg_xpts_dunks", "lg_xpts_close_twos", "lg_xpts_long_twos", "lg_xpts_threes"]
        ],
        on="year",
        how="left",
    )

    # ============================================================
    # EXPECTED PPP (xPPP) + RESIDUALS
    # ============================================================

    merged["xPPP_off"] = (
        merged["off_dunks_rate_total"] * merged["lg_xpts_dunks"]
        + merged["off_close_twos_rate_total"] * merged["lg_xpts_close_twos"]
        + merged["off_long_twos_rate_total"] * merged["lg_xpts_long_twos"]
        + merged["off_threes_rate_total"] * merged["lg_xpts_threes"]
    )

    merged["xPPP_def"] = (
        merged["def_dunks_rate_total"] * merged["lg_xpts_dunks"]
        + merged["def_close_twos_rate_total"] * merged["lg_xpts_close_twos"]
        + merged["def_long_twos_rate_total"] * merged["lg_xpts_long_twos"]
        + merged["def_threes_rate_total"] * merged["lg_xpts_threes"]
    )

    merged["ppp_residual_off"] = merged["ppp_off_full"] - merged["xPPP_off"]
    merged["ppp_residual_def"] = merged["ppp_def_full"] - merged["xPPP_def"]
    merged["residual_diff"] = merged["ppp_residual_off"] - merged["ppp_residual_def"]

    # ============================================================
    # COMBINED RIM ATTEMPTS + RIM FG% (OFF + DEF)
    # ============================================================

    # Offense
    merged["off_rim_rate_total"] = (
        merged["off_dunks_rate_total"] +
        merged["off_close_twos_rate_total"]
    )

    merged["off_rim_fg"] = (
        merged["off_dunks_made"] + merged["off_close_twos_made"]
    ) / (
        merged["off_dunks_att"] + merged["off_close_twos_att"]
    )

    # Defense
    merged["def_rim_rate_total"] = (
        merged["def_dunks_rate_total"] +
        merged["def_close_twos_rate_total"]
    )

    merged["def_rim_fg"] = (
        merged["def_dunks_made"] + merged["def_close_twos_made"]
    ) / (
        merged["def_dunks_att"] + merged["def_close_twos_att"]
    )

    # ============================================================
    # DROP RAW MADE–ATT STRINGS
    # ============================================================

    raw_cols = [
        f"{side}_{loc}"
        for side in sides
        for loc in locations
        if f"{side}_{loc}" in merged.columns
    ]

    merged = merged.drop(columns=raw_cols)

    # ============================================================
    # SAVE OUTPUT
    # ============================================================

    out = guard.to_csv(merged, paths.stage_file("master_team_fe", year), season=year, index=False)

    print(f"[DONE] {year}: team feature engineering ({len(merged)} teams) saved to:\n{out}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
