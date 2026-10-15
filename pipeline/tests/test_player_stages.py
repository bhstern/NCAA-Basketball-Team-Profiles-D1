"""
Player-stage tests — p101 scope, history index logic, leg-A order sensitivity.
No network, and all writes go to a pytest tmp dir (never touches Data/).

Run:  python -m pytest pipeline/tests -q
"""

import pandas as pd
import pytest

from pipeline import config
from pipeline.dev.compare_rebuild import leg_a_year
from pipeline.dev.stitch import CsvText
from pipeline.paths import DATASETS, Paths
from pipeline.player import history, p101_fetch_player_stats as p101


# ============================================================
# p101 — current season only, sandbox only
# ============================================================

class ExplodingSession:
    """Any network use fails the test: scope must be refused before a request is made."""

    def get(self, path):
        raise AssertionError(f"p101 made a request it should have refused: {path}")


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_p101_refuses_every_frozen_season(year):
    with pytest.raises(p101.FetchScopeError):
        p101.run(year, Paths(), session=ExplodingSession())


@pytest.mark.parametrize("year", [2015, config.CURRENT_SEASON + 1])
def test_p101_refuses_any_non_current_season(year):
    with pytest.raises(p101.FetchScopeError):
        p101.run(year, Paths(), session=ExplodingSession())


@pytest.mark.parametrize("out_root", [
    config.RAW_ROOT,                    # would land beside the hand-built raw files
    config.MASTER_ROOT,                 # baseline folder
    config.SCRAPE_TEST_ROOT,            # a sandbox, but not _rebuild
    config.REPO_ROOT,
    config.REBUILD_ROOT / ".." / "..",  # escape attempt
])
def test_p101_refuses_output_outside_rebuild(out_root):
    with pytest.raises(p101.FetchScopeError):
        p101.run(config.CURRENT_SEASON, Paths(out_root=out_root), session=ExplodingSession())


def test_p101_refuses_tmp_output_too(tmp_path):
    with pytest.raises(p101.FetchScopeError):
        p101.run(config.CURRENT_SEASON, Paths(out_root=tmp_path), session=ExplodingSession())


def test_p101_only_target_is_inside_rebuild_and_names_current_season():
    out = p101.output_path(config.CURRENT_SEASON, Paths())
    assert config.REBUILD_ROOT in out.parents
    assert out.name == f"{config.CURRENT_SEASON}_player_stats_full_RAW.csv"
    assert config.RAW_ROOT / config.PLAYER_RAW_DIR not in out.parents


def test_p101_rejects_wrong_season_or_shape_in_response():
    class Fake:
        def __init__(self, text):
            self.content = text.encode()

        def get(self, path):
            return self

    row = ",".join(["x"] * 31 + ["2026"] + ["x"] * 35)
    with pytest.raises(p101.TorvikFetchError):
        p101.fetch_year(config.CURRENT_SEASON, Fake(row + "\n"))          # wrong season inside
    with pytest.raises(p101.TorvikFetchError):
        p101.fetch_year(config.CURRENT_SEASON, Fake("a,b,c\n"))           # wrong width


# ============================================================
# History index — collision, years_in_d1, order replay
# ============================================================

def _index():
    return pd.DataFrame({
        "player_season_id": ["a16", "a17x", "a17y", "b18", "b19", "c19", "c18"],
        "player_id":        ["A",   "A",    "A",    "B",   "B",   "C",   "C"],
        "year":             [2016,  2017,   2017,   2018,  2019,  2019,  2018],
        "team":             ["Duke", "Duke", "Akron", "Yale", "Yale", "Rice", "Rice"],
        "legacy_pos":       [0,     1,      0,      0,     1,     0,     1],
    })


def test_collision_spills_from_another_season_into_the_one_being_built():
    # A collided in 2017 (two teams) -> A's 2016 row is flagged when 2016 is built
    season = pd.DataFrame({"player_id": ["A", "Z"], "year": [2016, 2016], "team": ["Duke", "Yale"]})
    assert history.collision_flags(_index(), season, 2016).tolist() == [True, False]


