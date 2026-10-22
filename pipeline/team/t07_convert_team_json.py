"""
t07 — Team profiles CSV -> site JSON (one season)
-------------------------------------------------
Year-scoped port of the repo's convert_data.py. Writes the season's cbb_{Y}.json
under <out_root>/json/data/, plus this season's slice of data/index.json as a
fragment; pipeline.assemble_json combines the fragments into index.json.

POST-BASELINE FIX (reviewed and approved 2026-10-21) — the ONE deliberate difference
from convert_data.py:
    06 writes full_season_record "Excel-safe" with a leading apostrophe ('9-18), and
    convert_data.py passed it through to the JSON. The site's existing JSON has never
    had the apostrophe (9-18), and team.js shows the field as-is. t07 drops ONE
    leading apostrophe from the JSON output only, so every season — the frozen ones
    and 2027 — renders the same. The team profiles CSV (06 / t06) keeps it.
    Consequence for validation: t07's output is compared against the repo JSON; it
    is intentionally NOT byte-identical to convert_data.py run unmodified.

Usage:
    python -m pipeline.team.t07_convert_team_json --year 2018 [--year 2023 ...]
"""

import json

import pandas as pd

from pipeline import guard
from pipeline.stage import stage_main


def run(year, paths):
    season = year

    # ── Load ──────────────────────────────────────────────────────────────────────
    print('Loading CSV...')
    df = pd.read_csv(paths.stage_file("team_profiles", season))
    print(f'  {len(df)} rows, {len(df.columns)} columns')

    # ── Clean full_season_record ──────────────────────────────────────────────────
    df['full_season_record'] = (
        df['full_season_record']
        .astype(str)
        .str.replace('="', '')
        .str.replace('"', '')
    )

    # POST-BASELINE FIX (see module docstring): drop the CSV's Excel-safe leading
    # apostrophe from the JSON output only — "'9-18" -> "9-18".
    df['full_season_record'] = df['full_season_record'].str.removeprefix("'")

    # ── Round numeric columns to reduce file size ─────────────────────────────────
    numeric_cols = df.select_dtypes(include='number').columns
    df[numeric_cols] = df[numeric_cols].round(4)

    # ── Fill NaN with None ────────────────────────────────────────────────────────
    df = df.where(pd.notnull(df), None)

    # ── Save one file per year ────────────────────────────────────────────────────
    years = sorted(df['year'].unique())
    print(f'\nWriting {len(years)} year files...')

    written = []
    for year in years:
        yr_df = df[df['year'] == year]
        records = yr_df.to_dict(orient='records')
        filepath = paths.json_file("data", f"cbb_{year}.json")
        written.append(guard.write_text(filepath, json.dumps(records, separators=(',', ':')), season=season))
        print(f'  cbb_{year}.json — {len(records)} teams')

    # ── This season's slice of the team/year index ───────────────────────────────
    index = {}
    for year in years:
        yr_df = df[df['year'] == year]
        index[str(year)] = sorted(yr_df['team_name'].tolist())

    guard.write_text(paths.json_fragment(season, "team_index.json"),
                     json.dumps(index, separators=(',', ':')), season=season)
    return written


if __name__ == "__main__":
    stage_main(run, __doc__)
