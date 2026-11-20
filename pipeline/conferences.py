"""
Conferences — ONE map from Torvik conference codes to display names, and the
season-aware Power / Mid-Major split. Used by t06 (team profiles) and p105 (player
feature engineering), which previously each carried their own copy.

Phase 5 (2026-27 realignment):
    • New Torvik codes: "Metro" (the 11 former MAAC teams) and "UAC" (Abilene Christian,
      Central Arkansas, Little Rock, North Alabama, West Georgia, ...).
    • Power for 2027 on = ACC, Big Ten, Big 12, SEC, Big East. The re-formed Pac-12 is
      Mid-Major from 2027 (decision 2026-11-04). Frozen seasons keep the original
      six-conference Power set, so their outputs are unchanged.
    • An unmapped code no longer becomes NaN (p105) or silently Mid-Major: it falls back
      to the raw code and prints a loud warning naming the code, season and teams.
    • Display names (decision 2026-11-05): Metro -> "Metro Conference", UAC -> "United
      Athletic Conference". The MAAC dissolved rather than rebranding, so 2016-2026 keep
      "MAAC" and 2027+ show "Metro Conference" — intentionally not rewritten.

Conference LINEAGE (static metadata, never a data column): conferences that are one
continuous league under different names across seasons share a lineage key, so views
that look ACROSS seasons treat them as one conference while per-season views keep each
season's actual name. Published to the site as data/conference_lineage.json
(see lineage_payload); a conference with no entry is its own lineage.
"""

import pandas as pd

CONFERENCE_MAP = {
    "Slnd": "Southland", "WAC": "WAC", "MWC": "Mountain West", "MAC": "MAC",
    "SWAC": "SWAC", "SEC": "SEC", "AE": "America East", "Pat": "Patriot",
    "SB": "Sun Belt", "P12": "Pac-12", "B12": "Big 12", "OVC": "Ohio Valley",
    "ASun": "Atlantic Sun", "WCC": "WCC", "MVC": "Missouri Valley",
    "MEAC": "MEAC", "ACC": "ACC", "Ivy": "Ivy", "NEC": "Northeast",
    "BE": "Big East", "BW": "Big West", "BSth": "Big South", "CAA": "CAA",
    "MAAC": "MAAC", "CUSA": "Conference USA", "Amer": "American",
    "SC": "SoCon", "ind": "Independent", "Horz": "Horizon", "A10": "A10",
    "Sum": "Summit", "BSky": "Big Sky", "B10": "Big Ten",
    # --- added Phase 5 (first seen in 2026-27) ---
    "Metro": "Metro Conference",
    "UAC": "United Athletic Conference",
}

# lineage key -> (label, [(display name, first season, last season or None), ...])
LINEAGES = {
    "maac_metro": ("MAAC / Metro Conference", [
        ("MAAC", 2016, 2026),
        ("Metro Conference", 2027, None),   # the same 11 schools the MAAC had
    ]),
}

# Power conferences by season. A season uses the newest entry whose start <= season.
POWER_BY_SEASON = (
    (2016, frozenset({"Big 12", "Big East", "SEC", "ACC", "Big Ten", "Pac-12"})),
    (2027, frozenset({"ACC", "Big Ten", "Big 12", "SEC", "Big East"})),   # Pac-12 -> Mid-Major
)


def power_conferences(season):
    chosen = None
    for start, confs in POWER_BY_SEASON:
        if season >= start:
            chosen = confs
    if chosen is None:
        raise ValueError(f"No Power-conference set defined for season {season}")
    return chosen


def is_power(conference, season):
    return conference in power_conferences(season)


def map_conferences(codes, season, stage, teams=None):
    """Torvik code -> display name. Unmapped codes fall back to the raw code (never NaN)
    with a loud warning; a missing code stays missing and is warned about too."""
    codes = pd.Series(codes)
    mapped = codes.map(CONFERENCE_MAP)

    unmapped = codes.notna() & mapped.isna()
    if unmapped.any():
        detail = []
        for code in sorted(codes[unmapped].astype(str).unique()):
            rows = unmapped & (codes.astype(str) == code)
            names = sorted(pd.Series(teams)[rows].astype(str).unique())[:8] if teams is not None else []
            detail.append(f"{code!r} ({int(rows.sum())} rows{': ' + ', '.join(names) if names else ''})")
        print("\n" + "!" * 78)
        print(f"!! WARNING [{stage} {season}]: UNMAPPED CONFERENCE CODE(S) — kept as the raw code,")
        print(f"!! classified Mid-Major unless added to pipeline.conferences:")
        for d in detail:
            print(f"!!   {d}")
        print("!" * 78 + "\n")

    missing = codes.isna()
    if missing.any():
        names = sorted(pd.Series(teams)[missing].astype(str).unique())[:8] if teams is not None else []
        print(f"!! WARNING [{stage} {season}]: {int(missing.sum())} row(s) have NO conference code"
              f"{': ' + ', '.join(names) if names else ''}")

    return mapped.where(mapped.notna(), codes)


def lineage_of(name):
    """Lineage key for a display name (the name itself when it has no lineage entry)."""
    for key, (_, members) in LINEAGES.items():
        if any(name == n for n, _, _ in members):
            return key
    return name


def lineage_payload():
    """The site's data/conference_lineage.json."""
    by_name = {}
    lineages = {}
    for key, (label, members) in LINEAGES.items():
        lineages[key] = {
            "label": label,
            "names": [{"name": n, "first_season": a, "last_season": b} for n, a, b in members],
        }
        for n, _, _ in members:
            by_name[n] = key
    return {"by_name": by_name, "lineages": lineages}
