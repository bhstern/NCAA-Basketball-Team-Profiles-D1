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

Additive-tolerant schema (Phase 5): Torvik appends new zones to the page from time to
time (2026-27 added "And-1s"). The four core zones must still appear first, in order,
with the same sort classes — a shifted or renamed core zone fails loudly. Zones AFTER
the core four are tolerated:
    • known extra zones (EXTRA_ZONES, currently And-1s) are parsed and stored in the
      raw CSV AFTER the Year column, so the first 20 columns keep the hand-built layout.
      They are raw-only: t02 keeps just the 20 core columns, so nothing downstream sees them.
    • unknown extra zones are skipped with a loud warning (add them to EXTRA_ZONES to keep).

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

CELLS_PER_ZONE = 4                                   # Off value, Off share/rate, Def value, Def share/rate
CORE_CELLS = 3 + CELLS_PER_ZONE * len(EXPECTED_ZONES)  # #, Team, Conference + 16 stat cells = 19

# Known zones Torvik appends after the core four: page name -> (sort classes, raw CSV columns).
# Raw-only: stored after Year, never read by t02 or any later stage.
EXTRA_ZONES = {
    "And-1s": (["22", "23", "24", "25"],
               ["Off_And1s_Tot", "Off_And1s_Rate", "Def_And1s_Tot", "Def_And1s_Rate"]),
}


def _classes(tag):
    c = tag.get("class") or []
    return c if isinstance(c, list) else c.split()


def _desktop_cells(tr):
    return [td for td in tr.find_all("td", recursive=False) if "mobileonly" not in _classes(td)]


def _zone_blocks(table):
    """Zone names per repeated header row, in page order (blank spacer headers dropped)."""
    blocks = {}
    for th in table.select("th.toprow"):
        name = th.get_text(strip=True)
        if name:
            blocks.setdefault(id(th.find_parent("tr")), []).append(name)
    return list(blocks.values())


def check_schema(table, year):
    """Validate the page layout and return the trailing zones (after the core four).

    Core zones and their sort classes must match exactly and come first; anything after
    them is tolerated. Every repeated header block must carry the same layout."""
    caption = table.find("caption").get_text(" ", strip=True)
    if not caption.startswith(str(year)):
        raise TorvikFetchError(f"Requested {year}, page caption is {caption!r}")

    # The page repeats its header block every ~50 rows (and its HTML nests oddly),
    # so require EVERY repeated block to match, and to match each other
    blocks = _zone_blocks(table)
    if not blocks:
        raise TorvikFetchError("Shooting-splits zone headers not found")
    for zones in blocks:
        if zones[:len(EXPECTED_ZONES)] != EXPECTED_ZONES:
            raise TorvikFetchError(f"Shooting-splits core zones changed or shifted: {zones}")
        if zones != blocks[0]:
            raise TorvikFetchError(f"Shooting-splits header blocks disagree: {blocks[0]} vs {zones}")
    trailing = blocks[0][len(EXPECTED_ZONES):]

    desktop_stat_rows = [
        tr for tr in table.find_all("tr")
        if "mobileout" in _classes(tr) and len(tr.find_all("a", recursive=True)) >= 16
        and tr.find("th")
    ]
    if len(desktop_stat_rows) != len(blocks):
        raise TorvikFetchError(
            f"Expected {len(blocks)} desktop stat header rows, found {len(desktop_stat_rows)}"
        )
    n_core = len(EXPECTED_STAT_CLASSES)
    for tr in desktop_stat_rows:
        stat_classes = [
            (th.find("a").get("class") or [None])[0]
            for th in tr.find_all("th", recursive=False)
            if th.find("a")
        ]
        if stat_classes[:n_core] != EXPECTED_STAT_CLASSES:
            raise TorvikFetchError(f"Shooting-splits core column layout changed: {stat_classes}")
        extra_classes = stat_classes[n_core:]
        if len(extra_classes) != CELLS_PER_ZONE * len(trailing):
            raise TorvikFetchError(
                f"Trailing zones {trailing} expect {CELLS_PER_ZONE * len(trailing)} stat columns, "
                f"found {len(extra_classes)}: {extra_classes}"
            )
        for i, zone in enumerate(trailing):
            got = extra_classes[i * CELLS_PER_ZONE:(i + 1) * CELLS_PER_ZONE]
            if zone in EXTRA_ZONES and got != EXTRA_ZONES[zone][0]:
                raise TorvikFetchError(f"Shooting-splits {zone} layout changed: {got}")

    unknown = [z for z in trailing if z not in EXTRA_ZONES]
    if unknown:
        print(f"  WARNING: {year} shooting splits has NEW trailing zone(s) {unknown} — skipped "
              f"(core zones unaffected). Add to EXTRA_ZONES to store them in the raw CSV.")
    return trailing


def header_for(trailing):
    """Raw CSV header: the 20 hand-built columns, then any known extra zones."""
    return HEADER + [c for z in trailing if z in EXTRA_ZONES for c in EXTRA_ZONES[z][1]]


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
    trailing = check_schema(table, year)
    n_cells = CORE_CELLS + CELLS_PER_ZONE * len(trailing)

    rows = []
    for tr in table.find_all("tr"):
        cells = _desktop_cells(tr)
        if not cells or not cells[0].get_text(strip=True).isdigit():
            continue
        if len(cells) != n_cells:
            raise TorvikFetchError(f"{year}: team row has {len(cells)} cells, expected {n_cells}")
        extra_cells = cells[CORE_CELLS:]
        cells = cells[:CORE_CELLS]

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

        # Known extra zones: visible text of each cell (Tot / Rate), stored after Year
        extras = []
        for i, zone in enumerate(trailing):
            if zone in EXTRA_ZONES:
                zone_cells = extra_cells[i * CELLS_PER_ZONE:(i + 1) * CELLS_PER_ZONE]
                extras += [td.get_text(strip=True) for td in zone_cells]

        rows.append([rank, team, conf] + stats + [str(year)] + extras)

    if not rows:
        raise TorvikFetchError(f"No team rows parsed for {year}")
    return header_for(trailing), rows


def to_csv_text(rows, header=HEADER):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return "﻿" + buf.getvalue()


def fetch_year(year, session):
    """Returns (header, rows)."""
    html = session.get(f"teampbp.php?year={year}&sort=1&csv=1").text
    return parse_table(html, year)


def run(years, raw_root=config.SCRAPE_TEST_ROOT):
    session = TorvikSession()
    written = []
    for year in years:
        header, rows = fetch_year(year, session)
        out = config.shooting_splits_path(year, raw_root=raw_root)
        guard.write_text(out, to_csv_text(rows, header), season=year)
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
