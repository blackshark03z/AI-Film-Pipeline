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
    """A state as a properly gated run now records it: metadata AND the
    pinned full-file digest of the authorized compilation."""
    import hashlib
    comp = json.loads(sample.read_text(encoding="utf-8"))
    return {
        "version": "v2-022-run-state-v1",
        "fixture_id": comp.get("fixture_id", comp["version"]),
        "planned_shots": comp["mutation_budget"]["planned_shots"],
        "compilation_path": str(sample),
        "compilation_sha256": hashlib.sha256(
            sample.read_bytes()).hexdigest(),
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


# =========================================================================
# Tech Lead PROVE 2026-10-24 corrective coverage (P1 integrity, P2 types)
# =========================================================================

def test_wrong_nested_container_types_fail_closed(tmp_path, monkeypatch):
    """PROVE P2: a wrong container type must raise the documented
    CompilationUnavailableError, never a raw AttributeError."""
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    base_budget = {"total_budget": 27, "planned_shots": 1, "rule": "r"}
    one_node = {"nodes": [{"shot_id": "S01"}]}
    cases = {
        "shot_graph-is-list": {"shot_graph": ["invalid-shape"],
                               "prompt_plans": {},
                               "mutation_budget": base_budget},
        "shot_graph-is-string": {"shot_graph": "invalid",
                                 "prompt_plans": {},
                                 "mutation_budget": base_budget},
        "nodes-hold-non-dicts": {"shot_graph": {"nodes": [1, 2]},
                                 "prompt_plans": {},
                                 "mutation_budget": base_budget},
        "node-empty-shot-id": {"shot_graph": {"nodes": [{"shot_id": ""}]},
                               "prompt_plans": {},
                               "mutation_budget": base_budget},
        "prompt_plans-is-list": {"shot_graph": one_node,
                                 "prompt_plans": [],
                                 "mutation_budget": base_budget},
        "budget-is-list": {"shot_graph": one_node,
                           "prompt_plans": {"S01": {"sections": {
                               "motion": "m" * 100}}},
                           "mutation_budget": ["nope"]},
        "plan-missing-for-node": {"shot_graph": one_node,
                                  "prompt_plans": {},
                                  "mutation_budget": base_budget},
    }
    for name, doc in cases.items():
        path = tmp_path / "case.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        try:
            tool.load_compilation(path)
            raise AssertionError(f"{name} must fail closed")
        except tool.CompilationUnavailableError:
            pass  # the documented fail-closed exception, exactly


def test_malformed_container_routes_to_cli_exit_four(tmp_path, monkeypatch):
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    bad = tmp_path / "bad_container.json"
    bad.write_text(json.dumps({
        "shot_graph": ["invalid-shape"], "prompt_plans": {},
        "mutation_budget": {"total_budget": 27, "planned_shots": 1,
                            "rule": "r"}}), encoding="utf-8")
    monkeypatch.setenv("V2_022_COMPILATION", str(bad))
    run_dir = tmp_path / "run"
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "status"])
    assert tool.main() == 4  # documented CLI behavior, not a traceback


def _tamper_prompt(sample: Path) -> None:
    doc = json.loads(sample.read_text(encoding="utf-8"))
    first = doc["shot_graph"]["nodes"][0]["shot_id"]
    doc["prompt_plans"][first]["compiled_text"] = "ALTERED"
    sample.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                      encoding="utf-8")


def test_activate_comp_rejects_prompt_tamper_same_metadata(
        tmp_path, monkeypatch):
    """PROVE P1 exact repro: prompt_plans mutation with identity, shot
    count and budget unchanged must be an integrity failure."""
    import run_v2_022_production as tool
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    sample = _build_sample(tmp_path)
    state = _sample_state(sample)  # pins the pre-tamper digest
    _tamper_prompt(sample)
    # structure and every metadata agreement still pass alone...
    comp = tool.load_compilation(sample)
    assert comp["mutation_budget"]["total_budget"] == 27
    # ...so only the digest pin can (and must) catch it
    try:
        tool._activate_comp(state)
        raise AssertionError("tampered prompt must be rejected")
    except tool.CompilationUnavailableError as error:
        assert "integrity failure" in str(error)


