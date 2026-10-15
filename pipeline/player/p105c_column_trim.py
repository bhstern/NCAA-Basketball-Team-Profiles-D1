"""
p105C — Player dataset column trimmer (one season)
--------------------------------------------------
Year-scoped port of Scripts/105C_master_player_dataset_column_trim.py. Trims the p105
output down to the final curated KEEP list (158 columns).

Usage:
    python -m pipeline.player.p105c_column_trim --year 2018 [--year 2023 ...]
"""

import pandas as pd

from pipeline import guard
from pipeline.stage import stage_main


def run(year, paths):
    # ============================================================
    # LOAD STEP 5 OUTPUT
    # ============================================================
    df = pd.read_csv(paths.stage_file("player_fe", year))

    # ============================================================
    # FINAL KEEP LIST (158 columns, validated)
    # ============================================================
    keep_cols = [
        "name","team","games","ortg","usage_pct","efg","ts","or_pct","dr_pct","ast_pct","tov_pct",
        "ftm","fta","ft_pct","two_pm","two_pa","three_pm","three_pa","blk_pct","stl_pct","ft_rate",
        "class","height","prpg","dprpg","oprpg","fc_40","year","recruit_rank_clean","ast_to_ratio",
        "close_two_made","close_two_att","close_two_pct","dunk_made","dunk_att","dunk_pct","drtg",
        "bpm","obpm","dbpm","rebpg","astpg","stlpg","blkpg","ppg","role","three_p_per_100",
        "player_id","player_season_id","player_id_collision","conference","power_mid","team_ts",
        "minutes_pct","minutes_played","minutes_per_game","total_points","total_reb","total_ast",
        "total_stl","total_blk","pts_per_40","reb_per_40","ast_per_40","stl_per_40","blk_per_40",
        "stocks_per_40","two_fg_pct","three_fg_pct","close_two_fg_pct","midrange_made","midrange_att",
        "midrange_fg_pct","dunk_fg_pct","total_fga","total_fgm","total_fg_pct","rim_made","rim_att",
        "rim_fg_pct","close_two_rate","midrange_rate","dunk_rate","rim_rate","three_rate",
        "close_vs_mid_ratio","rim_vs_three_ratio","paint_touch_proxy","two_att_pg","two_made_pg",
        "two_made_att_str","three_att_pg","three_made_pg","three_made_att_str","close_two_att_pg",
        "close_two_made_pg","close_two_made_att_str","midrange_att_pg","midrange_made_pg",
        "midrange_made_att_str","dunk_att_pg","dunk_made_pg","dunk_made_att_str","rim_att_pg",
        "rim_made_pg","rim_made_att_str","fga_pg","fgm_pg","fg_made_att_str","ft_att_pg","ft_made_pg",
        "ft_made_att_str","ast_tov_ratio","possessions","ppp_used","tov_sensitivity","foul_sensitivity",
        "ortg_delta_team","drtg_delta_team","age","height_in","height_str","class_num","years_in_d1",
        "hometown_city","hometown_state","ts_delta_team","efg_delta_team","rim_rate_delta_team",
        "three_rate_delta_team","conf_team_ts","conf_team_efg","conf_team_rim_rate","conf_team_three_rate",
        "conf_adj_o","conf_adj_d","ts_delta_conf","efg_delta_conf","rim_rate_delta_conf",
        "three_rate_delta_conf","ortg_delta_conf","drtg_delta_conf","sub_team_ts","sub_team_efg",
        "sub_team_rim_rate","sub_team_three_rate","sub_adj_o","sub_adj_d","ts_delta_sub","efg_delta_sub",
        "rim_rate_delta_sub","three_rate_delta_sub","ortg_delta_sub","drtg_delta_sub","mpg_tier",
        "usage_tier","games_tier","position"
    ]

    # ============================================================
    # TRIM TO FINAL SCHEMA
    # ============================================================
    df_trimmed = df[keep_cols].copy()

    # ============================================================
    # SAVE OUTPUT
    # ============================================================
    out = guard.to_csv(df_trimmed, paths.stage_file("player_trimmed", year), season=year, index=False)

    print(f"\n=== {year}: PLAYER DATASET TRIMMED SUCCESSFULLY ===")
    print(out)
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
