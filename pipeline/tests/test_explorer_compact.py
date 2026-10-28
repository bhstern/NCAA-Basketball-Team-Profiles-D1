"""
Phase 4a tests — compact explorer: keep-list, columnar writer, record rebuild (Python
twin AND the real js/explorer.js loadExplorerYear() run under node), p107 both formats.
All writes go to a pytest tmp dir (never touches Data/ or player_data/).

Run:  python -m pytest pipeline/tests -q
"""

import json
import math
import re
import shutil
import subprocess

import pandas as pd
import pytest

from pipeline import config
from pipeline.dev.compare_explorer import compare_year, is_equivalent, rebuild_records
from pipeline.paths import Paths
from pipeline.player import json_common as jc

RECORDS = [
    {"player_id": "A", "games": 5, "bpm": 1.25, "bpm_pct": None, "percentile_eligible": True, "oprpg": 0.5},
    {"player_id": "B", "games": 31, "bpm": -2.0, "bpm_pct": 0.875, "percentile_eligible": False, "oprpg": float("nan")},
]
COLS = ["player_id", "games", "bpm", "bpm_pct", "percentile_eligible"]


# ============================================================
# Keep-list
# ============================================================

def test_keep_list_is_the_approved_509_columns():
    k = jc.EXPLORER_KEEP_COLS
    assert len(k) == 509
    # the cross-file traps from the spec
    assert {"rim_made_att_str", "midrange_made_att_str", "three_made_att_str", "usage_tier",
            "player_season_id", "player_id_collision", "year"} <= k
    for stat in ("rim_rate", "rim_fg_pct", "midrange_rate", "midrange_fg_pct", "three_rate", "three_fg_pct"):
        assert set(jc._with_pcts(stat)) <= k
    # approved drops
    assert not {"oprpg", "hometown_city", "games_tier", "fg_made_att_str", "minutes_per_game_pct"} & k
    assert "fga_pg" in k and not any(c.startswith("fga_pg_") for c in k)


def test_compact_cols_follow_full_order_and_refuse_a_missing_kept_column():
    full = jc.get_explorer_cols(list(jc.EXPLORER_KEEP_COLS) + ["oprpg", "hometown_city"])
    compact = jc.get_compact_explorer_cols(full)
    assert compact == [c for c in full if c in jc.EXPLORER_KEEP_COLS] and len(compact) == 509
    with pytest.raises(ValueError, match="rim_made_att_str"):
        jc.get_compact_explorer_cols([c for c in full if c != "rim_made_att_str"])


# ============================================================
# Columnar writer + Python rebuild
# ============================================================

def test_columnar_shape_and_nan_becomes_null():
    out = jc.columnar(RECORDS, COLS + ["oprpg"])
    assert out["columns"] == COLS + ["oprpg"]
    assert out["rows"] == [["A", 5, 1.25, None, True, 0.5], ["B", 31, -2.0, 0.875, False, None]]


def test_write_columnar_round_trips_values_and_types(tmp_path):
    path = jc.write_columnar(tmp_path / "players_2018.json", RECORDS, COLS, 2018)
    text = path.read_text()
    assert "NaN" not in text and text.startswith('{"columns":')
    back = rebuild_records(json.loads(text))
    assert back == [{c: r[c] for c in COLS} for r in RECORDS]
    assert type(back[0]["games"]) is int and type(back[1]["bpm"]) is float


def test_write_columnar_refuses_infinity(tmp_path):
    with pytest.raises(ValueError):
        jc.write_columnar(tmp_path / "x.json", [{"a": float("inf")}], ["a"], 2018)


def test_compare_year_is_zero_when_equivalent_and_catches_each_kind_of_drift(tmp_path):
    keep = jc.EXPLORER_KEEP_COLS
    old = [{"player_id": "A", "player_season_id": "A_1", "games": 5, "oprpg": 1.0},
           {"player_id": "B", "player_season_id": "B_1", "games": 7, "oprpg": 2.0}]
    cols = [c for c in old[0] if c in keep]
    (tmp_path / "old.json").write_text(json.dumps(old))

    def check(rows, columns=cols):
        (tmp_path / "new.json").write_text(json.dumps({"columns": columns, "rows": rows}))
        return compare_year(tmp_path / "new.json", tmp_path / "old.json")

    assert is_equivalent(check([["A", "A_1", 5], ["B", "B_1", 7]]))
    assert check([["A", "A_1", 5.0], ["B", "B_1", 7]])["value_diffs"] == 1     # int vs float
    assert check([["B", "B_1", 7], ["A", "A_1", 5]])["order_moves"] == 2       # row order
    assert not check([["A", 5], ["B", 7]], ["player_id", "games"])["columns_ok"]
    with pytest.raises(ValueError):                                             # bare NaN token
        (tmp_path / "new.json").write_text('{"columns":["player_id"],"rows":[[NaN]]}')
        compare_year(tmp_path / "new.json", tmp_path / "old.json")


