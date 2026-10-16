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
