"""
Frozen-history guard tests.

Part A — real writes against a FAKE tree in a pytest tmp dir (never touches Data/).
Part B — the REAL configured guard, check-only (no writes): every existing file in
         Data/, Scripts/, and the repo's data dirs must be refused.

Run:  python -m pytest pipeline/tests -q
"""

import os

import pytest

from pipeline import config, guard
from pipeline.guard import FrozenHistoryError, WriteGuard

FROZEN = range(2016, 2027)
CURRENT = 2027
SENTINEL = b"PRECIOUS HAND-BUILT DATA - DO NOT TOUCH"


# ============================================================
# PART A — fake tree, real writes
# ============================================================

@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "CBB Analytics"
    raw = root / "Data" / "Yearly Raw"
    master = root / "Data" / "Master Datasets"
    sandbox_raw = raw / "_scrape_test"
    sandbox_master = master / "_rebuild"

    precious = {
        "raw_2018": raw / "Yearly Team Shooting Splits" / "2018shootingsplits_team_table_data.csv",
        "raw_2026": raw / "Yearly Player Stats Raw" / "2026_player_stats_full_RAW.csv",
        "master": master / "2016-2026 Master CBB Dataset.csv",
        "converter": root / "NCAA-Basketball-Team-Profiles-D1" / "convert_player_data.py",
    }
    for p in precious.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(SENTINEL)
    sandbox_raw.mkdir(parents=True)
    sandbox_master.mkdir(parents=True)

    allowlisted = root / "NCAA-Basketball-Team-Profiles-D1" / "data" / "index.json"

    g = WriteGuard(root, [sandbox_raw, sandbox_master], FROZEN, CURRENT,
                   unseasoned_allowlist=[allowlisted])
    return dict(root=root, raw=raw, master=master, sandbox_raw=sandbox_raw,
                precious=precious, allowlisted=allowlisted, guard=g, tmp=tmp_path)


def assert_untouched(tree):
    for name, p in tree["precious"].items():
        assert p.read_bytes() == SENTINEL, f"{name} was modified!"
    leftovers = [f for f in tree["root"].rglob("*.tmp")]
    assert not leftovers, f"temp files left behind: {leftovers}"


@pytest.mark.parametrize("key", ["raw_2018", "raw_2026", "master", "converter"])
@pytest.mark.parametrize("season", [2016, 2018, 2026, 2027, 2028, None])
def test_precious_files_refused_for_every_season(tree, key, season):
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(tree["precious"][key], b"CLOBBER", season)
    assert_untouched(tree)


@pytest.mark.parametrize("season", list(FROZEN))
def test_new_frozen_file_in_canonical_raw_refused(tree, season):
    target = tree["raw"] / "Full Season Yearly Team Stats" / f"{season}trank_team_table_data_fullseason.csv"
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(target, b"x", season)
    assert not target.exists()


def test_wrong_season_arg_still_caught_by_filename(tree):
    # Caller bug: says 2027 but the file is a 2019 file
    target = tree["raw"] / "Yearly Player Stats Raw" / "2019_player_stats_full_RAW.csv"
    with pytest.raises(FrozenHistoryError, match="frozen season"):
        tree["guard"].write_bytes(target, b"x", 2027)
    assert not target.exists()


def test_current_season_canonical_write_allowed(tree):
    target = tree["raw"] / "Yearly Player Stats Raw" / "2027_player_stats_full_RAW.csv"
    tree["guard"].write_bytes(target, b"v1", 2027)
    tree["guard"].write_bytes(target, b"v2", 2027)    # nightly overwrite of current season is OK
    assert target.read_bytes() == b"v2"
    assert_untouched(tree)


def test_current_season_unnamed_path_refused(tree):
    target = tree["root"] / "NCAA-Basketball-Team-Profiles-D1" / "js" / "explorer.js"
    with pytest.raises(FrozenHistoryError, match="does not name season"):
        tree["guard"].write_bytes(target, b"x", 2027)


def test_allowlisted_unseasoned_path(tree):
    tree["guard"].write_bytes(tree["allowlisted"], b"{}", 2027)
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(tree["allowlisted"], b"{}", 2026)


@pytest.mark.parametrize("season", [2016, 2018, 2026, 2027, None])
def test_sandbox_writes_allowed_for_any_season(tree, season):
    target = tree["sandbox_raw"] / "Yearly Team Shooting Splits" / f"{season}shootingsplits_team_table_data.csv"
    tree["guard"].write_bytes(target, b"scraped", season)
    assert target.read_bytes() == b"scraped"
    assert_untouched(tree)


