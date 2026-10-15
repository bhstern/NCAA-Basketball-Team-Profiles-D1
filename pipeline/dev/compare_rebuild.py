"""
Rebuild validation — read-only comparison of the refactor against the originals.
-------------------------------------------------------------------------------
LEG A — refactor vs the ORIGINAL scripts re-run on this machine (the legacy reference).
        STRICT BYTE IDENTITY. No float tolerance, no normalization.
          --leg a --year Y ...   each per-year file vs that season's rows of the reference
          --leg a --stitched     the stitched file vs the whole reference file

LEG B — the legacy reference vs the baseline files in Data/Master Datasets.
        Documents machine drift (BOM / line endings / last-digit floats). Informational:
        it reports, it never passes or fails.

Prerequisites: `python -m pipeline.dev.legacy_reference --chain team`, the per-year
stage runs, and (for --stitched) `python -m pipeline.dev.stitch`.

Usage:
    python -m pipeline.dev.compare_rebuild --leg a --chain team --year 2018 --year 2023
    python -m pipeline.dev.compare_rebuild --leg a --chain team --stitched
    python -m pipeline.dev.compare_rebuild --leg b --chain team
"""

import argparse
import hashlib
import io
import sys

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.dev.stitch import BOM, CHAINS, CsvText, parse_line, to_bytes
from pipeline.paths import DATASETS, Paths


def sha(data):
    return hashlib.sha256(data).hexdigest()[:12]


# ---------------------------------------------------------------------------
# LEG A — strict byte identity
# ---------------------------------------------------------------------------

def _first_row_diff(fields, got, want):
    g, w = parse_line(got), parse_line(want)
    cells = [(fields[i], g[i], w[i]) for i in range(min(len(g), len(w))) if g[i] != w[i]]
    return f"key={w[0]!r} " + "; ".join(f"{c}: got {a!r}, reference {b!r}" for c, a, b in cells[:4])


def leg_a_year(key, year, paths, reference, want_rows):
    """One season's file vs that season's rows of the reference, POSITIONALLY (row i vs
    row i) — a row-order drift therefore shows up as differing cells, never hidden.
    Returns (passed, detail, cells) where cells is the number of differing cells, or a
    word (MISSING / BOM / HEADER / ROWS) when the files cannot be lined up."""
    path = paths.stage_file(key, year)
    if not path.exists():
        return False, f"missing {path}", "MISSING"

    want = to_bytes(reference.bom, reference.header, want_rows)
    have = path.read_bytes()
    if have == want:
        return True, f"{len(want_rows)} rows, sha {sha(have)}", 0

    got = CsvText(path)
    if got.bom != reference.bom:
        return False, f"BOM differs (got {got.bom}, reference {reference.bom})", "BOM"
    if got.header != reference.header:
        missing = [c for c in reference.fields if c not in got.fields]
        extra = [c for c in got.fields if c not in reference.fields]
        return False, (f"header differs ({len(got.fields)} vs {len(reference.fields)} columns; "
                       f"missing {missing[:6]}, extra {extra[:6]})"), "HEADER"
    if len(got.rows) != len(want_rows):
        return False, f"row count {len(got.rows)} vs reference {len(want_rows)}", "ROWS"

    bad = [i for i, (x, y) in enumerate(zip(got.rows, want_rows)) if x != y]
    cells = 0
    by_col = {}
    for i in bad:
        for name, x, y in zip(reference.fields, parse_line(got.rows[i]), parse_line(want_rows[i])):
            if x != y:
                cells += 1
                by_col[name] = by_col.get(name, 0) + 1
    top = sorted(by_col.items(), key=lambda kv: -kv[1])[:6]
    return False, (f"{cells} cells in {len(bad)} of {len(want_rows)} rows, {len(by_col)} columns "
                   f"({', '.join(f'{c}: {n}' for c, n in top)}); first: "
                   + _first_row_diff(reference.fields, got.rows[bad[0]], want_rows[bad[0]])), cells


def print_cell_table(table, years):
    print("\nLEG A — cells differing from the reference, per file per season")
    width = max(len(k) for k in table)
    print("  " + "file".ljust(width) + "".join(f"{y:>8}" for y in years) + f"{'total':>8}")
    for key, counts in table.items():
        total = sum(counts) if all(isinstance(c, int) for c in counts) else "n/a"
        print("  " + key.ljust(width) + "".join(f"{c:>8}" for c in counts) + f"{total:>8}")


def leg_a_stitched(key, paths):
    stitched, reference = paths.stitched_file(key), paths.legacy_ref_file(key)
    if not stitched.exists():
        return False, f"missing {stitched}"
    a, b = stitched.read_bytes(), reference.read_bytes()
    if a == b:
        return True, f"{len(a):,} bytes, sha {sha(a)}"
    del a, b
    got, ref = CsvText(stitched), CsvText(reference)
    if got.header != ref.header or len(got.rows) != len(ref.rows):
        return False, f"header same: {got.header == ref.header}; rows {len(got.rows)} vs {len(ref.rows)}"
    bad = [i for i, (x, y) in enumerate(zip(got.rows, ref.rows)) if x != y]
    return False, (f"{len(bad)} of {len(ref.rows)} rows differ; first: "
                   + _first_row_diff(ref.fields, got.rows[bad[0]], ref.rows[bad[0]]))


