"""
t06 — Team profiles dataset, descriptive layer (one season)
-----------------------------------------------------------
Year-scoped port of Scripts/06_master_team_descriptive_profiles.py.

Loads the t05 feature-engineered season, selects a curated set of intuitive features,
standardizes conference names, and computes descriptive metrics including:

    • Overall D1 z-scores, percentiles, and ranks
    • Conference-only ranks + percentiles
    • Power vs Mid-Major subgroup z-scores, percentiles, and ranks
    • Efficiency differentials (PPP, xPPP, residual)
    • Rim Attempt Rate + Rim FG% (offense + defense)

All percentiles / z-scores / ranks are computed within the one season's pool — the
original already looped per season, so the per-season loop is kept as-is.

KNOWN RISK, REPRODUCED ON PURPOSE (spec §6 item 2): `.astype(int)` on the record and
rank columns will crash on NaN (early-season sparse data).

Usage:
    python -m pipeline.team.t06_team_profiles --year 2018 [--year 2023 ...]
"""

import pandas as pd

from pipeline import guard
from pipeline.stage import stage_main

# ============================================================
# CLEAN + STANDARDIZE CONFERENCE NAMES
# ============================================================

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

# ============================================================
# POWER VS MID-MAJOR FIELD
# ============================================================

power_confs = ["Big 12", "Big East", "SEC", "ACC", "Big Ten", "Pac-12"]

# ============================================================
# CURATED FEATURE LIST
# ============================================================

keep_cols = [

    # A. Team Identity
    "year", "team", "team_name", "full_season_record",
    "conference", "power_mid", "elite_sos_rate",

    # B. Roster
    "avg_hgt.", "eff._hgt.", "exp.", "talent",

    # C. Team Strength
    "adj_em", "adj_oe", "adj_de",
    "ppp_diff", "xPPP_diff", "residual_diff",
    "barthag",

    # D. Tempo
    "adj._t", "raw_t",

    # E. Four Factors
    "efg_rate_off", "tov_rate_off", "orb_rate_off", "ft_rate_off",
    "efg_rate_def", "tov_rate_def", "orb_rate_def", "ft_rate_def",

    # F. Shot Profile (Distribution + FG%)
    "off_dunks_rate_total", "off_dunks_fg",
    "off_close_twos_rate_total", "off_close_twos_fg",
    "off_long_twos_rate_total", "off_long_twos_fg",
    "off_threes_rate_total", "off_threes_fg",

    "def_dunks_rate_total", "def_dunks_fg",
    "def_close_twos_rate_total", "def_close_twos_fg",
    "def_long_twos_rate_total", "def_long_twos_fg",
    "def_threes_rate_total", "def_threes_fg",

    # Rim Metrics
    "off_rim_rate_total", "off_rim_fg",
    "def_rim_rate_total", "def_rim_fg",

    # G. Shotmaking
    "ppp_off_full", "ppp_def_full",
    "xPPP_off", "xPPP_def",
    "ppp_residual_off", "ppp_residual_def",
    "ft_pct_off",

    # H. Additional Descriptors
    "blk_pct_off", "blk_pct_def",
    "ast_pct_off", "ast_pct_def",
]

# ============================================================
# CORRECTED DIRECTIONALITY
# ============================================================

higher_better = [
    "elite_sos_rate", "avg_hgt.", "eff._hgt.", "exp.", "talent",
    "adj_em", "adj_oe",
    "ppp_diff", "xPPP_diff", "residual_diff", "barthag",
    "adj._t", "raw_t",
    "efg_rate_off", "orb_rate_off", "ft_rate_off", "tov_rate_def",

    # Offensive FG%
    "off_dunks_fg", "off_close_twos_fg", "off_long_twos_fg", "off_threes_fg",

    # Rim FG% (offense)
    "off_rim_fg",

    # Shotmaking
    "ppp_off_full", "xPPP_off", "ppp_residual_off",
    "blk_pct_def", "ast_pct_off",
    "ft_pct_off",
]

lower_better = [
    "adj_de",
    "tov_rate_off",
    "efg_rate_def", "orb_rate_def", "ft_rate_def",

    # Defensive FG%
    "def_dunks_fg", "def_close_twos_fg", "def_long_twos_fg", "def_threes_fg",

    # Rim FG% allowed
    "def_rim_fg",

    "ppp_def_full", "xPPP_def",
    "ast_pct_def",
    "ppp_residual_def",
    "blk_pct_off",
]

neutral_style = [
    # Offensive shot distribution
    "off_dunks_rate_total", "off_close_twos_rate_total",
    "off_long_twos_rate_total", "off_threes_rate_total",

    # Defensive shot distribution
    "def_dunks_rate_total", "def_close_twos_rate_total",
    "def_long_twos_rate_total", "def_threes_rate_total",

    # Rim attempt rate (style)
    "off_rim_rate_total",
    "def_rim_rate_total",
]

all_stats = higher_better + lower_better + neutral_style

# ============================================================
# DESCRIPTIVE METRIC FUNCTION
# ============================================================

