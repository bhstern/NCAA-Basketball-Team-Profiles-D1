"""
Stage paths — where a year-scoped stage reads its inputs and writes its outputs.

Every stage is `run(year, paths)`. A `Paths` object answers three questions:

    raw inputs      -> Data/Yearly Raw/...                 (read-only)
    stage outputs   -> <out_root>/by_year/{Y}/<file>.csv   (default: the _rebuild sandbox)
    legacy baseline -> Data/Master Datasets/...            (read-only, validation only)

Guardrail: a FROZEN season is always built from the existing hand-built raw files.
Pointing a frozen season at any other raw root (e.g. a re-scrape) is refused.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from . import config


class FrozenRawError(PermissionError):
    pass


# ---------------------------------------------------------------------------
# Datasets — one per stage output
#   file    : per-year file name under by_year/{Y}/
#   legacy  : the combined 2016-2026 file the original script writes
#   stitch  : how per-year files recombine into the legacy file
#               "concat"    -> year order (the original concatenated/looped by year)
#               "sort:team" -> re-sorted on the team key (the original sorted all years)
#   year_from : how to tell a legacy row's season ("team_suffix" = Team_2016, or a column)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Dataset:
    key: str
    file: str
    legacy: str
    stitch: str
    year_from: str


DATASETS = {d.key: d for d in (
    Dataset("team_shooting_splits", "team_shooting_splits.csv",
            "2016-2026 Team Shooting Splits.csv", "concat", "team_suffix"),
    Dataset("team_stats_full_season", "team_stats_full_season.csv",
            "2016-2026 Team Stats Full Season.csv", "concat", "team_suffix"),
    Dataset("master_team", "master_team.csv",
            "2016-2026 Master CBB Dataset.csv", "sort:team", "team_suffix"),
    Dataset("master_team_fe", "master_team_fe.csv",
            "2016-2026 Master CBB Dataset Full Feature Engineering.csv", "sort:team", "team_suffix"),
    Dataset("team_profiles", "team_profiles.csv",
            "2016-2026 CBB Dataset Team Profiles.csv", "concat", "team_suffix"),
    Dataset("player_stats", "player_stats.csv",
            "2016-2026 Player Stats Full Season.csv", "concat", "year"),
    Dataset("player_fe", "player_fe.csv",
            "2016-2026 Master Player Dataset Full Feature Engineering.csv", "concat", "year"),
    Dataset("player_trimmed", "player_trimmed.csv",
            "2016-2026 Master Player Dataset Column Trimmed.csv", "concat", "year"),
    Dataset("player_profiles", "player_profiles.csv",
            "2016-2026 CBB Dataset Player Profiles.csv", "concat", "year"),
)}

TEAM_DATASETS = ("team_shooting_splits", "team_stats_full_season", "master_team",
                 "master_team_fe", "team_profiles")

PLAYER_DATASETS = ("player_stats", "player_fe", "player_trimmed", "player_profiles")

# Deprecated regular-season file — only t03 reads it (reproducing the original's bug)
LEGACY_REGULAR_SEASON = "2016-2026 Team Stats Regular Season.csv"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Paths:
    raw_root: Path = config.RAW_ROOT
    out_root: Path = config.REBUILD_ROOT
    baseline_root: Path = config.MASTER_ROOT

    def __post_init__(self):
        for name in ("raw_root", "out_root", "baseline_root"):
            object.__setattr__(self, name, Path(getattr(self, name)))

    # --- raw inputs (read-only) ---

    def _raw_root_for(self, year):
        if year in config.FROZEN_SEASONS and \
                os.path.realpath(self.raw_root) != os.path.realpath(config.RAW_ROOT):
            raise FrozenRawError(
                f"Frozen season {year} must be built from the hand-built raw files in "
                f"{config.RAW_ROOT}, not {self.raw_root}"
            )
        return self.raw_root

    def raw_team_tables(self, year):
        return config.team_tables_path(year, raw_root=self._raw_root_for(year))

    def raw_shooting_splits(self, year):
        return config.shooting_splits_path(year, raw_root=self._raw_root_for(year))

    def raw_player(self, year):
        return config.player_raw_path(year, raw_root=self._raw_root_for(year))

    # --- stage outputs ---

    def year_dir(self, year):
        return self.out_root / "by_year" / str(year)

    def stage_file(self, key, year):
        return self.year_dir(year) / DATASETS[key].file

    # --- current-season fetch landing zone + frozen player history index ---

    @property
    def fetched_raw_root(self):
        """Where p101 lands the current season's raw player file (inside the sandbox)."""
        return self.out_root / "raw"

    @property
    def player_history_file(self):
        first, last = min(config.FROZEN_SEASONS), max(config.FROZEN_SEASONS)
        return self.out_root / "player_history" / f"player_history_{first}_{last}.csv"

    # --- validation side locations (all inside out_root) ---

    @property
    def legacy_ref_dir(self):
        return self.out_root / "_legacy_ref"

    @property
    def stitched_dir(self):
        return self.out_root / "stitched"

    def legacy_ref_file(self, key):
        return self.legacy_ref_dir / DATASETS[key].legacy

    def stitched_file(self, key):
        return self.stitched_dir / DATASETS[key].legacy

    def baseline_file(self, key):
        return self.baseline_root / DATASETS[key].legacy