def run_leg_a(keys, years, stitched, paths):
    ok = True
    table = {}
    print("\nLEG A — refactor vs original scripts on this machine (strict byte identity)")
    for key in keys:
        if not paths.legacy_ref_file(key).exists():
            print(f"  FAIL  {key}: no legacy reference — run pipeline.dev.legacy_reference first")
            ok = False
            continue
        if stitched:
            passed, detail = leg_a_stitched(key, paths)
            print(f"  {'PASS' if passed else 'FAIL'}  {key} [stitched]: {detail}", flush=True)
            ok &= passed
        if not years:
            continue
        reference = CsvText(paths.legacy_ref_file(key))
        by_year = reference.rows_by_year(DATASETS[key])
        table[key] = []
        for year in years:
            passed, detail, cells = leg_a_year(key, year, paths, reference, by_year.get(year, []))
            print(f"  {'PASS' if passed else 'FAIL'}  {key} {year}: {detail}", flush=True)
            table[key].append(cells)
            ok &= passed
        del reference, by_year
    if table:
        print_cell_table(table, years)
    print(f"\nLEG A RESULT: {'ALL BYTE-IDENTICAL' if ok else 'MISMATCH — see above'}")
    return ok


# ---------------------------------------------------------------------------
# LEG B — machine drift report (reference vs baseline)
# ---------------------------------------------------------------------------

def leg_b(key, paths):
    dataset = DATASETS[key]
    ref_raw = paths.legacy_ref_file(key).read_bytes()
    base_raw = paths.baseline_file(key).read_bytes()
    print(f"\n  {key}  ({dataset.legacy})")

    if ref_raw == base_raw:
        print("    byte-identical to baseline")
        return

    crlf = b"\r\n"
    print(f"    encoding    : BOM reference={ref_raw.startswith(BOM)} baseline={base_raw.startswith(BOM)}; "
          f"CRLF reference={crlf in ref_raw} baseline={crlf in base_raw}")
    ref_text = ref_raw.decode("utf-8-sig").replace("\r\n", "\n")
    base_text = base_raw.decode("utf-8-sig").replace("\r\n", "\n")
    if ref_text == base_text:
        print("    content     : identical once BOM / line endings are ignored")
        return

    a = pd.read_csv(io.StringIO(ref_text), low_memory=False, float_precision="round_trip")
    b = pd.read_csv(io.StringIO(base_text), low_memory=False, float_precision="round_trip")
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        print(f"    STRUCTURE DIFFERS: shape {a.shape} vs {b.shape}, "
              f"columns equal {list(a.columns) == list(b.columns)}")
        return

    rows = np.zeros(len(a), dtype=bool)
    numeric_cells = other_cells = nan_mismatch = 0
    cols = []
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(dtype=float), y.to_numpy(dtype=float)
            bad = ~((xv == yv) | (np.isnan(xv) & np.isnan(yv)))
            if bad.any():
                nan_mismatch += int((np.isnan(xv) != np.isnan(yv)).sum())
                rel = float(np.nanmax(np.abs(xv[bad] - yv[bad]) / np.maximum(np.abs(yv[bad]), 1e-300)))
                numeric_cells += int(bad.sum())
                cols.append((c, int(bad.sum()), rel))
                rows |= bad
        else:
            bad = x.astype(str).to_numpy() != y.astype(str).to_numpy()
            if bad.any():
                other_cells += int(bad.sum())
                cols.append((c, int(bad.sum()), None))
                rows |= bad

    if dataset.year_from == "team_suffix":
        row_year = a["team"].str.rsplit("_", n=1).str[1]
    else:
        row_year = a[dataset.year_from]
    by_year = row_year[rows].value_counts().sort_index()
    numeric = sorted((c for c in cols if c[2] is not None), key=lambda c: -c[2])

    print(f"    content     : {numeric_cells:,} numeric cell(s) and {other_cells:,} non-numeric cell(s) differ, "
          f"in {int(rows.sum()):,} of {len(a):,} rows and {len(cols)} of {len(a.columns)} columns")
    print(f"    NaN-vs-value mismatches: {nan_mismatch}")
    if numeric:
        print(f"    worst relative difference: {numeric[0][2]:.2e} ({numeric[0][0]})")
        print("    largest   : " + ", ".join(f"{c} ({n} cells, {r:.1e})" for c, n, r in numeric[:5]))
    print("    rows by year: " + ", ".join(f"{y}: {n}" for y, n in by_year.items()))
    non_numeric = [c for c in cols if c[2] is None]
    if non_numeric:
        print("    NON-NUMERIC columns differing: " + ", ".join(f"{c} ({n})" for c, n, _ in non_numeric))


def run_leg_b(keys, paths):
    print("\nLEG B — original scripts on this machine vs baseline files (machine drift, informational)")
    for key in keys:
        if not paths.legacy_ref_file(key).exists():
            print(f"\n  {key}: no legacy reference — run pipeline.dev.legacy_reference first")
            continue
        leg_b(key, paths)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leg", choices=["a", "b"], required=True)
    ap.add_argument("--chain", choices=sorted(CHAINS))
    ap.add_argument("--dataset", action="append", choices=sorted(DATASETS))
    ap.add_argument("--year", type=int, action="append")
    ap.add_argument("--stitched", action="store_true", help="leg A: compare the stitched all-years file")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()

    keys = list(CHAINS[args.chain]) if args.chain else (args.dataset or [])
    if not keys:
        ap.error("give --chain or --dataset")
    paths = Paths(out_root=args.out_root)

    if args.leg == "a":
        if not args.stitched and not args.year:
            ap.error("leg A needs --year (per-year), --stitched, or both")
        sys.exit(0 if run_leg_a(keys, args.year or [], args.stitched, paths) else 1)
    run_leg_b(keys, paths)


if __name__ == "__main__":
    main()
