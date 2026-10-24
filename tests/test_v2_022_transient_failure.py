"""V2-022 transient-failure classification (offline hardening WP A2).

Day-1 live evidence: the provider can reply
"動画を生成できません。今回の生成でクレジットは使用されませんで
した。" (video could not be generated; no credits were used). That
message CONTAINS the generic refusal marker 生成できません, so without
priority classification a transient server-side failure is mislabeled
as a content-policy refusal.

These tests exercise the ACTUAL dispatch_and_acquire control flow with
a scripted fake browser/provider surface (never any network):

  - overlap: transient marker wins over the refusal marker it contains
  - refusal-only text still stops as a policy refusal (unchanged)
  - a completed creation next to failure text is a SUCCESS, not a
    failure
  - unknown/ambiguous rows never spin past the bounded poll window
  - the latched release is accounted (on_release fires exactly once,
    budget never rolls back on the provider's provisional no-credit
    claim) and the journal blocks a second paid mutation
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import v2_020_runner as runner  # noqa: E402
from dola_010e_dispatch_journal import (  # noqa: E402
    NETWORK_RELEASE_OBSERVED, TERMINAL_SUCCESS)

NEEDLE = "a lone courier walks the mountain pass"
TRANSIENT_TEXT = ("動画を生成できません。今回の生成でクレジットは"
                  "使用されませんでした。")
REFUSAL_ONLY_TEXT = "クレジットが足りません"


def _shot_spec() -> SimpleNamespace:
    return SimpleNamespace(
        shot_id="QA_SHOT_A", role="ARRIVAL",
        prompt=NEEDLE + " " * 8, needle=NEEDLE,
        duration_class=5, camera="static", screen_direction="left-to-right")


def _row(text: str, creations: list | None = None) -> dict:
    return {"message_id": "m1", "create_time": 1, "text": text,
            "content_raw": {}, "creations": creations or []}


def _engine_kwargs(run_dir: Path, **extra):
    kwargs = {"shot_spec": _shot_spec(), "account_alias": "ACCOUNT_E",
              "run_dir": run_dir, "shot_tag": "QA_SHOT_A",
              "events_sink": [], "poll_seconds": 15}
    kwargs.update(extra)
    return kwargs


class _ScriptedPage:
    """Baseline (pre-submit) sees no conversations; discovery (after the
    receipt) sees conv_1 with the scripted rows — mirroring how a real
    creation/failure message only exists AFTER the dispatch."""

    def __init__(self, rows_by_conv):
        self.rows_by_conv = rows_by_conv
        self.recent_convs_calls = 0
        self.screenshots = []

    async def goto(self, *args, **kwargs):
        return None

    async def evaluate(self, js, arg=None):
        if js == runner.LOGIN_CHECK_JS:
            return {"composer": True, "logged_out": False}
        if js == runner.RECENT_CONVS_JS:
            self.recent_convs_calls += 1
            return [] if self.recent_convs_calls == 1 else ["conv_1"]
        if js == runner.PULL_RAW_JS:
            return list(self.rows_by_conv.get(arg["conversationId"], []))
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
        return True  # both RELEASE_OBSERVED and RECEIPT_CAPTURED

    async def verify_release_body(self, request_id):
        return {"duration": 5, "needle_present": True}


def _wire(monkeypatch, rows_by_conv):
    page = _ScriptedPage(rows_by_conv)

    class _Manager:
        def __init__(self, *args, **kwargs):
            self._context = object()

        async def launch_browser(self):
            return page

        async def close(self):
            pass

    monkeypatch.setattr(runner, "DolaSessionManager", _Manager)
    monkeypatch.setattr(runner, "DolaBrowserAdapter010E", _FakeAdapter)
    monkeypatch.setattr(runner, "NetworkCapture", _FakeCapture)
    return page


# ------------------------------------------------------ control flow --

def test_transient_failure_beats_refusal_marker_in_real_flow(
        tmp_path, monkeypatch):
    _wire(monkeypatch, {"conv_1": [_row(NEEDLE + " " + TRANSIENT_TEXT)]})
    released, creations = [], []

    with pytest.raises(RuntimeError,
                       match="STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=released.append, on_creation=creations.append))

    # the release was already latched: budget stays counted until
    # read-only reconciliation confirms the provider's no-credit claim
    assert len(released) == 1 and not creations
    journal_path = tmp_path / "dispatch_journal_QA_SHOT_A.jsonl"
    kinds = [e["kind"] for e in _events(journal_path)]
    assert NETWORK_RELEASE_OBSERVED in kinds
    assert TERMINAL_SUCCESS not in kinds
    assert not list(tmp_path.glob("dispatch_journal_QA_SHOT_A.prior-*"))

    # latched journal blocks a second paid mutation (no auto-retry)
    with pytest.raises(RuntimeError, match="beyond MUTATION_RESERVED"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=released.append, on_creation=creations.append))
    assert len(released) == 1


def test_refusal_only_text_still_stops_as_policy_refusal(
        tmp_path, monkeypatch):
    _wire(monkeypatch, {"conv_1": [_row(NEEDLE + " " + REFUSAL_ONLY_TEXT)]})
    with pytest.raises(RuntimeError,
                       match="STOPPED_PROVIDER_POLICY_REFUSAL"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path),
            on_release=lambda i: None, on_creation=lambda i: None))


def test_creation_next_to_failure_text_is_success(tmp_path, monkeypatch):
    _wire(monkeypatch, {"conv_1": [_row(
        NEEDLE + " " + TRANSIENT_TEXT,
        [{"id": "c1", "type": 2, "status": 1,
          "download_url": "https://cdn.dola.example/v/abc.mp4",
          "video_model_raw": "seedance_v2.0"}])]})

    class _FakeResolver:
        def __init__(self, *args, **kwargs):
            pass

        def select(self, creation_obj):
            return SimpleNamespace(
                variant=None, authority="PROVIDER_ISSUED_WATERMARKED",
                reason="offline-fake")

    payload_bytes = b"offline-fake-mp4-bytes"

    def _fake_download(url, dest):
        Path(dest).write_bytes(payload_bytes)
        return len(payload_bytes)

    monkeypatch.setattr(runner, "DolaAssetVariantResolver", _FakeResolver)
    monkeypatch.setattr(runner, "download_allowlisted", _fake_download)
    creations = []

    record = asyncio.run(runner.dispatch_and_acquire(
        **_engine_kwargs(tmp_path),
        on_release=lambda i: None, on_creation=creations.append))

    assert record["asset_sha256"] == hashlib.sha256(
        payload_bytes).hexdigest()
    assert record["watermarked_fallback"] is True
    assert creations and creations[0]["creation_ids"] == ["c1"]
    kinds = [e["kind"] for e in _events(
        tmp_path / "dispatch_journal_QA_SHOT_A.jsonl")]
    assert TERMINAL_SUCCESS in kinds


def test_ambiguous_rows_stop_at_bounded_poll_window(tmp_path, monkeypatch):
    page = _wire(monkeypatch, {"conv_1": [_row(NEEDLE)]})
    with pytest.raises(RuntimeError, match="CORRELATION_GAP"):
        asyncio.run(runner.dispatch_and_acquire(
            **_engine_kwargs(tmp_path, poll_seconds=0),
            on_release=lambda i: None, on_creation=lambda i: None))
    # baseline call only: zero discovery polls past the deadline — the
    # window is strictly bounded, no spin
    assert page.recent_convs_calls == 1


def _events(path: Path) -> list[dict]:
    sys.path.insert(0, str(ROOT / "tools"))
    from dola_010e_dispatch_journal import DispatchJournal
    return DispatchJournal(path, "").events


# --------------------------------------------------------- classifier --

def test_classifier_priority_and_guards():
    transient = [_row(TRANSIENT_TEXT)]
    assert runner.classify_recent_failure(transient) == \
        "TRANSIENT_GENERATION_FAILURE_NO_CREDIT"
    # the overlap case: same text ALSO hits a refusal marker, transient
    # must win because it is the more specific, evidenced outcome
    assert any(m in TRANSIENT_TEXT for m in runner.REFUSAL_MARKERS)
    assert runner.classify_recent_failure([_row(REFUSAL_ONLY_TEXT)]) == \
        "POLICY_REFUSAL"
    # success / ambiguous
    assert runner.classify_recent_failure(
        [_row("動画が生成されました。")]) is None
    assert runner.classify_recent_failure([_row("processing…")]) is None
    assert runner.classify_recent_failure([]) is None
    # a creation makes failure text non-decisive
    assert runner.classify_recent_failure([_row(
        TRANSIENT_TEXT, [{"id": "c9", "type": 2}])]) is None
    # only the 4 most recent rows are decisive (stale failure text in
    # older history must not stop a live run)
    stale = [_row("old " + NEEDLE)] * 4 + [_row(TRANSIENT_TEXT)]
    assert runner.classify_recent_failure(stale) is None


# ------------------------------------------------ recovery mirror ----

def test_recovery_scan_mirrors_transient_classification(tmp_path):
    import v2_021_recover as recover
    rows = [_row(TRANSIENT_TEXT)]
    assert recover._transient_failure(rows) is True
    # documented overlap: the transient text also trips the generic
    # refusal marker — scan reports BOTH keys and the reconciliation
    # reader prefers transient_failure
    assert recover._refusal(rows) is True
    assert recover._transient_failure([_row("動画が生成されました。")]) is False


def test_recovery_imports_and_fails_closed_without_compilation(
        tmp_path, monkeypatch):
    import v2_021_recover as recover
    monkeypatch.delenv("RECOVER_COMPILATION", raising=False)
    monkeypatch.setattr(recover, "COMP", None)
    monkeypatch.setattr(recover, "PKG", tmp_path / "missing_pkg")
    try:
        recover._require_comp()
        raise AssertionError("must fail closed")
    except RuntimeError as error:
        assert "RECOVER_COMPILATION" in str(error)

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({
        "shot_graph": {"nodes": [{"shot_id": "S01"}]},
        "prompt_plans": {"S01": {"sections": {"motion": "m" * 200}}}}),
        encoding="utf-8")
    monkeypatch.setenv("RECOVER_COMPILATION", str(fixture))
    monkeypatch.setattr(recover, "COMP", None)
    assert recover._shot_ids() == ["S01"]
    assert recover.needle_for("S01") == "m" * 80


# ------------------------------------- PROVE P1: recovery preflight order

def _wire_fake_open(monkeypatch, recover):
    """Fake async _open that records every session-open attempt; the
    assertion inside guarantees any open without a valid plan fails
    the test even if scan tried to continue."""
    opens = []

    async def fake_open(alias):
        opens.append(alias)
        raise AssertionError(
            f"session opened for {alias} before plan validation")

    monkeypatch.setattr(recover, "_open", fake_open)
    emitted = []
    monkeypatch.setattr(recover, "emit",
                        lambda payload: emitted.append(payload))
    return opens, emitted


def test_recovery_scan_never_opens_session_without_valid_plan(
        tmp_path, monkeypatch):
    import v2_021_recover as recover
    opens, emitted = _wire_fake_open(monkeypatch, recover)

    # missing compilation file
    monkeypatch.delenv("RECOVER_COMPILATION", raising=False)
    monkeypatch.setattr(recover, "COMP", None)
    monkeypatch.setattr(recover, "PKG", tmp_path / "missing_pkg")
    assert asyncio.run(recover.scan(["DUMMY_ACCOUNT"])) == 1
    assert opens == []

    # malformed JSON
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    monkeypatch.setenv("RECOVER_COMPILATION", str(bad))
    monkeypatch.setattr(recover, "COMP", None)
    assert asyncio.run(recover.scan(["DUMMY_ACCOUNT"])) == 1
    assert opens == []

    # structurally invalid: nodes not a list
    wrong_shape = tmp_path / "wrong_shape.json"
    wrong_shape.write_text(json.dumps({
        "shot_graph": {"nodes": "nope"},
        "prompt_plans": {}}), encoding="utf-8")
    monkeypatch.setenv("RECOVER_COMPILATION", str(wrong_shape))
    monkeypatch.setattr(recover, "COMP", None)
    assert asyncio.run(recover.scan(["DUMMY_ACCOUNT"])) == 1
    assert opens == []

    # plan present but a shot has no motion needle
    no_needle = tmp_path / "no_needle.json"
    no_needle.write_text(json.dumps({
        "shot_graph": {"nodes": [{"shot_id": "S01"}]},
        "prompt_plans": {"S01": {"sections": {"motion": ""}}}}),
        encoding="utf-8")
    monkeypatch.setenv("RECOVER_COMPILATION", str(no_needle))
    monkeypatch.setattr(recover, "COMP", None)
    assert asyncio.run(recover.scan(["DUMMY_ACCOUNT"])) == 1
    assert opens == []
    assert emitted[-1]["status"] == "RECOVERY_PREFLIGHT_FAILED"
    assert emitted[-1]["sessions_opened"] == 0
    assert "motion" in emitted[-1]["error"]


def test_recovery_scan_opens_sessions_only_after_valid_preflight(
        tmp_path, monkeypatch):
    import v2_021_recover as recover
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({
        "shot_graph": {"nodes": [{"shot_id": "S01"}]},
        "prompt_plans": {"S01": {"sections": {"motion": "m" * 200}}}}),
        encoding="utf-8")
    monkeypatch.setenv("RECOVER_COMPILATION", str(fixture))
    monkeypatch.setattr(recover, "COMP", None)
    out_pkg = tmp_path / "out_pkg"
    out_pkg.mkdir()
    monkeypatch.setattr(recover, "PKG", out_pkg)
    opens = []

    class _Page:
        async def evaluate(self, js, arg=None):
            return []  # no recent conversations

    class _Manager:
        async def close(self):
            pass

    async def fake_open(alias):
        opens.append(alias)
        return _Manager(), _Page()

    monkeypatch.setattr(recover, "_open", fake_open)
    emitted = []
    monkeypatch.setattr(recover, "emit",
                        lambda payload: emitted.append(payload))

    assert asyncio.run(recover.scan(["ACCOUNT_X"])) == 0
    assert opens == ["ACCOUNT_X"]  # opened exactly once, AFTER preflight
    report = json.loads((out_pkg / "V2_021_RECOVERY_SCAN.json")
                        .read_text(encoding="utf-8"))
    assert report["accounts"]["ACCOUNT_X"]["recent_conversations"] == 0
