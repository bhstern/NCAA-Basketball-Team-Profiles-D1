"""
Phase 1 validation — scraped raw vs hand-built raw, compared AFTER cleaning.
--------------------------------------------------------------------------
Applies the exact per-year logic of Scripts/02_clean_Torvik_team_stats_fullseason.py and
Scripts/02_clean_Torvik_team_shooting_splits.py (copied verbatim below, not imported —
those scripts run top-level code and write to Master Datasets) to BOTH the hand-built
file and the scraped file for a year, then diffs them keyed by team.

READ-ONLY: reads Data/Yearly Raw/ + Data/Yearly Raw/_scrape_test/, prints a report,
writes nothing.

Expected (not flagged) differences, per the user:
    - blank WAB column present/absent in hand team-table files (dropped by the cleaner)
    - manually added header row
Reported separately so they can be judged:
    - float precision lost when hand files were saved through Excel (~10 sig digits)

Usage:
    python -m pipeline.dev.compare_scrape_to_raw --year 2018 --year 2023 --year 2025
"""

import argparse
import calendar
import re

import numpy as np
import pandas as pd

from pipeline import config

EXCEL_REL_TOL = 1e-6     # Excel "General" CSV export keeps ~10 significant digits
EXCEL_ABS_TOL = 1e-9


# ============================================================
# Verbatim logic from 02_clean_Torvik_team_stats_fullseason.py (per-year)
# ============================================================

def clean_fullseason(filename, year):
    df = pd.read_csv(filename)

    team_col = df.columns[0]
    df[team_col] = df[team_col].astype(str) + f"_{year}"

    combined = pd.concat([df], ignore_index=True)
    combined = combined.loc[:, ~combined.columns.str.contains("^unnamed", case=False)]
    combined = combined.apply(
        lambda col: col.str.replace("â€“", "-", regex=False)
        if col.dtype == "object" else col
    )
    combined.columns = (
        combined.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("%", "pct")
    )
    str_cols = combined.select_dtypes(include=["object", "string"]).columns
    combined[str_cols] = combined[str_cols].apply(lambda col: col.str.strip())
    combined = combined.drop_duplicates()
    for col in combined.columns:
        try:
            combined[col] = pd.to_numeric(combined[col])
        except Exception:
            pass
    combined = combined.fillna(0)
    combined["adj_em"] = (combined["adj_oe"] - combined["adj_de"]).round(4)
    cols = combined.columns.tolist()
    cols.remove("adj_em")
    cols.insert(1, "adj_em")
    return combined[cols]


# ============================================================
# Verbatim logic from 02_clean_Torvik_team_shooting_splits.py (per-year)
# ============================================================

def normalize_team_format(s):
    if not isinstance(s, str):
        return s
    s = s.replace("\xa0", " ").strip()
    s = s.lstrip("_")
    parts = s.split()
    year = parts[-1]
    team_parts = parts[:-1]
    team_parts = [p for p in team_parts if not re.fullmatch(r"[0-9]{1,2}", p)]
    team = " ".join(team_parts)
    return f"{team}_{year}"


def fix_split_column(col):
    def convert(x):
        if isinstance(x, str) and re.fullmatch(r"\d{1,4}-\d{1,4}", x):
            return x
        if isinstance(x, str) and re.fullmatch(r"[A-Za-z]{3}-\d{1,2}", x):
            mon, day = x.split("-")
            try:
                month_num = list(calendar.month_abbr).index(mon.capitalize())
                return f"{month_num}-{day}"
            except Exception:
                return x
        if isinstance(x, str) and re.fullmatch(r"\d{1,2}-[A-Za-z]{3}", x):
            day, mon = x.split("-")
            try:
                month_num = list(calendar.month_abbr).index(mon.capitalize())
                return f"{month_num}-{day}"
            except Exception:
                return x
        if isinstance(x, str) and x.isdigit():
            try:
                dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(int(x), unit="D")
                return f"{dt.month}-{dt.day}"
            except Exception:
                return x
        if pd.api.types.is_number(x):
            try:
                dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(int(x), unit="D")
                return f"{dt.month}-{dt.day}"
            except Exception:
                return x
        return x
    return col.apply(convert)


def clean_shooting_splits(filename, year):
    df = pd.read_csv(filename)
    df = df.drop(df.columns[0], axis=1)
    team_col = df.columns[0]
    df = df[df[team_col].notna()]
    df[team_col] = df[team_col].str.replace(r"\s+\d+$", "", regex=True)
    df[team_col] = df[team_col].astype(str) + f" {year}"
    df[team_col] = df[team_col].apply(normalize_team_format)

    combined = pd.concat([df], ignore_index=True)
    combined.columns = (
        combined.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("%", "pct")
    )
    str_cols = combined.select_dtypes(include="object").columns
    combined[str_cols] = combined[str_cols].apply(lambda col: col.str.strip())
    combined = combined.drop_duplicates()
    for col in combined.columns:
        try:
            combined[col] = pd.to_numeric(combined[col])
        except Exception:
            pass
    combined = combined.fillna(0)
    combined["off_dunks"] = fix_split_column(combined["off_dunks"])
    combined["def_dunks"] = fix_split_column(combined["def_dunks"])
    return combined


