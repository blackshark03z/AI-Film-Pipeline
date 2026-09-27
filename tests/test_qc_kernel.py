import asyncio
import json
from pathlib import Path

import pytest

from film_pipeline.live_runtime import Asset
from film_pipeline.qc import (QCStore, derive_disposition, derive_report, evidence,
                              human_decision)
from film_pipeline.store import SQLiteStore


def sample_asset():
    return Asset(asset_id="asset_qc_fixture", uri_or_path="fixture.mp4", sha256="a" * 64,
                 file_size=100, source_attempt_id="attempt_qc_fixture",
                 provider_job_id="job_qc_fixture")


def evidence_set(asset, *, technical_pass=True, vlm=False):
    rows = []
    for criterion in ("file_nonempty", "asset_sha256", "valid_video_stream",
                      "stored_metadata", "duration_target", "full_video_decode"):
        fails = criterion == "asset_sha256" and not technical_pass
        rows.append(evidence(asset=asset, evaluator_type="ffprobe", evaluator_version="fixture-v1",
                             gate="technical", criterion=criterion, observation="fixture checked",
                             verdict="fail" if fails else "pass",
                             failure_code="TECHNICAL_HASH_MISMATCH" if fails else None))
    for gate in ("visual", "continuity", "editorial"):
        rows.append(evidence(asset=asset, evaluator_type="ffmpeg", evaluator_version="fixture-v1",
                             gate=gate, criterion=gate + "_review", observation="review packet",
                             verdict="uncertain"))
    if vlm:
        rows.append(evidence(asset=asset, evaluator_type="vlm", evaluator_version="fixture-model",
                             gate="visual", criterion="visual_model", observation="looks beautiful",
                             verdict="pass", confidence=0.99))
    return rows


def test_pending_report_is_stable_and_never_selects():
    asset = sample_asset()
    rows = evidence_set(asset, vlm=True)
    first = derive_report(asset, rows)
    second = derive_report(asset, list(reversed(rows)))
    assert first == second
    assert first.report["decision"] == "needs_human_review"
    assert all(not first.report[g]["pass"] for g in ("visual", "continuity", "editorial"))
    assert derive_disposition("SHOT", asset, first, None) is None


def test_human_approval_finalizes_exact_asset_take():
    asset = sample_asset()
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                              visual_pass=True, continuity_pass=True, editorial_pass=True)
    report = derive_report(asset, evidence_set(asset), decision)
    take = derive_disposition("SHOT", asset, report, decision)
    assert report.report["decision"] == "pass"
    assert take.asset_id == asset.asset_id
    assert take.selection_authority == "human"
    assert take.qc_report_id == report.report["qc_report_id"]


def test_human_rejection_makes_repair_without_transport_retry():
    asset = sample_asset()
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="REJECT",
                              visual_pass=True, continuity_pass=False, editorial_pass=True,
                              failure_codes=["CONTINUITY_GEOGRAPHY_DRIFT"],
                              failure_observations={"CONTINUITY_GEOGRAPHY_DRIFT":
                                                    "At 4s the alley layout changes relative to the opening."})
    report = derive_report(asset, evidence_set(asset), decision)
    repair = derive_disposition("SHOT", asset, report, decision)
    assert report.report["decision"] == "fail"
    assert not report.report["continuity"]["pass"]
    assert repair["strategy"] == "prompt_recompile"
    assert repair["requires_human_approval"] is True


def test_hard_technical_failure_overrides_beauty_and_approval():
    asset = sample_asset()
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                              visual_pass=True, continuity_pass=True, editorial_pass=True)
    report = derive_report(asset, evidence_set(asset, technical_pass=False, vlm=True), decision)
    repair = derive_disposition("SHOT", asset, report, decision)
    assert report.report["decision"] == "fail"
    assert repair["strategy"] == "human_review"
    assert "TECHNICAL_HASH_MISMATCH" in repair["failure_codes"]


def test_vlm_uncertainty_does_not_become_pass():
    asset = sample_asset()
    rows = evidence_set(asset)
    rows.append(evidence(asset=asset, evaluator_type="vlm", evaluator_version="fixture-model",
                         gate="continuity", criterion="people_absence", observation="cannot tell",
                         verdict="uncertain", confidence=0.9))
    report = derive_report(asset, rows)
    assert report.report["decision"] == "needs_human_review"


def test_missing_technical_check_blocks_selection():
    asset = sample_asset()
    rows = [e for e in evidence_set(asset) if e.criterion != "full_video_decode"]
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                              visual_pass=True, continuity_pass=True, editorial_pass=True)
    report = derive_report(asset, rows, decision)
    assert report.report["decision"] == "fail"
    assert "TECHNICAL_CHECK_MISSING:full_video_decode" in report.report["failure_codes"]


def test_invalid_human_approval_or_unsupported_rejection_fails_closed():
    asset = sample_asset()
    with pytest.raises(ValueError):
        human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                       visual_pass=True, continuity_pass=None, editorial_pass=True)
    with pytest.raises(ValueError):
        human_decision(asset=asset, reviewer_id="owner_fixture", action="REJECT",
                       visual_pass=False, continuity_pass=True, editorial_pass=True)
    with pytest.raises(ValueError, match="concrete human observation"):
        human_decision(asset=asset, reviewer_id="owner_fixture", action="REJECT",
                       visual_pass=False, continuity_pass=True, editorial_pass=True,
                       failure_codes=["VISUAL_TEMPORAL_FLICKER"])


