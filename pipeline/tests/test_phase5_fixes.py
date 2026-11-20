"""
Phase 5 fixes A + B — additive-tolerant fetch parsers, row-count invariants, nullable
rank cast, conference map / season-aware Power. Synthetic data only; no network.
"""

import json
import numpy as np
import pandas as pd
import pytest

from pipeline import conferences, freshness, row_invariants
from pipeline.paths import Paths
from pipeline.player.p101_fetch_player_stats import KNOWN_COLUMNS, check_anchors
from pipeline.team import t01_fetch_shooting_splits as ss
from pipeline.team.t02_clean_shooting_splits import keep_core_columns, strip_symbols
from pipeline.team.t06_team_profiles import rank_to_nullable_int
from pipeline.torvik import TorvikFetchError


# ---------------------------------------------------------------------------
# t01 shooting splits — synthetic teampbp table
# ---------------------------------------------------------------------------

def _page(zones=("Dunks", "Close Twos", "Farther Twos", "Threes", "And-1s"), classes=None,
          team_html="<a>Duke</a> 1 <a href='shotchart.php?team=Duke'>🎯</a>", blocks=2):
    core = ss.EXPECTED_STAT_CLASSES
    extra = {"And-1s": ["22", "23", "24", "25"]}
    classes = classes or (core + [c for z in zones[4:] for c in extra.get(z, ["90", "91", "92", "93"])])
    zone_ths = "".join(f"<th class='toprow' colspan='4'>{z}</th>" for z in zones)
    stat_ths = "".join(f"<th><a class='{c}'>x</a></th>" for c in classes)
    header = (f"<tr><th class='toprow' colspan='3'></th>{zone_ths}</tr>"
              f"<tr class='mobileout'><th></th><th></th><th></th>{stat_ths}</tr>")
    cells = "".join(
        f"<td title='{i}-{i + 1}'>50.0</td><td>10.0</td>" for i in range(2 * len(zones))
    )
    row = f"<tr><td>1</td><td>{team_html}</td><td>ACC</td>{cells}</tr>"
    body = (header + row) * blocks
    return f"<table id='teamStatTable'><caption>2027 College Basketball</caption>{body}</table>"


def test_shooting_splits_parses_and1s_after_year():
    header, rows = ss.parse_table(_page(blocks=1), 2027)
    assert header[:20] == ss.HEADER
    assert header[20:] == ["Off_And1s_Tot", "Off_And1s_Rate", "Def_And1s_Tot", "Def_And1s_Rate"]
    assert len(rows[0]) == 24 and rows[0][19] == "2027"


def test_shooting_splits_without_extras_keeps_the_hand_built_20():
    header, rows = ss.parse_table(_page(zones=tuple(ss.EXPECTED_ZONES), blocks=1), 2027)
    assert header == ss.HEADER and len(rows[0]) == 20


def test_shooting_splits_unknown_trailing_zone_is_skipped_not_fatal(capsys):
    header, rows = ss.parse_table(_page(zones=tuple(ss.EXPECTED_ZONES) + ("Putbacks",), blocks=1), 2027)
    assert header == ss.HEADER and len(rows[0]) == 20
    assert "NEW trailing zone" in capsys.readouterr().out


@pytest.mark.parametrize("zones", [
    ("Close Twos", "Dunks", "Farther Twos", "Threes", "And-1s"),    # core zones swapped
    ("And-1s", "Dunks", "Close Twos", "Farther Twos", "Threes"),    # new zone inserted first
])
def test_shooting_splits_shifted_core_zone_fails_loudly(zones):
    with pytest.raises(TorvikFetchError, match="core zones"):
        ss.parse_table(_page(zones=zones, classes=ss.EXPECTED_STAT_CLASSES + ["22", "23", "24", "25"]), 2027)


def test_shooting_splits_shifted_core_column_class_fails_loudly():
    bad = ss.EXPECTED_STAT_CLASSES[1:] + ["14", "22", "23", "24", "25"]
    with pytest.raises(TorvikFetchError, match="core column layout"):
        ss.parse_table(_page(classes=bad), 2027)


# ---------------------------------------------------------------------------
# t02 — core columns + 🎯 strip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Northwestern  🎯", "Northwestern"),
    ("Duke 1 🎯", "Duke 1"),
    ("Saint Mary's\xa0🎯", "Saint Mary's"),
    ("Texas A&M  Corpus Chris", "Texas A&M  Corpus Chris"),   # no symbol -> untouched, byte for byte
])
def test_strip_symbols(raw, expected):
    assert strip_symbols(raw) == expected


