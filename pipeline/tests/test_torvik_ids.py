"""
Torvik number lookup + split detector + --reuse-fetched-raw refusals.
No network; every write goes to a pytest tmp dir (never touches Data/).

Run:  python -m pytest pipeline/tests -q
"""

import pandas as pd
import pytest

from pipeline import config, run_pipeline
from pipeline.paths import Paths
from pipeline.player import history, p106c_split_detector as p106c, torvik_ids

CUR = config.CURRENT_SEASON


def write_owners(paths, rows):
    paths.torvik_owner_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=torvik_ids.COLUMNS).to_csv(paths.torvik_owner_file, index=False)


def write_numbers(paths, year, numbers):
    paths.year_dir(year).mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"torvik_number": numbers}).to_csv(paths.torvik_numbers_file(year), index=False)


def current_rows(rows):
    return pd.DataFrame(rows, columns=["player_id", "name", "team", "height"])


# ============================================================
# apply()
# ============================================================

@pytest.fixture
def paths(tmp_path):
    p = Paths(out_root=tmp_path)
    write_owners(p, [
        (78705, "MICHAELMCNAIR_2004-10-15_aaaaaa", 2026, "Michael McNair", 77.0),
        (900001, "BARRINGTONHARGRESS_2003-10-15_785915", 2026, "Barrington Hargress", 72.0),
        (900002, "QUINTONALSTON_2000-10-15_bbbbbb", 2020, "Quinton Alston", 77.0),
        (900003, "SAMEPERSON_2004-10-15_cccccc", 2026, "Same Person", 78.0),
        (900004, "RENAMED_2004-10-15_dddddd", 2026, "Cleveland Thomas", 76.0),
        (76538, "LEOBEATH_2003-10-15_95175b", 2024, "Leo Beath", 80.0),
        (127579, "DEUCEJONESII_2005-10-15_3b8dd0", 2026, "Deuce Jones II", 74.0),
    ])
    write_history(p, [
        ("MICHAELMCNAIR_2004-10-15_aaaaaa", 2026), ("BARRINGTONHARGRESS_2003-10-15_785915", 2026),
        ("QUINTONALSTON_2000-10-15_bbbbbb", 2020), ("SAMEPERSON_2004-10-15_cccccc", 2026),
        ("RENAMED_2004-10-15_dddddd", 2026),
        ("LEOBEATH_2003-10-15_95175b", 2024), ("LEOBEATH_2004-10-15_fe2008", 2026),
        ("DEUCEJONES_2005-10-15_f58ee6", 2025), ("DEUCEJONESII_2005-10-15_3b8dd0", 2026),
    ])
    return p


def write_history(paths, rows):
    paths.player_history_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"player_season_id": f"{pid}_{y}", "player_id": pid, "year": y, "team": "X",
                   "legacy_pos": i} for i, (pid, y) in enumerate(rows)],
                 columns=history.COLUMNS).to_csv(paths.player_history_file, index=False)


def test_computed_id_with_more_recent_frozen_season_is_kept(paths):
    # Leo Beath: #76538 in 2024 (95175b), renumbered #135435 in 2026 (fe2008), #76538 again in
    # 2027. Today's ID is the 2026 career -> keep it, don't move 2027 back onto the 2024 fragment.
    write_numbers(paths, CUR, [76538])
    out = torvik_ids.apply(current_rows([("LEOBEATH_2004-10-15_fe2008", "Leo Beath", "UC San Diego", 80.0)]),
                           CUR, paths)
    assert out["player_id"].tolist() == ["LEOBEATH_2004-10-15_fe2008"]
    assert pd.read_csv(paths.torvik_match_log(CUR))["action"].tolist() == [torvik_ids.KEPT_RECENT]


