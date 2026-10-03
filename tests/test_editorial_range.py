"""Editorial source-range proofs (FLOW-PRODUCTION-SCALE-007, Q5 / L5).

Full clip / head / tail / both-side trims; invalid negative, out-of-bounds
and zero-duration ranges; wrong-asset and hash-mismatch revalidation;
asset duration drift; restart reload; JSON serialization; EditManifest clip
roundtrip through the existing editorial boundary (no retiming, no new
assembly semantics). Offline; synthetic media only.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.editorial import EditClip, probe_media
from film_pipeline.editorial_range import (
    EditorialRange,
    make_editorial_range,
    probe_media as _probe,
    range_from_probe,
    read_range,
    revalidate,
    to_edit_clip_fields,
    write_range,
)
from film_pipeline.live_runtime import file_sha256


def synthetic_video(path, color="blue", fps=30, duration=1.2):
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i",
        f"color=c={color}:s=320x240:r={fps}:d={duration}",
        "-f", "lavfi", "-i",
        f"sine=frequency=440:sample_rate=48000:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path)], capture_output=True, text=True,
        check=False)
    assert result.returncode == 0, result.stderr


def basis(path):
    media = probe_media(path)
    from film_pipeline.editorial_range import ProbeBasis
    return ProbeBasis(duration_s=media.duration_s, fps_num=media.fps_num,
                      fps_den=media.fps_den)


def rng(path, source_in, source_out, asset_id="asset_A",
        sha=None, take="take_A", note=None):
    return make_editorial_range(
        selected_take_id=take, shot_id="SHOT_A", asset_id=asset_id,
        asset_sha256=sha or file_sha256(path),
        source_in_s=source_in, source_out_s=source_out,
        probe=basis(path), note=note)


@pytest.fixture(scope="module")
def clip_a(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "a.mp4"
    synthetic_video(path)
    return path


def test_full_clip_range(clip_a):
    duration = probe_media(clip_a).duration_s
    r = rng(clip_a, 0.0, duration)
    assert r.selected_duration_s == pytest.approx(duration, abs=1e-3)
    revalidate(r, clip_a)


def test_head_trim(clip_a):
    r = rng(clip_a, 0.2, probe_media(clip_a).duration_s)
    assert r.source_in_s == 0.2
    revalidate(r, clip_a)


def test_tail_trim(clip_a):
    r = rng(clip_a, 0.0, 0.7)
    assert r.selected_duration_s == pytest.approx(0.7)
    revalidate(r, clip_a)


def test_both_side_trim(clip_a):
    r = rng(clip_a, 0.15, 0.7)
    assert r.selected_duration_s == pytest.approx(0.55)
    revalidate(r, clip_a)


def test_invalid_negative_in(clip_a):
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        rng(clip_a, -0.1, 0.5)


def test_out_of_bounds_out(clip_a):
    duration = probe_media(clip_a).duration_s
    with pytest.raises(ValueError, match="exceeds the probed asset duration"):
        rng(clip_a, 0.0, duration + 0.5)


def test_zero_duration_refused(clip_a):
    with pytest.raises(ValueError, match="Input should be greater than 0"):
        rng(clip_a, 0.4, 0.4)
    with pytest.raises(ValueError, match="must be greater than source_in_s"):
        rng(clip_a, 0.5, 0.4)


def test_wrong_asset_revalidation_refused(clip_a, tmp_path):
    other = tmp_path / "b.mp4"
    synthetic_video(other, color="red")
    r = rng(clip_a, 0.0, 0.5)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        revalidate(r, other)


def test_hash_mismatch_refused(clip_a):
    r = rng(clip_a, 0.0, 0.5, sha="b" * 64)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        revalidate(r, clip_a)


def test_asset_duration_drift_refused(clip_a):
    from film_pipeline.editorial_range import ProbeBasis
    r = make_editorial_range(
        selected_take_id="take_A", shot_id="SHOT_A", asset_id="asset_A",
        asset_sha256=file_sha256(clip_a), source_in_s=0.0,
        source_out_s=0.5,
        probe=ProbeBasis(duration_s=probe_media(clip_a).duration_s + 0.5,
                         fps_num=30, fps_den=1))
    with pytest.raises(ValueError, match="duration drifted"):
        revalidate(r, clip_a)


def test_identity_is_deterministic_and_field_sensitive(clip_a):
    a = rng(clip_a, 0.0, 0.5)
    b = rng(clip_a, 0.0, 0.5)
    assert a.editorial_range_id == b.editorial_range_id
    assert a.editorial_range_id != rng(clip_a, 0.0, 0.6).editorial_range_id
    assert a.editorial_range_id != rng(clip_a, 0.0, 0.5,
                                       take="take_B").editorial_range_id
    assert a.editorial_range_id != rng(clip_a, 0.0, 0.5,
                                       note="x").editorial_range_id


def test_write_read_restart_roundtrip(clip_a, tmp_path):
    r = rng(clip_a, 0.1, 0.6)
    path = tmp_path / "editorial_range.json"
    write_range(r, path)
    write_range(r, path)  # idempotent
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["editorial_range_id"] == r.editorial_range_id
    assert payload["provenance"] == "PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE"
    with pytest.raises(ValueError, match="EVIDENCE_CONFLICT"):
        write_range(rng(clip_a, 0.2, 0.6), path)
    loaded = read_range(path)  # restart: fresh model re-derives identity
    assert loaded == r
    revalidate(loaded, clip_a)


def test_write_read_conflict_then_identity_readback(clip_a, tmp_path):
    r = rng(clip_a, 0.1, 0.6)
    path = tmp_path / "er.json"
    write_range(r, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["note"] = "tampered"  # duration-consistent tamper; identity must catch
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        read_range(path)


def test_edit_clip_roundtrip_no_retiming(clip_a):
    from film_pipeline.editorial import validate_source
    r = rng(clip_a, 0.1, 0.6, take="take_A")
    fields = to_edit_clip_fields(r)
    clip = EditClip(order=1, shot_id="SHOT_A", selected_take_id="take_A",
                    asset_id="asset_A", **fields)
    assert clip.source_in_s == pytest.approx(r.source_in_s)
    assert clip.source_out_s == pytest.approx(r.source_out_s)
    assert clip.target_duration_s == pytest.approx(r.selected_duration_s)
    resolved = validate_source(
        clip, path=clip_a, expected_sha256=r.asset_sha256,
        attempt_id="attempt_A", qc_report_id="qc_A")
    assert resolved.duration_s == pytest.approx(r.selected_duration_s)
    # The clip vocabulary refuses implicit retiming vs the range duration.
    late = EditClip(order=1, shot_id="SHOT_A", selected_take_id="take_A",
                    asset_id="asset_A", source_in_s=r.source_in_s,
                    source_out_s=r.source_out_s,
                    target_duration_s=r.selected_duration_s + 0.1)
    with pytest.raises(ValueError, match="implicit retiming"):
        validate_source(late, path=clip_a, expected_sha256=r.asset_sha256,
                        attempt_id="attempt_A", qc_report_id="qc_A")


def test_range_from_probe_and_revalidation(clip_a):
    r = range_from_probe(clip_a, selected_take_id="take_A",
                         shot_id="SHOT_A", asset_id="asset_A",
                         asset_sha256=file_sha256(clip_a),
                         source_in_s=0.0, source_out_s=0.4)
    assert r.probe_basis.duration_s == pytest.approx(
        probe_media(clip_a).duration_s, abs=1e-3)
    revalidate(r, clip_a)
