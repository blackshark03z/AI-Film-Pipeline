"""V2-022 fresh-checkout bootstrap contract (offline hardening WP A1/A3).

The runtime compilation under projects/ is Git-ignored by design, so a
fresh clean checkout (CI included) does not have it. These tests lock
the fail-closed contract:

  1. importing the operator tool and using read-only helpers must work
     without any compilation (no crash at import)
  2. every state-initializing / gate / mutation entrypoint refuses with
     an informative CompilationUnavailableError and ZERO probes or
     dispatches when the compilation is missing, malformed or
     inconsistent with the run state
  3. run state and compilation must agree (identity, planned shots,
     gate budget) — a disagreement refuses instead of silently
     rebinding run authority (V2-021 manifest defect class)

A deterministic rebuild from tools/build_v2_022_compilation.py is used
as a strictly NON-AUTHORITATIVE sample: it proves mechanics, never
spend authority.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))


def _no_default_comp(monkeypatch, tmp_path):
    """Point the runner at a compilation path that does not exist."""
    import run_v2_022_production as tool
    monkeypatch.delenv("V2_022_COMPILATION", raising=False)
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    missing = tmp_path / "missing_pkg" / "V2_022_LONGFORM_COMPILATION.json"
    monkeypatch.setattr(tool, "COMP_PATH", missing)
    return tool, missing


def _build_sample(tmp_path: Path) -> Path:
    """Deterministic NON-AUTHORITATIVE sample via the real builder."""
    spec = importlib.util.spec_from_file_location(
        "build_v2_022_sample", ROOT / "tools" / "build_v2_022_compilation.py")
    build = importlib.util.module_from_spec(spec)
    sys.modules["build_v2_022_sample"] = build
    spec.loader.exec_module(build)
    build.PKG = tmp_path
    assert build.main() == 0
    return tmp_path / "V2_022_LONGFORM_COMPILATION.json"


# ------------------------------------------------------------- A1.1 --

def test_import_and_read_only_helpers_work_without_compilation(tmp_path):
    import run_v2_022_production as tool
    assert tool.COMP is None and tool.BUDGET is None
    assert tool._state_path(tmp_path).name == "v2_022_run_state.json"
    assert tool._tranche_viable(0, [3]) is True
    assert tool._receipt_miss_streak_stop(1) is False


def test_fresh_interpreter_import_and_help_need_no_compilation(tmp_path):
    # honest fresh-process proof: clean sys.modules, no env override,
    # default ignored path absent (this worktree is a fresh checkout)
    env = {k: v for k, v in __import__("os").environ.items()
           if k != "V2_022_COMPILATION"}
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "import run_v2_022_production as t; "
         "assert t.COMP is None; "
         "assert t._tranche_viable(0, [1]) is True; "
         "print('FRESH_IMPORT_OK')" % (ROOT / "tools")],
        capture_output=True, text=True, env=env, cwd=str(ROOT))
    assert probe.returncode == 0, probe.stderr
    assert "FRESH_IMPORT_OK" in probe.stdout

    help_run = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_v2_022_production.py")],
        capture_output=True, text=True, env=env, cwd=str(ROOT))
    assert help_run.returncode == 2  # usage, not a traceback
    assert "V2-022 operator entry" in help_run.stdout
    assert "Traceback" not in help_run.stderr


# ------------------------------------------------------------- A1.2 --

def test_missing_compilation_error_is_informative(tmp_path, monkeypatch):
    tool, missing = _no_default_comp(monkeypatch, tmp_path)
    try:
        tool.load_compilation(missing)
        raise AssertionError("must fail closed")
    except tool.CompilationUnavailableError as error:
        message = str(error)
        assert str(missing) in message
        assert "Git-ignored" in message
        assert "build_v2_022_compilation.py" in message
        assert "NON-AUTHORITATIVE" in message


def test_malformed_compilation_fails_closed(tmp_path, monkeypatch):
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    try:
        tool.load_compilation(bad)
        raise AssertionError("must fail closed")
    except tool.CompilationUnavailableError as error:
        assert "not valid JSON" in str(error)


def test_structural_mismatch_fails_closed(tmp_path, monkeypatch):
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    mismatch = tmp_path / "mismatch.json"
    mismatch.write_text(json.dumps({
        "shot_graph": {"nodes": [{"shot_id": "S01"}] * 3},
        "prompt_plans": {},
        "mutation_budget": {"total_budget": 27, "planned_shots": 24,
                            "rule": "r"}}), encoding="utf-8")
    try:
        tool.load_compilation(mismatch)
        raise AssertionError("must fail closed")
    except tool.CompilationUnavailableError as error:
        assert "planned_shots" in str(error)

    lacking = tmp_path / "lacking.json"
    lacking.write_text(json.dumps({"version": "x"}), encoding="utf-8")
    try:
        tool.load_compilation(lacking)
        raise AssertionError("must fail closed")
    except tool.CompilationUnavailableError as error:
        assert "mutation_budget" in str(error)


def test_auto_and_gate_refuse_with_zero_dispatch(tmp_path, monkeypatch):
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    run_dir = tmp_path / "run"

    def _must_not_touch(*args, **kwargs):
        raise AssertionError("no probe/dispatch may run without the "
                             "frozen compilation")

    monkeypatch.setattr(tool, "_probe", _must_not_touch)
    monkeypatch.setattr(tool, "dispatch_and_acquire", _must_not_touch)
    monkeypatch.setattr(sys, "argv",
                        ["run_v2_022_production.py", str(run_dir), "auto"])
    assert tool.main() == 4

    monkeypatch.setattr(sys, "argv",
                        ["run_v2_022_production.py", str(run_dir), "gate"])
    assert tool.main() == 4
    # no run state, no gate artifact, nothing initialized
    assert not (run_dir / "v2_022_run_state.json").exists()
    assert not (run_dir / "V2_022_POOL_GATE.json").exists()


def test_status_on_existing_run_works_without_compilation(
        tmp_path, monkeypatch):
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    run_dir = tmp_path / "resume_run"
    run_dir.mkdir()
    (run_dir / "v2_022_run_state.json").write_text(json.dumps({
        "version": "v2-022-run-state-v1",
        "shots": {"S01": {"status": "ACQUIRED"}},
        "mutations_used": 1, "gate": {"decision": "X"}, "repairs": []}),
        encoding="utf-8")
    state = tool._load_state(run_dir)  # read-only resume, no COMP needed
    assert state["mutations_used"] == 1
    assert tool._activate_comp.__doc__  # sanity: module intact


# ------------------------------------------------------------- A3 ---

def _sample_state(sample: Path) -> dict:
    comp = json.loads(sample.read_text(encoding="utf-8"))
    return {
        "version": "v2-022-run-state-v1",
        "fixture_id": comp.get("fixture_id", comp["version"]),
        "planned_shots": comp["mutation_budget"]["planned_shots"],
        "compilation_path": str(sample),
        "gate": {"computed_budget":
                 comp["mutation_budget"]["total_budget"]},
        "shots": {}, "mutations_used": 0, "repairs": [],
    }


def test_activate_comp_binds_agreeing_state(tmp_path, monkeypatch):
    import run_v2_022_production as tool
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    sample = _build_sample(tmp_path)
    tool._activate_comp(_sample_state(sample))
    assert tool.COMP is not None
    assert tool.BUDGET["total_budget"] == 27


def test_activate_comp_refuses_state_file_disagreements(
        tmp_path, monkeypatch):
    import run_v2_022_production as tool
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    sample = _build_sample(tmp_path)

    vanished = dict(_sample_state(sample),
                    compilation_path=str(tmp_path / "vanished.json"))
    try:
        tool._activate_comp(vanished)
        raise AssertionError("must refuse substitute")
    except tool.CompilationUnavailableError as error:
        assert "no longer exists" in str(error)

    alien = dict(_sample_state(sample), fixture_id="some-other-fixture")
    try:
        tool._activate_comp(alien)
        raise AssertionError("must refuse rebind")
    except tool.CompilationUnavailableError as error:
        assert "disagrees" in str(error)

    resized = dict(_sample_state(sample), planned_shots=5)
    try:
        tool._activate_comp(resized)
        raise AssertionError("must refuse rebind")
    except tool.CompilationUnavailableError as error:
        assert "planned_shots" in str(error)

    rebudgeted = _sample_state(sample)
    rebudgeted["gate"] = {"computed_budget": 25}
    try:
        tool._activate_comp(rebudgeted)
        raise AssertionError("must refuse rebind")
    except tool.CompilationUnavailableError as error:
        assert "budget" in str(error)
