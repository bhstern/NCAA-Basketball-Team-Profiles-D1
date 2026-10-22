"""
Legacy reference run — the ORIGINAL scripts, on THIS machine, into the sandbox.
------------------------------------------------------------------------------
"Leg A" of the rebuild validation compares the refactored per-year stages against
what the untouched original scripts produce on the same machine (strict byte
identity). This tool produces that reference without editing or re-pathing anything
in Scripts/:

    - each script's source is read, and the one hardcoded output/input folder
      ".../Data/Master Datasets" is swapped IN MEMORY for <out_root>/_legacy_ref
    - raw inputs are still read from Data/Yearly Raw (read-only)
    - every DataFrame.to_csv call is checked by the frozen-history guard first, so a
      write anywhere outside the sandbox raises before a byte is written

The scripts run chained (04 reads the reference 02 outputs, and so on), exactly as
the original pipeline ran.

NEVER runs 101 (the scraper overwrites raw player files in place).

Usage:
    python -m pipeline.dev.legacy_reference --chain team
"""

import argparse
import time

import pandas as pd

from pipeline import config, guard
from pipeline.paths import Paths

SCRIPTS_DIR = config.CBB_ROOT / "Scripts"
LEGACY_MASTER_DIR = "/Users/benjstern/Documents/CBB Analytics/Data/Master Datasets"

CHAINS = {
    "team": [
        "02_clean_Torvik_team_shooting_splits.py",
        "02_clean_Torvik_team_stats_fullseason.py",
        "04_merge_master_team_dataset.py",
        "05_master_team_dataset_feature_engineering.py",
        "06_master_team_descriptive_profiles.py",
    ],
    # Reads the team chain's reference 05 output — run --chain team first
    "player": [
        "102_clean_Torvik_player_stats.py",
        "105_master_player_dataset_feature_engineering.py",
        "105C_master_player_dataset_column_trim.py",
        "106_master_player_descriptive_profiles.py",
    ],
}
NEVER_RUN = ("101_scrape_Torvik_player_stats.py",)

# The repo's team JSON converter. It writes with open(), so its output folder is
# redirected too and open() is guarded for every write.
REPO_SCRIPTS = {
    "convert_data.py": {
        "/Users/benjstern/Documents/CBB Analytics/NCAA-Basketball-Team-Profiles-D1/data": "json/data",
    },
}
CHAINS["json_team"] = ["convert_data.py"]


def _guarded_to_csv(original):
    def to_csv(self, path_or_buf=None, *args, **kwargs):
        if path_or_buf is not None and not hasattr(path_or_buf, "write"):
            guard.check(path_or_buf, season=None)   # sandbox or refuse
        return original(self, path_or_buf, *args, **kwargs)
    return to_csv


def _guarded_open(path, mode="r", *args, **kwargs):
    if any(m in mode for m in "wax+"):
        guard.check(path, season=None)   # sandbox or refuse
    return open(path, mode, *args, **kwargs)


def run_script(name, legacy_dir):
    if name in NEVER_RUN:
        raise PermissionError(f"{name} must never run (overwrites raw files in place)")

    script = (config.REPO_ROOT / name) if name in REPO_SCRIPTS else (SCRIPTS_DIR / name)
    source = script.read_text(encoding="utf-8")
    if LEGACY_MASTER_DIR not in source:
        raise RuntimeError(f"{name}: expected hardcoded path not found — script changed?")
    source = source.replace(LEGACY_MASTER_DIR, str(legacy_dir))
    for original, sandbox_rel in REPO_SCRIPTS.get(name, {}).items():
        if source.count(original) != 1:
            raise RuntimeError(f"{name}: expected output path not found exactly once — script changed?")
        source = source.replace(original, str(legacy_dir / sandbox_rel))
    leftover = source.replace(str(legacy_dir), "")
    if "Data/Master Datasets" in leftover or "NCAA-Basketball-Team-Profiles-D1" in leftover:
        raise RuntimeError(f"{name}: a real data path survived the redirect — refusing to run")

    print(f"\n{'=' * 70}\nLEGACY REFERENCE: {name}\n{'=' * 70}")
    started = time.time()
    exec(compile(source, str(script), "exec"), {"__name__": "__main__", "open": _guarded_open})
    print(f"[legacy_reference] {name} done in {time.time() - started:.0f}s")


def run(chain, paths=None):
    paths = paths or Paths()
    legacy_dir = guard.check(paths.legacy_ref_dir, season=None)
    legacy_dir.mkdir(parents=True, exist_ok=True)

    original = pd.DataFrame.to_csv
    pd.DataFrame.to_csv = _guarded_to_csv(original)
    try:
        for name in CHAINS[chain]:
            run_script(name, legacy_dir)
    finally:
        pd.DataFrame.to_csv = original
    return legacy_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chain", choices=sorted(CHAINS), required=True)
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()
    out = run(args.chain, Paths(out_root=args.out_root))
    print(f"\nLegacy reference files in: {out}")


if __name__ == "__main__":
    main()
