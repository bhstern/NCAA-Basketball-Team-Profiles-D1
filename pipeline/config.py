"""
Pipeline configuration — single source of truth for paths and season ranges.

Paths are derived from the repo location (repo lives inside "CBB Analytics/"),
overridable with the CBB_ROOT environment variable (used by CI).
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Seasons (Torvik convention: 2027 = the 2026-27 season)
# ---------------------------------------------------------------------------

FIRST_SEASON = 2016
CURRENT_SEASON = 2027
FROZEN_SEASONS = frozenset(range(FIRST_SEASON, CURRENT_SEASON))   # 2016–2026

# ---------------------------------------------------------------------------
# Roots
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
CBB_ROOT = Path(os.environ.get("CBB_ROOT", REPO_ROOT.parent)).resolve()

DATA_ROOT = CBB_ROOT / "Data"
RAW_ROOT = DATA_ROOT / "Yearly Raw"
MASTER_ROOT = DATA_ROOT / "Master Datasets"

# Sandboxes — the ONLY places under CBB_ROOT a test run may write for frozen seasons
SCRAPE_TEST_ROOT = RAW_ROOT / "_scrape_test"
REBUILD_ROOT = MASTER_ROOT / "_rebuild"
SANDBOX_ROOTS = (SCRAPE_TEST_ROOT, REBUILD_ROOT)

# Frozen per-player career files (hashed names can contain "2027" by chance) —
# the current season writes per-team shards elsewhere, never here
NEVER_WRITE_ROOTS = (REPO_ROOT / "player_data" / "layer2_profiles",)

# ---------------------------------------------------------------------------
# Raw file layout (mirrors the existing hand-built folders + names)
# ---------------------------------------------------------------------------

TEAM_TABLES_DIR = "Full Season Yearly Team Stats"
SHOOTING_SPLITS_DIR = "Yearly Team Shooting Splits"
PLAYER_RAW_DIR = "Yearly Player Stats Raw"


def team_tables_path(year, raw_root=RAW_ROOT):
    return Path(raw_root) / TEAM_TABLES_DIR / f"{year}trank_team_table_data_fullseason.csv"


def shooting_splits_path(year, raw_root=RAW_ROOT):
    return Path(raw_root) / SHOOTING_SPLITS_DIR / f"{year}shootingsplits_team_table_data.csv"


def player_raw_path(year, raw_root=RAW_ROOT):
    return Path(raw_root) / PLAYER_RAW_DIR / f"{year}_player_stats_full_RAW.csv"
