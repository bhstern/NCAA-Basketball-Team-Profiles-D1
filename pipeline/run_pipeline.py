"""
run_pipeline — build ONE season end to end, in order, inside the _rebuild sandbox.
-------------------------------------------------------------------------------
    [fetch]   t01 team tables, t01 shooting splits, p101 player stats
              (current season only, opt-in with --fetch)
    team      t02 shooting splits, t02 team stats, t03 check, t04, t05, t06
    player    p102, p103 check, p105, p105B check, p105C, p106, p106B check
    convert   t07 team JSON, p107 player JSON
    assemble  multi-season JSON: this season + every other season's existing output

Stops at the first stage that raises, and at the first BLOCKING gate that fails.
All gates are advisory for now (Phase 2/3 decision): they are run and reported but
never stop the run. They must become blocking before the Phase 6 cron.

Writes only inside the _rebuild sandbox; any other --out-root is refused. Every stage
also writes through the frozen-history guard. --publish is refused (Phase 6).

--simulate-current builds a FROZEN season as if it were the current one — for
rehearsing the nightly run before Torvik has 2026-27 data. Inside the run only, that
season is treated as current (stable row order, t03 not evaluated, a history index of
the seasons before it); output goes to <_rebuild>/_sim_current/ so the
frozen-reproduction files are never overwritten. --fetch is refused in simulation:
a frozen season is never re-scraped.

Usage:
    python -m pipeline.run_pipeline --year 2018
    python -m pipeline.run_pipeline --year 2026 --simulate-current
    python -m pipeline.run_pipeline --year 2027 --fetch            (once Torvik has data)
"""

import argparse
import contextlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from pipeline import assemble_json, config, guard
from pipeline.paths import Paths
from pipeline.player import (
    history, p101_fetch_player_stats, p102_clean_player_stats, p103_player_stats_checks,
    p105_feature_engineering, p105b_player_fe_checks, p105c_column_trim,
    p106_player_profiles, p106b_player_profiles_validation, p107_convert_player_json,
)
from pipeline.stage import GateResult
from pipeline.team import (
    t01_fetch_shooting_splits, t01_fetch_team_tables, t02_clean_shooting_splits,
    t02_clean_team_stats, t03_premerge_checks, t04_merge_master_team,
    t05_feature_engineering, t06_team_profiles, t07_convert_team_json,
)

SIM_DIR = "_sim_current"

STAGES = [
    ("team",     "t02_clean_shooting_splits", t02_clean_shooting_splits.run),
    ("team",     "t02_clean_team_stats",      t02_clean_team_stats.run),
    ("team",     "t03_premerge_checks",       t03_premerge_checks.run),
    ("team",     "t04_merge_master_team",     t04_merge_master_team.run),
    ("team",     "t05_feature_engineering",   t05_feature_engineering.run),
    ("team",     "t06_team_profiles",         t06_team_profiles.run),
    ("player",   "p102_clean_player_stats",   p102_clean_player_stats.run),
    ("player",   "p103_player_stats_checks",  p103_player_stats_checks.run),
    ("player",   "p105_feature_engineering",  p105_feature_engineering.run),
    ("player",   "p105b_player_fe_checks",    p105b_player_fe_checks.run),
    ("player",   "p105c_column_trim",         p105c_column_trim.run),
    ("player",   "p106_player_profiles",      p106_player_profiles.run),
    ("player",   "p106b_player_profiles_validation", p106b_player_profiles_validation.run),
    ("convert",  "t07_convert_team_json",     t07_convert_team_json.run),
    ("convert",  "p107_convert_player_json",  p107_convert_player_json.run),
]


class RunRefused(PermissionError):
    pass


def _inside_rebuild(path):
    sandbox = Path(os.path.realpath(config.REBUILD_ROOT))
    resolved = Path(os.path.realpath(path))
    return resolved == sandbox or sandbox in resolved.parents


@contextlib.contextmanager
def treat_as_current(year):
    """In-process only: make `year` the current season and earlier seasons the frozen ones.
    The write guard is NOT changed — it still holds the real frozen seasons."""
    saved = config.CURRENT_SEASON, config.FROZEN_SEASONS
    config.CURRENT_SEASON = year
    config.FROZEN_SEASONS = frozenset(range(config.FIRST_SEASON, year))
    try:
        yield
    finally:
        config.CURRENT_SEASON, config.FROZEN_SEASONS = saved


def fetch_current(year, paths):
    raw_root = paths.fetched_raw_root
    t01_fetch_team_tables.run([year], raw_root=raw_root)
    t01_fetch_shooting_splits.run([year], raw_root=raw_root)
    p101_fetch_player_stats.run(year, paths)
    return raw_root


