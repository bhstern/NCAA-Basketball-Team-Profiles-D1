"""
Data freshness — the site's `last_updated` (index.json "_meta"), advanced ONLY when a run
genuinely brought new data.
---------------------------------------------------------------------------------------
A run's data is fingerprinted from its CLEANED stage outputs, not the raw Torvik files
(formatting noise in a raw download must not count as news):

    team_stats_full_season (t02)   team_shooting_splits (t02)   player_stats (p102)

    fingerprint unchanged                -> carry the previous last_updated forward
    fingerprint changed, games >= before -> last_updated = this run's build time
    fingerprint changed, games  < before -> REGRESSION: reported, last_updated NOT advanced

`games_total` is the sum of team games (team_stats_full_season.games). A drop means the
source served older data than the last successful run; the site must not claim freshness.

`evaluate` is pure (reads the stage files and the persisted state); `record` persists the
state and is called only when the run COMPLETES — a failed run never moves the stamp.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline import guard
from pipeline.stage import GateResult

FINGERPRINT_DATASETS = ("team_stats_full_season", "team_shooting_splits", "player_stats")


def state_file(paths, year):
    return Path(paths.out_root) / "run_state" / f"freshness_{year}.json"


def load(paths, year):
    f = state_file(paths, year)
    return json.loads(f.read_text()) if f.exists() else None


def fingerprint(paths, year):
    h = hashlib.sha256()
    for key in FINGERPRINT_DATASETS:
        h.update(key.encode() + b"\0" + Path(paths.stage_file(key, year)).read_bytes() + b"\0")
    return h.hexdigest()


def games_total(paths, year):
    games = pd.read_csv(paths.stage_file("team_stats_full_season", year), usecols=["games"])["games"]
    return int(games.sum())


def evaluate(paths, year, now=None):
    """-> state dict for this run: {year, fingerprint, games_total, last_updated, status, previous}."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prev = load(paths, year)
    fp, games = fingerprint(paths, year), games_total(paths, year)
    state = {"year": year, "fingerprint": fp, "games_total": games}
    if prev is None:
        status, stamp = "NEW", now
    elif fp == prev["fingerprint"]:
        status, stamp = "UNCHANGED", prev["last_updated"]
    elif games < prev["games_total"]:
        status, stamp = "REGRESSION", prev["last_updated"]
        # keep the last GOOD fingerprint/games so the next run is judged against them
        state.update(fingerprint=prev["fingerprint"], games_total=prev["games_total"])
    else:
        status, stamp = "ADVANCED", now
    state.update(last_updated=stamp, status=status,
                 observed={"fingerprint": fp, "games_total": games},
                 previous=(prev or {}).get("last_updated"))
    return state


def gate(state):
    """The run-report entry. A games drop FAILS (advisory, like every gate for now)."""
    if state["status"] == "REGRESSION":
        return GateResult(
            name="freshness", year=state["year"], passed=False, blocking=False,
            messages=[f"REGRESSION: games played fell {state['games_total']} -> "
                      f"{state['observed']['games_total']}; last_updated held at {state['last_updated']}"])
    return GateResult(
        name="freshness", year=state["year"], passed=True, blocking=False,
        messages=[f"{state['status']}: games_total={state['games_total']}, last_updated={state['last_updated']}"])


def record(paths, year, state):
    payload = {k: state[k] for k in ("year", "fingerprint", "games_total", "last_updated")}
    return guard.write_text(state_file(paths, year), json.dumps(payload, indent=2), season=None)


def meta(state):
    """The index.json "_meta" block (None -> no block, e.g. no current-season run yet)."""
    if not state:
        return None
    return {"last_updated": state["last_updated"], "season": state["year"],
            "games_total": state["games_total"]}