def test_dotdot_escape_from_sandbox_refused(tree):
    escape = tree["sandbox_raw"] / ".." / "Yearly Team Shooting Splits" / "2018shootingsplits_team_table_data.csv"
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(escape, b"CLOBBER", 2018)
    assert_untouched(tree)


def test_symlink_escape_from_sandbox_refused(tree):
    link = tree["sandbox_raw"] / "sneaky.csv"
    os.symlink(tree["precious"]["raw_2018"], link)
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(link, b"CLOBBER", 2018)
    assert_untouched(tree)


def test_symlinked_dir_escape_from_sandbox_refused(tree):
    link_dir = tree["sandbox_raw"] / "linked_dir"
    os.symlink(tree["raw"] / "Yearly Team Shooting Splits", link_dir)
    with pytest.raises(FrozenHistoryError):
        tree["guard"].write_bytes(link_dir / "2018shootingsplits_team_table_data.csv", b"CLOBBER", 2018)
    assert_untouched(tree)


def test_hash_fragment_is_not_a_season_token(tree):
    # Real case found by Part B: frozen career file whose hash ends in "2027"
    target = tree["root"] / "NCAA-Basketball-Team-Profiles-D1" / "player_data" / "player_LUKEVARGO_1997-05-27_bc2027.json"
    with pytest.raises(FrozenHistoryError, match="does not name season"):
        tree["guard"].check(target, 2027)


def test_never_write_root_refused_even_with_current_token(tree):
    profiles = tree["root"] / "NCAA-Basketball-Team-Profiles-D1" / "player_data" / "layer2_profiles"
    g = WriteGuard(tree["root"], [tree["sandbox_raw"]], FROZEN, CURRENT, never_write_roots=[profiles])
    for name in ("player_X_2001-01-01_2027ab.json", "profiles_2027.json"):
        with pytest.raises(FrozenHistoryError, match="never-write"):
            g.write_bytes(profiles / name, b"x", 2027)


def test_outside_protected_root_allowed(tree):
    target = tree["tmp"] / "scratch" / "anything_2018.csv"
    tree["guard"].write_bytes(target, b"ok", 2018)
    assert target.read_bytes() == b"ok"


def test_to_csv_goes_through_guard(tree):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(FrozenHistoryError):
        tree["guard"].to_csv(df, tree["precious"]["master"], 2027, index=False)
    assert_untouched(tree)


# ============================================================
# PART B — real configured guard, CHECK ONLY (no writes)
# ============================================================

def _real_files(root):
    sandboxes = [os.path.realpath(s) for s in config.SANDBOX_ROOTS]
    for dirpath, _, files in os.walk(root):
        if any(os.path.realpath(dirpath).startswith(s) for s in sandboxes):
            continue
        for f in files:
            yield os.path.join(dirpath, f)


REAL_ROOTS = [
    config.DATA_ROOT,
    config.CBB_ROOT / "Scripts",
    config.REPO_ROOT / "data",
    config.REPO_ROOT / "player_data",
]


def test_real_config_paths():
    assert config.CURRENT_SEASON == 2027
    assert config.FROZEN_SEASONS == frozenset(range(2016, 2027))
    assert config.CBB_ROOT.name == "CBB Analytics"
    assert config.SCRAPE_TEST_ROOT.parent == config.RAW_ROOT


@pytest.mark.parametrize("root", REAL_ROOTS, ids=lambda p: p.name)
def test_every_real_existing_file_refused(root):
    files = list(_real_files(root))
    assert files, f"no files found under {root}"
    allowed = []
    for f in files:
        for season in (2016, 2021, 2026, 2027, None):
            try:
                guard.check(f, season)
                allowed.append((f, season))
            except FrozenHistoryError:
                pass
    assert not allowed, f"{len(allowed)} real files would be writable, e.g. {allowed[:5]}"


def test_real_converter_refused():
    for p in (config.REPO_ROOT / "convert_player_data.py", config.REPO_ROOT / "convert_data.py"):
        for season in (2026, 2027, None):
            with pytest.raises(FrozenHistoryError):
                guard.check(p, season)


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_real_canonical_raw_paths_refused_for_frozen(year):
    for path_fn in (config.team_tables_path, config.shooting_splits_path, config.player_raw_path):
        for season in (year, 2027, None):
            with pytest.raises(FrozenHistoryError):
                guard.check(path_fn(year), season)


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_real_sandbox_paths_allowed(year):
    for path_fn in (config.team_tables_path, config.shooting_splits_path, config.player_raw_path):
        guard.check(path_fn(year, raw_root=config.SCRAPE_TEST_ROOT), year)
