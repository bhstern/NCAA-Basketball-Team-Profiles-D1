"""
p105 — Player-level feature engineering (one season)
----------------------------------------------------
Year-scoped port of Scripts/105_master_player_dataset_feature_engineering.py. The body
below is the original, unchanged, except for the marked ONE-SEASON PORT blocks.

Major components:
    • Hybrid player IDs (readable + short hash)
    • Merge player + limited team context
    • Minutes + per-40 conversions
    • Shot profile (rates, ratios, FG%)
    • Efficiency (PPP, turnover sensitivity, foul sensitivity)
    • Contextual deltas (team / conf / subgroup / national)
    • Bio + height + class + experience
    • Stability tiers
    • Position mapping

Cross-season logic (player_id_collision, years_in_d1, row order) reads the frozen
player history index — see pipeline.player.history. Team context comes from this
season's t05 output, so the team chain must run first.

KNOWN ISSUE, REPRODUCED ON PURPOSE (spec §6 item 3): the conference map has no fillna,
so an unknown conference code becomes NaN.

Usage:
    python -m pipeline.player.p105_feature_engineering --year 2018 [--year 2023 ...]
"""

import pandas as pd
import numpy as np

from pipeline import guard
from pipeline.player import history
from pipeline.player.ids import add_player_ids
from pipeline.stage import stage_main