def test_owner_with_more_recent_frozen_season_wins(paths):
    # Deuce Jones: today's ID is his 2025 career; the number's owner (Deuce Jones II) has 2026
    write_numbers(paths, CUR, [127579])
    out = torvik_ids.apply(current_rows([("DEUCEJONES_2005-10-15_f58ee6", "Deuce Jones", "UAB", 74.0)]),
                           CUR, paths)
    assert out["player_id"].tolist() == ["DEUCEJONESII_2005-10-15_3b8dd0"]
    assert pd.read_csv(paths.torvik_match_log(CUR))["action"].tolist() == [torvik_ids.REATTACHED]


def test_number_match_reattaches_to_owner(paths):
    write_numbers(paths, CUR, [78705, 900001])
    out = torvik_ids.apply(current_rows([
        ("MIKEMCNAIR,JR._2004-10-15_xxxxxx", "Mike McNair, Jr.", "Maryland", 77.0),        # name changed
        ("BARRINGTONHARGRESS_2003-01-28_081549", "Barrington Hargress", "Colorado", 72.0),  # birthday changed
    ]), CUR, paths)
    assert out["player_id"].tolist() == ["MICHAELMCNAIR_2004-10-15_aaaaaa",
                                         "BARRINGTONHARGRESS_2003-10-15_785915"]
    log = pd.read_csv(paths.torvik_match_log(CUR))
    assert log["action"].tolist() == [torvik_ids.REATTACHED, torvik_ids.REATTACHED]


def test_no_match_keeps_todays_id(paths):
    # Jordan Johnson (UC San Diego 2027, #144991) is a different person from the 2026
    # Bethune-Cookman Jordan Johnson (#78921): his number isn't in the table -> not merged
    write_numbers(paths, CUR, [144991])
    rows = current_rows([("JORDANJOHNSON_2005-10-15_eeeeee", "Jordan Johnson", "UC San Diego", 75.0)])
    out = torvik_ids.apply(rows, CUR, paths)
    assert out["player_id"].tolist() == ["JORDANJOHNSON_2005-10-15_eeeeee"]
    assert pd.read_csv(paths.torvik_match_log(CUR))["action"].tolist() == [torvik_ids.NO_MATCH]


def test_same_id_is_logged_as_matched(paths):
    write_numbers(paths, CUR, [900003])
    out = torvik_ids.apply(current_rows([("SAMEPERSON_2004-10-15_cccccc", "Same Person", "X", 78.0)]),
                           CUR, paths)
    assert out["player_id"].tolist() == ["SAMEPERSON_2004-10-15_cccccc"]
    assert pd.read_csv(paths.torvik_match_log(CUR))["action"].tolist() == [torvik_ids.SAME]


def test_guard_skips_unrelated_name_and_height_gap(paths, capsys):
    # #70673: Quinton Alston (6-5) -> "Quavon Blackwood" (6-0): no shared word AND 5" gap
    write_numbers(paths, CUR, [900002])
    rows = current_rows([("QUAVONBLACKWOOD_2000-10-15_ffffff", "Quavon Blackwood", "MVSU", 72.0)])
    out = torvik_ids.apply(rows, CUR, paths)
    assert out["player_id"].tolist() == ["QUAVONBLACKWOOD_2000-10-15_ffffff"]    # today's ID: a split, not a merge
    assert pd.read_csv(paths.torvik_match_log(CUR))["action"].tolist() == [torvik_ids.SKIPPED]
    assert "GUARD SKIP" in capsys.readouterr().out


def test_guard_needs_both_conditions(paths):
    # "Pancake Thomas" / "Cleveland Thomas" share a word; an unrelated name at the same height
    # is still accepted (only BOTH signals together skip)
    write_numbers(paths, CUR, [900004])
    out = torvik_ids.apply(current_rows([("PANCAKE_2004-10-15_gggggg", "Pancake Smith", "X", 76.0)]),
                           CUR, paths)
    assert out["player_id"].tolist() == ["RENAMED_2004-10-15_dddddd"]


def test_contradicts():
    assert torvik_ids.contradicts("Quavon Blackwood", 72, "Quinton Alston", 77)
    assert not torvik_ids.contradicts("Mike McNair, Jr.", 72, "Michael McNair", 80)      # shares "mcnair"
    assert not torvik_ids.contradicts("Totally Other", 72, "Someone Else", None)          # height unknown


