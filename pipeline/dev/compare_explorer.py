"""
Explorer value-equivalence (Phase 4a §6.1) — compact explorer files vs the published ones.
-----------------------------------------------------------------------------------------
Read-only. For each season:
    OLD  the repo's published player_data/layer2_explorer/players_{Y}.json (array of records),
         projected down to the kept columns;
    NEW  the compact <_rebuild>/json/.../players_{Y}.json ({"columns", "rows"}), rebuilt into
         records exactly as js/explorer.js loadExplorerYear() does: one object per row,
         columns[i] -> row[i].
Compared positionally (record i vs record i — a row-order change shows as differing values),
every kept column, type-strict (5 vs 5.0, None vs missing, True vs "True" all count). Also
checked: the column list is exactly the kept columns in the old file's order, nothing
unexpected was dropped, and the new file has no NaN/Infinity tokens.

Usage:
    python -m pipeline.dev.compare_explorer                  (all frozen seasons)
    python -m pipeline.dev.compare_explorer --year 2018 --year 2026
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

from pipeline import config
from pipeline.dev.compare_json import count_diffs
from pipeline.paths import Paths
from pipeline.player.json_common import EXPLORER_KEEP_COLS

REL = ("player_data", "layer2_explorer")


def rebuild_records(data):
    """Python twin of loadExplorerYear(): {"columns", "rows"} -> list of record dicts."""
    cols = data["columns"]
    return [dict(zip(cols, row)) for row in data["rows"]]


def _no_nan(token):
    raise ValueError(f"bare {token} token in compact explorer file")


def compare_year(new_path, old_path):
    """Return a dict of counts for one season (all zeros / True = equivalent)."""
    new_bytes, old_bytes = new_path.read_bytes(), old_path.read_bytes()
    new = json.loads(new_bytes, parse_constant=_no_nan)
    old = json.loads(old_bytes)
    old_cols = list(old[0]) if old else []
    want_cols = [c for c in old_cols if c in EXPLORER_KEEP_COLS]
    got = rebuild_records(new)
    projected = [{c: r[c] for c in want_cols} for r in old]

    ragged = sum(len(row) != len(new["columns"]) for row in new["rows"])
    values = count_diffs(got, projected)          # positional rows, keyed columns, type-strict
    order_moves = sum(a.get("player_season_id") != b["player_season_id"]
                      for a, b in zip(got, old))
    return {
        "rows_old": len(old), "rows_new": len(got),
        "columns_ok": new["columns"] == want_cols,
        "kept": len(new["columns"]), "dropped": len(old_cols) - len(want_cols),
        "unknown_kept": sorted(set(new["columns"]) - set(old_cols)),
        "ragged_rows": ragged, "order_moves": order_moves, "value_diffs": values,
        "old_bytes": len(old_bytes), "new_bytes": len(new_bytes),
        "old_gz": len(gzip.compress(old_bytes, 6)), "new_gz": len(gzip.compress(new_bytes, 6)),
    }


def is_equivalent(r):
    return (r["rows_old"] == r["rows_new"] and r["columns_ok"] and not r["unknown_kept"]
            and r["ragged_rows"] == 0 and r["order_moves"] == 0 and r["value_diffs"] == 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, action="append")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    ap.add_argument("--repo-root", default=str(config.REPO_ROOT))
    args = ap.parse_args()
    years = sorted(args.year or config.FROZEN_SEASONS)
    new_dir = Paths(out_root=args.out_root).json_root.joinpath(*REL)
    old_dir = Path(args.repo_root).joinpath(*REL)

    rows = {y: compare_year(new_dir / f"players_{y}.json", old_dir / f"players_{y}.json") for y in years}
    mb = lambda b: f"{b / 1e6:.1f}"

    print("\nEXPLORER VALUE-EQUIVALENCE — compact (rebuilt like loadExplorerYear) vs published, projected")
    print(f"  kept columns: {len(EXPLORER_KEEP_COLS)}")
    print("  " + "check".ljust(26) + "".join(f"{y:>7}" for y in years) + f"{'total':>8}")
    for label, fn in [
        ("rows old / new differ", lambda r: abs(r["rows_old"] - r["rows_new"])),
        ("column list mismatch", lambda r: int(not r["columns_ok"]) + len(r["unknown_kept"])),
        ("ragged rows", lambda r: r["ragged_rows"]),
        ("row-order moves", lambda r: r["order_moves"]),
        ("differing values", lambda r: r["value_diffs"]),
    ]:
        vals = [fn(rows[y]) for y in years]
        print("  " + label.ljust(26) + "".join(f"{v:>7}" for v in vals) + f"{sum(vals):>8}")
    print("  " + "players".ljust(26) + "".join(f"{rows[y]['rows_new']:>7}" for y in years))
    print("  " + "columns kept / dropped".ljust(26)
          + "".join(f"{str(rows[y]['kept']) + '/' + str(rows[y]['dropped']):>7}" for y in years))

    print("\n  SIZES (MB)          old raw   new raw   old gz   new gz   raw cut")
    tot = dict(old_bytes=0, new_bytes=0, old_gz=0, new_gz=0)
    for y in years:
        r = rows[y]
        for k in tot:
            tot[k] += r[k]
        print(f"  players_{y}.json  {mb(r['old_bytes']):>8}  {mb(r['new_bytes']):>8} "
              f"{mb(r['old_gz']):>8} {mb(r['new_gz']):>8}  {1 - r['new_bytes'] / r['old_bytes']:>7.1%}")
    print(f"  {'total':<17} {mb(tot['old_bytes']):>8}  {mb(tot['new_bytes']):>8} "
          f"{mb(tot['old_gz']):>8} {mb(tot['new_gz']):>8}  {1 - tot['new_bytes'] / tot['old_bytes']:>7.1%}")

    ok = all(is_equivalent(rows[y]) for y in years)
    print(f"\nEXPLORER RESULT: {'ALL EQUIVALENT' if ok else 'MISMATCH — see above'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