def test_activate_comp_legacy_state_requires_trusted_evidence(
        tmp_path, monkeypatch):
    import run_v2_022_production as tool
    monkeypatch.delenv("V2_022_COMPILATION_SHA256", raising=False)
    sample = _build_sample(tmp_path)
    legacy = _sample_state(sample)
    legacy.pop("compilation_sha256")  # pre-integrity runtime state
    import hashlib
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()

    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    try:
        tool._activate_comp(legacy)
        raise AssertionError("legacy state must not be silently approved")
    except tool.CompilationUnavailableError as error:
        assert "AUTHORITY_REQUIRED" in str(error)
        assert "verify" in str(error)

    # matching explicit anchor = trusted evidence: binds
    monkeypatch.setenv("V2_022_COMPILATION_SHA256", digest)
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    tool._activate_comp(legacy)
    assert tool.BUDGET["total_budget"] == 27

    # wrong anchor = integrity failure
    monkeypatch.setenv("V2_022_COMPILATION_SHA256", "f" * 64)
    monkeypatch.setattr(tool, "COMP", None)
    try:
        tool._activate_comp(legacy)
        raise AssertionError("anchor mismatch must fail closed")
    except tool.CompilationUnavailableError as error:
        assert "integrity failure" in str(error)


def test_sidecar_sha256_is_a_valid_trust_anchor(tmp_path, monkeypatch):
    import run_v2_022_production as tool
    import hashlib
    monkeypatch.delenv("V2_022_COMPILATION_SHA256", raising=False)
    sample = _build_sample(tmp_path)
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    sidecar = Path(str(sample) + ".sha256")
    sidecar.write_text(f"{digest}  {sample.name}\n", encoding="utf-8")
    state = _sample_state(sample)
    state.pop("compilation_sha256")  # anchor vouches, state unpinned
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    tool._activate_comp(state)
    assert tool.BUDGET["total_budget"] == 27
    # a stale sidecar digest refuses
    sidecar.write_text("e" * 64, encoding="utf-8")
    monkeypatch.setattr(tool, "COMP", None)
    try:
        tool._activate_comp(state)
        raise AssertionError("stale sidecar must fail closed")
    except tool.CompilationUnavailableError as error:
        assert "integrity failure" in str(error)


def test_gate_requires_trust_anchor_and_pins_digest(tmp_path, monkeypatch):
    import hashlib
    import run_v2_022_production as tool
    sample = _build_sample(tmp_path)
    monkeypatch.setenv("V2_022_COMPILATION", str(sample))
    monkeypatch.delenv("V2_022_COMPILATION_SHA256", raising=False)
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    run_dir = tmp_path / "run"
    run_dir.mkdir()  # main() normally creates it before dispatch

    def probe(alias):
        return {"session_state": "SESSION_VALID",
                "known_credit_state": 30}

    emitted = []
    monkeypatch.setattr(tool, "_probe", probe)
    monkeypatch.setattr(tool, "_stale_overrides", lambda: {})
    monkeypatch.setattr(tool, "emit",
                        lambda payload: emitted.append(payload))

    # fundable pool + structurally valid compilation + NO trust anchor:
    # the gate must refuse to authorize anything
    assert tool.cmd_gate(run_dir) == 2
    state = json.loads((run_dir / "v2_022_run_state.json")
                       .read_text(encoding="utf-8"))
    assert state["gate"]["decision"] == "STOP_COMPILATION_TRUST_MISSING"
    assert "compilation_sha256" not in state
    assert len(state["gate"]["unpinned_digest"]) == 64

    # pin the digest deliberately: now the gate authorizes and records
    # the full-file SHA-256 the auto/manifest phases will verify
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    monkeypatch.setenv("V2_022_COMPILATION_SHA256", digest)
    assert tool.cmd_gate(run_dir) == 0
    state = json.loads((run_dir / "v2_022_run_state.json")
                       .read_text(encoding="utf-8"))
    assert state["gate"]["decision"] == "DISPATCH_AUTHORIZED"
    assert state["compilation_sha256"] == digest

    # PROVE boundary requirement: tamper the frozen prompt AFTER
    # authorization — auto AND manifest refuse, zero dispatch
    _tamper_prompt(sample)
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)

    def no_dispatch(*args, **kwargs):
        raise AssertionError("no dispatch after integrity failure")

    monkeypatch.setattr(tool, "dispatch_and_acquire", no_dispatch)
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "auto"])
    assert tool.main() == 4
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "manifest"])
    assert tool.main() == 4
    assert not (run_dir / "qualification_run").exists()


