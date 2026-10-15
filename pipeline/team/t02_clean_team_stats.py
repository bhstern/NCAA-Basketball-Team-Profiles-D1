"""
t02 — Clean Torvik full-season team stats (one season)
------------------------------------------------------
Year-scoped port of Scripts/02_clean_Torvik_team_stats_fullseason.py. Same logic,
one season in, one season out: Team_Year keys, corrupted-character cleanup,
normalized columns, adj_em.

Usage:
    python -m pipeline.team.t02_clean_team_stats --year 2018 [--year 2023 ...]
"""

import os

import pandas as pd

from pipeline import guard
from pipeline.legacy import pin_float_dtypes
from pipeline.stage import stage_main


def run(year, paths):
    # -----------------------------------------------------------------------
    # 1. Load the yearly file
    # -----------------------------------------------------------------------

    filename = paths.raw_team_tables(year)

    # The all-years original skipped a missing year; a one-year run has nothing to fall back on
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Missing raw team tables file: {filename}")

    df = pd.read_csv(filename)

    # Append year to the team name (first column)
    team_col = df.columns[0]
    df[team_col] = df[team_col].astype(str) + f"_{year}"

    # -----------------------------------------------------------------------
    # 2. Combine & Standardize Columns
    # -----------------------------------------------------------------------

    combined = pd.concat([df], ignore_index=True)

    # Remove fully blank unnamed columns
    combined = combined.loc[:, ~combined.columns.str.contains("^unnamed", case=False)]

    # Fix corrupted dash characters across string columns
    combined = combined.apply(
        lambda col: col.str.replace("â€“", "-", regex=False)
        if col.dtype == "object" else col
    )

    # Standardize column names
    combined.columns = (
        combined.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("%", "pct")
    )

    # Strip whitespace from string columns
    str_cols = combined.select_dtypes(include=["object", "string"]).columns
    combined[str_cols] = combined[str_cols].apply(lambda col: col.str.strip())

    # Remove duplicates
    combined = combined.drop_duplicates()

    # Convert numeric-looking columns to numeric
    for col in combined.columns:
        try:
            combined[col] = pd.to_numeric(combined[col])
        except Exception:
            pass

    # Fill missing values
    combined = combined.fillna(0)

    # Match the all-seasons original's column dtypes (see pipeline.legacy)
    combined = pin_float_dtypes(combined, int_columns=("wins", "games", "year"))

    # -----------------------------------------------------------------------
    # 3. Create Adjusted Efficiency Margin (adj_em)
    # -----------------------------------------------------------------------

    combined["adj_em"] = (combined["adj_oe"] - combined["adj_de"]).round(4)

    # Move adj_em to the second column
    cols = combined.columns.tolist()
    cols.remove("adj_em")
    cols.insert(1, "adj_em")
    combined = combined[cols]

    # -----------------------------------------------------------------------
    # 4. Save Output
    # -----------------------------------------------------------------------

    out = guard.to_csv(combined, paths.stage_file("team_stats_full_season", year), season=year,
                       index=False, encoding="utf-8-sig")

    print(f"[DONE] {year}: full-season team stats ({len(combined)} teams) saved to:\n{out}")
    return out


if __name__ == "__main__":
    stage_main(run, __doc__)
