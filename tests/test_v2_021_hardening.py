"""WP-FILM-POST-V2-021-001 — hardening regression coverage.

Covers the G2 audit findings on the exact code paths that produced them:

  D1  receipt-miss must account the latched release (on_release fires
      before failing) — manual retroactive budget correction was the
      live V2-021 workaround
  D2  the dispatch engine must never delete journal evidence and must
      fail closed when a prior journal holds events past reservation
  D3  manifest/auto must follow the state's compilation choice (the
      executed run's manifest documented 6 nodes beside 5-shot execution)
  D4  alias -> profile root and the MOTION-needle convention live in one
      shared module (E/F wrong-root was the duplication defect)
  D5  a standalone re-gate mid-run must preserve shot progress and only
      archive (never drop) records for shots that leave the graph
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import v2_020_runner as runner  # noqa: E402
import v2_021_common as common  # noqa: E402
from dola_010e_dispatch_journal import (  # noqa: E402
    DISPATCH_ARMED_EV, MUTATION_RESERVED, NETWORK_RELEASE_OBSERVED,
    DispatchJournal)


def _write_comp(path: Path, shots: int, *, budget: int | None = None) -> Path:
    ids = [f"S0{i}" for i in range(1, shots + 1)]
    comp = {
        "input": {"text": f"{shots}-shot test input"},
        "story_graph": {"nodes": []},
        "shot_graph": {"nodes": [{"shot_id": sid} for sid in ids]},
        "prompt_plans": {
            sid: {"sha256": "0" * 64,
                  "sections": {"motion": f"motion {sid} " * 12},
                  "compiled_text": f"prompt {sid}"}
            for sid in ids},
        "mutation_budget": {"total_budget": budget or shots,
                            "planned_shots": shots, "rule": "test rule"},
    }
    path.write_text(json.dumps(comp), encoding="utf-8")
    return path


def _shot_spec() -> SimpleNamespace:
    return SimpleNamespace(
        shot_id="QA_SHOT_A", role="ARRIVAL",
        prompt="a lone courier walks the mountain pass " * 8,
        needle="a lone courier walks the mountain pass",
        duration_class=5, camera="static",
        screen_direction="left-to-right")


def _journal(path: Path, *kinds: str) -> None:
    journal = DispatchJournal(path, "")
    for kind in kinds:
        journal.append(kind, {"test": True})


def _engine_kwargs(run_dir: Path):
    return {"shot_spec": _shot_spec(), "account_alias": "ACCOUNT_E",
            "run_dir": run_dir, "shot_tag": "QA_SHOT_A",
            "events_sink": []}


class _NeverManager:
    def __init__(self, *args, **kwargs):
        raise AssertionError("browser must not be constructed")


# ---------------------------------------------------------------- D2 --

def test_engine_refuses_latched_journal_without_touching_it(
        tmp_path, monkeypatch):
    journal_path = tmp_path / "dispatch_journal_QA_SHOT_A.jsonl"
    _journal(journal_path, MUTATION_RESERVED, DISPATCH_ARMED_EV)
    before = journal_path.read_bytes()
    monkeypatch.setattr(runner, "DolaSessionManager", _NeverManager)

    with pytest.raises(RuntimeError, match="beyond MUTATION_RESERVED"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=lambda info: None,
            on_creation=lambda info: None))
    assert journal_path.read_bytes() == before
    assert not list(tmp_path.glob("dispatch_journal_QA_SHOT_A.prior-*"))


def test_engine_archives_reservation_only_journal_then_launches(
        tmp_path, monkeypatch):
    journal_path = tmp_path / "dispatch_journal_QA_SHOT_A.jsonl"
    _journal(journal_path, MUTATION_RESERVED)

    class _BoomManager:
        def __init__(self, *args, **kwargs):
            pass

        async def launch_browser(self):
            raise RuntimeError("BOOTSTRAP_SENTINEL")

        async def close(self):
            pass

    monkeypatch.setattr(runner, "DolaSessionManager", _BoomManager)
    with pytest.raises(RuntimeError, match="BOOTSTRAP_SENTINEL"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=lambda info: None,
            on_creation=lambda info: None))

    archives = list(tmp_path.glob("dispatch_journal_QA_SHOT_A.prior-*.jsonl"))
    assert len(archives) == 1
    archived = DispatchJournal(archives[0], "")
    assert [e["kind"] for e in archived.events] == [MUTATION_RESERVED]
    fresh = DispatchJournal(journal_path, "")
    assert [e["kind"] for e in fresh.events] == [MUTATION_RESERVED]


# ---------------------------------------------------------------- D1 --

class _FakePage:
    def __init__(self):
        self.screenshots = []

    async def goto(self, *args, **kwargs):
        return None

    async def evaluate(self, js, arg=None):
        if js == runner.LOGIN_CHECK_JS:
            return {"composer": True, "logged_out": False}
        if js == runner.RECENT_CONVS_JS:
            return []
        return None

    async def screenshot(self, path=None, **kwargs):
        self.screenshots.append(path)

    async def wait_for_timeout(self, ms):
        return None


class _FakeCapture:
    def __init__(self, *args, **kwargs):
        pass

    async def start(self):
        return None

    async def get_post_data(self, request_id):
        return json.dumps({
            "chat_ability": {
                "ability_param": json.dumps({"model": "seedance_v2.0"})}})


class _FakeAdapter:
    def __init__(self, *args, **kwargs):
        self.run_id = kwargs.get("run_id", "fake_run")
        self.manager = None
        self.page = None
        self.capture = None

    async def ensure_video_mode(self):
        return None

    async def select_duration(self, duration_class):
        return None

    async def verify_duration_pre_dispatch(self, duration_class):
        return {"ok": True}

    def attach_journal(self, journal, **kwargs):
        self.journal = journal

    async def submit(self, prompt, conversation_id=None):
        return {"release": {"request_id": "req_1"}}

    async def wait_journal_state(self, state, timeout):
        return state == "RELEASE_OBSERVED"

    async def verify_release_body(self, request_id):
        return {"duration": 5, "needle_present": True}


def test_receipt_miss_fires_on_release_before_failing(tmp_path, monkeypatch):
    class _Manager:
        def __init__(self, *args, **kwargs):
            self._context = object()

        async def launch_browser(self):
            return _FakePage()

        async def close(self):
            pass

    monkeypatch.setattr(runner, "DolaSessionManager", _Manager)
    monkeypatch.setattr(runner, "DolaBrowserAdapter010E", _FakeAdapter)
    monkeypatch.setattr(runner, "NetworkCapture", _FakeCapture)

    released: list[dict] = []
    with pytest.raises(RuntimeError, match="receipt not captured"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=released.append,
            on_creation=lambda info: None))

    assert len(released) == 1
    assert released[0]["conversation_id"] is None
    assert released[0]["attempt_id"].startswith("attempt_")
    journal = DispatchJournal(
        tmp_path / "dispatch_journal_QA_SHOT_A.jsonl", "")
    kinds = [e["kind"] for e in journal.events]
    assert NETWORK_RELEASE_OBSERVED in kinds
    assert "MODEL_VERIFIED" in kinds

    # the latched journal now blocks any direct engine retry (D2 × D1)
    monkeypatch.setattr(runner, "DolaSessionManager", _NeverManager)
    with pytest.raises(RuntimeError, match="beyond MUTATION_RESERVED"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=lambda info: None,
            on_creation=lambda info: None))


# ---------------------------------------------------------------- D4 --

def test_shared_mapping_is_single_source_of_truth():
    legacy = Path("legacy-root")
    assert common.enrolled_profile_root("ACCOUNT_E", legacy) == \
        common.PKG_PROFILES
    assert common.enrolled_profile_root("ACCOUNT_F", legacy) == \
        common.PKG_PROFILES
    assert common.enrolled_profile_root("ACCOUNT_A", legacy) == legacy
    comp = {"prompt_plans": {"S01": {"sections": {"motion": "m" * 200}}}}
    assert common.needle_for(comp, "S01") == "m" * 80


# ---------------------------------------------------------- D3 + D5 --

@pytest.fixture(scope="module")
def runner_mod(tmp_path_factory):
    import_dir = tmp_path_factory.mktemp("runner_import")
    os.environ["V2_021_COMPILATION"] = str(
        _write_comp(import_dir / "comp6.json", 6))
    return importlib.import_module("run_v2_021_production")


def test_gate_preserves_progress_and_archives_dropped_shots(
        tmp_path, monkeypatch, runner_mod):
    tmp6 = _write_comp(tmp_path / "comp6.json", 6, budget=8)
    tmp5 = _write_comp(tmp_path / "comp5.json", 5, budget=5)
    monkeypatch.setattr(runner_mod, "COMPS", {"6": tmp6, "5": tmp5})

    def fake_probe(alias):
        if alias == "ACCOUNT_A":
            return {"account_alias": alias, "session_state":
                    "SESSION_VALID", "known_credit_state": 5}
        return {"account_alias": alias, "session_state": "SESSION_INVALID"}

    monkeypatch.setattr(runner_mod, "_probe", fake_probe)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "shots": {"S01": {"status": "QC_ACCEPT",
                               "qc_verdict": "ACCEPT"},
                       "S06": {"status": "RELEASED"}},
             "mutations_used": 1, "repairs": [], "gate": None}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")

    assert runner_mod.cmd_gate(run_dir) == 0
    after = json.loads((run_dir / "v2_021_run_state.json")
                       .read_text(encoding="utf-8"))
    assert sorted(after["shots"]) == ["S01", "S02", "S03", "S04", "S05"]
    assert after["shots"]["S01"]["status"] == "QC_ACCEPT"
    assert after["retired_shots"]["S06"]["status"] == "RELEASED"
    assert after["compilation_path"] == str(tmp5)
    assert (run_dir / "V2_021_POOL_GATE.json").exists()


def test_manifest_follows_state_compilation(tmp_path, runner_mod):
    tmp5 = _write_comp(tmp_path / "comp5.json", 5, budget=5)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "compilation_path": str(tmp5),
             "shots": {f"S0{i}": {"status": "QC_ACCEPT"}
                       for i in range(1, 6)},
             "mutations_used": 5, "repairs": [], "gate":
             {"decision": "DISPATCH_AUTHORIZED"}}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")

    assert runner_mod.cmd_manifest(run_dir) == 0
    doc = json.loads((run_dir / "qualification_run"
                      / "V2_021_RUN_MANIFEST.json")
                     .read_text(encoding="utf-8"))
    assert [n["shot_id"] for n in doc["shot_graph"]["nodes"]] == \
        [f"S0{i}" for i in range(1, 6)]
    assert sorted(doc["prompt_plans"]) == \
        [f"S0{i}" for i in range(1, 6)]
    assert runner_mod.BUDGET["total_budget"] == 5


# ---------------------------------- D3 fail-closed on missing compilation
# PR #2 Tech Lead review blocker: a state-selected compilation that is
# missing/unreadable/malformed must fail closed for BOTH auto and
# manifest — never a silent fallback to the 6-shot import-time default.


def _executed_state(run_dir: Path, compilation_path: str | None) -> None:
    """Five-shot executed run as the review repro builds it (the named
    5-shot compilation is absent; the import-time default is 6-shot)."""
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "compilation_path": compilation_path,
             "planned_shots": 5,
             "shots": {f"S0{i}": {"status": "QC_ACCEPT"}
                       for i in range(1, 6)},
             "mutations_used": 5, "repairs": [],
             "gate": {"decision": "DISPATCH_AUTHORIZED",
                      "computed_budget": 5}}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")


def test_manifest_fails_closed_on_missing_state_compilation(
        tmp_path, monkeypatch, runner_mod):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    missing = tmp_path / "vanished_5shot.json"
    _executed_state(run_dir, str(missing))

    with pytest.raises(runner_mod.CompilationUnavailableError,
                       match="no longer exists"):
        runner_mod.cmd_manifest(run_dir)
    # ZERO incorrect manifest output: nothing was written anywhere
    assert not (run_dir / "qualification_run").exists()

    # same refusal through the CLI surface with the documented exit code
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "manifest"])
    assert runner_mod.main() == 4
    assert not (run_dir / "qualification_run").exists()


def test_auto_fails_closed_on_missing_state_compilation_zero_dispatch(
        tmp_path, monkeypatch, runner_mod):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    missing = tmp_path / "vanished_5shot.json"
    _executed_state(run_dir, str(missing))

    def guard(*args, **kwargs):
        raise AssertionError(
            "no account probe or dispatch may run when the state-named "
            "compilation is missing")

    monkeypatch.setattr(runner_mod, "_probe", guard)
    monkeypatch.setattr(runner_mod, "dispatch_and_acquire", guard)
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "auto"])
    assert runner_mod.main() == 4
    assert not list(run_dir.glob("dispatch_journal_*.jsonl"))
    assert not (run_dir / "slots").exists()


def test_activate_comp_fails_closed_on_unreadable_or_malformed(
        tmp_path, runner_mod):
    # unreadable (directory instead of a file)
    directory = tmp_path / "as_directory"
    directory.mkdir()
    with pytest.raises(runner_mod.CompilationUnavailableError,
                       match="unreadable"):
        runner_mod._activate_comp(
            {"compilation_path": str(directory)})

    # malformed: not valid JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    with pytest.raises(runner_mod.CompilationUnavailableError,
                       match="not valid JSON"):
        runner_mod._activate_comp({"compilation_path": str(bad_json)})

    # malformed: wrong nested container type (never a raw AttributeError)
    bad_shape = tmp_path / "bad_shape.json"
    bad_shape.write_text(json.dumps({
        "shot_graph": ["invalid-shape"], "prompt_plans": {},
        "mutation_budget": {"total_budget": 5, "planned_shots": 5}}),
        encoding="utf-8")
    with pytest.raises(runner_mod.CompilationUnavailableError,
                       match="shot_graph"):
        runner_mod._activate_comp({"compilation_path": str(bad_shape)})

    # malformed: structurally incomplete
    thin = tmp_path / "thin.json"
    thin.write_text(json.dumps({"version": "x"}), encoding="utf-8")
    with pytest.raises(runner_mod.CompilationUnavailableError,
                       match="malformed"):
        runner_mod._activate_comp({"compilation_path": str(thin)})


def test_pregate_state_keeps_import_time_default(runner_mod, monkeypatch):
    """Legitimate pre-gate behavior preserved: a state WITHOUT a
    compilation_path is a planning surface and keeps the import-time
    compilation — no refusal, no rebind."""
    sentinel = {"fixture_id": "import-default",
                "shot_graph": {"nodes": [{"shot_id": "S01"}]},
                "prompt_plans": {}, "input": {},
                "mutation_budget": {"total_budget": 6, "planned_shots": 6,
                                    "rule": "r"}}
    monkeypatch.setattr(runner_mod, "COMP", sentinel)
    monkeypatch.setattr(runner_mod, "BUDGET",
                        sentinel["mutation_budget"])
    runner_mod._activate_comp({"gate": None, "shots": {}})
    assert runner_mod.COMP is sentinel  # unchanged, by design


# ------------------------- final guard correction (PROVE addendum c12b622)


def test_auto_preflight_precedes_regate_and_probes(
        tmp_path, monkeypatch, runner_mod):
    """Residual gap 1: gate=None with an ALREADY RECORDED but missing
    compilation must fail closed BEFORE cmd_gate or any account probe
    (reviewer repro: two fake accounts -> previously rc 2, probes 2)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "compilation_path": str(tmp_path / "vanished_5shot.json"),
             "shots": {f"S0{i}": {"status": "PENDING"}
                       for i in range(1, 6)},
             "mutations_used": 0, "repairs": [], "gate": None}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")

    probes = []

    def fake_probe(alias):
        probes.append(alias)
        return {"account_alias": alias,
                "session_state": "SESSION_INVALID"}

    monkeypatch.setattr(runner_mod, "POOL_ACCOUNTS",
                        ["FAKE_A", "FAKE_B"])
    monkeypatch.setattr(runner_mod, "_probe", fake_probe)
    monkeypatch.setattr(runner_mod, "_comp_for", lambda _available: None)
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "auto"])
    assert runner_mod.main() == 4          # COMPILATION_UNAVAILABLE
    assert probes == []                    # zero account probes
    assert not list(run_dir.glob("dispatch_journal_*.jsonl"))
    assert not (run_dir / "slots").exists()