def test_keep_core_columns_drops_raw_only_extras_and_requires_core():
    df = pd.DataFrame([[0] * 24], columns=ss.HEADER + ["Off_And1s_Tot", "Off_And1s_Rate",
                                                       "Def_And1s_Tot", "Def_And1s_Rate"])
    assert list(keep_core_columns(df, "f").columns) == ss.HEADER
    with pytest.raises(ValueError, match="missing core"):
        keep_core_columns(df.drop(columns=["Off_Threes"]), "f")


# ---------------------------------------------------------------------------
# p101 — anchor check, not a pinned width
# ---------------------------------------------------------------------------

def _player_frame(n_cols, year=2027, rows=20):
    df = pd.DataFrame(np.zeros((rows, n_cols)), dtype=object)
    df[0] = [f"Player {i}" for i in range(rows)]
    df[3] = 1
    df[25] = "Fr"
    df[31] = year
    df[66] = "2005-01-31"
    return df


@pytest.mark.parametrize("n_cols", [67, 78, 90])
def test_p101_tolerates_trailing_columns(n_cols):
    assert check_anchors(_player_frame(n_cols), 2027) == n_cols - KNOWN_COLUMNS


def test_p101_too_few_columns_fails():
    with pytest.raises(TorvikFetchError, match="at least 67"):
        check_anchors(_player_frame(67).iloc[:, :66], 2027)


def test_p101_inserted_column_shifts_anchors_and_fails():
    df = _player_frame(78)
    df.insert(10, "new", 0.5)
    df.columns = range(df.shape[1])
    with pytest.raises(TorvikFetchError):
        check_anchors(df, 2027)


def test_p101_blank_birthdays_allowed_but_wrong_birthday_column_fails():
    df = _player_frame(78)
    df.loc[:3, 66] = np.nan
    check_anchors(df, 2027)
    df[66] = 7.5
    with pytest.raises(TorvikFetchError, match="birthday"):
        check_anchors(df, 2027)


# ---------------------------------------------------------------------------
# t06 rank cast
# ---------------------------------------------------------------------------

def test_rank_cast_matches_astype_int_and_keeps_nan():
    vals = pd.Series([1.0, 4.5, 4.5, 12.0, 280.0])
    assert rank_to_nullable_int(vals).tolist() == vals.astype(int).tolist()
    out = rank_to_nullable_int(pd.Series([3.5, np.nan, 2.0]))
    assert str(out.dtype) == "Int64"
    assert out[0] == 3 and pd.isna(out[1]) and out[2] == 2


def test_rank_cast_csv_text_is_unchanged_without_nan(tmp_path):
    vals = pd.Series([1.0, 4.5, 12.0], name="r")
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    vals.astype(int).to_frame().to_csv(a, index=False)
    rank_to_nullable_int(vals).to_frame().to_csv(b, index=False)
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# Conferences
# ---------------------------------------------------------------------------

def test_new_2027_codes_are_mapped():
    out = conferences.map_conferences(pd.Series(["Metro", "UAC", "B10"]), 2027, "test")
    assert out.tolist() == ["Metro Conference", "United Athletic Conference", "Big Ten"]


def test_unmapped_code_falls_back_to_raw_and_warns_loudly(capsys):
    out = conferences.map_conferences(pd.Series(["B10", "NEWCO"]), 2027, "test",
                                      teams=pd.Series(["Iowa", "Somewhere St."]))
    assert out.tolist() == ["Big Ten", "NEWCO"]
    printed = capsys.readouterr().out
    assert "UNMAPPED CONFERENCE" in printed and "NEWCO" in printed and "Somewhere St." in printed


def test_power_set_is_season_aware():
    for frozen in range(2016, 2027):
        assert conferences.power_conferences(frozen) == {"Big 12", "Big East", "SEC", "ACC", "Big Ten", "Pac-12"}
    assert conferences.power_conferences(2027) == {"ACC", "Big Ten", "Big 12", "SEC", "Big East"}
    assert not conferences.is_power("Pac-12", 2027) and conferences.is_power("Pac-12", 2024)


# ---------------------------------------------------------------------------
# Row-count invariants
# ---------------------------------------------------------------------------

def _write(paths, key, year, n, extra=None):
    f = paths.stage_file(key, year)
    f.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"team": [f"T{i}_{year}" for i in range(n)]})
    for c, v in (extra or {}).items():
        df[c] = v
    df.to_csv(f, index=False)


@pytest.fixture
def ip(tmp_path):
    return Paths(out_root=tmp_path)


def test_zero_rows_fails(ip):
    _write(ip, "team_stats_full_season", 2027, 0)
    with pytest.raises(row_invariants.RowCountError, match="0 rows"):
        row_invariants.check_after("t02_clean_team_stats", 2027, ip, {}, {})