def test_collision_inside_the_season_being_built_uses_its_own_rows():
    # Index rows for the season being built are ignored in favour of the live frame
    season = pd.DataFrame({"player_id": ["B", "B"], "year": [2018, 2018], "team": ["Yale", "Rice"]})
    assert history.collision_flags(_index(), season, 2018).tolist() == [True, True]
    clean = pd.DataFrame({"player_id": ["A"], "year": [2017], "team": ["Duke"]})
    assert history.collision_flags(_index(), clean, 2017).tolist() == [False]


def test_current_season_is_flagged_by_frozen_history_but_never_writes_back():
    index = _index()
    before = index.copy()
    season = pd.DataFrame({"player_id": ["A", "B"], "year": [2027, 2027], "team": ["Duke", "Yale"]})
    assert history.collision_flags(index, season, config.CURRENT_SEASON).tolist() == [True, False]
    pd.testing.assert_frame_equal(index, before)


def test_prior_season_rows_counts_only_earlier_seasons():
    season = pd.DataFrame({"player_id": ["B", "C", "NEW"]})
    assert history.prior_season_rows(_index(), season, 2019).tolist() == [1, 1, 0]
    assert history.prior_season_rows(_index(), season, 2027).tolist() == [2, 2, 0]


def test_order_replay_is_keyed_on_player_season_id():
    season = pd.DataFrame({"player_season_id": ["b19", "c19"], "year": [2019, 2019]})
    assert history.order_rows(_index(), season, 2019)["player_season_id"].tolist() == ["c19", "b19"]


def test_order_replay_refuses_a_frozen_season_that_does_not_match_the_index():
    season = pd.DataFrame({"player_season_id": ["b19", "SOMEONE_ELSE"], "year": [2019, 2019]})
    with pytest.raises(history.PlayerHistoryError):
        history.order_rows(_index(), season, 2019)
    short = pd.DataFrame({"player_season_id": ["b19"], "year": [2019]})
    with pytest.raises(history.PlayerHistoryError):
        history.order_rows(_index(), short, 2019)


def test_current_season_keeps_raw_input_order():
    season = pd.DataFrame({"player_season_id": ["z", "y", "x"], "year": [2027] * 3})
    out = history.order_rows(_index(), season, config.CURRENT_SEASON)
    assert out["player_season_id"].tolist() == ["z", "y", "x"]


def test_build_refuses_to_overwrite_an_existing_index(tmp_path):
    p = Paths(out_root=tmp_path)
    p.player_history_file.parent.mkdir(parents=True)
    p.player_history_file.write_text("existing")
    with pytest.raises(history.PlayerHistoryError):
        history.build(p)
    assert p.player_history_file.read_text() == "existing"


# ============================================================
# Leg A is positional: a row-order drift must show up as differing cells
# ============================================================

def test_leg_a_counts_cells_when_row_order_drifts(tmp_path):
    p = Paths(out_root=tmp_path)
    ref = p.legacy_ref_file("player_fe")
    ref.parent.mkdir(parents=True)
    ref.write_text('name,year,x\n"Smith, J",2024,1\nJones,2024,2\nLee,2024,3\nOld,2023,9\n')
    out = p.stage_file("player_fe", 2024)
    out.parent.mkdir(parents=True)

    reference = CsvText(ref)
    want = reference.rows_by_year(DATASETS["player_fe"])[2024]

    out.write_text('name,year,x\n"Smith, J",2024,1\nJones,2024,2\nLee,2024,3\n')
    assert leg_a_year("player_fe", 2024, p, reference, want)[::2] == (True, 0)

    out.write_text('name,year,x\nJones,2024,2\n"Smith, J",2024,1\nLee,2024,3\n')   # same rows, swapped
    passed, _, cells = leg_a_year("player_fe", 2024, p, reference, want)
    assert passed is False and cells == 4
