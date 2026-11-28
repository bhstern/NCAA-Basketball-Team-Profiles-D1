"""
Torvik number lookup — keeps a returning player's player_id stable across seasons.
---------------------------------------------------------------------------------
player_id is computed from NAME + BIRTHDAY (pipeline.player.ids). When Torvik changes
either one (e.g. replaces the Oct 15 placeholder birthday with the real date), the same
person gets a new ID: a new career file with only the current season, years_in_d1 = 1.

Torvik's own player number (raw column AG) usually survives those edits. This module:

    build()   seeds  torvik_number -> player_id  ONCE from the frozen seasons, using
              today's add_player_ids, so every ID in it is an existing frozen ID. Where a
              number maps to several legacy IDs, the owner is the ID from the number's most
              recent season. Refuses to overwrite.
    apply()   for CURRENT-season rows only: a row whose number is in the table gets the
              owner's player_id; no match keeps the ID computed today. Frozen seasons are
              returned untouched.

Contradiction guard (fail-safe): if a match would give a row an owner whose name shares
NO word with the row's name AND whose height differs by more than 3 inches, the match is
skipped and today's computed ID is kept. Skipping reproduces today's behavior (a split),
never a merge. Every row's outcome is logged to by_year/{Y}/torvik_match_log.csv.

More-recent rule: if the ID computed today is ITSELF a frozen career (the person's frozen
history is already split, and Torvik renumbered him in one season so the number points at
an older fragment), the row attaches to whichever of the two careers has the more recent
frozen season. A tie keeps today's ID (today's behavior).

    python -m pipeline.player.torvik_ids --build            (refuses to overwrite)
    python -m pipeline.player.torvik_ids --build --force
"""

import argparse
import io
import re
import unicodedata

import pandas as pd

from pipeline import config, guard
from pipeline.paths import Paths
from pipeline.player import history
from pipeline.player.ids import add_player_ids
from pipeline.player.p102_clean_player_stats import load_and_clean_year

COLUMNS = ["torvik_number", "player_id", "year", "name", "height"]
NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
MAX_HEIGHT_GAP = 3          # inches

# match-log actions
SAME = "matched_same_id"
REATTACHED = "reattached"
SKIPPED = "skipped_guard"
KEPT_RECENT = "kept_more_recent"
NO_MATCH = "no_match"


class TorvikIdError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def normalize_name(name):
    """ASCII-folded, lowercased words, punctuation removed, suffixes (Jr, II, ...) dropped."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.sub(r"[^a-z]+", " ", s).split() if w not in NAME_SUFFIXES)


def name_words(name):
    return set(normalize_name(name).split())


def contradicts(name, height, owner_name, owner_height):
    """The guard: no shared name word AND a height gap over MAX_HEIGHT_GAP inches."""
    if name_words(name) & name_words(owner_name):
        return False
    if pd.isna(height) or pd.isna(owner_height):
        return False
    return abs(float(height) - float(owner_height)) > MAX_HEIGHT_GAP


# ---------------------------------------------------------------------------
# Build (once, frozen seasons only)
# ---------------------------------------------------------------------------

def _frozen_rows(year, raw_path):
    """One frozen season exactly as p105 sees it: p102's cleaning, the stage CSV round trip,
    then today's add_player_ids."""
    df, numbers = load_and_clean_year(year, raw_path, with_torvik_number=True)
    df = pd.read_csv(io.StringIO(df.to_csv(index=False)))
    df = add_player_ids(df)
    out = df[["player_id", "year", "name", "height"]].copy()
    out.insert(0, "torvik_number", numbers.to_numpy())
    return out