def test_auto_fresh_run_without_recorded_path_still_gates(
        tmp_path, monkeypatch, runner_mod):
    """Fresh-run behavior preserved: with NO recorded compilation path
    the auto command still runs the gate (probes happen), and no
    dispatch occurs when nothing is affordable."""
    tmp6 = _write_comp(tmp_path / "c6.json", 6, budget=8)
    tmp5 = _write_comp(tmp_path / "c5.json", 5, budget=5)
    monkeypatch.setattr(runner_mod, "COMPS", {"6": tmp6, "5": tmp5})
    # realistic import-time default: carries a fixture identity (the
    # _write_comp helper omits one; real fixture compilations have it)
    default6 = json.loads(tmp6.read_text(encoding="utf-8"))
    default6["fixture_id"] = "fresh-run-default"
    monkeypatch.setattr(runner_mod, "COMP", default6)
    monkeypatch.setattr(runner_mod, "BUDGET",
                        default6["mutation_budget"])
    probes = []

    def fake_probe(alias):
        probes.append(alias)
        return {"account_alias": alias,
                "session_state": "SESSION_INVALID"}

    monkeypatch.setattr(runner_mod, "_probe", fake_probe)
    run_dir = tmp_path / "fresh"  # no state file at all
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "auto"])
    assert runner_mod.main() == 2  # gate stop, NOT a provenance refusal
    assert len(probes) == len(runner_mod.POOL_ACCOUNTS)  # gate did run
    assert not list(run_dir.glob("dispatch_journal_*.jsonl"))