# ============================================================
# Diff
# ============================================================

IGNORE_COLS = {"#"}   # Torvik's row rank — depends on page sort, dropped by the cleaner anyway


def compare(hand, scraped, label, key="team"):
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
    print(f"  rows: hand={len(hand)}  scraped={len(scraped)}")
    real_issues = []

    for name, df in (("hand", hand), ("scraped", scraped)):
        d = df[key][df[key].duplicated()].tolist()
        if d:
            real_issues.append(f"duplicate {key} in {name}: {d}")

    hk, sk = set(hand[key]), set(scraped[key])
    only_h, only_s = sorted(hk - sk), sorted(sk - hk)
    if only_h:
        real_issues.append(f"teams only in HAND ({len(only_h)}): {only_h}")
    if only_s:
        real_issues.append(f"teams only in SCRAPED ({len(only_s)}): {only_s}")

    hc, sc = set(hand.columns) - IGNORE_COLS, set(scraped.columns) - IGNORE_COLS
    if hc - sc:
        real_issues.append(f"columns only in HAND: {sorted(hc - sc)}")
    if sc - hc:
        real_issues.append(f"columns only in SCRAPED: {sorted(sc - hc)}")

    h = hand.set_index(key)
    s = scraped.set_index(key)
    common_keys = sorted(hk & sk)
    common_cols = [c for c in hand.columns if c in sc and c != key and c not in IGNORE_COLS]
    h, s = h.loc[common_keys, common_cols], s.loc[common_keys, common_cols]

    exact_cols, excel_cols = [], []
    for col in common_cols:
        a, b = h[col], s[col]
        a_num = pd.api.types.is_numeric_dtype(a)
        b_num = pd.api.types.is_numeric_dtype(b)

        if a_num != b_num:
            real_issues.append(f"[{col}] dtype differs: hand={a.dtype} scraped={b.dtype}")
            continue

        if not a_num:
            diff = a.astype(str) != b.astype(str)
            if diff.any():
                ex = [(k, a[k], b[k]) for k in a.index[diff][:5]]
                real_issues.append(f"[{col}] {int(diff.sum())} string mismatches, e.g. {ex}")
            else:
                exact_cols.append(col)
            continue

        af, bf = a.astype(float), b.astype(float)
        if (af == bf).all():
            exact_cols.append(col)
            continue
        close = np.isclose(af, bf, rtol=EXCEL_REL_TOL, atol=EXCEL_ABS_TOL)
        if close.all():
            excel_cols.append((col, float((af - bf).abs().max())))
        else:
            bad = ~close
            ex = [(k, af[k], bf[k]) for k in af.index[bad][:5]]
            real_issues.append(f"[{col}] {int(bad.sum())} value mismatches, e.g. {ex}")

    print(f"  common teams: {len(common_keys)}   compared columns: {len(common_cols)}")
    print(f"  identical columns: {len(exact_cols)}")
    if excel_cols:
        worst = max(excel_cols, key=lambda t: t[1])
        print(f"  columns differing only by Excel float rounding (rtol {EXCEL_REL_TOL:g}): "
              f"{len(excel_cols)}  (largest abs diff {worst[1]:.3g} in '{worst[0]}')")
    if real_issues:
        print(f"  >>> REAL DISCREPANCIES ({len(real_issues)}):")
        for msg in real_issues:
            print(f"      - {msg}")
    else:
        print("  >>> NO REAL DISCREPANCIES")
    return real_issues


def raw_shape_notes(hand_path, scraped_path):
    """Report the known/expected raw-level differences (blank column, header)."""
    def first_line(p):
        with open(p, encoding="utf-8-sig") as f:
            return f.readline().rstrip("\r\n").split(",")
    h, s = first_line(hand_path), first_line(scraped_path)
    blanks = [i for i, c in enumerate(h) if c == ""]
    note = f"blank header col(s) at {blanks} (expected: manual WAB column)" if blanks else "no blank column"
    same_named = [c for c in h if c] == s
    print(f"  raw header: hand {len(h)} cols, {note}; scraped {len(s)} cols; "
          f"named columns identical & same order: {same_named}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, action="append", required=True)
    args = ap.parse_args()

    total = {}
    for year in args.year:
        for label, path_fn, cleaner in (
            ("TEAM TABLES (full season)", config.team_tables_path, clean_fullseason),
            ("SHOOTING SPLITS", config.shooting_splits_path, clean_shooting_splits),
        ):
            hand_p = path_fn(year)
            scr_p = path_fn(year, raw_root=config.SCRAPE_TEST_ROOT)
            hand = cleaner(hand_p, year)
            scraped = cleaner(scr_p, year)
            issues = compare(hand, scraped, f"{year} — {label}")
            raw_shape_notes(hand_p, scr_p)
            total[(year, label)] = len(issues)

    print(f"\n{'=' * 78}\nSUMMARY (real discrepancies)\n{'=' * 78}")
    for (year, label), n in total.items():
        print(f"  {year}  {label:28} {'OK' if n == 0 else f'{n} ISSUE(S)'}")


if __name__ == "__main__":
    main()