def build(paths=None, force=False):
    paths = paths or Paths()
    out = paths.torvik_owner_file
    if out.exists() and not force:
        raise TorvikIdError(f"Torvik owner table already exists (use --force to rebuild): {out}")

    index = history.load(paths)                      # cross-check: IDs must be today's IDs
    frames = []
    for year in sorted(config.FROZEN_SEASONS):
        rows = _frozen_rows(year, paths.raw_player(year))
        expected = index.loc[index["year"] == year, "player_id"].tolist()
        if rows["player_id"].tolist() != expected:
            raise TorvikIdError(f"{year}: seeded IDs differ from the history index's player_ids")
        if not rows["torvik_number"].is_unique:
            raise TorvikIdError(f"{year}: a Torvik number repeats within the season")
        frames.append(rows)

    seen = pd.concat(frames, ignore_index=True)      # year order; stable -> "last" = most recent
    owners = seen.drop_duplicates("torvik_number", keep="last").sort_values("torvik_number")
    guard.to_csv(owners[COLUMNS], out, season=None, index=False)

    ids_per_number = seen.groupby("torvik_number")["player_id"].nunique()
    print(f"Torvik owner table: {len(owners):,} numbers from {len(seen):,} frozen rows; "
          f"{int((ids_per_number > 1).sum()):,} numbers span more than one legacy ID "
          f"(owner = most recent season) -> {out}")
    return out


def load(paths):
    path = paths.torvik_owner_file
    if not path.exists():
        raise TorvikIdError(
            f"Torvik owner table not found: {path}\n"
            f"Build it once with: python -m pipeline.player.torvik_ids --build"
        )
    owners = pd.read_csv(path)
    if list(owners.columns) != COLUMNS:
        raise TorvikIdError(f"Unexpected Torvik owner table columns: {list(owners.columns)}")
    return owners


# ---------------------------------------------------------------------------
# Apply (p105, current season only)
# ---------------------------------------------------------------------------

def apply(player, year, paths):
    """Return `player` with current-season player_ids replaced by their Torvik owner's ID.
    Frozen seasons are returned untouched (nothing is read or written)."""
    if year in config.FROZEN_SEASONS:
        return player

    numbers = pd.read_csv(paths.torvik_numbers_file(year))["torvik_number"]
    if len(numbers) != len(player):
        raise TorvikIdError(f"{year}: {len(numbers)} Torvik numbers for {len(player)} player rows")
    owners = load(paths).set_index("torvik_number")
    last_season = history.load(paths).groupby("player_id")["year"].max()   # frozen careers

    ids, log = [], []
    for num, pid, name, team, height in zip(numbers, player["player_id"], player["name"],
                                            player["team"], player["height"]):
        entry = {"torvik_number": num, "name": name, "team": team, "computed_id": pid,
                 "owner_id": None, "owner_name": None, "final_id": pid}
        if num not in owners.index:
            entry["action"] = NO_MATCH
        else:
            o = owners.loc[num]
            entry.update(owner_id=o["player_id"], owner_name=o["name"])
            if o["player_id"] == pid:
                entry["action"] = SAME
            elif pid in last_season.index and last_season[pid] >= last_season.get(o["player_id"], -1):
                entry["action"] = KEPT_RECENT
            elif contradicts(name, height, o["name"], o["height"]):
                entry["action"] = SKIPPED
            else:
                entry.update(action=REATTACHED, final_id=o["player_id"])
        ids.append(entry["final_id"])
        log.append(entry)

    player = player.copy()
    player["player_id"] = ids
    log = pd.DataFrame(log)
    guard.to_csv(log, paths.torvik_match_log(year), season=year, index=False)

    counts = log["action"].value_counts().to_dict()
    print(f"Torvik number lookup {year}: " + ", ".join(f"{k}={counts.get(k, 0)}"
          for k in (SAME, REATTACHED, KEPT_RECENT, SKIPPED, NO_MATCH)))
    for _, s in log[log["action"] == SKIPPED].iterrows():
        print(f"  GUARD SKIP #{s['torvik_number']}: {s['name']} ({s['team']}) vs owner "
              f"{s['owner_name']} [{s['owner_id']}] -> kept {s['computed_id']}")
    return player


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", required=True)
    ap.add_argument("--force", action="store_true", help="overwrite an existing table")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()
    build(Paths(out_root=args.out_root), force=args.force)


if __name__ == "__main__":
    main()