def test_state_compilation_rejects_malformed_nodes_and_plans(
        tmp_path, runner_mod):
    """Residual gap 2: nested malformed shot nodes and invalid plan
    structure must fail closed with CompilationUnavailableError before
    the data can reach manifest or auto."""
    def base() -> dict:
        return {
            "fixture_id": "t", "input": {"text": "x"},
            "story_graph": {"nodes": []},
            "shot_graph": {"nodes": [{"shot_id": "S01"},
                                     {"shot_id": "S02"}]},
            "prompt_plans": {
                sid: {"sha256": "0" * 64,
                      "sections": {"motion": f"motion {sid} " * 12},
                      "compiled_text": f"prompt {sid}"}
                for sid in ("S01", "S02")},
            "mutation_budget": {"total_budget": 2, "planned_shots": 2,
                                "rule": "r"}}

    def activate(doc) -> None:
        path = tmp_path / "case.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        runner_mod._activate_comp({"compilation_path": str(path)})

    cases = []
    doc = base()
    doc["shot_graph"]["nodes"] = ["badnode"]
    cases.append(("nodes-hold-strings", doc))
    doc = base()
    doc["shot_graph"]["nodes"] = [{"shot_id": ""}]
    cases.append(("empty-shot-id", doc))
    doc = base()
    doc["shot_graph"]["nodes"] = [{"shot_id": 5}]
    cases.append(("numeric-shot-id", doc))
    doc = base()
    doc["shot_graph"]["nodes"] = [{}]
    cases.append(("missing-shot-id", doc))
    doc = base()
    del doc["prompt_plans"]["S02"]
    cases.append(("plan-missing-for-node", doc))
    doc = base()
    doc["prompt_plans"]["S01"] = "not-an-object"
    cases.append(("plan-not-object", doc))
    doc = base()
    doc["prompt_plans"]["S01"]["sections"]["motion"] = "   "
    cases.append(("blank-motion-needle", doc))
    doc = base()
    del doc["prompt_plans"]["S01"]["sha256"]
    cases.append(("sha256-missing", doc))
    doc = base()
    doc["prompt_plans"]["S02"]["compiled_text"] = ""
    cases.append(("blank-compiled-text", doc))

    for name, doc in cases:
        with pytest.raises(runner_mod.CompilationUnavailableError):
            activate(doc)

    # sanity: the valid base document still activates (successful
    # paths intact)
    activate(base())
    assert runner_mod.BUDGET["total_budget"] == 2