def test_normalize_name():
    assert torvik_ids.normalize_name("Mike McNair, Jr.") == "mike mcnair"
    assert torvik_ids.normalize_name("Abdoul Khadre Kébé") == "abdoul khadre kebe"
    assert torvik_ids.normalize_name("Larry Hughes II") == "larry hughes"


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_frozen_seasons_untouched(tmp_path, year):
    rows = current_rows([("X_2000-10-15_aaaaaa", "X", "T", 70.0)])
    out = torvik_ids.apply(rows, year, Paths(out_root=tmp_path))    # no table, no side file: must not read
    assert out is rows
    assert list(tmp_path.iterdir()) == []                            # nothing written


def test_row_count_mismatch_is_an_error(paths):
    write_numbers(paths, CUR, [78705, 900001])
    with pytest.raises(torvik_ids.TorvikIdError):
        torvik_ids.apply(current_rows([("A_x", "A", "T", 70.0)]), CUR, paths)


# ============================================================
# build(): owner = the number's most recent season, never overwrites
# ============================================================

def test_build_owner_is_most_recent_season(tmp_path, monkeypatch):
    seasons = frozenset({2016, 2017, 2018})
    monkeypatch.setattr(config, "FROZEN_SEASONS", seasons)
    frames = {   # #500 is MJ Collins' case: two legacy IDs (name variant); 2018's must own it
        2016: [(500, "MICHAELCOLLINSJR._a", 2016, "Michael Collins Jr.", 75.0), (600, "P_b", 2016, "P", 70.0)],
        2017: [(500, "MJCOLLINS_c", 2017, "MJ Collins", 75.0)],
        2018: [(500, "MJCOLLINS_c", 2018, "MJ Collins", 75.0), (700, "Q_d", 2018, "Q", 71.0)],
    }
    monkeypatch.setattr(torvik_ids, "_frozen_rows",
                        lambda year, raw: pd.DataFrame(frames[year], columns=torvik_ids.COLUMNS))
    index = pd.DataFrame([(r[1], y) for y, rs in frames.items() for r in rs], columns=["player_id", "year"])
    monkeypatch.setattr(history, "load", lambda paths: index)

    paths = Paths(out_root=tmp_path)
    monkeypatch.setattr(Paths, "raw_player", lambda self, year: f"raw_{year}")
    torvik_ids.build(paths)
    owners = torvik_ids.load(paths).set_index("torvik_number")["player_id"].to_dict()
    assert owners == {500: "MJCOLLINS_c", 600: "P_b", 700: "Q_d"}

    with pytest.raises(torvik_ids.TorvikIdError):
        torvik_ids.build(paths)                    # refuses to overwrite


def test_build_refuses_ids_that_differ_from_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FROZEN_SEASONS", frozenset({2016}))
    monkeypatch.setattr(torvik_ids, "_frozen_rows", lambda year, raw: pd.DataFrame(
        [(1, "A_x", 2016, "A", 70.0)], columns=torvik_ids.COLUMNS))
    monkeypatch.setattr(history, "load", lambda paths: pd.DataFrame({"player_id": ["A_DIFFERENT"], "year": [2016]}))
    monkeypatch.setattr(Paths, "raw_player", lambda self, year: "raw")
    with pytest.raises(torvik_ids.TorvikIdError):
        torvik_ids.build(Paths(out_root=tmp_path))


# ============================================================
# p106C split detector
# ============================================================

def fe(rows):
    return pd.DataFrame(rows, columns=p106c.COLS)


PREV_2026 = fe([
    ("BARRINGTONHARGRESS_2003-10-15_785915", "Barrington Hargress", "Colorado", "Inglewood, CA", "JR", 3.0),
    ("JORDANJOHNSON_2004-10-15_hhhhhh", "Jordan Johnson", "Bethune Cookman", "West Palm Beach, FL", "JR", 2.0),
])


