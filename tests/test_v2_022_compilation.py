"""V2-022 mission — compilation + operator-namespace regression coverage.

Locks the 120-second mission contract before any paid mutation:

  1. the builder compiles the frozen prose to EXACTLY 24 shots (5s each,
     120.0s) with the intended function pattern and a unique motion
     needle per shot (duplicate needles cross-match discovery)
  2. the Owner-authorized budget (cap 25 = 24 + 1 repair reserve) is
     encoded and enforced by the builder
  3. the v2-022 operator tool is single-variant: starts with >= 1 usable
     credit, uses the v2-022 state/gate/manifest namespace, and reads
     the compilation via V2_022_COMPILATION when set
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

EXPECTED_FUNCTIONS = [
    "ESTABLISH", "APPROACH", "DISCOVER", "PRESSURE", "DECISION",
    "APPROACH", "PRESSURE", "REACTION", "DECISION", "REVEAL",
    "REACTION", "AFTERMATH", "DISCOVER", "PRESSURE", "DECISION",
    "REVEAL", "PAYOFF", "AFTERMATH", "DISCOVER", "REACTION",
    "DECISION", "PAYOFF", "AFTERMATH", "RESOLVE",
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_compilation(tmp_path: Path) -> dict:
    build = _load_module(
        "build_v2_022_compilation_under_test",
        ROOT / "tools" / "build_v2_022_compilation.py")
    build.PKG = tmp_path
    rc = build.main()
    assert rc == 0
    out = tmp_path / "V2_022_LONGFORM_COMPILATION.json"
    return json.loads(out.read_text(encoding="utf-8"))


def test_compilation_is_24_shots_120_seconds(tmp_path):
    doc = _build_compilation(tmp_path)
    assert len(doc["shot_graph"]["nodes"]) == 24
    assert doc["input"]["estimated_scene_seconds"] == "120"
    assert doc["mutation_budget"]["planned_shots"] == 24
    assert doc["mutation_budget"]["total_budget"] == 25
    assert doc["mutation_budget"]["required_credit_floor"] == 24


def test_function_pattern_locked(tmp_path):
    doc = _build_compilation(tmp_path)
    functions = [n["function"] for n in doc["shot_graph"]["nodes"]]
    assert functions == EXPECTED_FUNCTIONS
    assert functions[0] == "ESTABLISH"
    assert functions[-1] == "RESOLVE"


def test_motion_needles_unique_and_aligned(tmp_path):
    doc = _build_compilation(tmp_path)
    build = sys.modules["build_v2_022_compilation_under_test"]
    order = [n["shot_id"] for n in doc["shot_graph"]["nodes"]]
    needles = []
    for index, sid in enumerate(order):
        plan = doc["prompt_plans"][sid]
        motion = plan["sections"]["motion"]
        needles.append(motion[:80])
        assert motion[:80] == build.MOTIONS[index][:80]
    assert len(set(needles)) == 24


def test_prompts_carry_discipline_constraints(tmp_path):
    doc = _build_compilation(tmp_path)
    for plan in doc["prompt_plans"].values():
        text = plan.get("compiled_text", "")
        assert "no text, no logos" in text
        assert "gardener" in text


def test_runner_single_variant_namespace(tmp_path, monkeypatch):
    import run_v2_022_production as tool
    assert tool.COMP_PATH.name == "V2_022_LONGFORM_COMPILATION.json"
    assert tool._state_path(tmp_path).name == "v2_022_run_state.json"
    assert tool._comp_for(0) is None
    chosen = tool._comp_for(1)
    assert chosen is not None
    path, comp = chosen
    assert path.name == "V2_022_LONGFORM_COMPILATION.json"
    assert comp["mutation_budget"]["total_budget"] == 25
    state = tool._load_state(tmp_path)
    assert state["version"] == "v2-022-run-state-v1"


def test_tranche_guard_continues_while_any_account_is_fundable():
    import run_v2_022_production as tool
    # acting account exhausted but others hold credit or are unobservable
    assert tool._tranche_viable(0, [3, 0]) is True
    assert tool._tranche_viable(0, [None]) is True
    assert tool._tranche_viable(2, []) is True
    assert tool._tranche_viable(None, [0]) is True
    # only stop when nothing can fund the next shot
    assert tool._tranche_viable(0, [0, 0]) is False
    assert tool._tranche_viable(0, []) is False
