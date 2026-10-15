"""
Scaffolding tests — paths guardrail, dtype pin, text stitching.
All writes go to a pytest tmp dir (never touches Data/).

Run:  python -m pytest pipeline/tests -q
"""

import pandas as pd
import pytest

from pipeline import config
from pipeline.dev import legacy_reference
from pipeline.dev.stitch import BOM, CsvText, stitch
from pipeline.legacy import pin_float_dtypes
from pipeline.paths import FrozenRawError, Paths


# ============================================================
# Paths
# ============================================================

def test_default_outputs_land_in_rebuild_sandbox():
    p = Paths()
    assert p.stage_file("team_profiles", 2018) == config.REBUILD_ROOT / "by_year" / "2018" / "team_profiles.csv"
    assert config.REBUILD_ROOT in p.legacy_ref_dir.parents
    assert config.REBUILD_ROOT in p.stitched_dir.parents


def test_frozen_season_reads_hand_built_raw():
    p = Paths()
    assert p.raw_team_tables(2018) == config.team_tables_path(2018)
    assert p.raw_shooting_splits(2026) == config.shooting_splits_path(2026)


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_frozen_season_refuses_any_other_raw_root(year):
    p = Paths(raw_root=config.SCRAPE_TEST_ROOT)
    for accessor in (p.raw_team_tables, p.raw_shooting_splits, p.raw_player):
        with pytest.raises(FrozenRawError):
            accessor(year)


def test_current_season_may_use_another_raw_root():
    p = Paths(raw_root=config.SCRAPE_TEST_ROOT)
    assert config.SCRAPE_TEST_ROOT in p.raw_team_tables(config.CURRENT_SEASON).parents


# ============================================================
# Legacy reference harness
# ============================================================

def test_legacy_reference_never_runs_the_scraper(tmp_path):
    with pytest.raises(PermissionError):
        legacy_reference.run_script("101_scrape_Torvik_player_stats.py", tmp_path)
    assert all("101" not in name for chain in legacy_reference.CHAINS.values() for name in chain)


# ============================================================
# Dtype pin
# ============================================================

def test_pin_float_dtypes_only_upcasts_unlisted_ints():
    df = pd.DataFrame({"team": ["a", "b"], "wins": [1, 2], "pake": [0, 0], "exp.": [1.5, 2.0]})
    out = pin_float_dtypes(df, int_columns=("wins",))
    assert out["wins"].dtype.kind == "i"
    assert out["pake"].dtype == "float64"
    assert out["exp."].dtype == "float64"
    assert out["team"].dtype == object
    assert out.to_csv(index=False).splitlines()[1] == "a,1,0.0,1.5"


# ============================================================
# Stitch (text level)
# ============================================================

def _write(path, text, bom=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((BOM if bom else b"") + text.encode("utf-8"))


def test_stitch_sorts_on_team_key_without_reformatting(tmp_path):
    p = Paths(out_root=tmp_path)
    _write(p.stage_file("master_team", 2017), "team,x\nDuke_2017,1.50\nAkron_2017,2\n")
    _write(p.stage_file("master_team", 2016), "team,x\nDuke_2016,0.10\nAkron_2016,7.0\n")
    out = stitch("master_team", [2017, 2016], p)
    assert out.read_bytes() == BOM + b"team,x\nAkron_2016,7.0\nAkron_2017,2\nDuke_2016,0.10\nDuke_2017,1.50\n"


def test_stitch_concat_keeps_year_order(tmp_path):
    p = Paths(out_root=tmp_path)
    _write(p.stage_file("team_profiles", 2017), "year,team\n2017,Duke_2017\n", bom=False)
    _write(p.stage_file("team_profiles", 2016), "year,team\n2016,Zed_2016\n2016,Akron_2016\n", bom=False)
    out = stitch("team_profiles", [2017, 2016], p)
    assert out.read_bytes() == b"year,team\n2016,Zed_2016\n2016,Akron_2016\n2017,Duke_2017\n"


def test_stitch_refuses_mismatched_headers(tmp_path):
    p = Paths(out_root=tmp_path)
    _write(p.stage_file("master_team", 2016), "team,x\nDuke_2016,1\n")
    _write(p.stage_file("master_team", 2017), "team,y\nDuke_2017,1\n")
    with pytest.raises(ValueError):
        stitch("master_team", [2016, 2017], p)


def test_csv_text_keeps_quoted_fields_and_rejects_ragged_rows(tmp_path):
    f = tmp_path / "q.csv"
    _write(f, 'team,x\n"Duke, NC_2016",1\n')
    assert CsvText(f).column("team") == ["Duke, NC_2016"]
    _write(f, "team,x\nDuke_2016,1,2\n")
    with pytest.raises(ValueError):
        CsvText(f).column("team")
    _write(f, 'team,x\n"Duke\nNC_2016",1\n')          # embedded newline
    with pytest.raises(ValueError):
        CsvText(f).column("team")