# ============================================================
# The real loadExplorerYear() from js/explorer.js, run under node
# ============================================================

def _load_explorer_year_js():
    src = (config.REPO_ROOT / "js" / "explorer.js").read_text()
    m = re.search(r"^async function loadExplorerYear\(year\) \{.*?^\}", src, re.S | re.M)
    assert m, "loadExplorerYear not found in js/explorer.js"
    return m.group(0)


def _run_js(payload):
    """Call the real loadExplorerYear twice with a stubbed fetch; return both results + fetch count."""
    script = f"""
let EXPLORER_CACHE = {{}};
let fetches = 0;
const PAYLOAD = {json.dumps(payload)};
globalThis.fetch = async url => {{ fetches++; return {{ json: async () => JSON.parse(JSON.stringify(PAYLOAD)) }}; }};
{_load_explorer_year_js()}
(async () => {{
  const a = await loadExplorerYear(2018);
  const b = await loadExplorerYear(2018);
  console.log(JSON.stringify({{a, sameObject: a === b, cached: EXPLORER_CACHE[2018] === a, fetches,
                              isArray: Array.isArray(a)}}));
}})();
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@needs_node
def test_js_loader_rebuilds_records_from_the_compact_format():
    compact = jc.columnar(RECORDS, COLS)
    r = _run_js(compact)
    assert r["isArray"] and r["a"] == [{c: rec[c] for c in COLS} for rec in RECORDS]
    assert r["cached"] and r["sameObject"] and r["fetches"] == 1     # caches the rebuilt records


@needs_node
def test_js_loader_passes_the_old_array_format_through_unchanged():
    old = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in rec.items()} for rec in RECORDS]
    r = _run_js(old)
    assert r["a"] == old and r["cached"] and r["fetches"] == 1


@needs_node
def test_js_and_python_rebuild_agree_on_a_real_compact_file():
    path = Paths().json_file("player_data", "layer2_explorer", "players_2018.json")
    if not path.exists() or path.read_bytes()[:1] != b"{":
        pytest.skip("no compact 2018 explorer file in the sandbox")
    data = json.loads(path.read_bytes())
    sample = {"columns": data["columns"], "rows": data["rows"][:200]}
    assert _run_js(sample)["a"] == rebuild_records(sample)


# ============================================================
# p107 — compact by default, legacy full format on demand
# ============================================================

def _tiny_profiles(tmp_path):
    cols = sorted(jc.EXPLORER_KEEP_COLS) + ["oprpg", "hometown_city", "minutes_played"]
    text = {"player_id", "player_season_id", "name", "team", "conference", "power_mid", "position",
            "role", "class", "mpg_tier", "usage_tier", "percentile_tier", "player_id_collision",
            "rim_made_att_str", "midrange_made_att_str", "three_made_att_str", "hometown_city"}
    rows = []
    for i, (team, pos) in enumerate([("Duke", "Guard"), ("Duke", "Big"), ("Yale", "Wing")]):
        r = {c: (f"{c}_{i}" if c in text else 1.5 + i) for c in cols}
        r.update(team=team, position=pos, power_mid="Power", conference="ACC", year=2018, games=10 + i,
                 percentile_tier="Tier 1", percentile_eligible=True, mpg_tier="Core Player (26+ MPG)",
                 minutes_played=100.0 * (i + 1), rim_made_att_str=f"{i}/{i + 3}")
        rows.append(r)
    p = Paths(out_root=tmp_path)
    path = p.stage_file("player_profiles", 2018)
    path.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return p


def test_p107_writes_compact_by_default_and_full_format_with_the_legacy_flag(tmp_path):
    from pipeline.player import p107_convert_player_json as p107
    p = _tiny_profiles(tmp_path)
    explorer = p.json_file("player_data", "layer2_explorer", "players_2018.json")

    p107.run(2018, p, legacy_explorer=True)
    full = json.loads(explorer.read_text())
    rosters = p.json_file("player_data", "layer1_rosters", "rosters_2018.json").read_bytes()
    assert isinstance(full, list) and len(full) == 3 and "oprpg" in full[0]

    p107.run(2018, p)
    compact = json.loads(explorer.read_text())
    assert len(compact["columns"]) == 509 and "oprpg" not in compact["columns"]
    assert rebuild_records(compact) == [{c: r[c] for c in compact["columns"]} for r in full]
    # the explorer flag changes only the explorer file
    assert p.json_file("player_data", "layer1_rosters", "rosters_2018.json").read_bytes() == rosters