# ------------------ direct-gate provenance guard (final PR #2 blocker)


def test_direct_gate_fails_closed_on_missing_recorded_compilation(
        tmp_path, monkeypatch, runner_mod):
    """Exact reviewer repro: 5-shot run state whose recorded
    compilation is MISSING, gate=None, one fake fundable account (6
    credits) and a valid alternative 6-shot compilation — previously
    rc 0 / DISPATCH_AUTHORIZED / 1 probe / state compilation replaced
    and shots grown 5 -> 6. Now: exit 4, zero probes, original state
    preserved byte-for-byte."""
    alternative = _write_comp(tmp_path / "alt6.json", 6, budget=6)
    monkeypatch.setattr(runner_mod, "COMPS", {"6": alternative,
                                              "5": alternative})
    probes = []

    def fake_probe(alias):
        probes.append(alias)
        return {"account_alias": alias, "session_state": "SESSION_VALID",
                "known_credit_state": 6}

    monkeypatch.setattr(runner_mod, "POOL_ACCOUNTS", ["FAKE_A"])
    monkeypatch.setattr(runner_mod, "_probe", fake_probe)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "compilation_path": str(tmp_path / "vanished_5shot.json"),
             "shots": {f"S0{i}": {"status": "PENDING"}
                       for i in range(1, 6)},
             "mutations_used": 0, "repairs": [], "gate": None}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")
    before = (run_dir / "v2_021_run_state.json").read_text(
        encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "gate"])
    assert runner_mod.main() == 4
    assert probes == []
    # original run state preserved untouched; no rebind, no shots
    # growth, no authorization artifact
    assert (run_dir / "v2_021_run_state.json").read_text(
        encoding="utf-8") == before
    assert not (run_dir / "V2_021_POOL_GATE.json").exists()


