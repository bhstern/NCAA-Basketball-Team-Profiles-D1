"""
t01 — Fetch Torvik full-season team tables (replaces the manual csv=1 download)
------------------------------------------------------------------------------
team-tables_each.php?csv=1 does not return a CSV: it returns an HTML page that embeds
every row as `var gdata = [[...]]`, then the page's JavaScript patches in six columns
from lookup files and exports the rows client-side. We replicate that exactly:

    gdata (40 cols)  +  all_avg_ht / all_eff_ht / exp_history / effective_talent
                     +  pake_dict_all (PAKE / PASE)
    -> sort by Barthag desc (page default) -> drop blank WAB column (index 34)
    -> write with header + UTF-8 BOM, same filename as the hand-built files

Output defaults to the _scrape_test sandbox; all writes go through the frozen-history guard.

Usage:
    python -m pipeline.team.t01_fetch_team_tables --year 2018 [--year 2022 ...]
"""

import argparse
import json
import math
import re

from pipeline import config, guard
from pipeline.torvik import TorvikFetchError, TorvikSession

# Header by gdata index (exactly the page's `statnames`); index 34 (WAB) is dropped
STATNAMES = {
    0: "Team", 1: "Adj OE", 2: "Adj DE", 3: "Barthag", 4: "Record", 5: "Wins", 6: "Games",
    7: "eFG", 8: "eFG D.", 9: "FT Rate", 10: "FT Rate D", 11: "TOV%", 12: "TOV% D",
    13: "O Reb%", 14: "Op OReb%", 15: "Raw T", 16: "2P %", 17: "2P % D.", 18: "3P %",
    19: "3P % D.", 20: "Blk %", 21: "Blked %", 22: "Ast %", 23: "Op Ast %", 24: "3P Rate",
    25: "3P Rate D", 26: "Adj. T", 27: "Avg Hgt.", 28: "Eff. Hgt.", 29: "Exp.", 30: "Year",
    31: "PAKE", 32: "PASE", 33: "Talent", 35: "FT%", 36: "Op. FT%", 37: "PPP Off.",
    38: "PPP Def.", 39: "Elite SOS",
}
N_COLS = 40
DROP_INDEX = 34
OUTPUT_INDICES = [i for i in range(N_COLS) if i != DROP_INDEX]

# PASE seed expectations (page's `pse` array)
PSE = {
    1: 3.289473684, 2: 2.328947368, 3: 1.848684211, 4: 1.546052632, 5: 1.157894736,
    6: 1.059210526, 7: 0.90131579, 8: 0.723684211, 9: 0.611842105, 10: 0.611842105,
    11: 0.638157895, 12: 0.506578947, 13: 0.25, 14: 0.157894737, 15: 0.105263158,
    16: 0.013157895,
}

LOOKUP_FILES = {
    "efht": "all_eff_ht.json",
    "ht": "all_avg_ht.json",
    "exp": "exp_history.json?new",
    "talent": "effective_talent.json",
    "pake": "pake_dict_all.json",
}

UNDEFINED = object()   # JS `undefined` -> empty field on export


# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------

def parse_gdata(html):
    m = re.search(r"var gdata = (\[\[.*?\]\]);", html)
    if not m:
        raise TorvikFetchError("gdata array not found in team-tables page")
    rows = json.loads(m.group(1))
    bad = {len(r) for r in rows} - {N_COLS}
    if bad:
        raise TorvikFetchError(f"Unexpected gdata row width(s): {bad} (expected {N_COLS})")
    return rows


def check_statnames(html):
    """Fail loudly if Torvik changes the column schema."""
    found = {int(i): name for i, name in re.findall(r"^\s*statnames\[(\d+)\]='([^']*)';", html, re.M)}
    mismatched = {
        i: (found.get(i), STATNAMES.get(i))
        for i in OUTPUT_INDICES
        if found.get(i) != STATNAMES.get(i)
    }
    if mismatched:
        raise TorvikFetchError(f"Torvik team-table schema changed (index: found, expected): {mismatched}")


# ---------------------------------------------------------------------------
# Replicate the page's makeFig() patch-in for type=All, conyes=0
# ---------------------------------------------------------------------------

def _lookup(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return UNDEFINED
        d = d[k]
    return UNDEFINED if d is None else d


def patch_rows(rows, lookups):
    for row in rows:
        team = row[0]
        yr = str(int(row[30])) if isinstance(row[30], (int, float)) else str(row[30])

        if row[2] == 0:
            continue

        ht = _lookup(lookups["ht"], yr, team)
        efht = _lookup(lookups["efht"], yr, team)
        if ht is UNDEFINED or ht < 72 or efht is UNDEFINED or efht < 72:
            row[28] = row[27] = row[29] = row[33] = 0
        else:
            row[28] = efht
            row[27] = ht
            row[29] = _lookup(lookups["exp"], yr, team)
            row[33] = _lookup(lookups["talent"], yr, team)

        p = _lookup(lookups["pake"], team, yr)
        if p is UNDEFINED:
            row[31] = row[32] = 0
        else:
            seed = p[1]
            row[31] = p[5]
            pse = PSE.get(int(seed)) if isinstance(seed, (int, float)) and float(seed).is_integer() else None
            row[32] = float(p[6]) - pse if pse is not None else math.nan
    return rows


# ---------------------------------------------------------------------------
# Serialize like JS Array.join (shortest round-trip numbers, undefined -> "")
# ---------------------------------------------------------------------------

def js_str(v):
    if v is UNDEFINED or v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        return repr(v)
    s = str(v)
    if "," in s or '"' in s or "\n" in s:
        raise TorvikFetchError(f"Field needs CSV quoting, unexpected in Torvik data: {s!r}")
    return s


def to_csv_text(rows):
    lines = [",".join(STATNAMES[i] for i in OUTPUT_INDICES)]
    for row in rows:
        lines.append(",".join(js_str(row[i]) for i in OUTPUT_INDICES))
    return "﻿" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_lookups(session):
    return {k: session.get_json(path) for k, path in LOOKUP_FILES.items()}


def fetch_year(year, session, lookups):
    html = session.get(f"team-tables_each.php?year={year}&type=All&csv=1").text
    check_statnames(html)
    rows = parse_gdata(html)

    years_in_page = {int(r[30]) for r in rows}
    if years_in_page != {year}:
        raise TorvikFetchError(f"Requested {year}, page contains years {years_in_page}")

    wab_values = {r[DROP_INDEX] for r in rows} - {"", None}
    if wab_values:
        print(f"  [INFO] {year}: dropped column 34 (WAB) has values, e.g. {list(wab_values)[:3]}")

    rows = patch_rows(rows, lookups)
    rows.sort(key=lambda r: r[3], reverse=True)   # page default: Barthag desc (stable)
    return rows


def run(years, raw_root=config.SCRAPE_TEST_ROOT):
    session = TorvikSession()
    lookups = fetch_lookups(session)
    written = []
    for year in years:
        rows = fetch_year(year, session, lookups)
        out = config.team_tables_path(year, raw_root=raw_root)
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
