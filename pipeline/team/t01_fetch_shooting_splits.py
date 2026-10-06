"""
t01 — Fetch Torvik team shooting splits (replaces manual copy-paste into Excel)
------------------------------------------------------------------------------
teampbp.php has no CSV export: it is a server-rendered HTML table. Each zone has a
made-att cell (the "M-A" string lives in the cell's title attribute; the visible text
is FG%) followed by a share cell (visible text). Cells marked `mobileonly` are
duplicates for phones and are skipped.

Produces the same 20 columns as the hand-built files:
    #, Team ("Name Seed"), Conference, then Off/Def x Dunks/Close Twos/Long Twos/Threes
    as "M-A" + Share, then Year
— with no Excel date corruption to repair.

Output defaults to the _scrape_test sandbox; all writes go through the frozen-history guard.

Usage:
    python -m pipeline.team.t01_fetch_shooting_splits --year 2018 [--year 2022 ...]
"""

import argparse
import csv
import io
import re

from bs4 import BeautifulSoup

from pipeline import config, guard
from pipeline.torvik import TorvikFetchError, TorvikSession

HEADER = [
    "#", "Team", "Conference",
    "Off_Dunks", "Off_Dunk_Share", "Def_Dunks", "Def_Dunk_Share",
    "Off_Close_Twos", "Off_Close_Twos_Share", "Def_Close_Twos", "Def_Close_Twos_Share",
    "Off_Long_Twos", "Off_Long_Twos_Share", "Def_Long_Twos", "Def_Long_Twos_Share",
    "Off_Threes", "Off_Threes_Share", "Def_Threes", "Def_Threes_Share",
    "Year",
]

# Sort-class of each desktop stat column, in page order — pins the zone/side mapping
EXPECTED_STAT_CLASSES = ["14", "15", "16", "17", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
EXPECTED_ZONES = ["Dunks", "Close Twos", "Farther Twos", "Threes"]
MADE_ATT = re.compile(r"^\d+-\d+$")


def _classes(tag):
    c = tag.get("class") or []
    return c if isinstance(c, list) else c.split()


def _desktop_cells(tr):
    return [td for td in tr.find_all("td", recursive=False) if "mobileonly" not in _classes(td)]


def check_schema(table, year):
    caption = table.find("caption").get_text(" ", strip=True)
    if not caption.startswith(str(year)):
        raise TorvikFetchError(f"Requested {year}, page caption is {caption!r}")

    # The page repeats its header block every ~50 rows (and its HTML nests oddly),
    # so require EVERY repeated block to match the expected layout exactly
    zones = [z for z in (th.get_text(strip=True) for th in table.select("th.toprow")) if z]
    n_blocks = len(zones) // len(EXPECTED_ZONES)
    if n_blocks == 0 or zones != EXPECTED_ZONES * n_blocks:
        raise TorvikFetchError(f"Shooting-splits zone headers changed: {zones[:8]}")

    desktop_stat_rows = [
        tr for tr in table.find_all("tr")
        if "mobileout" in _classes(tr) and len(tr.find_all("a", recursive=True)) >= 16
        and tr.find("th")
    ]
    if len(desktop_stat_rows) != n_blocks:
        raise TorvikFetchError(
            f"Expected {n_blocks} desktop stat header rows, found {len(desktop_stat_rows)}"
        )
    for tr in desktop_stat_rows:
        stat_classes = [
            (th.find("a").get("class") or [None])[0]
            for th in tr.find_all("th", recursive=False)
            if th.find("a")
        ]
        if stat_classes != EXPECTED_STAT_CLASSES:
            raise TorvikFetchError(f"Shooting-splits column layout changed: {stat_classes}")


def parse_team_cell(td):
    """'Creighton' + seed span ' 8' -> 'Creighton 8' (drops the mobile '1. ' prefix)."""
    parts = []
    for child in td.children:
        if getattr(child, "name", None) == "span" and "mobileonly" in _classes(child):
            continue
        parts.append(child.get_text() if hasattr(child, "get_text") else str(child))
    return "".join(parts).replace("\xa0", " ").strip()


def parse_table(html, year):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="teamStatTable")
    if table is None:
        raise TorvikFetchError("teamStatTable not found in shooting-splits page")
    check_schema(table, year)

    rows = []
    for tr in table.find_all("tr"):
        cells = _desktop_cells(tr)
        if len(cells) != 19 or not cells[0].get_text(strip=True).isdigit():
            continue

        rank = cells[0].get_text(strip=True)
        team = parse_team_cell(cells[1])
        conf = cells[2].get_text(strip=True)

        stats = []
        for i, td in enumerate(cells[3:]):
            if i % 2 == 0:
                val = (td.get("title") or "").strip()
                if not MADE_ATT.match(val):
                    raise TorvikFetchError(f"{year} {team}: expected M-A in title, got {val!r}")
            else:
                val = td.get_text(strip=True)
            stats.append(val)

        rows.append([rank, team, conf] + stats + [str(year)])

    if not rows:
        raise TorvikFetchError(f"No team rows parsed for {year}")
    return rows


def to_csv_text(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    w.writerows(rows)
    return "﻿" + buf.getvalue()


def fetch_year(year, session):
    html = session.get(f"teampbp.php?year={year}&sort=1&csv=1").text
    return parse_table(html, year)


def run(years, raw_root=config.SCRAPE_TEST_ROOT):
    session = TorvikSession()
    written = []
    for year in years:
        rows = fetch_year(year, session)
        out = config.shooting_splits_path(year, raw_root=raw_root)
        guard.write_text(out, to_csv_text(rows), season=year)
        print(f"  {year}: {len(rows)} teams -> {out}")
        written.append(out)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, action="append", required=True)
    ap.add_argument("--raw-root", default=str(config.SCRAPE_TEST_ROOT),
                    help="Raw root to write under (default: _scrape_test sandbox)")
    args = ap.parse_args()
    run(args.year, raw_root=args.raw_root)


if __name__ == "__main__":
    main()