def test_direct_gate_fresh_run_without_recorded_path_authorizes(
        tmp_path, monkeypatch, runner_mod):
    """Positive: a genuinely fresh run (no recorded path) keeps
    legitimate gate behavior — the probe runs and an affordable
    compilation is selected and authorized."""
    comp6 = _write_comp(tmp_path / "c6.json", 6, budget=6)
    monkeypatch.setattr(runner_mod, "COMPS", {"6": comp6, "5": comp6})
    default6 = json.loads(comp6.read_text(encoding="utf-8"))
    default6["fixture_id"] = "fresh-run-default"
    monkeypatch.setattr(runner_mod, "COMP", default6)
    monkeypatch.setattr(runner_mod, "BUDGET",
                        default6["mutation_budget"])
    probes = []

    def fake_probe(alias):
        probes.append(alias)
        return {"account_alias": alias, "session_state": "SESSION_VALID",
                "known_credit_state": 6}

    monkeypatch.setattr(runner_mod, "POOL_ACCOUNTS", ["FAKE_A"])
    monkeypatch.setattr(runner_mod, "_probe", fake_probe)
    run_dir = tmp_path / "fresh"  # no state file at all
    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "gate"])
    assert runner_mod.main() == 0
    assert len(probes) == 1  # the gate DID probe the account
    after = json.loads((run_dir / "v2_021_run_state.json")
                       .read_text(encoding="utf-8"))
    assert after["gate"]["decision"] == "DISPATCH_AUTHORIZED"
    assert after["compilation_path"] == str(comp6)


