import asyncio
import subprocess
from pathlib import Path

import pytest

from film_pipeline.editorial import (EditClip, EditManifest, EditorialStore,
                                     make_edit_manifest, probe_media, validate_source)
from film_pipeline.live_runtime import file_sha256
from film_pipeline.qc import QCStore, human_decision
from film_pipeline.rough_cut import persist_render, read_render, render_sources
from film_pipeline.store import SQLiteStore


def clip(order, name, *, start=0.0, end=None, target=None):
    return EditClip(order=order, shot_id="SHOT_" + name, selected_take_id="take_" + name,
                    asset_id="asset_" + name, source_in_s=start,
                    source_out_s=end, target_duration_s=target)


def synthetic_video(path, color, size, fps):
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d=1.2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1.2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_manifest_identity_order_trim_and_machine_path_independence():
    first = [clip(1, "A", start=0.1, end=0.9, target=0.8), clip(2, "B")]
    manifest = make_edit_manifest("film_1", first)
    assert manifest == make_edit_manifest("film_1", list(first))
    assert manifest.edit_manifest_id != make_edit_manifest("film_1", [
        clip(1, "B"), clip(2, "A", start=0.1, end=0.9, target=0.8)]).edit_manifest_id
    assert manifest.edit_manifest_id != make_edit_manifest("film_1", [
        clip(1, "A", start=0.2, end=0.9, target=0.7), clip(2, "B")]).edit_manifest_id
    assert manifest.edit_manifest_id != make_edit_manifest("film_1", [
        clip(1, "X", start=0.1, end=0.9, target=0.8), clip(2, "B")]).edit_manifest_id
    assert "D:\\" not in manifest.model_dump_json()
    with pytest.raises(ValueError, match="contiguous"):
        make_edit_manifest("film_1", [clip(2, "A"), clip(1, "B")])
    with pytest.raises(ValueError, match="contiguous"):
        make_edit_manifest("film_1", [clip(1, "A"), clip(1, "B")])
    with pytest.raises(ValueError, match="greater"):
        clip(1, "A", start=0.5, end=0.5)
    with pytest.raises(ValueError):
        clip(1, "A", start=float("nan"))


def test_multi_clip_filtergraph_orders_trims_normalizes_and_preserves_audio(tmp_path):
    paths = [tmp_path / name for name in ("red.mp4", "green.mp4", "blue.mp4")]
    for path, color, size, fps in zip(paths, ("red", "green", "blue"),
                                      ("64x48", "80x60", "64x48"), (24, 30, 15)):
        synthetic_video(path, color, size, fps)
    clips = [clip(1, "RED", start=0.2, end=0.8, target=0.6),
             clip(2, "GREEN", start=0.1, end=0.5, target=0.4),
             clip(3, "BLUE", start=0.0, end=0.5, target=0.5)]
    manifest = make_edit_manifest("synthetic", clips)
    sources = tuple(validate_source(c, path=p, expected_sha256=file_sha256(p),
                                    attempt_id="attempt_" + str(i), qc_report_id="qcr_" + str(i))
                    for i, (c, p) in enumerate(zip(clips, paths)))
    output = tmp_path / "rough.mp4"
    record = render_sources(manifest, sources, output)
    assert record.render_method == "normalized_filtergraph"
    assert record.audio_policy == "preserve_all_source_audio"
    assert record.audio_codec == "aac" and record.video_codec == "h264"
    assert (record.width, record.height) == (64, 48)
    assert abs(record.duration_s - 1.5) < 0.1
    assert record.full_decode and file_sha256(output) == record.output_sha256
    # Sample each segment midpoint to prove actual output order, not just plan order.
    for at, dominant in ((0.3, 0), (0.8, 1), (1.25, 2)):
        result = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(output),
                                 "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo",
                                 "-pix_fmt", "rgb24", "-"], capture_output=True, check=False)
        assert result.returncode == 0 and len(result.stdout) == 3
        rgb = result.stdout
        assert rgb[dominant] > max(rgb[i] for i in range(3) if i != dominant) + 30
    reversed_clips = [clip(1, "BLUE", start=0.0, end=0.5, target=0.5),
                      clip(2, "GREEN", start=0.1, end=0.5, target=0.4),
                      clip(3, "RED", start=0.2, end=0.8, target=0.6)]
    reversed_manifest = make_edit_manifest("synthetic", reversed_clips)
    reversed_sources = tuple(validate_source(c, path=p, expected_sha256=file_sha256(p),
                                             attempt_id="attempt_reverse_" + str(i),
                                             qc_report_id="qcr_reverse_" + str(i))
                             for i, (c, p) in enumerate(zip(reversed_clips, reversed(paths))))
    reversed_output = tmp_path / "rough_reverse.mp4"
    reversed_record = render_sources(reversed_manifest, reversed_sources, reversed_output)
    assert reversed_record.render_id != record.render_id
    result = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.25", "-i", str(reversed_output),
                             "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-"], capture_output=True, check=False)
    assert result.returncode == 0 and len(result.stdout) == 3
    assert result.stdout[2] > max(result.stdout[0], result.stdout[1]) + 30


