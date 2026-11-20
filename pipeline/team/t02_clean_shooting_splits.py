"""
t02 — Clean Torvik team shooting splits (one season)
----------------------------------------------------
Year-scoped port of Scripts/02_clean_Torvik_team_shooting_splits.py. Same logic,
one season in, one season out: standardizes team names into Team_Year keys and
repairs Excel-corrupted split columns.

Usage:
    python -m pipeline.team.t02_clean_shooting_splits --year 2018 [--year 2023 ...]
"""

import calendar
import os
import re
import unicodedata

import pandas as pd

from pipeline import guard
from pipeline.legacy import pin_float_dtypes
from pipeline.stage import stage_main
from pipeline.team.t01_fetch_shooting_splits import HEADER as CORE_RAW_COLUMNS


# ---------------------------------------------------------------------------
# Phase 5 — raw-file hygiene for the live 2026-27 fetch (both no-ops on the frozen
# hand-built files, which have exactly the 20 core columns and no symbol characters)
# ---------------------------------------------------------------------------

def keep_core_columns(df, filename):
    """Keep the 20 hand-built columns, in order. Extra raw-only columns (e.g. And-1s,
    which t01 stores after Year) never reach the cleaned splits or any later stage."""
    missing = [c for c in CORE_RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{filename}: raw shooting splits missing core columns {missing}")
    return df[CORE_RAW_COLUMNS]


def strip_symbols(s):
    """Drop pictographs from a team cell — Torvik's 🎯 "Interactive Shot Chart" link text
    (Unicode category So, plus emoji variation selectors) — and collapse the spaces it
    leaves, so 'Northwestern  🎯' keys as 'Northwestern', and 'Duke 1 🎯' still loses its seed."""
    if not isinstance(s, str):
        return s
    kept = "".join(ch for ch in s if unicodedata.category(ch) != "So" and ch not in "︎️")
    if kept == s:
        return s                      # untouched unless a symbol was actually present
    return re.sub(r"[ \xa0]+", lambda m: m.group(0)[0], kept).strip()

# ---------------------------------------------------------------------------
# 0. Team Name Normalization Function
# ---------------------------------------------------------------------------

def normalize_team_format(s):
    """
    Normalizes Torvik shooting splits team names into 'Team_Name_Year' format.
    Handles:
    - Non-breaking spaces (\xa0)
    - Embedded seed numbers (1–16)
    - Leading underscores
    - Multi-word team names
    - Extra spaces
    """
    if not isinstance(s, str):
        return s

    # Replace non-breaking spaces and strip whitespace
    s = s.replace("\xa0", " ").strip()

    # Remove leading underscores
    s = s.lstrip("_")

    # Split into parts
    parts = s.split()

    # Last part is always the year
    year = parts[-1]

    # Everything before the year is the team name
    team_parts = parts[:-1]

    # Remove seed-like numbers (1–16)
    team_parts = [p for p in team_parts if not re.fullmatch(r"[0-9]{1,2}", p)]

    # Rejoin cleaned team name
    team = " ".join(team_parts)

    return f"{team}_{year}"


# ---------------------------------------------------------------------------
# 3. Repair Excel‑Corrupted Split Columns
# ---------------------------------------------------------------------------

def fix_split_column(col):
    """
    Normalizes corrupted Torvik split columns into 'M-D' format.
    Handles:
    - 'Jul-8' or '8-Jul'
    - Excel serial dates
    - Numeric strings
    - Already-correct '20-30' style splits
    """
    def convert(x):
        # Already valid: "20-30"
        if isinstance(x, str) and re.fullmatch(r"\d{1,4}-\d{1,4}", x):
            return x

        # Excel corruption: "Jul-8"
        if isinstance(x, str) and re.fullmatch(r"[A-Za-z]{3}-\d{1,2}", x):
            mon, day = x.split("-")
            try:
                month_num = list(calendar.month_abbr).index(mon.capitalize())
                return f"{month_num}-{day}"
            except Exception:
                return x

        # Reverse Excel corruption: "8-Jul"
        if isinstance(x, str) and re.fullmatch(r"\d{1,2}-[A-Za-z]{3}", x):
            day, mon = x.split("-")
            try:
                month_num = list(calendar.month_abbr).index(mon.capitalize())
                return f"{month_num}-{day}"
            except Exception:
                return x

        # Excel serial stored as text
        if isinstance(x, str) and x.isdigit():
            try:
                dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(int(x), unit="D")
                return f"{dt.month}-{dt.day}"
            except Exception:
                return x

        # Excel serial as numeric
        if pd.api.types.is_number(x):
            try:
                dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(int(x), unit="D")
                return f"{dt.month}-{dt.day}"
            except Exception:
                return x

        return x

    return col.apply(convert)


def run(year, paths):
    # -----------------------------------------------------------------------
    # 1. Load the yearly file
    # -----------------------------------------------------------------------

    filename = paths.raw_shooting_splits(year)

    # The all-years original skipped a missing year; a one-year run has nothing to fall back on
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Missing raw shooting splits file: {filename}")

    df = pd.read_csv(filename)

    # Phase 5: the 20 core columns only (raw-only extras such as And-1s stay in the raw file)
    df = keep_core_columns(df, filename)

    # Drop the first column (Torvik index column)
    df = df.drop(df.columns[0], axis=1)

    # Identify team column
    team_col = df.columns[0]

    # Drop rows with missing team names
    df = df[df[team_col].notna()]

    # Phase 5: strip the 🎯 shot-chart link text before the name becomes a merge key
    df[team_col] = df[team_col].apply(strip_symbols)

    # Clean Torvik's trailing digits (e.g., "Gonzaga 11")
    df[team_col] = df[team_col].str.replace(r"\s+\d+$", "", regex=True)

    # Append year suffix
    df[team_col] = df[team_col].astype(str) + f" {year}"

    # Normalize team names into Team_Year format
    df[team_col] = df[team_col].apply(normalize_team_format)

    # -----------------------------------------------------------------------
    # 2. Combine & Standardize Columns
    # -----------------------------------------------------------------------

    combined = pd.concat([df], ignore_index=True)

    # Standardize column names
    combined.columns = (
        combined.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("%", "pct")
    )

    # Strip whitespace from string columns
    str_cols = combined.select_dtypes(include="object").columns
    combined[str_cols] = combined[str_cols].apply(lambda col: col.str.strip())

    # Remove duplicates
    combined = combined.drop_duplicates()

    # Convert numeric‑looking columns to numeric
    for col in combined.columns:
        try:
            combined[col] = pd.to_numeric(combined[col])
        except Exception:
            pass

    # Fill missing values
    combined = combined.fillna(0)

    # Match the all-seasons original's column dtypes (see pipeline.legacy)
    combined = pin_float_dtypes(combined, int_columns=())

    # Apply to the two corrupted columns
    combined["off_dunks"] = fix_split_column(combined["off_dunks"])
    combined["def_dunks"] = fix_split_column(combined["def_dunks"])

    # -----------------------------------------------------------------------
    # 4. Save Output
    # -----------------------------------------------------------------------

    out = guard.to_csv(combined, paths.stage_file("team_shooting_splits", year), season=year,
                       index=False, encoding="utf-8-sig")

    print(f"[SUCCESS] {year}: saved cleaned shooting splits ({len(combined)} teams) to:\n{out}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
