"""
JSON leg A — rebuilt site JSON (<_rebuild>/json/) vs the repo's existing JSON.
-----------------------------------------------------------------------------
Read-only. Every file pair is compared byte-for-byte; only when the bytes differ are
both sides parsed and the differing values counted (each leaf value that differs,
each key or list item present on one side only). No tolerance, no normalization.

Counts are positional for lists (item i vs item i), so a record-order drift shows up
as differing values rather than being hidden.

Usage:
    python -m pipeline.dev.compare_json                    (all frozen seasons)
    python -m pipeline.dev.compare_json --year 2018 --year 2026
"""

import argparse
import json
import math
import sys
from pathlib import Path

from pipeline import config
from pipeline.paths import Paths

PER_YEAR = {
    "cbb_{Y}.json (team)": ("data", "cbb_{Y}.json"),
    "rosters_{Y}.json": ("player_data", "layer1_rosters", "rosters_{Y}.json"),
    "players_{Y}.json (explorer)": ("player_data", "layer2_explorer", "players_{Y}.json"),
}
MULTI = {
    "data/index.json": ("data", "index.json"),
    "team_positional.json": ("player_data", "layer3_positional", "team_positional.json"),
    "positional_benchmarks.json": ("player_data", "layer3_positional", "positional_benchmarks.json"),
    "players_index.json": ("player_data", "players_index.json"),
}
PROFILES = ("player_data", "layer2_profiles")


def _same_leaf(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def count_diffs(a, b):
    """Number of differing leaf values between two parsed JSON documents."""
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b) and set(a) == set(b):
            return 1 + sum(count_diffs(a[k], b[k]) for k in a)        # same keys, different order
        return (sum(count_diffs(a[k], b[k]) for k in a if k in b)
                + len(set(a) ^ set(b)))
    if isinstance(a, list) and isinstance(b, list):
        return sum(count_diffs(x, y) for x, y in zip(a, b)) + abs(len(a) - len(b))
    return 0 if _same_leaf(a, b) else 1


def compare_file(got, want):
    """0 if byte-identical; else the number of differing values; or a word if a side is missing."""
    if not got.exists():
        return "MISSING"
    if not want.exists():
        return "NO-BASELINE"
    a, b = got.read_bytes(), want.read_bytes()
    if a == b:
        return 0
    n = count_diffs(json.loads(a), json.loads(b))
    return n if n else "BYTES"          # same values, different bytes (e.g. formatting)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, action="append")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    ap.add_argument("--repo-root", default=str(config.REPO_ROOT))
    args = ap.parse_args()
    years = sorted(args.year or config.FROZEN_SEASONS)
    rebuilt = Paths(out_root=args.out_root).json_root
    repo = Path(args.repo_root)
    ok = True

    print("\nJSON LEG A — rebuilt vs repo, differing values per file (0 = byte-identical)")
    width = max(len(k) for k in PER_YEAR)
    print("  " + "file".ljust(width) + "".join(f"{y:>8}" for y in years) + f"{'total':>8}")
    for label, parts in PER_YEAR.items():
        counts = []
        for y in years:
            rel = Path(*[p.replace("{Y}", str(y)) for p in parts])
            counts.append(compare_file(rebuilt / rel, repo / rel))
        total = sum(counts) if all(isinstance(c, int) for c in counts) else "n/a"
        ok &= total == 0
        print("  " + label.ljust(width) + "".join(f"{c:>8}" for c in counts) + f"{total:>8}")

    print("\n  multi-season files" + " " * 18 + "differing values")
    for label, parts in MULTI.items():
        c = compare_file(rebuilt.joinpath(*parts), repo.joinpath(*parts))
        ok &= c == 0
        print(f"  {label:<36}{c:>8}")

    got_dir, want_dir = rebuilt.joinpath(*PROFILES), repo.joinpath(*PROFILES)
    got = {p.name for p in got_dir.glob("*.json")} if got_dir.exists() else set()
    want = {p.name for p in want_dir.glob("*.json")}
    common = sorted(got & want)
    differing_files = differing_values = 0
    examples = []
    for name in common:
        c = compare_file(got_dir / name, want_dir / name)
        if c != 0:
            differing_files += 1
            differing_values += c if isinstance(c, int) else 0
            examples.append((name, c))
    only_rebuilt, only_repo = sorted(got - want), sorted(want - got)
    ok &= not (differing_files or only_rebuilt or only_repo)

    print("\n  career files (layer2_profiles)")
    print(f"    files in repo / rebuilt         {len(want):>8} / {len(got)}")
    print(f"    of which collision files        {sum(n.endswith('_collision.json') for n in want):>8} / "
          f"{sum(n.endswith('_collision.json') for n in got)}")
    print(f"    compared                        {len(common):>8}")
    print(f"    files differing                 {differing_files:>8}")
    print(f"    values differing                {differing_values:>8}")
    print(f"    only in rebuilt                 {len(only_rebuilt):>8}  {only_rebuilt[:3]}")
    print(f"    only in repo                    {len(only_repo):>8}  {only_repo[:3]}")
    for name, c in examples[:5]:
        print(f"      e.g. {name}: {c}")

    print(f"\nJSON LEG A RESULT: {'ALL BYTE-IDENTICAL' if ok else 'MISMATCH — see above'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