def test_detector_flags_hargress_before_the_fix():
    before = fe([("BARRINGTONHARGRESS_2003-01-28_081549", "Barrington Hargress", "Colorado",
                  "Inglewood, CA", "SR", 1.0)])
    hits = p106c.detect(before, PREV_2026)
    assert len(hits) == 1 and hits[0]["corroborated"]


def test_detector_clear_after_the_fix():
    after = fe([("BARRINGTONHARGRESS_2003-10-15_785915", "Barrington Hargress", "Colorado",
                 "Inglewood, CA", "SR", 4.0)])
    assert p106c.detect(after, PREV_2026) == []


def test_detector_jordan_johnson_is_uncorroborated():
    cur = fe([("JORDANJOHNSON_2005-10-15_eeeeee", "Jordan Johnson", "UC San Diego", "Decatur, AL", "JR", 1.0)])
    hits = p106c.detect(cur, PREV_2026)
    assert len(hits) == 1 and not hits[0]["corroborated"]


def test_detector_ignores_freshmen():
    cur = fe([("BARRINGTONHARGRESS_new", "Barrington Hargress", "Colorado", "Inglewood, CA", "FR", 1.0)])
    assert p106c.detect(cur, PREV_2026) == []


def _gate(tmp_path, cur_rows, prev_rows):
    paths = Paths(out_root=tmp_path)
    for year, rows in ((CUR, cur_rows), (CUR - 1, prev_rows)):
        paths.year_dir(year).mkdir(parents=True, exist_ok=True)
        fe(rows).to_csv(paths.stage_file("player_fe", year), index=False)
    return p106c.run(CUR, paths)


def test_gate_blocks_on_a_corroborated_hit(tmp_path):
    r = _gate(tmp_path, [("NEW_ID", "Barrington Hargress", "Colorado", "Inglewood, CA", "SR", 1.0)],
              PREV_2026.values.tolist())
    assert r.blocking and r.passed is False


def test_gate_passes_a_few_uncorroborated(tmp_path):
    r = _gate(tmp_path, [("NEW_ID", "Jordan Johnson", "UC San Diego", "Decatur, AL", "JR", 1.0)],
              PREV_2026.values.tolist())
    assert r.passed is True and any("uncorroborated" in m for m in r.messages)


def test_gate_blocks_above_25_uncorroborated(tmp_path):
    n = p106c.MAX_UNCORROBORATED + 1
    prev = [(f"OLD_{i}", f"Common Name{chr(97 + i)}", f"Team A{i}", "Here, XX", "JR", 2.0) for i in range(n)]
    cur = [(f"NEW_{i}", f"Common Name{chr(97 + i)}", f"Team B{i}", "There, YY", "SR", 1.0) for i in range(n)]
    r = _gate(tmp_path, cur, prev)
    assert r.passed is False and len(r.messages) == n + 1


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_gate_not_evaluated_on_frozen(tmp_path, year):
    assert p106c.run(year, Paths(out_root=tmp_path)).passed is None


# ============================================================
# run_pipeline --reuse-fetched-raw refusals (nothing is run)
# ============================================================

def test_reuse_refused_for_frozen_season():
    with pytest.raises(run_pipeline.RunRefused):
        run_pipeline.run(2026, reuse_fetched_raw=True)


@pytest.mark.parametrize("kw", [{"fetch": True}, {"simulate_current": True}])
def test_reuse_refused_with_fetch_or_simulate(kw):
    with pytest.raises(run_pipeline.RunRefused):
        run_pipeline.run(CUR, reuse_fetched_raw=True, **kw)


def test_reuse_refused_when_raw_missing():
    empty = config.REBUILD_ROOT / "_test_reuse_missing_does_not_exist"
    with pytest.raises(run_pipeline.RunRefused, match="missing"):
        run_pipeline.run(CUR, out_root=empty, reuse_fetched_raw=True)
    assert not empty.exists()