def test_direct_gate_with_valid_recorded_compilation_proceeds(
        tmp_path, monkeypatch, runner_mod):
    """Positive: a run whose recorded compilation is INTACT gates
    normally — probe runs, the same affordable variant is re-selected,
    and nothing is rebound."""
    recorded5 = _write_comp(tmp_path / "recorded5.json", 5, budget=5)
    comp6 = _write_comp(tmp_path / "c6.json", 6, budget=6)
    monkeypatch.setattr(runner_mod, "COMPS", {"6": comp6,
                                              "5": recorded5})
    probes = []

    def fake_probe(alias):
        probes.append(alias)
        return {"account_alias": alias, "session_state": "SESSION_VALID",
                "known_credit_state": 5}

    monkeypatch.setattr(runner_mod, "POOL_ACCOUNTS", ["FAKE_A"])
    monkeypatch.setattr(runner_mod, "_probe", fake_probe)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"version": "v2-021-run-state-v1", "fixture_id": "t",
             "compilation_path": str(recorded5),
             "shots": {f"S0{i}": {"status": "PENDING"}
                       for i in range(1, 6)},
             "mutations_used": 0, "repairs": [], "gate": None}
    (run_dir / "v2_021_run_state.json").write_text(
        json.dumps(state), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["t", str(run_dir), "gate"])
    # 5 credits: the 6-shot variant is NOT affordable, the recorded
    # 5-shot variant is — selection equals the recording, no rebind
    assert runner_mod.main() == 0
    assert len(probes) == 1
    after = json.loads((run_dir / "v2_021_run_state.json")
                       .read_text(encoding="utf-8"))
    assert after["gate"]["decision"] == "DISPATCH_AUTHORIZED"
    assert after["compilation_path"] == str(recorded5)
    assert sorted(after["shots"]) == [f"S0{i}" for i in range(1, 6)]