def test_sqlite_qc_persistence_fresh_readback_and_immutable_collision(tmp_path):
    from test_live_runtime import FakeTransport, make_executor

    transport = FakeTransport()
    executor, runtime, attempt, job = make_executor(tmp_path, transport)
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    asset = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))[0]
    rows = evidence_set(asset)
    qc = QCStore(runtime)
    pending, disposition = qc.save(asset, rows)
    assert disposition is None
    fresh, fresh_disposition = QCStore(SQLiteStore(runtime.path)).read(asset, pending.report["qc_report_id"])
    assert fresh == pending and fresh_disposition is None
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                              visual_pass=True, continuity_pass=True, editorial_pass=True)
    passed, take = qc.save(asset, rows, decision)
    assert QCStore(SQLiteStore(runtime.path)).read(asset, passed.report["qc_report_id"]) == (passed, take)
    c = runtime._connect()
    try:
        c.execute("UPDATE qc_evidence SET payload=? WHERE id=?", ('{}', rows[0].evidence_id))
        c.commit()
    finally:
        c.close()
    with pytest.raises((ValueError, KeyError)):
        QCStore(SQLiteStore(runtime.path)).read(asset, passed.report["qc_report_id"])


def test_gemini_advisory_fake_transport_is_structured_and_never_authoritative(tmp_path, monkeypatch):
    from film_pipeline.qc_media import (VISUAL_CRITERIA, CONTINUITY_CRITERIA,
                                         EDITORIAL_CRITERIA, gemini_advisory)

    key_file = tmp_path / "keys.txt"
    key_file.write_text("fake-test-key-long-enough-for-parsing", encoding="utf-8")
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake image bytes")
    frames = [{"time_s": i * 2, "path": str(frame), "sha256": "b" * 64} for i in range(5)]
    criteria = [name for group in (VISUAL_CRITERIA, CONTINUITY_CRITERIA,
                                    EDITORIAL_CRITERIA) for name, _ in group]
    findings = [{"criterion": name, "verdict": "uncertain", "confidence": 0.51,
                 "observation": "sample cannot establish whole-video fact", "time_ranges": []}
                for name in criteria]
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/models?pageSize=1000"):
            return Response({"models": [{"name": "models/fixture-model",
                                         "supportedGenerationMethods": ["generateContent"]}]})
        payload = json.loads(request.data)
        assert len(payload["contents"][0]["parts"]) == 11
        return Response({"candidates": [{"content": {"parts": [{"text": json.dumps({"findings": findings})}]}}],
                         "usageMetadata": {"totalTokenCount": 123}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    asset = sample_asset()
    rows, metadata = gemini_advisory(asset, frames, key_file=key_file, model="fixture-model")
    assert len(rows) == len(criteria)
    assert all(e.evaluator_type == "vlm" and e.verdict == "uncertain" for e in rows)
    assert metadata["usage"] == {"totalTokenCount": 123}
    assert derive_report(asset, evidence_set(asset) + rows).report["decision"] == "needs_human_review"
    assert all("fake-test-key" not in canonical for canonical in
               [json.dumps(e.payload()) for e in rows])


def test_runner_real_media_technical_failure_persists_repair_without_visual_claim(tmp_path):
    from test_live_runtime import FakeTransport, make_executor
    from film_pipeline.qc_runner import run_qc

    executor, runtime, attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    asset = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))[0]
    result = run_qc(runtime.path, attempt.generation_attempt_id, job.provider_job_id,
                    asset.asset_id, tmp_path / "review")
    assert result["decision"] == "fail"
    assert result["disposition"] == "REPAIR_DECISION"
    assert "TECHNICAL_DURATION_MISMATCH" in result["gates"]["technical"]["issues"]
    assert result["fresh_readback"] is True
    assert "Contact sheet unavailable" in Path(result["packet"]).read_text(encoding="utf-8")


def test_changed_asset_before_human_approval_cannot_commit_selected_take(tmp_path):
    from test_live_runtime import FakeTransport, make_executor

    executor, runtime, _attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    asset = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))[0]
    qc = QCStore(runtime)
    rows = evidence_set(asset)
    qc.save(asset, rows)
    Path(asset.uri_or_path).write_bytes(Path(asset.uri_or_path).read_bytes() + b"changed")
    decision = human_decision(asset=asset, reviewer_id="owner_fixture", action="APPROVE",
                              visual_pass=True, continuity_pass=True, editorial_pass=True)
    with pytest.raises(ValueError, match="exact Asset bytes"):
        qc.save(asset, rows, decision)
    c = runtime._connect()
    try:
        assert c.execute("SELECT COUNT(*) FROM selected_takes").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM qc_reports WHERE human_decision_id IS NOT NULL").fetchone()[0] == 0
    finally:
        c.close()


def test_missing_review_frame_invalidates_fresh_readback(tmp_path):
    from test_live_runtime import FakeTransport, make_executor
    from film_pipeline.live_runtime import file_sha256

    executor, runtime, _attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    asset = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))[0]
    frame = tmp_path / "review.jpg"
    frame.write_bytes(b"fixture frame")
    rows = evidence_set(asset)
    rows.append(evidence(asset=asset, evaluator_type="ffmpeg", evaluator_version="fixture-v1",
                         gate="visual", criterion="preview_frame", observation="review this frame",
                         verdict="uncertain", source_artifacts=[{"path": str(frame),
                                                                  "sha256": file_sha256(frame)}]))
    qc = QCStore(runtime)
    pending, _ = qc.save(asset, rows)
    frame.write_bytes(b"changed frame")
    with pytest.raises(ValueError, match="artifact changed"):
        QCStore(SQLiteStore(runtime.path)).read(asset, pending.report["qc_report_id"])