def run(year, paths):
    EPS = 1e-6

    # ============================================================
    # LOAD PLAYER DATA
    # ============================================================
    player = pd.read_csv(paths.stage_file("player_stats", year))

    # ------------------------------------------------------------
    # PLAYER IDENTIFIERS — HYBRID FORMAT (FINAL)
    # ------------------------------------------------------------
    # Birthday is cleaned BEFORE ID creation. The ID functions live in pipeline.player.ids
    # (unchanged) so the history index is keyed by exactly the same IDs.

    player = add_player_ids(player)

    # ------------------------------------------------------------
    # TRUE COLLISION FLAG
    # TRUE if the same player_id appears on multiple teams in the SAME year
    # (indicating two different humans)
    # ------------------------------------------------------------

    # ONE-SEASON PORT: the original scanned every season in one frame. Here the other
    # (frozen) seasons come from the read-only history index, plus this season's rows.
    # Only this season's rows are flagged — frozen seasons are never rewritten.
    history_index = history.load(paths)
    player["player_id_collision"] = history.collision_flags(history_index, player, year)

    # ------------------------------------------------------------
    # NUMERIC CONVERSIONS
    # ------------------------------------------------------------
    numeric_cols = [
        "games","min_pct","ortg","usage_pct","efg","ts",
        "or_pct","dr_pct","ast_pct","tov_pct",
        "ftm","fta","two_pm","two_pa","three_pm","three_pa",
        "close_two_made","close_two_att",
        "far_two_made","far_two_att",
        "dunk_made","dunk_att",
        "blk_pct","stl_pct",
        "prpg","raw_ortg","fc_40",
        "raw_drtg","drtg","dprpg",
        "rebpg","astpg","stlpg","blkpg","ppg",
        "height","recruit_rank",
        "ast_to_ratio","three_p_per_100"
    ]

    for col in numeric_cols:
        if col in player.columns:
            player[col] = pd.to_numeric(player[col], errors="coerce")

    # ============================================================
    # LOAD TEAM DATA
    # ============================================================
    team = pd.read_csv(paths.stage_file("master_team_fe", year))

    team.columns = team.columns.str.strip()
    team["team"] = team["team"].astype(str).str.strip()

    if team["team"].str.contains("_").any():
        team[["team","year"]] = team["team"].str.rsplit("_", n=1, expand=True)

    team["team"] = team["team"].astype("string").str.strip()
    team["year"] = team["year"].astype(int)
    team["conference"] = team["conference"].astype("string").str.strip()

    # ------------------------------------------------------------
    # LIMIT TEAM COLUMNS TO ONLY WHAT WE NEED
    # ------------------------------------------------------------
    team_keep = [
        "team", "year", "conference",
        "full_season_games",
        "adj_oe", "adj_de", "adj._t",
        "efg_rate_off", "off_rim_rate_total", "off_threes_rate_total",
        "pts_off_est", "off_fga", "fta_off_est"
    ]

    team = team[team_keep]

    # ============================================================
    # MERGE PLAYER + TEAM CONTEXT
    # ============================================================
    df = player.merge(team, on=["team","year"], how="left")

    # ============================================================
    # CONFERENCE COLUMN CLEANUP + NORMALIZATION
    # ============================================================

    # First, fix conference_x / conference_y from the merge
    if "conference_x" in df.columns and "conference_y" in df.columns:
        df = df.drop(columns=["conference_x"])
        df = df.rename(columns={"conference_y": "conference"})
    elif "conference_x" in df.columns:
        df = df.rename(columns={"conference_x": "conference"})
    elif "conference_y" in df.columns:
        df = df.rename(columns={"conference_y": "conference"})

    # Now apply the mapping *only if* conference exists
    conference_map = {
        "Slnd": "Southland", "WAC": "WAC", "MWC": "Mountain West", "MAC": "MAC",
        "SWAC": "SWAC", "SEC": "SEC", "AE": "America East", "Pat": "Patriot",
        "SB": "Sun Belt", "P12": "Pac-12", "B12": "Big 12", "OVC": "Ohio Valley",
        "ASun": "Atlantic Sun", "WCC": "WCC", "MVC": "Missouri Valley",
        "MEAC": "MEAC", "ACC": "ACC", "Ivy": "Ivy", "NEC": "Northeast",
        "BE": "Big East", "BW": "Big West", "BSth": "Big South", "CAA": "CAA",
        "MAAC": "MAAC", "CUSA": "Conference USA", "Amer": "American",
        "SC": "SoCon", "ind": "Independent", "Horz": "Horizon", "A10": "A10",
        "Sum": "Summit", "BSky": "Big Sky", "B10": "Big Ten"
    }

    if "conference" in df.columns:
        df["conference"] = df["conference"].map(conference_map)
    else:
        print("WARNING: conference column missing after merge.")

    # ============================================================
    # TEAM CONTEXT FEATURES (PREFIXED WITH team_)
    # ============================================================
    df["team_minutes"] = df["full_season_games"] * 40

    df["team_ts"] = df["pts_off_est"] / (
        2 * (df["off_fga"] + 0.44 * df["fta_off_est"] + EPS)
    )

    power_confs = {"ACC","Big Ten","Big 12","SEC","Pac-12","Big East"}
    df["power_mid"] = np.where(df["conference"].isin(power_confs), "Power", "Mid")

    df["team_efg"] = df["efg_rate_off"]
    df["team_rim_rate"] = df["off_rim_rate_total"]
    df["team_three_rate"] = df["off_threes_rate_total"]

    df["team_adj_o"] = df["adj_oe"]
    df["team_adj_d"] = df["adj_de"]
    df["team_adj_t"] = df["adj._t"]

    # Remove short versions
    df = df.drop(columns=["adj_oe","adj_de","adj._t"])

    # ============================================================
    # MINUTES + MPG
    # ============================================================
    df["minutes_pct"] = df["min_pct"]  # rename
    df["minutes_played"] = (df["minutes_pct"] / 100) * df["team_minutes"]
    df["minutes_per_game"] = df["minutes_played"] / df["games"].replace(0, np.nan)

    # ============================================================
    # PER-40 STATS
    # ============================================================
    df["total_points"] = (
        2*df["two_pm"].fillna(0)
        + 3*df["three_pm"].fillna(0)
        + df["ftm"].fillna(0)
    )

    df["total_reb"] = df["rebpg"] * df["games"]
    df["total_ast"] = df["astpg"] * df["games"]
    df["total_stl"] = df["stlpg"] * df["games"]
    df["total_blk"] = df["blkpg"] * df["games"]

    df["pts_per_40"] = (df["total_points"] / df["minutes_played"]) * 40
    df["reb_per_40"] = (df["total_reb"] / df["minutes_played"]) * 40
    df["ast_per_40"] = (df["total_ast"] / df["minutes_played"]) * 40
    df["stl_per_40"] = (df["total_stl"] / df["minutes_played"]) * 40
    df["blk_per_40"] = (df["total_blk"] / df["minutes_played"]) * 40

    df["stocks_per_40"] = df["stl_per_40"] + df["blk_per_40"]

    # ============================================================
    # SHOT PROFILE
    # ============================================================

    # Fix close_two to exclude dunks (Torvik's close_two_att includes dunks)
    df["close_two_att"] = df["close_two_att"].fillna(0) - df["dunk_att"].fillna(0)
    df["close_two_made"] = df["close_two_made"].fillna(0) - df["dunk_made"].fillna(0)

    # FG%
    df["two_fg_pct"] = df["two_pm"] / (df["two_pa"] + EPS)
    df["three_fg_pct"] = df["three_pm"] / (df["three_pa"] + EPS)
    df["close_two_fg_pct"] = df["close_two_made"] / (df["close_two_att"] + EPS)

    # midrange replaces far_two
    df["midrange_made"] = df["far_two_made"]
    df["midrange_att"] = df["far_two_att"]
    df["midrange_fg_pct"] = df["midrange_made"] / (df["midrange_att"] + EPS)

    df["dunk_fg_pct"] = df["dunk_made"] / (df["dunk_att"] + EPS)

    # totals
    df["total_fga"] = df["two_pa"].fillna(0) + df["three_pa"].fillna(0)
    df["total_fgm"] = df["two_pm"].fillna(0) + df["three_pm"].fillna(0)
    df["total_fg_pct"] = df["total_fgm"] / (df["total_fga"] + EPS)

    # rim = close_two + dunks (now correctly non-overlapping)
    df["rim_att"] = df["close_two_att"].fillna(0) + df["dunk_att"].fillna(0)
    df["rim_made"] = df["close_two_made"].fillna(0) + df["dunk_made"].fillna(0)
    df["rim_fg_pct"] = df["rim_made"] / (df["rim_att"] + EPS)

    df["three_att"] = df["three_pa"].fillna(0)

    denom = df["total_fga"].replace(0, np.nan)

    # rates
    df["close_two_rate"] = df["close_two_att"] / denom
    df["midrange_rate"] = df["midrange_att"] / denom
    df["dunk_rate"] = df["dunk_att"] / denom
    df["rim_rate"] = df["rim_att"] / denom
    df["three_rate"] = df["three_att"] / denom

    # FT%
    df["ft_pct"] = df["ftm"] / (df["fta"] + EPS)
    df["ft_rate"] = df["fta"] / (df["total_fga"] + EPS)

    # ratios
    df["close_vs_mid_ratio"] = df["rim_att"] / (df["midrange_att"] + EPS)
    df["rim_vs_three_ratio"] = df["rim_att"] / (df["three_att"] + EPS)
    df["paint_touch_proxy"] = df["rim_att"] / (df["total_fga"] + EPS)

    # ============================================================
    # PER-GAME VOLUMES + MADE/ATTEMPT STRINGS
    # ============================================================

    # 2PT
    df["two_att_pg"] = df["two_pa"] / df["games"]
    df["two_made_pg"] = df["two_pm"] / df["games"]
    df["two_made_att_str"] = (df["two_pm"].fillna(0).astype(int).astype(str) + "/" + df["two_pa"].fillna(0).astype(int).astype(str))

    # 3PT
    df["three_att_pg"] = df["three_pa"] / df["games"]
    df["three_made_pg"] = df["three_pm"] / df["games"]
    df["three_made_att_str"] = (df["three_pm"].fillna(0).astype(int).astype(str) + "/" + df["three_pa"].fillna(0).astype(int).astype(str))

    # Close Twos
    df["close_two_att_pg"] = df["close_two_att"] / df["games"]
    df["close_two_made_pg"] = df["close_two_made"] / df["games"]
    df["close_two_made_att_str"] = (df["close_two_made"].fillna(0).astype(int).astype(str) + "/" + df["close_two_att"].fillna(0).astype(int).astype(str))

    # Midrange
    df["midrange_att_pg"] = df["midrange_att"] / df["games"]
    df["midrange_made_pg"] = df["midrange_made"] / df["games"]
    df["midrange_made_att_str"] = (df["midrange_made"].fillna(0).astype(int).astype(str) + "/" + df["midrange_att"].fillna(0).astype(int).astype(str))

    # Dunks
    df["dunk_att_pg"] = df["dunk_att"] / df["games"]
    df["dunk_made_pg"] = df["dunk_made"] / df["games"]
    df["dunk_made_att_str"] = (df["dunk_made"].fillna(0).astype(int).astype(str) + "/" + df["dunk_att"].fillna(0).astype(int).astype(str))

    # Rim (combined)
    df["rim_att_pg"] = df["rim_att"] / df["games"]
    df["rim_made_pg"] = df["rim_made"] / df["games"]
    df["rim_made_att_str"] = (df["rim_made"].fillna(0).astype(int).astype(str) + "/" + df["rim_att"].fillna(0).astype(int).astype(str))

    # Totals
    df["fga_pg"] = df["total_fga"] / df["games"]
    df["fgm_pg"] = df["total_fgm"] / df["games"]
    df["fg_made_att_str"] = (df["total_fgm"].fillna(0).astype(int).astype(str) + "/" + df["total_fga"].fillna(0).astype(int).astype(str))

    # FT
    df["ft_att_pg"] = df["fta"] / df["games"]
    df["ft_made_pg"] = df["ftm"] / df["games"]
    df["ft_made_att_str"] = (df["ftm"].fillna(0).astype(int).astype(str) + "/" + df["fta"].fillna(0).astype(int).astype(str))

    # ============================================================
    # EFFICIENCY FEATURES
    # ============================================================
    df["ast_tov_ratio"] = df["ast_to_ratio"].replace(0, np.nan)

    df["possessions"] = df["full_season_games"] * df["team_adj_t"]

    df["ppp_used"] = df["total_points"] / (
        (df["usage_pct"]/100) * df["possessions"].replace(0, np.nan)
    )

    df["oprpg"] = df["prpg"] - df["dprpg"]

    df["three_p_per_100"] = df["three_p_per_100"].fillna(
        (df["three_pm"] / df["possessions"].replace(0, np.nan)) * 100
    )

    df["tov_sensitivity"] = df["tov_pct"] * (df["usage_pct"]/100)
    df["foul_sensitivity"] = df["fc_40"] / (df["minutes_per_game"] + EPS)

    df["ortg_delta_team"] = df["ortg"] - df["team_adj_o"]
    df["drtg_delta_team"] = df["drtg"] - df["team_adj_d"]

    # ============================================================
    # PLAYER INFO (AGE, HEIGHT, CLASS, EXPERIENCE)
    # ============================================================
    df["season_date"] = pd.to_datetime(df["year"].astype(str) + "-02-01")
    df["age"] = (df["season_date"] - pd.to_datetime(df["birthday"])).dt.days / 365.25

    # HEIGHT — already in inches in the raw dataset
    df["height_in"] = pd.to_numeric(df["height"], errors="coerce")

    df["height_cm"] = df["height_in"] * 2.54
    df["height_ft"] = (df["height_in"] // 12).astype("Int64")
    df["height_in_rem"] = (df["height_in"] % 12).astype("Int64")

    df["height_str"] = (
        df["height_ft"].astype(str) + "'" +
        df["height_in_rem"].astype(str) + "\""
    )

    # Normalize class labels
    df["class"] = (
        df["class"]
        .str.upper()
        .str.replace(".", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    # Normalize class labels
    df["class"] = (
        df["class"]
        .str.upper()
        .str.replace(".", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    class_map = {
        "FR":1,"SO":2,"JR":3,"SR":4,"GR":5,
        "R-FR":1,"R-SO":2,"R-JR":3,"R-SR":4,
    }

    df["class_num"] = df["class"].map(class_map)

    # ONE-SEASON PORT: match the all-seasons original's dtype (see pipeline.legacy). There
    # class_num is float because some seasons have unmapped classes ("--"), so it is
    # written "2.0"; a season where every class maps would otherwise infer int ("2").
    df["class_num"] = df["class_num"].astype("float64")

    # Compute years_in_d1
    # ONE-SEASON PORT of:  df = df.sort_values('year')
    #                      df['years_in_d1'] = df.groupby('player_id')['year'].cumcount() + 1
    # The original's sort is unstable and shuffles rows within the season; a frozen season
    # replays that exact order from the history index (legacy_pos, keyed on
    # player_season_id). The current season uses an explicit stable sort.
    # The cumcount then starts from the player's rows in EARLIER seasons.
    df = history.order_rows(history_index, df, year)
    df['years_in_d1'] = (
        history.prior_season_rows(history_index, df, year)
        + df.groupby('player_id')['year'].cumcount() + 1
    )

    # Null out collision players
    df.loc[df['player_id_collision'] == True, 'years_in_d1'] = pd.NA

    # Null out early years — unreliable before 2020 due to dataset starting in 2016
    df.loc[df['year'] <= 2019, 'years_in_d1'] = pd.NA

    df["recruit_rank_clean"] = df["recruit_rank"].replace(0, np.nan)

    if "hometown" in df.columns:
        df["hometown_city"] = df["hometown"].str.split(",").str[0]
        df["hometown_state"] = df["hometown"].str.split(",").str[1].str.strip()

    # ============================================================
    # CONTEXTUAL DELTAS
    # ============================================================
    df["ts_delta_team"] = df["ts"] - (df["team_ts"] * 100)
    df["efg_delta_team"] = df["efg"] - (df["team_efg"] * 100)
    df["rim_rate_delta_team"] = df["rim_rate"] - df["team_rim_rate"]
    df["three_rate_delta_team"] = df["three_rate"] - df["team_three_rate"]

    # CONFERENCE DELTAS
    conf_means = df.groupby(["year","conference"]).agg(
        conf_team_ts=("team_ts","mean"),
        conf_team_efg=("team_efg","mean"),
        conf_team_rim_rate=("team_rim_rate","mean"),
        conf_team_three_rate=("team_three_rate","mean"),
        conf_adj_o=("team_adj_o","mean"),
        conf_adj_d=("team_adj_d","mean"),
    ).reset_index()

    df = df.merge(conf_means, on=["year","conference"], how="left")

    df["ts_delta_conf"] = df["ts"] - (df["conf_team_ts"] * 100)
    df["efg_delta_conf"] = df["efg"] - (df["conf_team_efg"] * 100)
    df["rim_rate_delta_conf"] = df["rim_rate"] - df["conf_team_rim_rate"]
    df["three_rate_delta_conf"] = df["three_rate"] - df["conf_team_three_rate"]
    df["ortg_delta_conf"] = df["ortg"] - df["conf_adj_o"]
    df["drtg_delta_conf"] = df["drtg"] - df["conf_adj_d"]

    # SUBGROUP DELTAS
    sub_means = df.groupby(["year","power_mid"]).agg(
        sub_team_ts=("team_ts","mean"),
        sub_team_efg=("team_efg","mean"),
        sub_team_rim_rate=("team_rim_rate","mean"),
        sub_team_three_rate=("team_three_rate","mean"),
        sub_adj_o=("team_adj_o","mean"),
        sub_adj_d=("team_adj_d","mean"),
    ).reset_index()

    df = df.merge(sub_means, on=["year","power_mid"], how="left")

    df["ts_delta_sub"] = df["ts"] - (df["sub_team_ts"] * 100)
    df["efg_delta_sub"] = df["efg"] - (df["sub_team_efg"] * 100)
    df["rim_rate_delta_sub"] = df["rim_rate"] - df["sub_team_rim_rate"]
    df["three_rate_delta_sub"] = df["three_rate"] - df["sub_team_three_rate"]
    df["ortg_delta_sub"] = df["ortg"] - df["sub_adj_o"]
    df["drtg_delta_sub"] = df["drtg"] - df["sub_adj_d"]

    # NATIONAL DELTAS
    nat_means = df.groupby("year").agg(
        nat_team_ts=("team_ts","mean"),
        nat_team_efg=("team_efg","mean"),
        nat_team_rim_rate=("team_rim_rate","mean"),
        nat_team_three_rate=("team_three_rate","mean"),
        nat_adj_o=("team_adj_o","mean"),
        nat_adj_d=("team_adj_d","mean"),
    ).reset_index()

    df = df.merge(nat_means, on="year", how="left")

    df["ts_delta_nat"] = df["ts"] - df["nat_team_ts"]
    df["efg_delta_nat"] = df["efg"] - df["nat_team_efg"]
    df["rim_rate_delta_nat"] = df["rim_rate"] - df["nat_team_rim_rate"]
    df["three_rate_delta_nat"] = df["three_rate"] - df["nat_team_three_rate"]
    df["ortg_delta_nat"] = df["ortg"] - df["nat_adj_o"]
    df["drtg_delta_nat"] = df["drtg"] - df["nat_adj_d"]

    # ============================================================
    # STABILITY FEATURES
    # ============================================================
    df["mpg_tier"] = pd.cut(
        df["minutes_per_game"],
        bins=[0,5,10,18,26,np.inf],
        labels=[
            "End of Bench (0–5 MPG)",
            "Fringe Rotation (5–10 MPG)",
            "Bench Rotation (10–18 MPG)",
            "Primary Rotation (18–26 MPG)",
            "Core Player (26+ MPG)",
        ],
        right=False
    )

    df["usage_tier"] = pd.cut(
        df["usage_pct"],
        bins=[0,15,20,25,np.inf],
        labels=[
            "Low Usage (<15%)",
            "Secondary (15–20%)",
            "Primary (20–25%)",
            "High Usage (25%+)",
        ],
        right=False
    )

    df["games_tier"] = pd.cut(
        df["games"],
        bins=[0,10,20,np.inf],
        labels=[
            "Low Games (<10)",
            "Medium Games (10–20)",
            "High Games (21+)",
        ],
        right=False
    )

    # ============================================================
    # POSITION MAPPING
    # ============================================================
    guard_roles = ["Combo G","Scoring PG","Pure PG"]
    wing_roles = ["Wing G","Wing F"]
    big_roles = ["Stretch 4","PF/C","C"]

    df["position"] = "NA"
    df.loc[df["role"].isin(guard_roles), "position"] = "Guard"
    df.loc[df["role"].isin(wing_roles), "position"] = "Wing"
    df.loc[df["role"].isin(big_roles), "position"] = "Big"

    # ============================================================
    # SAVE FULL FEATURE ENGINEERING OUTPUT
    # ============================================================
    out = guard.to_csv(df, paths.stage_file("player_fe", year), season=year, index=False)

    print(f"Saved: {year} player feature engineering ({len(df)} rows) -> {out}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
