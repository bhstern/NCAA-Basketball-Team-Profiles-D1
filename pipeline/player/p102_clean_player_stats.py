"""
p102 — Clean Torvik player stats (one season)
---------------------------------------------
Year-scoped port of Scripts/102_clean_Torvik_player_stats.py. The original already
cleaned one season at a time and then concatenated; this writes the one season.

Assigns the 67-column header, drops the unidentifiable columns, converts height
("6-10", or Excel-corrupted "10-Jun") to inches.

Torvik's own player number (column AG, header "col_33_unidentifiable") is dropped from
the stage CSV exactly as the original did, so the stage output stays byte-identical. It
is written instead to a row-aligned side file, by_year/{Y}/torvik_numbers.csv, which
pipeline.player.torvik_ids uses to keep a returning player's ID stable.

Usage:
    python -m pipeline.player.p102_clean_player_stats --year 2018 [--year 2023 ...]
"""

import numpy as np
import pandas as pd

from pipeline import guard
from pipeline.legacy import pin_float_dtypes
from pipeline.player.p101_fetch_player_stats import KNOWN_COLUMNS, check_anchors
from pipeline.stage import stage_main
from pipeline.torvik import TorvikFetchError

# ---------------------------------------------------------
# Final 67-column header list (A → BO, 2026 schema)
# ---------------------------------------------------------
HEADERS_67 = [
    "name",                 # A
    "team",                 # B
    "conference",           # C
    "games",                # D
    "min_pct",              # E
    "ortg",                 # F
    "usage_pct",            # G
    "efg",                  # H
    "ts",                   # I
    "or_pct",               # J
    "dr_pct",               # K
    "ast_pct",              # L
    "tov_pct",              # M
    "ftm",                  # N
    "fta",                  # O
    "ft_pct",               # P
    "two_pm",               # Q
    "two_pa",               # R
    "two_p_pct",            # S
    "three_pm",             # T
    "three_pa",             # U
    "three_p_pct",          # V
    "blk_pct",              # W
    "stl_pct",              # X
    "ft_rate",              # Y
    "class",                # Z
    "height",               # AA
    "col_28_unidentifiable",# AB (drop)
    "prpg",                 # AC
    "raw_ortg",             # AD
    "fc_40",                # AE
    "year",                 # AF
    "col_33_unidentifiable",# AG (drop)
    "hometown",             # AH
    "recruit_rank",         # AI
    "ast_to_ratio",         # AJ
    "close_two_made",       # AK
    "close_two_att",        # AL
    "far_two_made",         # AM
    "far_two_att",          # AN
    "close_two_pct",        # AO
    "far_two_pct",          # AP
    "dunk_made",            # AQ
    "dunk_att",             # AR
    "dunk_pct",             # AS
    "col_46_unidentifiable",# AT (drop)
    "raw_drtg",             # AU
    "drtg",                 # AV
    "dprpg",                # AW
    "col_50_unidentifiable",# AX (drop)
    "col_51_unidentifiable",# AY (drop)
    "col_52_unidentifiable",# AZ (drop)
    "col_53_unidentifiable",# BA (drop)
    "bpm",                  # BB
    "col_55_unidentifiable",# BC (drop)
    "obpm",                 # BD
    "dbpm",                 # BE
    "col_59_unidentifiable",# BF (drop)
    "col_60_unidentifiable",# BG (drop)
    "rebpg",                # BH
    "astpg",                # BI
    "stlpg",                # BJ
    "blkpg",                # BK
    "ppg",                  # BL
    "role",                 # BM
    "three_p_per_100",      # BN
    "birthday"              # BO
]

# Columns that are whole-number typed in the original all-seasons frame
INT_COLUMNS = ("games", "ftm", "fta", "two_pm", "two_pa", "three_pm", "three_pa", "year")