def run(year, out_root=config.REBUILD_ROOT, fetch=False, simulate_current=False):
    if not _inside_rebuild(out_root):
        raise RunRefused(f"run_pipeline only writes inside {config.REBUILD_ROOT}; refusing {out_root}")
    if simulate_current:
        if year not in config.FROZEN_SEASONS:
            raise RunRefused(f"--simulate-current is for rehearsing on a frozen season; {year} is not frozen")
        if fetch:
            raise RunRefused("--fetch is refused with --simulate-current: a frozen season is never re-scraped")
    elif fetch and year != config.CURRENT_SEASON:
        raise RunRefused(f"--fetch is only for the current season ({config.CURRENT_SEASON}), not {year}")
    if not simulate_current and year not in config.FROZEN_SEASONS and year != config.CURRENT_SEASON:
        raise RunRefused(f"{year} is neither a frozen season nor the current season")

    main_paths = Paths(out_root=out_root)
    paths = Paths(out_root=Path(out_root) / SIM_DIR) if simulate_current else main_paths
    report = {
        "year": year, "mode": "simulate-current" if simulate_current else
                             ("current" if year == config.CURRENT_SEASON else "frozen"),
        "out_root": str(paths.out_root), "started": datetime.now(timezone.utc).isoformat(),
        "steps": [], "result": None,
    }

    with (treat_as_current(year) if simulate_current else contextlib.nullcontext()):
        steps = []
        if fetch:
            steps.append(("fetch", "fetch_current", None))
        if simulate_current:
            steps.append(("player", "history_index (seasons before this one)", None))
        steps += STAGES
        steps.append(("assemble", "assemble_json", None))

        all_years = sorted(config.FROZEN_SEASONS | {year})
        source = lambda y: paths if y == year else main_paths   # other seasons: existing output

        for group, name, fn in steps:
            started = time.time()
            entry = {"group": group, "step": name}
            print(f"\n{'#' * 78}\n# {year} · {group} · {name}\n{'#' * 78}", flush=True)
            try:
                if name == "fetch_current":
                    paths = Paths(raw_root=fetch_current(year, paths), out_root=paths.out_root)
                    result = None
                elif name.startswith("history_index"):
                    result = history.build(paths, force=True, source=main_paths)
                elif name == "assemble_json":
                    result = assemble_json.run(all_years, paths, source)
                else:
                    result = fn(year, paths)
            except Exception as e:
                entry.update(status="ERROR", seconds=round(time.time() - started, 1),
                             error=f"{type(e).__name__}: {e}")
                report["steps"].append(entry)
                report["result"] = f"STOPPED at {name} (error)"
                traceback.print_exc()
                break

            entry["seconds"] = round(time.time() - started, 1)
            if isinstance(result, GateResult):
                entry.update(status=f"GATE {result.status}", blocking=result.blocking,
                             messages=result.messages)
                print(result.summary())
                report["steps"].append(entry)
                if result.blocking and result.passed is False:
                    report["result"] = f"STOPPED at {name} (blocking gate failed)"
                    break
            else:
                entry["status"] = "OK"
                report["steps"].append(entry)
        else:
            report["result"] = "COMPLETE"

    report["finished"] = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = guard.write_text(paths.out_root / "run_reports" / f"{year}_{stamp}.json",
                                   json.dumps(report, indent=2), season=None)
    print_report(report, report_path)
    return report


def print_report(report, report_path):
    print(f"\n{'=' * 78}\nRUN REPORT — {report['year']} ({report['mode']}) -> {report['out_root']}\n{'=' * 78}")
    for s in report["steps"]:
        print(f"  {s['group']:<9}{s['step']:<42}{s['status']:<22}{s['seconds']:>7.1f}s")
    gates = [s for s in report["steps"] if s["status"].startswith("GATE")]
    if gates:
        print("\n  GATES (all advisory — reported, never stop the run)")
        for g in gates:
            print(f"    {g['step']}: {g['status'].removeprefix('GATE ')}")
            for m in g["messages"][:6]:
                print(f"        - {m}")
            if len(g["messages"]) > 6:
                print(f"        - … {len(g['messages']) - 6} more")
    for s in report["steps"]:
        if s["status"] == "ERROR":
            print(f"\n  ERROR in {s['step']}: {s['error']}")
    total = sum(s["seconds"] for s in report["steps"])
    print(f"\n  RESULT: {report['result']}   ({total / 60:.1f} min)\n  report: {report_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT),
                    help="must be inside the _rebuild sandbox")
    ap.add_argument("--fetch", action="store_true", help="fetch raw data first (current season only)")
    ap.add_argument("--simulate-current", action="store_true",
                    help="rehearse a nightly run on a frozen season (output to _rebuild/_sim_current)")
    ap.add_argument("--publish", action="store_true", help="REFUSED until Phase 6")
    args = ap.parse_args()
    if args.publish:
        ap.error("--publish is disabled until Phase 6 — nothing is written outside _rebuild/")
    try:
        report = run(args.year, out_root=args.out_root, fetch=args.fetch, simulate_current=args.simulate_current)
    except RunRefused as e:
        ap.error(str(e))
    sys.exit(0 if report["result"] == "COMPLETE" else 1)


if __name__ == "__main__":
    main()
