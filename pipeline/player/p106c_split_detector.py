"""
p106C — Split detector (current season) — BLOCKING GATE
-------------------------------------------------------
Catches a returning player who was given a new player_id (so his new season sits in a
career file of its own and years_in_d1 restarts at 1). On the Nov 20 2026 publish ~270
such splits went live silently; this gate exists so that can't recur unnoticed.

A HIT is a current-season row with years_in_d1 = 1 and class != FR whose normalized name
(pipeline.player.torvik_ids.normalize_name) matches a career that ENDED the previous
season (a player_id present last season and absent this season).

    corroborated    the ended career also has the same team or the same hometown city
    uncorroborated  name only (common names: usually a different person)

The gate FAILS (blocking) on any corroborated hit, or on more than MAX_UNCORROBORATED
uncorroborated hits. Every hit of both kinds is listed in the run report.

Reads p105 output (player_fe.csv: name, team, hometown, class, years_in_d1) for this
season and the previous one. Frozen seasons are not evaluated.

Usage:
    python -m pipeline.player.p106c_split_detector --year 2027
"""

import pandas as pd

from pipeline import config
from pipeline.paths import Paths
from pipeline.player.torvik_ids import normalize_name
from pipeline.stage import GateResult, stage_main

NAME = "p106c_split_detector"
MAX_UNCORROBORATED = 25
COLS = ["player_id", "name", "team", "hometown", "class", "years_in_d1"]


def _city(hometown):
    if not isinstance(hometown, str):
        return ""
    return hometown.split(",")[0].strip().lower()


def detect(current, previous):
    """-> list of hit dicts. `current`/`previous`: frames with COLS (one season each)."""
    ended = previous[~previous["player_id"].isin(set(current["player_id"]))].copy()
    ended["key"] = ended["name"].map(normalize_name)
    ended = ended[ended["key"] != ""]
    by_key = {k: g for k, g in ended.groupby("key")}

    candidates = current[(current["years_in_d1"] == 1)
                         & (current["class"].astype(str).str.upper() != "FR")]
    hits = []
    for _, r in candidates.iterrows():
        match = by_key.get(normalize_name(r["name"]))
        if match is None:
            continue
        city = _city(r["hometown"])
        same_team = bool((match["team"] == r["team"]).any())
        same_home = bool(city) and any(_city(h) == city for h in match["hometown"])
        hits.append({
            "corroborated": same_team or same_home,
            "why": ", ".join(w for w, ok in (("same team", same_team), ("same hometown", same_home)) if ok),
            "name": r["name"], "team": r["team"], "hometown": r["hometown"], "class": r["class"],
            "player_id": r["player_id"],
            "ended": [(e["player_id"], e["team"], e["hometown"]) for _, e in match.iterrows()],
        })
    return hits


def _load(paths, year):
    f = paths.stage_file("player_fe", year)
    if not f.exists():                                   # simulate-current: earlier seasons
        f = Paths(out_root=config.REBUILD_ROOT).stage_file("player_fe", year)   # live in the main sandbox
    return pd.read_csv(f, usecols=COLS, low_memory=False)


def run(year, paths):
    if year in config.FROZEN_SEASONS:
        return GateResult(NAME, year, None, blocking=True,
                          messages=["Frozen season: not evaluated (guards the current season only)."])

    hits = detect(_load(paths, year), _load(paths, year - 1))
    corr = [h for h in hits if h["corroborated"]]
    weak = [h for h in hits if not h["corroborated"]]
    passed = not corr and len(weak) <= MAX_UNCORROBORATED

    messages = [f"{len(corr)} corroborated hit(s) (block on any), {len(weak)} uncorroborated "
                f"(block above {MAX_UNCORROBORATED})"]
    for h in corr + weak:
        kind = f"CORROBORATED ({h['why']})" if h["corroborated"] else "uncorroborated"
        ended = "; ".join(f"{pid} [{team}, {home}]" for pid, team, home in h["ended"])
        messages.append(f"{kind}: {h['name']} ({h['team']}, {h['hometown']}, {h['class']}) "
                        f"{h['player_id']} -- ended {year - 1}: {ended}")
    for m in messages:
        print(m)
    return GateResult(NAME, year, passed, blocking=True, messages=messages)


if __name__ == "__main__":
    stage_main(run, __doc__)
