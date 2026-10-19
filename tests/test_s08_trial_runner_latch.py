"""Focused deterministic offline unit tests for S08 trial runner latching.

Covers R3 requirements:
(1) Pre-release error -> knowledge=RESOLVED_NO_EFFECT, mutations_used=0
(2) Post-release generic refusal -> knowledge=RESOLVED_EFFECT_IDENTIFIED, authority=LATCHED_CLOSED, retry refused
(3) Receipt miss/timeout post-release -> knowledge=RESOLVED_EFFECT_IDENTIFIED, authority=LATCHED_CLOSED, retry refused
(4) Cancellation post-release -> knowledge=RESOLVED_EFFECT_IDENTIFIED, authority=LATCHED_CLOSED, retry refused
(5) Ambiguous release (armed but unverified) -> knowledge=UNKNOWN, authority=LATCHED_CLOSED, retry refused
(6) Success -> knowledge=RESOLVED_EFFECT_IDENTIFIED, authority=LATCHED_CLOSED, retry refused
(7) Original evidence directory preserved unmodified
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from mutation_authority import (
    AUTHORITY_LATCHED_CLOSED,
    AUTHORITY_OPEN,
    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
    KNOWLEDGE_RESOLVED_NO_EFFECT,
    KNOWLEDGE_UNKNOWN,
    MutationAuthority,
)
import run_s08_unknown_quota_trial as trial_mod


@pytest.fixture
def test_dirs(tmp_path):
    isolated = tmp_path / "isolated"
    review = tmp_path / "review"
    isolated.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)
    return isolated, review


def test_pre_release_error(test_dirs):
    """(1) Pre-release error: fails before any video submission is armed/released."""
    isolated, review = test_dirs
    scope = "TEST_SCOPE_PRE_RELEASE"

    async def mock_dispatch(**kwargs):
        raise RuntimeError("Browser failed to launch pre-dispatch")

    code = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code == 2
    state = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED_PRE_RELEASE_ERROR"
    assert state["mutations_used"] == 0

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_NO_EFFECT
    assert auth.authority == AUTHORITY_OPEN


def test_post_release_generic_refusal(test_dirs):
    """(2) Post-release generic refusal: provider returned transient failure (0 credit charged).
    Must record RESOLVED_EFFECT_IDENTIFIED (not RESOLVED_NO_EFFECT), latch closed, and refuse retry.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_REFUSAL"
    call_count = 0

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_test_refusal",
            "conversation_id": "conv_test_refusal",
        })
        raise RuntimeError("STOPPED_PROVIDER_POLICY_REFUSAL: 動画を生成できません。今回の生成でクレジットは使用されませんでした。")

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT"
    assert state1["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    # RETRY PROOF: Second attempt in same scope must be rejected immediately at gate
    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1  # dispatch_fn was NOT called again

    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2["status"] == "STOPPED_PROVIDER_GENERATION_FAILED_NO_CREDIT"
    assert state2 == state1


def test_receipt_miss_timeout(test_dirs):
    """(3) Receipt miss / timeout post-release: provider released, receipt never captured."""
    isolated, review = test_dirs
    scope = "TEST_SCOPE_RECEIPT_MISS"
    call_count = 0

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_receipt_miss",
            "conversation_id": None,
        })
        raise RuntimeError("OWNER_AMBIGUITY_GATE:receipt not captured")

    code = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code == 2
    assert call_count == 1

    state = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED_RECEIPT_MISS"
    assert state["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED


def test_cancellation_post_release(test_dirs):
    """(4) Cancellation post-release: asyncio.CancelledError during acquisition."""
    isolated, review = test_dirs
    scope = "TEST_SCOPE_CANCELLED"
    call_count = 0

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_cancelled",
            "conversation_id": "conv_cancelled",
        })
        raise asyncio.CancelledError("Simulated job cancellation")

    code = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code == 2
    assert call_count == 1

    state = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED_CANCELLED_POST_RELEASE"
    assert state["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED


def test_ambiguous_release_armed(test_dirs):
    """(5) Possible release ambiguous: DISPATCH_ARMED written to journal, but unverified."""
    isolated, review = test_dirs
    scope = "TEST_SCOPE_AMBIGUOUS"
    call_count = 0

    journal_path = isolated / "dispatch_journal_S08.jsonl"

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        # Write DISPATCH_ARMED event to simulate browser crashing during POST
        journal_path.write_text(
            json.dumps({"kind": "MUTATION_RESERVED"}) + "\n" +
            json.dumps({"kind": "DISPATCH_ARMED"}) + "\n",
            encoding="utf-8"
        )
        raise RuntimeError("Browser process terminated during submit POST")

    code = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code == 2
    assert call_count == 1

    state = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED_AMBIGUOUS_RELEASE"

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_UNKNOWN
    assert auth.authority == AUTHORITY_LATCHED_CLOSED


def test_success_path_latches_one_shot(test_dirs, monkeypatch):
    """(6) Success: acquisition completes, review prepared, authority latches against retry."""
    isolated, review = test_dirs
    scope = "TEST_SCOPE_SUCCESS"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_success",
            "conversation_id": "conv_success",
        })
        kwargs["on_creation"]({
            "creation_ids": ["c_12345"],
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    monkeypatch.setattr(trial_mod, "extract_frames", lambda mp4, out: 120)
    monkeypatch.setattr(trial_mod, "technical_qc", lambda mp4, fdir: {"decode_ok": True, "fps": 24.0})
    monkeypatch.setattr(trial_mod, "generate_contact_sheet", lambda fdir, out: None)
    monkeypatch.setattr(trial_mod, "generate_s01_s08_preview", lambda s08, out: True)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 0
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "REVIEW_READY"
    assert state1["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    manifest = json.loads((review / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["shot_id"] == "S08"
    assert manifest["asset_sha256"] == hashlib.sha256(b"dummy mp4 video bytes").hexdigest()

    # Retry in same scope must be refused:
    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1
    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2["status"] == "REVIEW_READY"
    assert state2 == state1


def test_original_evidence_unmodified():
    """(7) Assert that the real historical isolated_s08_single_trial_001 evidence is intact."""
    evidence_dir = ROOT / "isolated_s08_single_trial_001"
    if not evidence_dir.exists():
        pytest.skip("isolated_s08_single_trial_001 not present")

    state_path = evidence_dir / "s08_trial_state.json"
    evidence_path = evidence_dir / "S08_TRIAL_EVIDENCE.json"
    journal_path = evidence_dir / "dispatch_journal_S08.jsonl"
    auth_path = evidence_dir / "slots" / "S08" / "mutation_authority.json"

    assert state_path.exists()
    assert evidence_path.exists()
    assert journal_path.exists()
    assert auth_path.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["shot_id"] == "S08"
    assert state["account"] == "ACCOUNT_A"

    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    assert auth["mutation_authority"] == "LATCHED_CLOSED"


def test_post_acquisition_frame_extraction_failure_latches_closed(test_dirs, monkeypatch):
    """(8) Post-acquisition frame extraction failure: Tech Lead reproduced defect.
    Provider release succeeds and returns valid asset metadata, then extract_frames() raises exception.
    MUST latch closed, record RESOLVED_EFFECT_IDENTIFIED, and strictly reject retry in same scope.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_POST_ACQ_FRAME_FAIL"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_post_acq_fail",
            "conversation_id": "conv_post_acq_fail",
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    def failing_extract_frames(mp4, out_dir):
        raise RuntimeError("INDEPENDENT_OFFLINE_POST_ACQUISITION_QC_FAILURE")

    monkeypatch.setattr(trial_mod, "extract_frames", failing_extract_frames)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_POST_ACQUISITION_QC_ERROR"
    assert state1["mutations_used"] == 1
    assert "INDEPENDENT_OFFLINE_POST_ACQUISITION_QC_FAILURE" in state1["error"]

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    # RETRY PROOF: Second attempt in same scope MUST be rejected immediately without calling dispatch_fn
    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1  # Dispatch count remains exactly 1!

    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2["status"] == "STOPPED_POST_ACQUISITION_QC_ERROR"
    assert state2 == state1


def test_post_acquisition_technical_qc_failure_latches_closed(test_dirs, monkeypatch):
    """(9) Post-acquisition technical QC failure: extract_frames succeeds but technical_qc fails.
    MUST latch closed, record RESOLVED_EFFECT_IDENTIFIED, and reject retry in same scope.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_POST_ACQ_TECH_QC_FAIL"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_tech_qc_fail",
            "conversation_id": "conv_tech_qc_fail",
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    monkeypatch.setattr(trial_mod, "extract_frames", lambda mp4, out: 120)

    def failing_technical_qc(mp4, fdir):
        raise RuntimeError("FFPROBE_QC_FAILURE: Corrupted video stream")

    monkeypatch.setattr(trial_mod, "technical_qc", failing_technical_qc)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_POST_ACQUISITION_QC_ERROR"
    assert state1["mutations_used"] == 1
    assert "FFPROBE_QC_FAILURE" in state1["error"]

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1
    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2 == state1


def test_post_acquisition_preview_manifest_failure_latches_closed(test_dirs, monkeypatch):
    """(10) Post-acquisition review/preview/manifest failure: error during review packaging.
    MUST latch closed, record RESOLVED_EFFECT_IDENTIFIED, and reject retry in same scope.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_POST_ACQ_REVIEW_FAIL"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_review_fail",
            "conversation_id": "conv_review_fail",
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    monkeypatch.setattr(trial_mod, "extract_frames", lambda mp4, out: 120)
    monkeypatch.setattr(trial_mod, "technical_qc", lambda mp4, fdir: {"decode_ok": True, "fps": 24.0})

    def failing_contact_sheet(fdir, out):
        raise OSError("Disk full writing contact sheet")

    monkeypatch.setattr(trial_mod, "generate_contact_sheet", failing_contact_sheet)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_POST_RELEASE_ERROR"
    assert state1["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1
    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2 == state1


def test_post_acquisition_cancellation_latches_closed(test_dirs, monkeypatch):
    """(11) Post-acquisition cancellation: task cancelled after video is acquired.
    MUST latch closed, record RESOLVED_EFFECT_IDENTIFIED, and reject retry in same scope.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_POST_ACQ_CANCEL"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_cancel_post_acq",
            "conversation_id": "conv_cancel_post_acq",
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    def cancelled_extract_frames(mp4, out_dir):
        raise asyncio.CancelledError("Async task cancelled during frame extraction")

    monkeypatch.setattr(trial_mod, "extract_frames", cancelled_extract_frames)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_CANCELLED_POST_RELEASE"
    assert state1["mutations_used"] == 1

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1
    state2 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state2 == state1


def test_attempted_replay_preserves_state_json_sha256(test_dirs, monkeypatch):
    """(12) Evidence integrity: rerun on an already latched scope preserves
    original s08_trial_state.json SHA256 bit-for-bit without overwriting.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_PRESERVE_SHA"
    call_count = 0

    dummy_mp4 = isolated / "dummy_S08.mp4"
    dummy_mp4.write_bytes(b"dummy mp4 video bytes")

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        kwargs["on_release"]({
            "attempt_id": "attempt_preserve_sha",
            "conversation_id": "conv_preserve_sha",
        })
        return {
            "asset_path": str(dummy_mp4),
            "asset_sha256": hashlib.sha256(b"dummy mp4 video bytes").hexdigest(),
            "size": len(b"dummy mp4 video bytes"),
            "variant_authority": "TEST_SEEDANCE_2_0",
        }

    monkeypatch.setattr(trial_mod, "extract_frames", lambda mp4, out: 120)
    monkeypatch.setattr(trial_mod, "technical_qc", lambda mp4, fdir: {"decode_ok": True, "fps": 24.0})
    monkeypatch.setattr(trial_mod, "generate_contact_sheet", lambda fdir, out: None)
    monkeypatch.setattr(trial_mod, "generate_s01_s08_preview", lambda s08, out: True)

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code1 == 0
    assert call_count == 1

    state_file = isolated / "s08_trial_state.json"
    sha_before = hashlib.sha256(state_file.read_bytes()).hexdigest()

    # Attempt replay
    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1  # dispatch_fn NOT invoked

    sha_after = hashlib.sha256(state_file.read_bytes()).hexdigest()
    assert sha_before == sha_after, "s08_trial_state.json must not be modified on rerun"


def test_malformed_journal_fails_closed(test_dirs):
    """(13) Malformed journal fails closed: unparseable/corrupted journal lines
    must NOT fail open to PRE_RELEASE. Must latch closed with UNKNOWN knowledge.
    """
    isolated, review = test_dirs
    scope = "TEST_SCOPE_MALFORMED_JOURNAL"
    call_count = 0

    journal_path = isolated / "dispatch_journal_S08.jsonl"
    journal_path.write_text(
        '{"kind": "MUTATION_RESERVED"}\n'
        '{"corrupted_json_line: INVALID_SYNTAX\n',
        encoding="utf-8"
    )

    async def mock_dispatch(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Network drop during POST")

    code1 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))

    assert code1 == 2
    assert call_count == 1

    state1 = json.loads((isolated / "s08_trial_state.json").read_text(encoding="utf-8"))
    assert state1["status"] == "STOPPED_AMBIGUOUS_RELEASE"

    auth = MutationAuthority(isolated / "slots" / "S08", scope)
    assert auth.knowledge == KNOWLEDGE_UNKNOWN
    assert auth.authority == AUTHORITY_LATCHED_CLOSED

    code2 = asyncio.run(trial_mod.run_trial(
        isolated_dir=isolated,
        review_dir=review,
        scope_id=scope,
        dispatch_fn=mock_dispatch,
    ))
    assert code2 == 1
    assert call_count == 1


def test_inspect_journal_states(tmp_path):
    """(14) Direct unit test of inspect_journal_release_state covering all states."""
    j = tmp_path / "test_journal.jsonl"

    # 1. Non-existent -> PRE_RELEASE
    assert trial_mod.inspect_journal_release_state(j) == "PRE_RELEASE"

    # 2. Empty file -> UNKNOWN_OR_ARMED
    j.write_text("", encoding="utf-8")
    assert trial_mod.inspect_journal_release_state(j) == "UNKNOWN_OR_ARMED"

    # 3. Only MUTATION_RESERVED -> PRE_RELEASE
    j.write_text(json.dumps({"kind": "MUTATION_RESERVED"}) + "\n", encoding="utf-8")
    assert trial_mod.inspect_journal_release_state(j) == "PRE_RELEASE"

    # 4. DISPATCH_ARMED -> ARMED
    j.write_text(
        json.dumps({"kind": "MUTATION_RESERVED"}) + "\n" +
        json.dumps({"kind": "DISPATCH_ARMED"}) + "\n",
        encoding="utf-8"
    )
    assert trial_mod.inspect_journal_release_state(j) == "ARMED"

    # 5. NETWORK_RELEASE_OBSERVED -> CONFIRMED_RELEASE
    j.write_text(
        json.dumps({"kind": "MUTATION_RESERVED"}) + "\n" +
        json.dumps({"kind": "DISPATCH_ARMED"}) + "\n" +
        json.dumps({"kind": "NETWORK_RELEASE_OBSERVED"}) + "\n",
        encoding="utf-8"
    )
    assert trial_mod.inspect_journal_release_state(j) == "CONFIRMED_RELEASE"

    # 6. MODEL_VERIFIED -> CONFIRMED_RELEASE
    j.write_text(json.dumps({"kind": "MODEL_VERIFIED"}) + "\n", encoding="utf-8")
    assert trial_mod.inspect_journal_release_state(j) == "CONFIRMED_RELEASE"

    # 7. SSE_RECEIPT_CAPTURED -> CONFIRMED_RELEASE
    j.write_text(json.dumps({"kind": "SSE_RECEIPT_CAPTURED"}) + "\n", encoding="utf-8")
    assert trial_mod.inspect_journal_release_state(j) == "CONFIRMED_RELEASE"

    # 8. Malformed / corrupted line -> UNKNOWN_OR_ARMED
    j.write_text('{"bad_json: 123\n', encoding="utf-8")
    assert trial_mod.inspect_journal_release_state(j) == "UNKNOWN_OR_ARMED"