def test_verify_command_reports_without_mutating(tmp_path, monkeypatch):
    import run_v2_022_production as tool
    sample = _build_sample(tmp_path)
    monkeypatch.setenv("V2_022_COMPILATION", str(sample))
    monkeypatch.delenv("V2_022_COMPILATION_SHA256", raising=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "v2_022_run_state.json").write_text(json.dumps({
        "version": "v2-022-run-state-v1", "shots": {},
        "mutations_used": 3, "gate": {"decision": "LEGACY"},
        "repairs": []}), encoding="utf-8")
    before = (run_dir / "v2_022_run_state.json").read_bytes()
    emitted = []
    monkeypatch.setattr(tool, "emit",
                        lambda payload: emitted.append(payload))
    assert tool.cmd_verify(run_dir) == 2  # AUTHORITY_REQUIRED, not silent
    report = emitted[-1]
    assert report["status"] == "AUTHORITY_REQUIRED"
    assert len(report["sha256"]) == 64
    assert "pin_instruction" in report
    assert (run_dir / "v2_022_run_state.json").read_bytes() == before

    monkeypatch.setenv("V2_022_COMPILATION_SHA256", report["sha256"])
    assert tool.cmd_verify(run_dir) == 0
    assert emitted[-1]["status"] == "ANCHOR_OK_STATE_UNPINNED"
    assert (run_dir / "v2_022_run_state.json").read_bytes() == before


# =========================================================================
# PROVE addendum 2026-10-25: trust preflight BEFORE probes; budget values
# =========================================================================