# Columns to drop (your confirmed list)
DROP_COLS = [
    "col_28_unidentifiable",
    "col_33_unidentifiable",
    "col_46_unidentifiable",
    "col_50_unidentifiable",
    "col_51_unidentifiable",
    "col_52_unidentifiable",
    "col_53_unidentifiable",
    "col_55_unidentifiable",
    "col_59_unidentifiable",
    "col_60_unidentifiable",
]

# ---------------------------------------------------------
# Height parsing / correction
#
# Torvik stores height as "6-10", "5-11", etc.
# Excel corrupts these into "10-Jun", "11-May", etc.
#
# We convert BOTH formats into total inches:
#   6-10  -> 82
#   5-10  -> 70
#   10-Jun -> 82  (month=6, day=10)
# ---------------------------------------------------------
MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

def parse_height_to_inches(value):
    if pd.isna(value):
        return np.nan

    s = str(value).strip()

    # Case 1: Normal Torvik format "6-10"
    if "-" in s and s.replace("-", "").isdigit():
        try:
            ft, inch = s.split("-")
            return int(ft) * 12 + int(inch)
        except:
            return np.nan

    # Case 2: Excel-corrupted "10-Jun"
    if "-" in s:
        day, mon = s.split("-")
        mon = mon[:3].title()
        if mon in MONTH_MAP and day.isdigit():
            feet = MONTH_MAP[mon]
            inches = int(day)
            return feet * 12 + inches

    return np.nan

# Torvik's player number (raw column AG): dropped from the stage CSV, kept in a side file
TORVIK_NUMBER_COL = "col_33_unidentifiable"


# ---------------------------------------------------------
# Load + clean a single year
# ---------------------------------------------------------
def load_and_clean_year(year, raw_path, with_torvik_number=False):
    """The cleaned season. With with_torvik_number=True, returns (df, torvik_numbers):
    Torvik's player number per row (column AG), row-aligned with df."""
    print(f"Loading raw file for {year}: {raw_path}")

    df = pd.read_csv(raw_path, header=None)

    # Sanity check (Phase 5: additive-tolerant). The 67 known columns must be in place
    # (anchor-checked); trailing columns Torvik has appended are dropped here. The frozen
    # hand-built files have exactly 67, so this is a no-op for them.
    try:
        check_anchors(df, year, source=f"raw file {raw_path}")
    except TorvikFetchError as e:
        raise ValueError(str(e)) from e
    df = df.iloc[:, :KNOWN_COLUMNS]

    # Assign headers
    df.columns = HEADERS_67

    torvik_numbers = df[TORVIK_NUMBER_COL].astype("int64").rename("torvik_number")

    # Drop unidentifiable columns
    df = df.drop(columns=DROP_COLS, errors="ignore")

    # Fix height
    df["height"] = df["height"].apply(parse_height_to_inches)

    if with_torvik_number:
        return df, torvik_numbers.reset_index(drop=True)
    return df


def run(year, paths):
    df_year, torvik_numbers = load_and_clean_year(year, paths.raw_player(year), with_torvik_number=True)
    print(f"{year}: rows={df_year.shape[0]}, cols={df_year.shape[1]}")

    full = pd.concat([df_year], ignore_index=True)

    # Match the all-seasons original's column dtypes (see pipeline.legacy): e.g. height is
    # float there because some seasons have blanks, so it is written "78.0", not "78"
    full = pin_float_dtypes(full, int_columns=INT_COLUMNS)

    out = guard.to_csv(full, paths.stage_file("player_stats", year), season=year, index=False)
    print(f"Saved CLEAN dataset to: {out}")

    # Side file, row-aligned with the stage CSV (never a column in it: see the docstring)
    if len(torvik_numbers) != len(full):
        raise ValueError(f"{year}: {len(torvik_numbers)} Torvik numbers for {len(full)} rows")
    side = guard.to_csv(torvik_numbers.to_frame(), paths.torvik_numbers_file(year), season=year, index=False)
    print(f"Saved Torvik numbers to: {side}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
