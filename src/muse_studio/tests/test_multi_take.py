"""Parallel multi-take: K independent sends per shot per round, best passing take kept."""

import json
from pathlib import Path

from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.tests.test_lane_review_r2 import _make_accounts, _sent_shots, _video_client_factory
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project


def _engine(tmp_path, scores):
    """`scores(batch_id, shot_id)` -> quality_score (None = QC reject)."""
    mgr, _ = _make_accounts(tmp_path, 3)
    seed = tmp_path / "seed.mp4"
    seed.write_bytes(b"\x00" * 2048)
    calls = []

    def qc(clip_path, shot, **kw):
        batch = Path(clip_path).parent.parent.name
        score = scores(batch, shot["shot_id"])
        Path(kw["strip_output_path"]).write_bytes(b"strip")
        if score is None:
            return {"verdict": "FAIL", "defects": ["BLUR"], "metrics": {"quality_score": 0.0}}
        return {"verdict": "PASS", "defects": [], "metrics": {"quality_score": score}, "batch": batch}

    engine = ParallelPoolEngine(
        account_manager=mgr, client_factory=_video_client_factory(seed, calls, lambda n: None),
        qc_evaluator=qc, sync_ui=False,
    )
    return engine, calls


def test_takes_sends_each_shot_k_times_never_twice_in_one_batch(tmp_path: Path):
    engine, calls = _engine(tmp_path, lambda b, s: 50.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=4)
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=3)
    assert set(_sent_shots(calls).values()) == {3}
    for _, sids in calls:
        assert len(sids) == len(set(sids)), "a batch held the same shot twice"
    assert res["sends_by_shot"] == _sent_shots(calls)
    assert set(res["takes_by_shot"].values()) == {3}
    assert res["status"] == "COMPLETED"
    assert len({acc for acc, _ in calls}) > 1, "takes should spread across lane accounts"


def test_manifest_takes_field_overrides_flag(tmp_path: Path):
    engine, calls = _engine(tmp_path, lambda b, s: 50.0)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=3)
    manifest_path = proj / "shots_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["shots"][0]["takes"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    first = manifest["shots"][0]["shot_id"]
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=1)
    sent = _sent_shots(calls)
    assert sent[first] == 2 and all(n == 1 for sid, n in sent.items() if sid != first)
    assert res["takes_by_shot"][first] == 2


def test_best_passing_take_is_kept_and_reject_never_overwrites_pass(tmp_path: Path):
    # Take 2 scores best, take 3 is rejected: the canonical clip and QC record must be take 2.
    def scores(batch, sid):
        if batch.endswith("_T3"):
            return None
        return 80.0 if batch.endswith("_T2") else 40.0

    engine, _ = _engine(tmp_path, scores)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=3)
    assert res["status"] == "COMPLETED"
    audit = json.loads((proj / "qc_audit_report.json").read_text(encoding="utf-8"))
    for sid, rec in audit["per_shot_qc"].items():
        assert rec["verdict"] == "PASS" and rec["take"] == 2, (sid, rec)
        assert rec["metrics"]["quality_score"] == 80.0
        assert (proj / "qc_strips" / f"{sid}_strip.jpg").exists()


def test_all_takes_rejected_reports_qc_reject(tmp_path: Path):
    engine, calls = _engine(tmp_path, lambda b, s: None)
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=2)
    res = engine.run_videos(project_dir=proj, max_accounts=3, max_rounds=1, auto_repair=False, takes=2)
    assert set(_sent_shots(calls).values()) == {2}
    assert res["status"] == "INCOMPLETE"
    assert {f["reason"] for f in res["failed_shots"]} == {"QC_REJECT"}