def test_invalid_source_bounds_target_missing_and_wrong_hash(tmp_path):
    path = tmp_path / "red.mp4"
    synthetic_video(path, "red", "64x48", 24)
    digest = file_sha256(path)
    with pytest.raises(ValueError, match="bounds"):
        validate_source(clip(1, "A", end=2.0), path=path, expected_sha256=digest,
                        attempt_id="attempt", qc_report_id="qcr")
    with pytest.raises(ValueError, match="implicit retiming"):
        validate_source(clip(1, "A", end=0.5, target=1.0), path=path,
                        expected_sha256=digest, attempt_id="attempt", qc_report_id="qcr")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_source(clip(1, "A"), path=path, expected_sha256="0" * 64,
                        attempt_id="attempt", qc_report_id="qcr")
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_source(clip(1, "A"), path=tmp_path / "missing.mp4", expected_sha256=digest,
                        attempt_id="attempt", qc_report_id="qcr")


def approved_runtime(tmp_path):
    from test_live_runtime import FakeTransport, make_executor
    from test_qc_kernel import evidence_set

    executor, runtime, attempt, job = make_executor(tmp_path, FakeTransport())
    asyncio.run(executor.submit_once(job.provider_job_id))
    asyncio.run(executor.reconcile(job.provider_job_id))
    asset = asyncio.run(executor.download_assets(job.provider_job_id, tmp_path / "outputs"))[0]
    human = human_decision(asset=asset, reviewer_id="fixture_owner", action="APPROVE",
                           visual_pass=True, continuity_pass=True, editorial_pass=True)
    report, take = QCStore(runtime).save(asset, evidence_set(asset), human)
    assert report.report["decision"] == "pass"
    return runtime, asset, take


def test_real_sqlite_approved_resolution_persistence_and_rejections(tmp_path):
    runtime, asset, take = approved_runtime(tmp_path)
    valid = EditClip(order=1, shot_id=take.shot_id, selected_take_id=take.selected_take_id,
                     asset_id=asset.asset_id, target_duration_s=asset.duration_s)
    manifest = make_edit_manifest("fixture_project", [valid])
    editorial = EditorialStore(runtime)
    sources = editorial.save_manifest(manifest)
    assert len(sources) == 1 and sources[0].qc_report_id == take.qc_report_id
    fresh, fresh_sources = EditorialStore(SQLiteStore(runtime.path)).read_manifest(manifest.edit_manifest_id)
    assert fresh == manifest and fresh_sources == sources
    assert editorial.save_manifest(manifest) == sources
    record = render_sources(manifest, sources, tmp_path / "approved_rough.mp4")
    persist_render(editorial, record)
    read_record, read_manifest, read_sources = read_render(
        EditorialStore(SQLiteStore(runtime.path)), record.render_id)
    assert (read_record, read_manifest, read_sources) == (record, manifest, sources)
    assert record.selected_take_ids == [take.selected_take_id]
    assert record.source_asset_ids == [asset.asset_id]
    longer = tmp_path / "wrong_duration.mp4"
    duplicate = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-stream_loop", "3", "-i", asset.uri_or_path,
                                "-c", "copy", str(longer)], capture_output=True, text=True,
                               check=False)
    assert duplicate.returncode == 0, duplicate.stderr
    forged = record.model_copy(update={"output_path": str(longer),
                                       "output_sha256": file_sha256(longer),
                                       "duration_s": probe_media(longer).duration_s})
    with pytest.raises(ValueError, match="duration differs from manifest"):
        persist_render(editorial, forged)
    bad_take = make_edit_manifest("fixture_project", [valid.model_copy(update={
        "selected_take_id": "take_missing"})])
    with pytest.raises(ValueError, match="missing or unapproved"):
        editorial.save_manifest(bad_take)
    bad_asset = make_edit_manifest("fixture_project", [valid.model_copy(update={
        "asset_id": "asset_unapproved"})])
    with pytest.raises(ValueError, match="differs"):
        editorial.save_manifest(bad_asset)
    Path(asset.uri_or_path).write_bytes(Path(asset.uri_or_path).read_bytes() + b"changed")
    with pytest.raises(ValueError):
        EditorialStore(SQLiteStore(runtime.path)).read_manifest(manifest.edit_manifest_id)
