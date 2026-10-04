"""Narration/caption ingestion, content input bundle, semantic waiver,
final release compiler + Owner decision replay (Package-015 Phases 6-12).

All fixtures are synthetic and offline; canonical production state is
never touched — every simulation runs in tmp_path and the canonical
OWNER_TAKE_REVIEW_COMPLETE stays false.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from film_pipeline.content_release import (
    ContentReleaseInputBundle, FinalContentReleaseCompiler,
    NarrationSourceReceipt, SemanticQCWaiverDecision, TimedCaptionSource,
    parse_captions, verify_caption_source, verify_narration_receipt)
from film_pipeline.owner_review import (OwnerDecisionLedger,
                                        OwnerReviewRequest,
                                        build_decision_template,
                                        import_decision_set,
                                        make_owner_decision)

MASTER_SHA = "976876a1" * 8
STORY = {"story_authority_id": "story_swordsman_canonical",
         "story_authority_sha256": "b" * 64}


def make_receipt(tmp_path: Path, **overrides) -> NarrationSourceReceipt:
    wav = tmp_path / "narration.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(b"\x00\x00" * 24000)  # 0.5 s mono 48 kHz
    import hashlib
    fields = dict(
        project="swordsman_film", story_authority_id=STORY["story_authority_id"],
        story_authority_sha256=STORY["story_authority_sha256"],
        text_authority_id="narration_script_v1",
        text_authority_sha256="c" * 64, audio_locator="narration.wav",
        audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
        duration_s=0.5, sample_rate=48000, channels=1, mime_type="audio/x-wav",
        voice_provenance="human performer (session note)",
        production_provenance="Owner-produced 2026-10-04")
    fields.update(overrides)
    return NarrationSourceReceipt(**fields)


def test_narration_valid_receipt(tmp_path: Path):
    receipt = make_receipt(tmp_path)
    out = verify_narration_receipt(receipt, project="swordsman_film",
                                   story_authority=STORY,
                                   base_dir=tmp_path)
    assert out["verified"] is True
    assert out["probed"]["sample_rate"] == 48000


def test_narration_wrong_project_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path, project="other_film")
    with pytest.raises(ValueError, match="another project"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_wrong_story_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path)
    with pytest.raises(ValueError, match="story authority"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority={
                                     "story_authority_id": "other_story",
                                     "story_authority_sha256": "d" * 64})


def test_narration_missing_text_authority_refused(tmp_path: Path):
    with pytest.raises(Exception, match="text_authority_id"):
        make_receipt(tmp_path, text_authority_id="",
                     text_authority_sha256="e" * 64)


def test_narration_hash_drift_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path)
    receipt = receipt.model_copy(
        update={"audio_sha256": "f" * 64})
    with pytest.raises(ValueError, match="hash drift"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_source_mutation_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path)
    wav = tmp_path / receipt.audio_locator
    wav.write_bytes(wav.read_bytes() + b"mutated")
    with pytest.raises(ValueError, match="hash drift"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_duration_mismatch_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path, duration_s=9.5)
    with pytest.raises(ValueError, match="duration mismatch"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_sample_rate_mismatch_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path, sample_rate=44100)
    with pytest.raises(ValueError, match="sample rate"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_channel_mismatch_refused(tmp_path: Path):
    receipt = make_receipt(tmp_path, channels=2)
    with pytest.raises(ValueError, match="channel mismatch"):
        verify_narration_receipt(receipt, project="swordsman_film",
                                 story_authority=STORY,
                                 base_dir=tmp_path)


def test_narration_unsupported_audio_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="unsupported audio"):
        make_receipt(tmp_path, mime_type="video/mp4")


def test_narration_missing_provenance_refused():
    with pytest.raises(Exception):
        NarrationSourceReceipt(
            project="p", story_authority_id="s",
            story_authority_sha256="a" * 64, text_authority_id="t",
            text_authority_sha256="b" * 64, audio_locator="x.wav",
            audio_sha256="c" * 64, duration_s=1.0, sample_rate=48000,
            channels=1, mime_type="audio/x-wav",
            voice_provenance="", production_provenance="")


SRT = "1\n00:00:00,000 --> 00:00:02,000\nHello.\n\n" \
      "2\n00:00:03,000 --> 00:00:05,000\nWorld.\n"
VTT = "WEBVTT\n\n00:00.000 --> 00:02.000\nHello.\n\n" \
      "00:03.000 --> 00:05.000\nWorld.\n"


def make_caption(tmp_path: Path, raw: bytes, fmt: str = "srt",
                 **overrides) -> TimedCaptionSource:
    path = tmp_path / f"captions.{fmt}"
    path.write_bytes(raw)
    import hashlib
    fields = dict(project="swordsman_film",
                  story_authority_id=STORY["story_authority_id"],
                  transcript_authority_id="narration_script_v1",
                  format=fmt, caption_locator=f"captions.{fmt}",
                  caption_sha256=hashlib.sha256(raw).hexdigest(),
                  language="vi", lineage={"authored_by": "OWNER",
                                          "basis": "narration_script_v1"})
    fields.update(overrides)
    return TimedCaptionSource(**fields)


def test_caption_valid_srt(tmp_path: Path):
    source = make_caption(tmp_path, SRT.encode("utf-8"))
    out = verify_caption_source(source, project="swordsman_film",
                                story_authority=STORY,
                                master_duration_s=194.541667,
                                base_dir=tmp_path)
    assert out["cues"] == 2 and out["last_end_s"] == 5.0


def test_caption_valid_vtt(tmp_path: Path):
    source = make_caption(tmp_path, VTT.encode("utf-8"), fmt="vtt")
    out = verify_caption_source(source, project="swordsman_film",
                                story_authority=STORY,
                                master_duration_s=194.541667,
                                base_dir=tmp_path)
    assert out["cues"] == 2


def test_caption_negative_start_refused(tmp_path: Path):
    raw = "1\n00:00:00,500 --> 00:00:02,000\nx\n\n" \
          "2\n-00:00:01,000 --> 00:00:01,500\ny\n".encode("utf-8")
    source = make_caption(tmp_path, raw)
    with pytest.raises(ValueError, match="malformed"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_end_before_start_refused(tmp_path: Path):
    raw = "1\n00:00:02,000 --> 00:00:01,000\nx\n".encode("utf-8")
    source = make_caption(tmp_path, raw)
    with pytest.raises(ValueError, match="invalid cue window"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_beyond_master_refused(tmp_path: Path):
    raw = "1\n00:03:10,000 --> 00:03:20,000\nx\n".encode("utf-8")
    source = make_caption(tmp_path, raw)
    with pytest.raises(ValueError, match="beyond the canonical master"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_bad_encoding_refused(tmp_path: Path):
    source = make_caption(tmp_path, SRT.encode("utf-16"))
    with pytest.raises(ValueError, match="UTF-8"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_transcript_mismatch_refused(tmp_path: Path):
    source = make_caption(tmp_path, SRT.encode("utf-8"),
                          transcript_authority_id="other_transcript")
    with pytest.raises(Exception):
        verify_caption_source(source, project="swordsman_film",
                              story_authority={
                                  "story_authority_id": "story_swordsman_"
                                                        "canonical"},
                              master_duration_s=194.541667)


def test_caption_wrong_project_refused(tmp_path: Path):
    source = make_caption(tmp_path, SRT.encode("utf-8"), project="other")
    with pytest.raises(ValueError, match="another project"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_hash_drift_refused(tmp_path: Path):
    source = make_caption(tmp_path, SRT.encode("utf-8"))
    source = source.model_copy(update={"caption_sha256": "f" * 64})
    with pytest.raises(ValueError, match="hash drift"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_overlap_refused_not_fixed(tmp_path: Path):
    raw = ("1\n00:00:00,000 --> 00:00:04,000\nx\n\n"
           "2\n00:00:02,000 --> 00:00:05,000\ny\n").encode("utf-8")
    source = make_caption(tmp_path, raw)
    with pytest.raises(ValueError, match="overlapping cues refused"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_caption_empty_source_refused(tmp_path: Path):
    source = make_caption(tmp_path, "WEBVTT\n\n".encode("utf-8"),
                          fmt="vtt")
    with pytest.raises(ValueError, match="no cues|timing line"):
        verify_caption_source(source, project="swordsman_film",
                              story_authority=STORY,
                              master_duration_s=194.541667,
                              base_dir=tmp_path)


def test_bundle_binds_exact_master_and_zero_authority():
    bundle = ContentReleaseInputBundle(
        project="swordsman_film", master_sha256=MASTER_SHA,
        canonical_lineage_version="master-editorial-010-v1")
    assert bundle.digest()
    with pytest.raises(Exception, match="provider"):
        ContentReleaseInputBundle(
            project="swordsman_film", master_sha256=MASTER_SHA,
            canonical_lineage_version="master-editorial-010-v1",
            notes="generate on approval")
    with pytest.raises(Exception, match="different master"):
        FinalContentReleaseCompiler(
            project="swordsman_film",
            master_receipt={"output_sha256": "1" * 64,
                            "version": "master-editorial-010-v1",
                            "full_decode": True},
            manifest_truth={}, bundle=bundle)


def test_waiver_satisfies_gate_without_rewriting_truth():
    waiver = SemanticQCWaiverDecision(
        project="swordsman_film", master_sha256=MASTER_SHA,
        reason="Owner reviewed the reel and accepts current visual "
               "quality for this release",
        known_limitations=["worker semantic backend NOT_QUALIFIED; no "
                           "autonomous semantic QC on this release"],
        waived_at="2026-10-04T00:00:00+00:00", decision_source="OWNER")
    assert waiver.semantic_autonomous_ready_after_waiver is False
    assert waiver.semantic_qc_gate_effect == "OWNER_WAIVED"
    compiler = FinalContentReleaseCompiler(
        project="swordsman_film",
        master_receipt={"output_sha256": MASTER_SHA,
                        "version": "master-editorial-010-v1",
                        "full_decode": True},
        manifest_truth={},
        bundle=ContentReleaseInputBundle(
            project="swordsman_film", master_sha256=MASTER_SHA,
            canonical_lineage_version="master-editorial-010-v1"),
        semantic_waiver=waiver)
    report = compiler.gate_report()
    semantic = next(g for g in report["gates"]
                    if g["name"] == "SEMANTIC_RELEASE")
    assert semantic["blocking"] is False
    assert "OWNER_WAIVED" in semantic["current_truth"]
    assert waiver.semantic_autonomous_ready_after_waiver is False


def test_waiver_wrong_master_refused():
    waiver = SemanticQCWaiverDecision(
        project="swordsman_film", master_sha256="2" * 64,
        reason="x", known_limitations=["y"],
        waived_at="2026-10-04T00:00:00+00:00", decision_source="OWNER")
    compiler = FinalContentReleaseCompiler(
        project="swordsman_film",
        master_receipt={"output_sha256": MASTER_SHA,
                        "version": "master-editorial-010-v1",
                        "full_decode": True},
        manifest_truth={},
        bundle=ContentReleaseInputBundle(
            project="swordsman_film", master_sha256=MASTER_SHA,
            canonical_lineage_version="v"),
        semantic_waiver=waiver)
    with pytest.raises(ValueError, match="different master"):
        compiler.gate_report()


def compiler_fixture(tmp_path: Path, owner_state=None, waiver=None):
    return FinalContentReleaseCompiler(
        project="swordsman_film",
        master_receipt={"output_sha256": MASTER_SHA,
                        "version": "master-editorial-010-v1",
                        "full_decode": True},
        manifest_truth={"delivery": "delivery_014"},
        bundle=ContentReleaseInputBundle(
            project="swordsman_film", master_sha256=MASTER_SHA,
            canonical_lineage_version="master-editorial-010-v1"),
        owner_decision_state=owner_state, semantic_waiver=waiver)


def test_compiler_dry_run_canonical_state_all_remaining_gates():
    report = compiler_fixture(None).gate_report()
    assert report["release_state"] == "FINAL_CONTENT_RELEASE_BLOCKED"
    assert report["blocked_gates"] == ["OWNER_TAKE_REVIEW",
                                       "SEMANTIC_RELEASE",
                                       "PRODUCTION_NARRATION",
                                       "TIMED_CAPTIONS"]
    assert report["provider_generation_authority"] == "NONE"
    for gate in report["gates"]:
        assert {"name", "required", "current_truth", "blocking",
                "satisfying_artifact"} <= set(gate)


def test_compiler_release_builder_refuses_while_blocked():
    with pytest.raises(ValueError, match="FINAL_CONTENT_RELEASE_BLOCKED"):
        compiler_fixture(None).compile_release()


# -- Phase 6: Owner decision replay / simulation (offline, synthetic) --

def simulate(tmp_path: Path, decisions: dict) -> dict:
    request = OwnerReviewRequest(
        review_request_id="OWNER-REV-015-001", project="swordsman_film",
        scope="SHOT", canonical_shot_id="SEQ7_E2",
        shot_spec_identity={"shot_id": "SEQ7_E2C", "spec_version": 1,
                            "shot_spec_sha256": "c" * 64},
        selected_take="take_" + "b" * 64, asset_sha256="a" * 64,
        reason_review_required="Owner take review",
        created_at="2026-10-04T00:00:00+00:00")
    template = build_decision_template([request],
                                       tmp_path / "template.json",
                                       "set" + "0" * 61)
    filled = {**template, "items": [{**template["items"][0],
                                     "decision": decisions["001"],
                                     "note": "simulated"}]}
    (tmp_path / "filled.json").write_text(json.dumps(filled),
                                          encoding="utf-8")
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    out = import_decision_set(tmp_path / "filled.json", [request], ledger,
                              "set" + "0" * 61)
    return {"resolved": ledger.resolved_state(),
            "imported": out["imported"], "ledger": ledger}


def test_simulation_all_accept(tmp_path: Path):
    out = simulate(tmp_path, {"001": "ACCEPT"})
    assert out["resolved"] == {"OWNER-REV-015-001": "ACCEPT"}
    assert out["ledger"].release_blockers() == []


def test_simulation_reject(tmp_path: Path):
    out = simulate(tmp_path, {"001": "REJECT"})
    assert out["ledger"].release_blockers() == ["OWNER-REV-015-001"]


def test_simulation_needs_repair(tmp_path: Path):
    out = simulate(tmp_path, {"001": "NEEDS_REPAIR"})
    assert out["ledger"].release_blockers() == ["OWNER-REV-015-001"]
    assert out["ledger"].provider_mutation_authority() == "NONE"


def test_simulation_defer(tmp_path: Path):
    out = simulate(tmp_path, {"001": "DEFER"})
    assert out["resolved"] == {"OWNER-REV-015-001": "DEFER"}
    assert out["ledger"].release_blockers() == ["OWNER-REV-015-001"]


def test_simulation_stale_binding_refused(tmp_path: Path):
    request = OwnerReviewRequest(
        review_request_id="OWNER-REV-015-001", project="swordsman_film",
        scope="SHOT", canonical_shot_id="SEQ7_E2",
        shot_spec_identity={"shot_id": "SEQ7_E2C", "spec_version": 1,
                            "shot_spec_sha256": "c" * 64},
        selected_take="take_" + "b" * 64, asset_sha256="a" * 64,
        reason_review_required="Owner take review",
        created_at="2026-10-04T00:00:00+00:00")
    template = build_decision_template([request],
                                       tmp_path / "template.json",
                                       "set" + "0" * 61)
    stale = json.loads(json.dumps(template))
    stale["items"][0]["reviewed_bindings"]["asset_sha256"] = "9" * 64
    stale["items"][0]["decision"] = "ACCEPT"
    (tmp_path / "stale.json").write_text(json.dumps(stale),
                                         encoding="utf-8")
    with pytest.raises(ValueError, match="stale asset"):
        import_decision_set(tmp_path / "stale.json", [request],
                            OwnerDecisionLedger(tmp_path / "l.json",
                                                [request]),
                            "set" + "0" * 61)


def test_simulation_conflicting_decisions_require_supersession(
        tmp_path: Path):
    request = OwnerReviewRequest(
        review_request_id="OWNER-REV-015-001", project="swordsman_film",
        scope="SHOT", canonical_shot_id="SEQ7_E2",
        shot_spec_identity={"shot_id": "SEQ7_E2C", "spec_version": 1,
                            "shot_spec_sha256": "c" * 64},
        selected_take="take_" + "b" * 64, asset_sha256="a" * 64,
        reason_review_required="Owner take review",
        created_at="2026-10-04T00:00:00+00:00")
    ledger = OwnerDecisionLedger(tmp_path / "ledger.json", [request])
    first = make_owner_decision(request=request, decision="ACCEPT")
    ledger.record(first)
    second = make_owner_decision(request=request, decision="REJECT")
    with pytest.raises(ValueError, match="supersession"):
        ledger.record(second)
    ledger.supersede(superseded_decision_id=first.decision_id,
                     new_decision=second, reason="simulated change")
    assert ledger.resolved_state() == {"OWNER-REV-015-001": "REJECT"}


def test_simulation_never_touches_canonical_state(tmp_path: Path):
    """The replay writes only inside its sandbox; canonical production
    truth keeps OWNER_TAKE_REVIEW_COMPLETE = false."""
    simulate(tmp_path, {"001": "ACCEPT"})
    sandbox_files = sorted(p.name for p in tmp_path.iterdir())
    assert sandbox_files == ["filled.json", "ledger.json", "template.json"]
    readiness_014 = json.loads(
        (Path(__file__).resolve().parents[1] /
         "projects/flow_worker_semantic_backend_014/delivery_014/qc/"
         "release_readiness.json").read_text(encoding="utf-8"))
    assert readiness_014["OWNER_TAKE_REVIEW_COMPLETE"] is False


def test_all_gates_satisfied_synthetic_fixture(tmp_path: Path):
    """Synthetic complete inputs -> the compiler reaches READY in
    dry-run; canonical production state is untouched (fixtures only)."""
    receipt = make_receipt(tmp_path)
    narration = verify_narration_receipt(
        receipt, project="swordsman_film", story_authority=STORY,
        base_dir=tmp_path)
    source = make_caption(tmp_path, SRT.encode("utf-8"))
    captions = verify_caption_source(
        source, project="swordsman_film", story_authority=STORY,
        master_duration_s=194.541667, base_dir=tmp_path)
    waiver = SemanticQCWaiverDecision(
        project="swordsman_film", master_sha256=MASTER_SHA,
        reason="synthetic fixture", known_limitations=["synthetic"],
        waived_at="2026-10-04T00:00:00+00:00", decision_source="OWNER")
    compiler = FinalContentReleaseCompiler(
        project="swordsman_film",
        master_receipt={"output_sha256": MASTER_SHA,
                        "version": "master-editorial-010-v1",
                        "full_decode": True},
        manifest_truth={}, bundle=ContentReleaseInputBundle(
            project="swordsman_film", master_sha256=MASTER_SHA,
            canonical_lineage_version="master-editorial-010-v1"),
        owner_decision_state={"OWNER-REV-015-001": "ACCEPT"},
        narration_verification=narration,
        caption_verification=captions,
        semantic_waiver=waiver)
    report = compiler.gate_report()
    assert report["release_state"] == "FINAL_CONTENT_RELEASE_READY"
    assert report["blocked_gates"] == []
    with pytest.raises(NotImplementedError):
        compiler.compile_release()


def test_one_missing_gate_reported_exactly(tmp_path: Path):
    waiver = SemanticQCWaiverDecision(
        project="swordsman_film", master_sha256=MASTER_SHA,
        reason="x", known_limitations=["y"],
        waived_at="2026-10-04T00:00:00+00:00", decision_source="OWNER")
    report = compiler_fixture(None, waiver=waiver).gate_report()
    assert report["blocked_gates"] == ["OWNER_TAKE_REVIEW",
                                       "PRODUCTION_NARRATION",
                                       "TIMED_CAPTIONS"]