def compute_descriptives(group, stat, direction):
    values = group[stat].astype(float)

    z = (values - values.mean()) / values.std(ddof=0)
    if direction == "lower":
        z = -z

    pct = values.rank(pct=True)
    if direction == "lower":
        pct = 1 - pct

    rank = values.rank(ascending=(direction == "lower"))

    return z, pct, rank


def run(year, paths):
    # ============================================================
    # LOAD STEP 5 OUTPUT
    # ============================================================

    df = pd.read_csv(paths.stage_file("master_team_fe", year))

    # ============================================================
    # TEAM NAME FIELD
    # ============================================================

    df["team_name"] = df["team"].str.replace(r"_\d{4}$", "", regex=True)

    # ============================================================
    # EXCEL-SAFE RECORD FIELD
    # ============================================================

    df["full_season_record"] = (
        "'" +
        df["full_season_wins"].astype(int).astype(str)
        + "-"
        + df["full_season_losses"].astype(int).astype(str)
    )

    # ============================================================
    # DIFFERENTIAL METRICS
    # ============================================================

    df["ppp_diff"] = df["ppp_off_full"] - df["ppp_def_full"]
    df["xPPP_diff"] = df["xPPP_off"] - df["xPPP_def"]
    df["residual_diff"] = df["ppp_residual_off"] - df["ppp_residual_def"]

    df["conference"] = df["conference"].map(conference_map).fillna(df["conference"])

    df["power_mid"] = df["conference"].apply(
        lambda c: "Power" if c in power_confs else "Mid-Major"
    )

    df_team_profiles = df[keep_cols].copy()

    # ============================================================
    # SUBGROUP FIELD
    # ============================================================

    df_team_profiles["subgroup"] = df_team_profiles["conference"].apply(
        lambda c: "power" if c in power_confs else "midmajor"
    )

    # ============================================================
    # MAIN LOOP — PER SEASON
    # ============================================================

    output_frames = []

    for season, season_df in df_team_profiles.groupby("year"):

        season_df = season_df.copy()

        # Overall D1 descriptives
        for stat in all_stats:

            if stat in higher_better:
                direction = "higher"
            elif stat in lower_better:
                direction = "lower"
            else:
                direction = "neutral"

            z, pct, rank = compute_descriptives(season_df, stat, direction)

            season_df[f"{stat}_z"] = z
            season_df[f"{stat}_pct"] = pct
            season_df[f"{stat}_rank"] = rank

        # ============================================================
        # Conference ranks + percentiles (FIXED)
        #   - conf_rank: 1 = best, n = worst
        #   - conf_pct:  1.0 = best, 1/n = worst
        # ============================================================

        for conf, conf_df in season_df.groupby("conference"):
            n = len(conf_df)

            for stat in all_stats:
                asc = stat in lower_better

                # Rank (1 = best, n = worst)
                ranks = conf_df[stat].rank(ascending=asc)
                season_df.loc[conf_df.index, f"{stat}_conf_rank"] = ranks

                # Percentile: invert rank so lower rank = higher percentile
                season_df.loc[conf_df.index, f"{stat}_conf_pct"] = (n - ranks + 1) / n

        # Subgroup descriptives
        for subgroup, sub_df in season_df.groupby("subgroup"):
            for stat in all_stats:

                if stat in higher_better:
                    direction = "higher"
                elif stat in lower_better:
                    direction = "lower"
                else:
                    direction = "neutral"

                z, pct, rank = compute_descriptives(sub_df, stat, direction)

                season_df.loc[sub_df.index, f"{stat}_sub_z"] = z
                season_df.loc[sub_df.index, f"{stat}_sub_pct"] = pct
                season_df.loc[sub_df.index, f"{stat}_sub_rank"] = rank

        output_frames.append(season_df)

    # ============================================================
    # MERGE ALL SEASONS
    # ============================================================

    df_team_profiles_full = pd.concat(output_frames, ignore_index=True)

    # ============================================================
    # FINAL COLUMN ORDERING
    # ============================================================

    raw_stats = [
        col for col in keep_cols
        if col not in ["year", "team", "team_name", "full_season_record", "conference", "power_mid"]
    ]

    final_cols = [
        "year", "team", "team_name", "full_season_record",
        "conference", "power_mid"
    ]

    for stat in raw_stats:
        final_cols.extend([
            stat,
            f"{stat}_z",
            f"{stat}_pct",
            f"{stat}_rank",
            f"{stat}_conf_rank",
            f"{stat}_conf_pct",
            f"{stat}_sub_z",
            f"{stat}_sub_pct",
            f"{stat}_sub_rank",
        ])

    df_team_profiles_full = df_team_profiles_full[final_cols].copy()

    # ============================================================
    # CAST RANK COLUMNS TO INTEGERS
    # ============================================================

    rank_cols = [col for col in df_team_profiles_full.columns if col.endswith("_rank")]

    for col in rank_cols:
        df_team_profiles_full[col] = df_team_profiles_full[col].astype(int)

    # ============================================================
    # SAVE OUTPUT
    # ============================================================

    out = guard.to_csv(df_team_profiles_full, paths.stage_file("team_profiles", year),
                       season=year, index=False)

    print(f"\n=== {year}: TEAM PROFILES SAVED ({len(df_team_profiles_full)} teams) ===")
    print(out)
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
