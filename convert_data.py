"""
CBB Data Converter — Per-Year Version
Converts your CSV into one JSON file per season (e.g. cbb_2026.json).
Each file is ~3MB, well under GitHub's 25MB limit.
Run this once, and re-run whenever you update the CSV.
"""

import pandas as pd
import json
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
CSV_PATH = r'C:\Users\bstern\OneDrive - Harris Blitzer Sports & Entertainment\Desktop\CBB Analysis\2016-2026 CBB Dataset Team Profiles.csv'
OUTPUT_DIR = r'C:\Users\bstern\OneDrive - Harris Blitzer Sports & Entertainment\Desktop\CBB Analysis\Team Profiles Website\cbb_site\data'

# ── Load ──────────────────────────────────────────────────────────────────────
print('Loading CSV...')
df = pd.read_csv(CSV_PATH)
print(f'  {len(df)} rows, {len(df.columns)} columns')

# ── Clean full_season_record ──────────────────────────────────────────────────
df['full_season_record'] = (
    df['full_season_record']
    .astype(str)
    .str.replace('="', '')
    .str.replace('"', '')
)

# ── Round numeric columns to reduce file size ─────────────────────────────────
numeric_cols = df.select_dtypes(include='number').columns
df[numeric_cols] = df[numeric_cols].round(4)

# ── Fill NaN with None ────────────────────────────────────────────────────────
df = df.where(pd.notnull(df), None)

# ── Save one file per year ────────────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)

years = sorted(df['year_stats'].unique())
print(f'\nWriting {len(years)} year files...')

for year in years:
    yr_df = df[df['year_stats'] == year]
    records = yr_df.to_dict(orient='records')
    filepath = os.path.join(OUTPUT_DIR, f'cbb_{year}.json')
    with open(filepath, 'w') as f:
        json.dump(records, f, separators=(',', ':'))
    size_kb = os.path.getsize(filepath) / 1024
    print(f'  cbb_{year}.json — {len(records)} teams, {size_kb:.0f} KB')

# ── Save team/year index ──────────────────────────────────────────────────────
index = {}
for year in years:
    yr_df = df[df['year_stats'] == year]
    index[str(year)] = sorted(yr_df['team_name'].tolist())

index_path = os.path.join(OUTPUT_DIR, 'index.json')
with open(index_path, 'w') as f:
    json.dump(index, f, separators=(',', ':'))
print(f'  index.json saved')

print('\nAll done! Files saved to:', OUTPUT_DIR)