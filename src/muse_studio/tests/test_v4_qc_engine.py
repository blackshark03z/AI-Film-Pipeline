import subprocess
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from muse_studio.core.film_qc_engine import FilmQCEngine


def _build_textured_canvas(
    width: int = 1440,
    height: int = 720,
    bg_bgr=(58, 42, 28),
    accent_bgr=(95, 145, 205),
    secondary_bgr=(150, 110, 75),
    seed: int = 42,
) -> np.ndarray:
    """Create a deterministic textured BGR canvas with corner features for optical flow & HSV continuity."""
    rng = np.random.default_rng(seed)
    canvas = np.full((height, width, 3), bg_bgr, dtype=np.uint8)
    for _ in range(90):
        x = int(rng.integers(10, width - 70))
        y = int(rng.integers(10, height - 60))
        w = int(rng.integers(24, 64))
        h = int(rng.integers(20, 52))
        color = accent_bgr if rng.random() > 0.5 else secondary_bgr
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, -1)
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (220, 215, 205), 2)
    return canvas


def _encode_frames_with_audio(
    out_path: Path,
    frames_bgr: list[np.ndarray],
    audio_lavfi: str = "sine=frequency=440:sample_rate=48000:duration=2.5",
    audio_filter: Optional[str] = None,
    audio_codec: str = "aac",
    fps: int = 24,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames_bgr[0].shape[:2]
    dur = round(len(frames_bgr) / float(fps), 3)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-f", "lavfi", "-i", audio_lavfi,
    ]
    if audio_filter:
        cmd.extend(["-af", audio_filter])
    cmd.extend([
        "-t", str(dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "10",
    ])
    if audio_codec == "flac":
        cmd.extend(["-c:a", "flac", "-strict", "-2"])
    else:
        cmd.extend(["-c:a", "aac", "-ac", "2", "-b:a", "192k"])
    cmd.extend(["-shortest", str(out_path)])
    raw_bytes = b"".join(f.tobytes() for f in frames_bgr)
    subprocess.run(cmd, input=raw_bytes, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out_path


def _make_panning_or_steady_clip(
    out_path: Path,
    pan_total_px: int = 0,
    duration_s: float = 2.5,
    fps: int = 24,
    bg_bgr=(58, 42, 28),
    accent_bgr=(95, 145, 205),
    secondary_bgr=(150, 110, 75),
    animate_subject: bool = True,
) -> tuple[Path, np.ndarray]:
    n_frames = int(round(duration_s * fps))
    canvas = _build_textured_canvas(
        width=1440,
        height=720,
        bg_bgr=bg_bgr,
        accent_bgr=accent_bgr,
        secondary_bgr=secondary_bgr,
    )
    frames = []
    for i in range(n_frames):
        shift = int(round((pan_total_px * i) / max(1, n_frames - 1)))
        frame = canvas[:, shift : shift + 1280].copy()
        if animate_subject:
            # Gentle lower-body sway so clip is never flagged frozen while keeping camera corners steady
            dx = int(round(12 * np.sin(2 * np.pi * i / 16.0)))
            cv2.rectangle(frame, (520 + dx, 420), (760 + dx, 690), (80, 170, 220), -1)
        frames.append(frame)
    _encode_frames_with_audio(
        out_path,
        frames,
        audio_lavfi=f"sine=frequency=440:sample_rate=48000:duration={duration_s}",
        fps=fps,
    )
    return out_path, frames[0]


def _make_dialogue_lipsync_clip(
    out_path: Path,
    animate_mouth: bool,
    audio_mode: str = "clean",
    duration_s: float = 2.5,
    fps: int = 24,
) -> Path:
    """Build a synthetic talking/ventriloquist clip.
    Central mouth ROI is x: 0.25..0.75 (320..960), y: 0.20..0.65 (144..468).
    """
    n_frames = int(round(duration_s * fps))
    base = _build_textured_canvas(width=1280, height=720, seed=99)
    # Clear central face ROI background cleanly so mouth ROI has zero background clutter
    cv2.rectangle(base, (310, 135), (970, 475), (48, 56, 72), -1)
    # Static portrait torso/head in center
    cv2.ellipse(base, (640, 300), (110, 135), 0, 0, 360, (145, 170, 205), -1)
    cv2.rectangle(base, (480, 475), (800, 710), (75, 95, 130), -1)

    frames = []
    for i in range(n_frames):
        f = base.copy()
        # Subtle motion outside the central face ROI (y > 0.70) so whole clip is non-frozen & >100KB
        bar_x = 60 + int(round(55 * np.sin(2 * np.pi * i / 11.0)))
        cv2.rectangle(f, (bar_x, 530), (bar_x + 160, 690), (180, 195, 210), -1)
        bar2_x = 1020 - int(round(55 * np.cos(2 * np.pi * i / 13.0)))
        cv2.rectangle(f, (bar2_x, 530), (bar2_x + 160, 690), (135, 165, 195), -1)

        if animate_mouth:
            mouth_h = 6 + (18 if (i % 4 < 2) else 2)
            cv2.ellipse(f, (640, 355), (38, mouth_h), 0, 0, 360, (25, 25, 45), -1)
            if i % 4 < 2:
                cv2.rectangle(f, (615, 345), (665, 353), (235, 235, 240), -1)
        else:
            cv2.line(f, (605, 355), (675, 355), (30, 30, 45), 4)
        frames.append(f)

    audio_codec = "aac"
    if audio_mode == "silent":
        audio_lavfi = f"anullsrc=r=48000:cl=stereo:d={duration_s}"
        af = None
    elif audio_mode == "warn_clip":
        # Clip strongly for ~0.32s out of 2.5s (~12% clipping ratio: > 0.05 and <= 0.20)
        audio_lavfi = f"sine=frequency=35:sample_rate=16000:duration={duration_s}"
        af = "volume='if(lt(t,0.32),50,0.2)':eval=frame,aformat=sample_fmts=s16"
        audio_codec = "flac"
    elif audio_mode == "hard_clip":
        audio_lavfi = f"sine=frequency=35:sample_rate=16000:duration={duration_s}"
        af = "volume=45dB,aformat=sample_fmts=s16"
        audio_codec = "flac"
    else:
        audio_lavfi = f"sine=frequency=330:sample_rate=48000:duration={duration_s}"
        af = None

    return _encode_frames_with_audio(
        out_path, frames, audio_lavfi=audio_lavfi, audio_filter=af, audio_codec=audio_codec, fps=fps
    )


def test_preflight_controlled_camera_motion_gate():
    pan_prompt = "Wide cinematic 16:9 shot of Captain Brianna walking across tarmac with smooth dolly push-in."

    ok_default, errs_default = FilmQCEngine.validate_shot_preflight({"id": "S_PAN_1", "prompt": pan_prompt})
    assert ok_default is False
    assert any("UNLOCKED_CAMERA" in e for e in errs_default)

    ok_false, errs_false = FilmQCEngine.validate_shot_preflight(
        {"id": "S_PAN_2", "prompt": pan_prompt, "allow_camera_motion": False}
    )
    assert ok_false is False
    assert any("UNLOCKED_CAMERA" in e for e in errs_false)

    ok_allowed, errs_allowed = FilmQCEngine.validate_shot_preflight(
        {"id": "S_PAN_3", "prompt": pan_prompt, "allow_camera_motion": True}
    )
    assert ok_allowed is True, errs_allowed
    assert not any("UNLOCKED_CAMERA" in e for e in errs_allowed)


def test_postflight_controlled_camera_motion_skips_drift_defect(tmp_path: Path):
    pan_clip, _ = _make_panning_or_steady_clip(tmp_path / "pan_clip.mp4", pan_total_px=64, duration_s=2.5)

    flow = FilmQCEngine.analyze_optical_flow(pan_clip)
    assert flow["camera_drift_px"] > 28.0

    res_locked = FilmQCEngine.evaluate_generated_clip(
        pan_clip,
        {"id": "SH_LOCKED", "action_summary": "Brianna walks across corridor."},
        min_duration_s=2.0,
    )
    assert res_locked["verdict"] == "REJECT"
    assert any("DEFECT_CAMERA_DRIFT" in d for d in res_locked["defects"])

    res_allowed = FilmQCEngine.evaluate_generated_clip(
        pan_clip,
        {"id": "SH_MOTION_OK", "action_summary": "Brianna walks across corridor.", "allow_camera_motion": True},
        min_duration_s=2.0,
    )
    assert res_allowed["verdict"] == "PASS", res_allowed["defects"]
    assert not any("DEFECT_CAMERA_DRIFT" in d for d in res_allowed["defects"])


def test_actor_visual_consistency_face_boxes_and_identity_drift(tmp_path: Path):
    clip_path, opening_bgr = _make_panning_or_steady_clip(
        tmp_path / "actor_clip.mp4",
        pan_total_px=0,
        duration_s=2.5,
        bg_bgr=(58, 42, 28),
        accent_bgr=(95, 145, 205),
        secondary_bgr=(150, 110, 75),
    )

    matching_ref = tmp_path / "ref_match.png"
    Image.fromarray(cv2.cvtColor(opening_bgr, cv2.COLOR_BGR2RGB)).save(matching_ref)

    # Completely different bright neon green/yellow scene reference
    drifted_ref = tmp_path / "ref_drift.png"
    drift_img = Image.new("RGB", (1280, 720), (225, 245, 60))
    d = ImageDraw.Draw(drift_img)
    d.rectangle([100, 80, 1180, 640], fill=(40, 235, 130))
    drift_img.save(drifted_ref)

    cons_match = FilmQCEngine.analyze_actor_visual_consistency(clip_path, reference_image_path=matching_ref)
    assert isinstance(cons_match["face_boxes"], list)
    assert isinstance(cons_match["max_faces_detected"], int)
    assert -1.0 <= cons_match["identity_similarity"] <= 1.0
    assert cons_match["identity_similarity"] > 0.65

    cons_drift = FilmQCEngine.analyze_actor_visual_consistency(clip_path, reference_image_path=drifted_ref)
    assert -1.0 <= cons_drift["identity_similarity"] <= 1.0
    assert cons_drift["identity_similarity"] < 0.20

    # Verify normalized 0..1 face bounding box conversion via CascadeClassifier (compatible with OpenCV 4 & 5)
    fake_cascade_rects = np.array([[320, 180, 256, 252]], dtype=np.int32)

    class _FakeCascade:
        def __init__(self, *_args, **_kwargs):
            pass

        def empty(self) -> bool:
            return False

        def detectMultiScale(self, *_args, **_kwargs):
            return fake_cascade_rects

    with patch.object(cv2, "CascadeClassifier", _FakeCascade, create=True):
        cons_faces = FilmQCEngine.analyze_actor_visual_consistency(clip_path)
    assert cons_faces["max_faces_detected"] == 1
    assert len(cons_faces["face_boxes"]) == 1
    fb = cons_faces["face_boxes"][0]
    assert set(fb.keys()) == {"x_norm", "y_norm", "w_norm", "h_norm"}
    assert all(0.0 <= fb[k] <= 1.0 for k in ("x_norm", "y_norm", "w_norm", "h_norm"))
    assert abs(fb["x_norm"] - 0.25) < 0.02
    assert abs(fb["y_norm"] - 0.25) < 0.02

    # Also verify unmocked runtime face detection on portrait clip
    portrait_clip = _make_dialogue_lipsync_clip(tmp_path / "portrait_face.mp4", animate_mouth=True, audio_mode="clean")
    cons_portrait = FilmQCEngine.analyze_actor_visual_consistency(portrait_clip)
    assert cons_portrait["max_faces_detected"] >= 1
    assert len(cons_portrait["face_boxes"]) >= 1

    # Wiring in evaluate_generated_clip: warning by default, HARD defect only when enforce_identity_qc is True
    res_warn_only = FilmQCEngine.evaluate_generated_clip(
        clip_path,
        {"id": "SH_ID_WARN", "first_frame_path": str(drifted_ref)},
        min_duration_s=2.0,
    )
    assert res_warn_only["verdict"] == "PASS", res_warn_only["defects"]
    assert "actor_consistency" in res_warn_only["metrics"]
    assert any("VISUAL_IDENTITY_DRIFT_WARNING" in w for w in res_warn_only["warnings"])
    assert not any("DEFECT_VISUAL_IDENTITY_DRIFT" in d for d in res_warn_only["defects"])

    res_enforced = FilmQCEngine.evaluate_generated_clip(
        clip_path,
        {"id": "SH_ID_HARD", "first_frame_path": str(drifted_ref), "enforce_identity_qc": True},
        min_duration_s=2.0,
    )
    assert res_enforced["verdict"] == "REJECT"
    assert any("DEFECT_VISUAL_IDENTITY_DRIFT" in d for d in res_enforced["defects"])


def test_audio_signal_silent_dialogue_and_clipping_gates(tmp_path: Path):
    silent_clip = _make_dialogue_lipsync_clip(tmp_path / "silent_dlg.mp4", animate_mouth=True, audio_mode="silent")
    warn_clip = _make_dialogue_lipsync_clip(tmp_path / "warn_clip.mp4", animate_mouth=True, audio_mode="warn_clip")
    hard_clip = _make_dialogue_lipsync_clip(tmp_path / "hard_clip.mp4", animate_mouth=True, audio_mode="hard_clip")

    sig_silent = FilmQCEngine.analyze_audio_signal_and_lipsync(silent_clip, has_dialogue=True)
    assert sig_silent["rms_dbfs"] < -55.0
    assert sig_silent["clipping_ratio"] == 0.0

    sig_warn = FilmQCEngine.analyze_audio_signal_and_lipsync(warn_clip, has_dialogue=True)
    assert 0.05 < sig_warn["clipping_ratio"] <= 0.20

    sig_hard = FilmQCEngine.analyze_audio_signal_and_lipsync(hard_clip, has_dialogue=True)
    assert sig_hard["clipping_ratio"] > 0.20

    mock_asr_ok = {
        "passed": True,
        "spoken_stage_direction": False,
        "transcript": "Captain Johnson speaking.",
        "expected": "Captain Johnson speaking.",
        "wer": 0.0,
        "word_count": 3,
        "words": [],
        "speech_start_s": 0.4,
        "speech_end_s": 2.0,
        "pauses": [],
        "has_long_pause": False,
    }

    with patch.object(FilmQCEngine, "verify_native_dialogue", return_value=mock_asr_ok):
        res_silent = FilmQCEngine.evaluate_generated_clip(
            silent_clip,
            {"id": "SH_SILENT_DLG", "dialogue": "Captain Johnson speaking."},
            min_duration_s=2.0,
        )
        assert res_silent["verdict"] == "REJECT"
        assert "audio_lipsync" in res_silent["metrics"]
        assert any("DEFECT_SILENT_DIALOGUE_TRACK" in d for d in res_silent["defects"])

        res_warn = FilmQCEngine.evaluate_generated_clip(
            warn_clip,
            {"id": "SH_CLIP_WARN", "dialogue": "Captain Johnson speaking."},
            min_duration_s=2.0,
        )
        assert res_warn["verdict"] == "PASS", res_warn["defects"]
        assert any("AUDIO_CLIPPING_WARNING" in w for w in res_warn["warnings"])
        assert not any("DEFECT_AUDIO_CLIPPING" in d for d in res_warn["defects"])

        res_hard = FilmQCEngine.evaluate_generated_clip(
            hard_clip,
            {"id": "SH_CLIP_HARD", "dialogue": "Captain Johnson speaking."},
            min_duration_s=2.0,
        )
        assert res_hard["verdict"] == "REJECT"
        assert any("AUDIO_CLIPPING_WARNING" in w for w in res_hard["warnings"])
        assert any("DEFECT_AUDIO_CLIPPING" in d for d in res_hard["defects"])


def test_ventriloquist_lipsync_frozen_vs_active_mouth(tmp_path: Path):
    frozen_mouth_clip = _make_dialogue_lipsync_clip(
        tmp_path / "frozen_mouth.mp4", animate_mouth=False, audio_mode="clean"
    )
    active_mouth_clip = _make_dialogue_lipsync_clip(
        tmp_path / "active_mouth.mp4", animate_mouth=True, audio_mode="clean"
    )

    sig_frozen = FilmQCEngine.analyze_audio_signal_and_lipsync(
        frozen_mouth_clip, has_dialogue=True, speech_start_s=0.4, speech_end_s=2.1
    )
    assert sig_frozen["mouth_motion_energy"] < 0.15

    sig_active = FilmQCEngine.analyze_audio_signal_and_lipsync(
        active_mouth_clip, has_dialogue=True, speech_start_s=0.4, speech_end_s=2.1
    )
    assert sig_active["mouth_motion_energy"] >= 0.15

    mock_asr_ok = {
        "passed": True,
        "spoken_stage_direction": False,
        "transcript": "Stand back from the cockpit door.",
        "expected": "Stand back from the cockpit door.",
        "wer": 0.0,
        "word_count": 6,
        "words": [],
        "speech_start_s": 0.4,
        "speech_end_s": 2.1,
        "pauses": [],
        "has_long_pause": False,
    }

    with patch.object(FilmQCEngine, "verify_native_dialogue", return_value=mock_asr_ok):
        res_warn = FilmQCEngine.evaluate_generated_clip(
            frozen_mouth_clip,
            {"id": "SH_VENT_WARN", "dialogue": "Stand back from the cockpit door."},
            min_duration_s=2.0,
        )
        assert res_warn["verdict"] == "PASS", res_warn["defects"]
        assert any("VENTRILOQUIST_LIPSYNC_WARNING" in w for w in res_warn["warnings"])
        assert not any("DEFECT_LIPSYNC_FROZEN_MOUTH" in d for d in res_warn["defects"])

        res_enforced = FilmQCEngine.evaluate_generated_clip(
            frozen_mouth_clip,
            {
                "id": "SH_VENT_HARD",
                "dialogue": "Stand back from the cockpit door.",
                "enforce_lipsync_qc": True,
            },
            min_duration_s=2.0,
        )
        assert res_enforced["verdict"] == "REJECT"
        assert any("DEFECT_LIPSYNC_FROZEN_MOUTH" in d for d in res_enforced["defects"])

        res_active = FilmQCEngine.evaluate_generated_clip(
            active_mouth_clip,
            {
                "id": "SH_TALK_OK",
                "dialogue": "Stand back from the cockpit door.",
                "enforce_lipsync_qc": True,
            },
            min_duration_s=2.0,
        )
        assert res_active["verdict"] == "PASS", res_active["defects"]
        assert not any("VENTRILOQUIST_LIPSYNC_WARNING" in w for w in res_active["warnings"])
        assert not any("DEFECT_LIPSYNC_FROZEN_MOUTH" in d for d in res_active["defects"])


def test_compute_take_quality_score_deterministic_formula():
    assert FilmQCEngine.compute_take_quality_score({"verdict": "REJECT", "metrics": {}, "warnings": []}) == 0.0

    qc_dialogue = {
        "verdict": "PASS",
        "warnings": ["W1", "W2"],  # 15 - 6 = 9.0
        "metrics": {
            "dialogue_qc": {"wer": 0.10},  # (1 - 0.10) * 40 = 36.0
            "spatial_continuity": {"span_grid_corr": 0.80},  # 0.80 * 25 = 20.0
            "optical_flow": {"camera_drift_px": 10.0},  # 20 - 6 = 14.0
        },
    }
    assert FilmQCEngine.compute_take_quality_score(qc_dialogue) == pytest.approx(79.0, abs=0.01)

    qc_silent_perfect = {
        "verdict": "PASS",
        "warnings": [],
        "metrics": {
            "spatial_continuity": {"span_grid_corr": 1.0},
            "optical_flow": {"camera_drift_px": 0.0},
        },
    }
    assert FilmQCEngine.compute_take_quality_score(qc_silent_perfect) == pytest.approx(100.0, abs=0.01)


def test_select_best_candidate_multi_take_ranking_and_strip(tmp_path: Path):
    # Take 1: Frozen -> REJECT (score 0.0)
    take_bad, _ = _make_panning_or_steady_clip(
        tmp_path / "take_01_bad.mp4", pan_total_px=0, duration_s=2.5, animate_subject=False
    )
    # Take 2: PASS, but camera drifts ~20px (< 28px threshold) and triggers identity drift warning -> lower score
    take_mid, _ = _make_panning_or_steady_clip(
        tmp_path / "take_02_mid.mp4",
        pan_total_px=22,
        duration_s=2.5,
        bg_bgr=(215, 230, 55),
        accent_bgr=(45, 220, 120),
        secondary_bgr=(80, 210, 180),
        animate_subject=True,
    )
    # Take 3: PASS, rock-steady camera (0px drift), matches reference image cleanly -> highest score
    take_best, best_frame = _make_panning_or_steady_clip(
        tmp_path / "take_03_best.mp4", pan_total_px=0, duration_s=2.5, animate_subject=True
    )

    ref_img = tmp_path / "anchor_ref.png"
    Image.fromarray(cv2.cvtColor(best_frame, cv2.COLOR_BGR2RGB)).save(ref_img)

    strip_winner = tmp_path / "strips" / "winner_strip.jpg"
    shot_spec = {"shot_id": "SH_MULTI", "first_frame_path": str(ref_img)}

    winner, best_res, all_results = FilmQCEngine.select_best_candidate(
        [take_bad, take_mid, take_best],
        shot_spec=shot_spec,
        min_duration_s=2.0,
        strip_output_path=strip_winner,
    )

    assert winner == take_best
    assert best_res["verdict"] == "PASS"
    assert len(all_results) == 3
    assert all_results[0]["verdict"] == "REJECT"
    assert all_results[0]["metrics"]["quality_score"] == 0.0
    assert all_results[1]["verdict"] == "PASS"
    assert best_res["metrics"]["quality_score"] > all_results[1]["metrics"]["quality_score"]
    assert strip_winner.exists() and strip_winner.stat().st_size > 1000
    assert best_res["metrics"].get("qc_strip") == str(strip_winner)
    assert "qc_strip" not in all_results[0]["metrics"]
    assert "qc_strip" not in all_results[1]["metrics"]

    # Fallback when all candidates fail: returns (None, last_failed_res, all_results) and writes strip for last failed
    strip_failed = tmp_path / "strips" / "failed_strip.jpg"
    winner_none, last_failed_res, failed_list = FilmQCEngine.select_best_candidate(
        [take_bad],
        shot_spec={"shot_id": "SH_ALL_FAIL"},
        min_duration_s=2.0,
        strip_output_path=strip_failed,
    )
    assert winner_none is None
    assert last_failed_res["verdict"] == "REJECT"
    assert len(failed_list) == 1
    assert strip_failed.exists() and strip_failed.stat().st_size > 1000
