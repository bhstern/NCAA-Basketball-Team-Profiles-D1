"""
p101 — Fetch Torvik raw player stats — CURRENT SEASON ONLY, SANDBOX ONLY
------------------------------------------------------------------------
Year-scoped replacement for Scripts/101_scrape_Torvik_player_stats.py, which
downloaded every season and OVERWROTE the raw player files in place.

Two hard limits, enforced here in addition to the frozen-history guard:

    1. The only season it will fetch is config.CURRENT_SEASON. Any other year raises
       before a request is made. Frozen seasons are built from the hand-built raw
       files and are never re-scraped.
    2. The only place it will write is inside the _rebuild sandbox
       (<_rebuild>/raw/Yearly Player Stats Raw/). An output root anywhere else raises
       before a request is made.

Same download as the original: getadvstats.php?year=Y&csv=1 (67 columns, no header),
round-tripped through pandas and saved with no header, so the file has the same
layout as the hand-built raw files.

Usage:
    python -m pipeline.player.p101_fetch_player_stats --year 2027
"""

import argparse
import io
import os
from pathlib import Path

import pandas as pd

from pipeline import config, guard
from pipeline.paths import Paths
from pipeline.torvik import TorvikFetchError, TorvikSession

EXPECTED_COLUMNS = 67
YEAR_COLUMN = 31          # "year" in the 67-column layout (see p102 HEADERS_67)


class FetchScopeError(PermissionError):
    pass


def output_path(year, paths):
    """Validate scope and return the one path this stage may write. Raises otherwise."""
    if year != config.CURRENT_SEASON:
        raise FetchScopeError(
            f"p101 only fetches the current season ({config.CURRENT_SEASON}); refusing {year}. "
            f"Frozen seasons are built from the hand-built raw files."
        )
    out = config.player_raw_path(year, raw_root=paths.fetched_raw_root)
    resolved = Path(os.path.realpath(out))
    sandbox = Path(os.path.realpath(config.REBUILD_ROOT))
    if sandbox not in resolved.parents:
        raise FetchScopeError(f"p101 only writes inside {sandbox}; refusing {resolved}")
    return out


def fetch_year(year, session):
    content = session.get(f"getadvstats.php?year={year}&csv=1").content
    try:
        # Load CSV with no header row (the original read the URL straight into pandas)
        df = pd.read_csv(io.BytesIO(content), header=None)
    except Exception as e:
        raise TorvikFetchError(f"{year}: player stats response is not a CSV ({e}): {content[:200]!r}") from e

    if df.shape[1] != EXPECTED_COLUMNS:
        raise TorvikFetchError(f"{year}: expected {EXPECTED_COLUMNS} columns, found {df.shape[1]}")
    if df.empty:
        raise TorvikFetchError(f"{year}: player stats response has no rows")
    years_in_file = set(df[YEAR_COLUMN].unique())
    if years_in_file != {year}:
        raise TorvikFetchError(f"Requested {year}, response contains years {sorted(years_in_file)}")
    return df


def run(year, paths, session=None):
    out = output_path(year, paths)           # scope checks BEFORE any request

    print(f"Downloading RAW {year} full...")
    df = fetch_year(year, session or TorvikSession())

    # Save with no headers, preserving raw structure
    written = guard.to_csv(df, out, season=year, index=False, header=False)
    print(f"Saved: {written}  (rows = {df.shape[0]}, columns = {df.shape[1]})")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()
    run(args.year, Paths(out_root=args.out_root))


if __name__ == "__main__":
    main()