def test_silent_zero_row_merge_fails(ip):
    counts = {}
    _write(ip, "team_stats_full_season", 2027, 365)
    _write(ip, "team_shooting_splits", 2027, 280)
    row_invariants.check_after("t02_clean_team_stats", 2027, ip, counts, {})
    row_invariants.check_after("t02_clean_shooting_splits", 2027, ip, counts, {})
    _write(ip, "master_team", 2027, 0)
    with pytest.raises(row_invariants.RowCountError):
        row_invariants.check_after("t04_merge_master_team", 2027, ip, counts, {})


def test_partial_key_mismatch_fails_on_retention(ip):
    counts = {"team_stats_full_season": 365, "team_shooting_splits": 280}
    _write(ip, "master_team", 2027, 200)
    with pytest.raises(row_invariants.RowCountError, match="inner join kept 200 of 280"):
        row_invariants.check_after("t04_merge_master_team", 2027, ip, counts, {})


def test_early_season_growth_is_fine_but_a_sharp_drop_fails(ip):
    counts = {"team_stats_full_season": 365, "team_shooting_splits": 330}
    _write(ip, "master_team", 2027, 330)
    row_invariants.check_after("t04_merge_master_team", 2027, ip, dict(counts), {"master_team": 280})
    _write(ip, "master_team", 2027, 250)
    counts["team_shooting_splits"] = 250
    with pytest.raises(row_invariants.RowCountError, match="previous successful run"):
        row_invariants.check_after("t04_merge_master_team", 2027, ip, counts, {"master_team": 330})


def test_row_preserving_stage_must_keep_count(ip):
    _write(ip, "master_team_fe", 2027, 279)
    with pytest.raises(row_invariants.RowCountError, match="must not add or drop rows"):
        row_invariants.check_after("t05_feature_engineering", 2027, ip, {"master_team": 280}, {})


def test_player_team_join_match_rate(ip):
    f = ip.stage_file("player_fe", 2027)
    f.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"team": ["A"] * 10, "full_season_games": [1.0] * 5 + [np.nan] * 5}).to_csv(f, index=False)
    with pytest.raises(row_invariants.RowCountError, match="matched a team"):
        row_invariants.check_after("p105_feature_engineering", 2027, ip, {"player_stats": 10}, {})


def test_baseline_round_trip(ip):
    assert row_invariants.load_previous(ip, 2027) == {}
    row_invariants.record_success(ip, 2027, {"master_team": 280}, "now")
    assert row_invariants.load_previous(ip, 2027) == {"master_team": 280}


# ---------------------------------------------------------------------------
# §3C — conference names + lineage, season status, team-tables width tolerance
# ---------------------------------------------------------------------------

def test_2027_display_names_and_frozen_maac_untouched():
    out = conferences.map_conferences(pd.Series(["Metro", "UAC", "MAAC"]), 2027, "test")
    assert out.tolist() == ["Metro Conference", "United Athletic Conference", "MAAC"]


def test_lineage_links_maac_and_metro_only():
    assert conferences.lineage_of("MAAC") == conferences.lineage_of("Metro Conference") == "maac_metro"
    assert conferences.lineage_of("United Athletic Conference") == "United Athletic Conference"
    payload = conferences.lineage_payload()
    assert payload["by_name"] == {"MAAC": "maac_metro", "Metro Conference": "maac_metro"}
    names = [n["name"] for n in payload["lineages"]["maac_metro"]["names"]]
    assert names == ["MAAC", "Metro Conference"]
    # every lineage member is a real display name the pipeline produces
    assert set(payload["by_name"]) <= set(conferences.CONFERENCE_MAP.values())


def _tier_file(path, tier1):
    pd.DataFrame({"percentile_tier": ["Tier 1"] * tier1 + ["Tier 2"] * 5 + [None] * 5}).to_csv(path, index=False)
    return path


@pytest.mark.parametrize("tier1, active", [(0, False), (1643, False), (1644, True), (3288, True)])
def test_season_status_flag_is_half_of_prior_tier1(tmp_path, tier1, active):
    from pipeline.season_status import season_status
    prior = _tier_file(tmp_path / "prior.csv", 3288)     # 2026's Tier 1 pool -> threshold 1,644
    st = season_status(_tier_file(tmp_path / "p.csv", tier1), prior)
    assert st["percentiles_active"] is active and st["tier1_players"] == tier1
    assert st["min_tier1_pool"] == 1644


def test_season_status_rounds_up_and_first_season_is_active(tmp_path):
    from pipeline.season_status import season_status
    st = season_status(_tier_file(tmp_path / "p.csv", 1500), _tier_file(tmp_path / "prior.csv", 3001))
    assert st["min_tier1_pool"] == 1501 and st["percentiles_active"] is False
    first = season_status(_tier_file(tmp_path / "f.csv", 3041))   # no prior season (2016)
    assert first["percentiles_active"] is True


from pipeline.team import t01_fetch_team_tables as tt


