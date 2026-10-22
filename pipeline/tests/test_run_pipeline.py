"""
Orchestrator tests — refusals and the in-process "simulate current" override.
Nothing here runs a stage or writes a file.

Run:  python -m pytest pipeline/tests -q
"""

import pytest

from pipeline import config, guard
from pipeline import run_pipeline as rp
from pipeline.player import p101_fetch_player_stats as p101


@pytest.mark.parametrize("out_root", [
    config.MASTER_ROOT, config.RAW_ROOT, config.REPO_ROOT, config.SCRAPE_TEST_ROOT,
    config.REBUILD_ROOT / ".." , "/tmp/somewhere",
])
def test_refuses_any_out_root_outside_rebuild(out_root):
    with pytest.raises(rp.RunRefused):
        rp.run(2018, out_root=out_root)


@pytest.mark.parametrize("year", sorted(config.FROZEN_SEASONS))
def test_fetch_is_refused_for_every_frozen_season(year):
    with pytest.raises(rp.RunRefused):
        rp.run(year, fetch=True)
    with pytest.raises(rp.RunRefused):
        rp.run(year, fetch=True, simulate_current=True)


def test_simulation_only_for_frozen_seasons_and_unknown_years_refused():
    with pytest.raises(rp.RunRefused):
        rp.run(config.CURRENT_SEASON, simulate_current=True)
    with pytest.raises(rp.RunRefused):
        rp.run(config.CURRENT_SEASON + 3)


def test_publish_flag_is_refused(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run_pipeline", "--year", "2018", "--publish"])
    with pytest.raises(SystemExit):
        rp.main()
    assert "disabled until Phase 6" in capsys.readouterr().err


def test_treat_as_current_is_scoped_and_leaves_the_guard_alone():
    before = (config.CURRENT_SEASON, config.FROZEN_SEASONS, guard.DEFAULT_GUARD.frozen_seasons)
    with rp.treat_as_current(2026):
        assert config.CURRENT_SEASON == 2026 and 2026 not in config.FROZEN_SEASONS
        assert 2026 in guard.DEFAULT_GUARD.frozen_seasons          # guard still protects 2026
        with pytest.raises(p101.FetchScopeError):                   # and p101 still refuses it
            p101.output_path(2026, rp.Paths())
    assert (config.CURRENT_SEASON, config.FROZEN_SEASONS, guard.DEFAULT_GUARD.frozen_seasons) == before
