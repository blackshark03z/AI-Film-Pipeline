from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from film_pipeline.e2e import (prepare, references_for_shot, resume, status,
                               validate_review_entry)
from film_pipeline.live_runtime import Asset, file_sha256
from film_pipeline.qc import QCStore
from film_pipeline.store import SQLiteStore


def test_finish_real_mux_readback_and_changed_source_are_not_false_success(tmp_path, monkeypatch):
    from film_pipeline import e2e
    from film_pipeline.editorial import EditClip
    from test_editorial_slice import approved_runtime
    runtime, asset, take = approved_runtime(tmp_path)
    audio, captions = tmp_path / 'audio.mp3', tmp_path / 'source.srt'
    media(audio)
    captions.write_text('1\n00:00:00,000 --> 00:00:01,000\nOriginal narration\n', encoding='utf-8')
    meta = {'project_id': 'offline_export_test', 'audio_path': audio.name,
        'srt_path': captions.name, 'audio_sha256': file_sha256(audio),
        'srt_sha256': file_sha256(captions), 'audio_start_s': 0,
        'film_duration_s': asset.duration_s}
    clip = EditClip(order=1, shot_id=take.shot_id, selected_take_id=take.selected_take_id,
        asset_id=asset.asset_id, target_duration_s=asset.duration_s)
    # Existing runtime/editorial fixtures prove selection custody; this test
    # isolates the new real FFmpeg mux, receipt and stale-file behavior.
    monkeypatch.setattr(e2e, '_selected_sources', lambda *args: (meta, {}, [clip]))
    result = e2e.finish(tmp_path, runtime.path, 'offline-project')
    master = tmp_path / result['master_path']
    assert file_sha256(master) == result['master_sha256']
    streams = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
        '-of', 'json', str(master)]))['streams']
    assert {s['codec_name'] for s in streams} == {'h264', 'aac', 'mov_text'}
    assert e2e.finish(tmp_path, runtime.path, 'offline-project') == result
    audio.write_bytes(audio.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='source bytes changed'):
        e2e.finish(tmp_path, runtime.path, 'offline-project')


def media(path: Path) -> None:
    result = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=48000:duration=60", "-c:a", "libmp3lame",
        str(path)], capture_output=True, check=False, timeout=30)
    assert result.returncode == 0, result.stderr


def source_srt(path: Path) -> None:
    path.write_text("1\n00:00:19,000 --> 00:00:22,000\nShe enters.\n\n"
                    "2\n00:00:21,500 --> 00:00:24,000\nHe takes the badge.\n\n"
                    "3\n00:00:34,000 --> 00:00:38,000\nShe stands her ground.\n", encoding="utf-8")


def test_prepare_preserves_overlapping_caption_windows_and_locks_sources(tmp_path):
    audio, srt = tmp_path / "source.mp3", tmp_path / "source.srt"
    media(audio)
    source_srt(srt)
    result = prepare(audio, srt, 18, 55, tmp_path / "film")
    assert result["shot_count"] == 8
    assert Path(result["runtime_database"]).is_file()
    connection = SQLiteStore(result["runtime_database"])._connect()
    try:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='selected_takes'").fetchone()
    finally:
        connection.close()
    state = status(tmp_path / "film")
    assert state["plan_review_required"] is True
    assert state["missing_selected_shots"] == [f"SHOT_{n:02d}" for n in range(1, 9)]
    plan = json.loads((tmp_path / "film" / "shots.json").read_text(encoding="utf-8"))
    assert any("She enters." in shot["source_text"] for shot in plan["shots"])
    assert (tmp_path / "film" / "source" / "captions.srt").read_text(encoding="utf-8") == srt.read_text(encoding="utf-8")
    (tmp_path / "film" / "source" / "audio.mp3").write_bytes(b"drift")
    with pytest.raises(ValueError, match="audio source.*changed"):
        status(tmp_path / "film")


def test_owner_review_rejects_wrong_media_hash_and_implicit_gates(tmp_path):
    video = tmp_path / "shot.mp4"
    video.write_bytes(b"test-only review bytes")
    digest = file_sha256(video)
    asset = Asset(asset_id="asset_1", origin="generated", uri_or_path=str(video),
        sha256=digest, file_size=video.stat().st_size, source_attempt_id="attempt_1",
        provider_job_id="job_1", provider_asset_id="provider_1")
    review = {"asset_id": asset.asset_id, "asset_sha256": asset.sha256,
        "source_attempt_id": asset.source_attempt_id, "provider_job_id": asset.provider_job_id,
        "provider_asset_id": asset.provider_asset_id, "asset_path": asset.uri_or_path,
        "reviewer_id": "owner", "visual_pass": True, "continuity_pass": True,
        "editorial_pass": True, "notes": ["Watched this exact shot."],
        "failure_observations": {}}
    validate_review_entry(review, asset)
    review["asset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="identity or SHA-256 mismatch"):
        validate_review_entry(review, asset)
    review["asset_sha256"] = digest
    review["continuity_pass"] = None
    with pytest.raises(ValueError, match="explicit booleans"):
        validate_review_entry(review, asset)


def test_resume_locks_plan_early_and_appends_partial_shared_references(tmp_path):
    audio, srt = tmp_path / "source.mp3", tmp_path / "source.srt"
    media(audio)
    source_srt(srt)
    root = tmp_path / "film"
    prepare(audio, srt, 18, 55, root)
    database = tmp_path / "runtime.sqlite"
    QCStore(SQLiteStore(database)).initialize()
    plan_path = root / "shots.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for shot in plan["shots"]:
        shot.update(visual_intent="Visible story beat from the source text",
                    image_prompt="Police station, same adult characters",
                    video_prompt="Animate only the action described in source text")
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    reference = tmp_path / "ref.png"
    reference.write_bytes(b"image test bytes")
    sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    receipt = tmp_path / "references.json"
    receipt.write_text(json.dumps({"profile_email": "nethaolabycss222@gmail.com", "tab_index": 2,
        "images": [{"shot_ids": ["SHOT_01", "SHOT_02"], "path": str(reference), "sha256": sha,
                    "chat_url": "https://chatgpt.com/c/example"}]}), encoding="utf-8")
    state = resume(root, database, "flow-project")
    assert state["status"] == "PLAN_LOCKED_AWAITING_FLOW_MEDIA"
    frozen = json.loads((root / "project.json").read_text(encoding="utf-8"))["locked_plan_sha256"]
    assert frozen == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    state = resume(root, database, "flow-project", receipt)
    assert state["reference_coverage"]["SHOT_01"] == 1
    assert state["reference_coverage"]["SHOT_02"] == 1
    assert state["reference_coverage"]["SHOT_03"] == 0
    assert len(references_for_shot(root, "SHOT_01")) == 1
    assert len(references_for_shot(root, "SHOT_02")) == 1
    assert references_for_shot(root, "SHOT_03") == []
    assert json.loads((root / "project.json").read_text(encoding="utf-8"))["locked_plan_sha256"] == frozen
    plan_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        status(root)