def test_gate_trust_preflight_precedes_any_probe(tmp_path, monkeypatch):
    """PROVE addendum finding 1: with a missing or mismatched trust
    anchor the gate must stop BEFORE the POOL_ACCOUNTS probe loop —
    zero provider/account interaction. A valid anchor proceeds into
    the (fake) probe loop."""
    import hashlib
    import run_v2_022_production as tool
    sample = _build_sample(tmp_path)
    monkeypatch.setenv("V2_022_COMPILATION", str(sample))
    monkeypatch.setattr(tool, "COMP", None)
    monkeypatch.setattr(tool, "BUDGET", None)
    probes = []

    def no_probe(alias):
        probes.append(alias)
        raise AssertionError(
            f"_probe({alias}) must not run while the trust anchor is "
            f"missing or mismatched")

    monkeypatch.setattr(tool, "_probe", no_probe)
    monkeypatch.setattr(tool, "_stale_overrides", lambda: {})
    emitted = []
    monkeypatch.setattr(tool, "emit",
                        lambda payload: emitted.append(payload))

    # missing anchor: stop with ZERO probes
    monkeypatch.delenv("V2_022_COMPILATION_SHA256", raising=False)
    run_a = tmp_path / "gate_missing"
    run_a.mkdir()
    assert tool.cmd_gate(run_a) == 2
    assert probes == []
    state = json.loads((run_a / "v2_022_run_state.json")
                       .read_text(encoding="utf-8"))
    assert state["gate"]["decision"] == "STOP_COMPILATION_TRUST_MISSING"
    assert state["gate"]["probes_suppressed"] is True
    pool_gate = json.loads((run_a / "V2_022_POOL_GATE.json")
                           .read_text(encoding="utf-8"))
    assert pool_gate["decision"] == "STOP_COMPILATION_TRUST_MISSING"
    assert pool_gate["pool"] == {}

    # mismatched anchor: same zero-probe guarantee
    monkeypatch.setenv("V2_022_COMPILATION_SHA256", "f" * 64)
    run_b = tmp_path / "gate_mismatch"
    run_b.mkdir()
    assert tool.cmd_gate(run_b) == 2
    assert probes == []
    state = json.loads((run_b / "v2_022_run_state.json")
                       .read_text(encoding="utf-8"))
    assert state["gate"]["decision"] == "STOP_COMPILATION_TRUST_MISMATCH"

    # valid anchor: the gate DOES proceed into the probe loop
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    monkeypatch.setenv("V2_022_COMPILATION_SHA256", digest)
    monkeypatch.setattr(
        tool, "_probe",
        lambda alias: probes.append(alias) or {
            "session_state": "SESSION_VALID", "known_credit_state": 30})
    run_c = tmp_path / "gate_valid"
    run_c.mkdir()
    assert tool.cmd_gate(run_c) == 0
    assert len(probes) == len(tool.POOL_ACCOUNTS)
    state = json.loads((run_c / "v2_022_run_state.json")
                       .read_text(encoding="utf-8"))
    assert state["gate"]["decision"] == "DISPATCH_AUTHORIZED"
    assert state["compilation_sha256"] == digest


def test_malformed_budget_values_fail_closed(tmp_path, monkeypatch):
    """PROVE addendum finding 2: budget values of the wrong type or
    range (list/str/bool/float/zero/negative, blank rule, budget below
    planned shots) must fail closed through CompilationUnavailableError."""
    tool, _ = _no_default_comp(monkeypatch, tmp_path)
    cases = {
        "total-budget-is-list": {"total_budget": ["27"],
                                 "planned_shots": 1, "rule": "r"},
        "total-budget-is-string": {"total_budget": "27",
                                   "planned_shots": 1, "rule": "r"},
        "total-budget-is-bool": {"total_budget": True,
                                 "planned_shots": 1, "rule": "r"},
        "total-budget-is-float": {"total_budget": 27.0,
                                  "planned_shots": 1, "rule": "r"},
        "total-budget-zero": {"total_budget": 0,
                              "planned_shots": 1, "rule": "r"},
        "total-budget-negative": {"total_budget": -3,
                                  "planned_shots": 1, "rule": "r"},
        "planned-shots-is-string": {"total_budget": 27,
                                    "planned_shots": "1", "rule": "r"},
        "planned-shots-is-bool": {"total_budget": 27,
                                  "planned_shots": True, "rule": "r"},
        "planned-shots-zero": {"total_budget": 27, "planned_shots": 0,
                               "rule": "r"},
        "planned-shots-negative": {"total_budget": 27,
                                   "planned_shots": -1, "rule": "r"},
        "rule-blank": {"total_budget": 27, "planned_shots": 1,
                       "rule": "   "},
        "rule-is-list": {"total_budget": 27, "planned_shots": 1,
                         "rule": ["rule"]},
        "budget-below-planned": {"total_budget": 1,
                                 "planned_shots": 3, "rule": "r"},
    }
    for name, budget in cases.items():
        path = tmp_path / "case.json"
        path.write_text(json.dumps({
            "shot_graph": {"nodes": [{"shot_id": "S01"}]},
            "prompt_plans": {"S01": {"sections": {"motion": "m" * 100}}},
            "mutation_budget": budget}), encoding="utf-8")
        try:
            tool.load_compilation(path)
            raise AssertionError(f"{name} must fail closed")
        except tool.CompilationUnavailableError as error:
            assert "mutation_budget" in str(error) or \
                "shot_graph" in str(error), name