def _gdata_page(width=40, extra_names=None, record="3\u20131", year=2027):
    row = ["Duke"] + [0.5] * (width - 1)
    row[4], row[30] = record, year
    names = "".join(f"statnames[{i}]='{n}';\n" for i, n in tt.STATNAMES.items())
    names += "".join(f"statnames[{i}]='{n}';\n" for i, n in (extra_names or {}).items())
    import json as _j
    return f"<script>\n{names}var gdata = {_j.dumps([row, row])};\n</script>"


def test_team_tables_known_width_parses():
    html = _gdata_page()
    tt.check_statnames(html)
    rows = tt.parse_gdata(html)
    assert tt.extra_columns(html, rows) == {}


def test_team_tables_tolerates_trailing_columns_and_names_them():
    html = _gdata_page(width=42, extra_names={40: "WAB Rk", 41: "New"})
    tt.check_statnames(html)
    rows = tt.parse_gdata(html)
    assert tt.extra_columns(html, rows) == {40: "WAB Rk", 41: "New"}
    assert len(tt.to_csv_text(rows).splitlines()[1].split(",")) == len(tt.OUTPUT_INDICES)


def test_team_tables_shifted_known_column_fails():
    with pytest.raises(TorvikFetchError, match="anchor"):
        tt.parse_gdata(_gdata_page(record=0.5))
    with pytest.raises(TorvikFetchError, match="at least 40"):
        tt.parse_gdata(_gdata_page(width=39))


# ============================================================
# Data freshness (index.json "_meta".last_updated)
# ============================================================

def _fresh_inputs(paths, year, games, player_rows=("a",)):
    d = paths.year_dir(year)
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"team": [f"T{i}" for i in range(len(games))], "games": games}).to_csv(
        paths.stage_file("team_stats_full_season", year), index=False)
    pd.DataFrame({"team": ["T0"], "x": [1]}).to_csv(paths.stage_file("team_shooting_splits", year), index=False)
    pd.DataFrame({"player": list(player_rows)}).to_csv(paths.stage_file("player_stats", year), index=False)


def _save_state(paths, year, state):
    f = freshness.state_file(paths, year)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({k: state[k] for k in ("year", "fingerprint", "games_total", "last_updated")}))


def test_freshness_advances_only_on_new_data_and_holds_on_regression(tmp_path):
    paths, Y = Paths(out_root=tmp_path), 2027
    _fresh_inputs(paths, Y, [4, 5])
    s1 = freshness.evaluate(paths, Y, now="2026-11-18T03:00:00+00:00")
    assert (s1["status"], s1["last_updated"], s1["games_total"]) == ("NEW", "2026-11-18T03:00:00+00:00", 9)
    _save_state(paths, Y, s1)

    # same cleaned data on a later run (stale fetch): stamp carried forward
    s2 = freshness.evaluate(paths, Y, now="2026-11-19T03:00:00+00:00")
    assert (s2["status"], s2["last_updated"]) == ("UNCHANGED", "2026-11-18T03:00:00+00:00")
    assert freshness.gate(s2).passed is True

    # new games: stamp advances
    _fresh_inputs(paths, Y, [5, 6])
    s3 = freshness.evaluate(paths, Y, now="2026-11-20T03:00:00+00:00")
    assert (s3["status"], s3["last_updated"], s3["games_total"]) == ("ADVANCED", "2026-11-20T03:00:00+00:00", 11)
    _save_state(paths, Y, s3)

    # different data with FEWER games: regression, stamp + last good fingerprint held
    _fresh_inputs(paths, Y, [4, 4], player_rows=("a", "b"))
    s4 = freshness.evaluate(paths, Y, now="2026-11-21T03:00:00+00:00")
    assert (s4["status"], s4["last_updated"]) == ("REGRESSION", "2026-11-20T03:00:00+00:00")
    assert (s4["games_total"], s4["fingerprint"]) == (11, s3["fingerprint"])
    g = freshness.gate(s4)
    assert g.passed is False and g.blocking is False and "11 -> 8" in g.messages[0]


def test_freshness_fingerprint_sees_stat_changes_without_new_games(tmp_path):
    paths, Y = Paths(out_root=tmp_path), 2027
    _fresh_inputs(paths, Y, [4])
    a = freshness.fingerprint(paths, Y)
    _fresh_inputs(paths, Y, [4], player_rows=("a", "changed"))      # same games, stat change
    assert freshness.fingerprint(paths, Y) != a


def test_freshness_meta_block():
    assert freshness.meta(None) is None
    m = freshness.meta({"year": 2027, "last_updated": "2026-11-18T03:00:00+00:00", "games_total": 9})
    assert m == {"last_updated": "2026-11-18T03:00:00+00:00", "season": 2027, "games_total": 9}
