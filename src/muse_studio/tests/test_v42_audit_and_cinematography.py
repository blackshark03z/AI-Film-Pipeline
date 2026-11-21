import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from muse_studio.app import _safe_export_stem, _safe_filename
from muse_studio.core.animatic_builder import AnimaticBuilder
from muse_studio.core.batch_packager import BatchPackager, KeyframeItem
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.master_assembler import MasterAssembler
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.core.prompt_repair_agent import PromptRepairAgent
from muse_studio.core.screenplay_compiler import ScreenplayCompiler
from muse_studio.core.script_ingestor import ScriptIngestor


def _make_16_9_png(path: Path, bg=(40, 62, 88), fg=(190, 148, 112)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(19)
    arr = rng.integers(25, 75, size=(720, 1280, 3), dtype=np.uint8)
    im = Image.fromarray(arr, mode="RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([110, 110, 540, 620], fill=bg)
    d.ellipse([720, 150, 1100, 540], fill=fg)
    im.save(path, format="PNG")
    return path


def test_prompt_repair_preserves_timecodes_gaze_and_location_while_stripping_stage_leaks():
    shot = {
        "shot_id": "SH_REPAIR_01",
        "framing": "Over-the-shoulder Medium Shot",
        "gaze": "looking screen-right",
        "dialogue": "(brief pause) Check the flight deck log. [sighs] Every entry is signed.",
        "compiled_prompt": (
            "Image 1 is the exact first frame of the shot, Over-the-shoulder Medium Shot, looking screen-right. "
            "Locked-off static tripod shot of exactly 10 seconds, in exactly 16:9 aspect ratio. "
            "Setting (Precinct Counter Lobby): warm fluorescent interior. "
            "Primary speaker: Captain Marcus (looking screen-right). "
            "[0-0.5s] Subtle pre-speech listening reaction, looking screen-right. "
            "[0.5-9s] Speaking directly in English (deep, calm baritone voice), the character says verbatim: "
            "\"(brief pause) Check the flight deck log. [sighs] Every entry is signed.\" "
            "[9-10s] Mouth closes cleanly."
        ),
    }

    repaired = PromptRepairAgent.repair_shot(
        shot,
        defects=["DEFECT_SPOKEN_STAGE_DIRECTION", "DEFECT_DIALOGUE_MISMATCH"],
    )
    cp = repaired["compiled_prompt"]
    # Stage directions must be gone
    assert "brief pause" not in cp.lower()
    assert "[sighs]" not in cp.lower()
    assert "brief pause" not in repaired["dialogue"].lower()
    # Structural markers MUST remain intact
    assert "[0-0.5s]" in cp
    assert "[0.5-9s]" in cp
    assert "[9-10s]" in cp
    assert "(looking screen-right)" in cp
    assert "Setting (Precinct Counter Lobby)" in cp
    assert "(deep, calm baritone voice)" in cp


def test_compiler_scene_gaze_override_and_keyframe_key_disambiguation(tmp_path: Path):
    anchors = tmp_path / "assets" / "anchors"
    _make_16_9_png(anchors / "marcus.png")
    _make_16_9_png(anchors / "karen.png", bg=(65, 45, 55))
    _make_16_9_png(anchors / "ceo.png", bg=(50, 75, 55))

    bible = {
        "project_title": "Keyframe Collision Guard",
        "characters": [
            {
                "id": "CHAR_MARCUS",
                "name": "Marcus",
                "look_verbatim": "55yo dignified captain with short gray hair",
                "anchor_image": "marcus.png",
                "axis_gaze": "looking screen-right",
                "wardrobe_by_chapter": {
                    "CH01": "white pilot shirt with gold epaulets",
                    "CH02": "dark charcoal courtroom suit",
                },
            },
            {
                "id": "CHAR_KAREN",
                "name": "Karen",
                "look_verbatim": "38yo gate supervisor in navy vest",
                "anchor_image": "karen.png",
                "axis_gaze": "looking screen-left",
            },
            {
                "id": "CHAR_CEO",
                "name": "David",
                "look_verbatim": "60yo airline executive in pinstripe suit",
                "anchor_image": "ceo.png",
                "axis_gaze": "looking screen-right",
            },
        ],
        "locations": [
            {
                "id": "LOC_GATE",
                "name": "Gate B14",
                "look_verbatim": "modern glass airport gate concourse",
                "set_facts": ["boarding podium center"],
            }
        ],
    }

    beats = [
        # Beat 1: OTS Marcus + Karen in CH01 (pilot shirt)
        {
            "beat_id": "B01",
            "chapter_id": "CH01",
            "location": "LOC_GATE",
            "speaker": "Marcus",
            "characters_present": ["CHAR_MARCUS", "CHAR_KAREN"],
            "framing": "Over-the-shoulder Medium Shot",
            "dialogue": "Check my dispatch release.",
        },
        # Beat 2: OTS Marcus + CEO in CH01 -> MUST NOT collide with Marcus + Karen keyframe!
        {
            "beat_id": "B02",
            "chapter_id": "CH01",
            "location": "LOC_GATE",
            "speaker": "Marcus",
            "characters_present": ["CHAR_MARCUS", "CHAR_CEO"],
            "framing": "Over-the-shoulder Medium Shot",
            "dialogue": "Good morning sir.",
        },
        # Beat 3: CEO speaking in CH02 with scene-level gaze override ("looking screen-left")
        {
            "beat_id": "B03",
            "chapter_id": "CH02",
            "location": "LOC_GATE",
            "speaker": "David",
            "characters_present": ["CHAR_CEO", "CHAR_MARCUS"],
            "framing": "Medium Shot",
            "gaze": "looking screen-left",
            "camera_angle": "low-angle",
            "dialogue": "Captain Marcus is cleared to command.",
        },
        # Beat 4: Marcus single MCU in CH01 vs CH02 -> different wardrobe must produce distinct keyframe_key!
        {
            "beat_id": "B04",
            "chapter_id": "CH01",
            "location": "LOC_GATE",
            "speaker": "Marcus",
            "characters_present": ["CHAR_MARCUS"],
            "framing": "Medium Close-up",
            "dialogue": "Thank you.",
        },
        {
            "beat_id": "B05",
            "chapter_id": "CH02",
            "location": "LOC_GATE",
            "speaker": "Marcus",
            "characters_present": ["CHAR_MARCUS"],
            "framing": "Medium Close-up",
            "dialogue": "Justice prevailed.",
        },
    ]

    manifest = ScreenplayCompiler.compile_shots(bible, beats, anchors_dir=anchors)
    s1, s2, s3, s4, s5 = manifest["shots"]

    # 1. Multi-person cast disambiguation + secondary extra_refs populated
    assert s1["keyframe_key"] != s2["keyframe_key"]
    assert s1["keyframe_key"].endswith("__default")
    assert s2["keyframe_key"].endswith("__default")
    assert any("karen.png" in r for r in s1["extra_refs"])
    assert any("ceo.png" in r for r in s2["extra_refs"])

    # 2. Scene-level gaze override works for 3rd character
    assert s3["gaze"] == "looking screen-left"
    assert "looking screen-left" in s3["compiled_prompt"]
    assert "ang_low_angle" in s3["keyframe_key"]

    # 3. Wardrobe progression produces distinct keyframe keys and propagates into KeyframeComposer prompts
    assert s4["keyframe_key"] != s5["keyframe_key"]
    pdir = tmp_path
    planned = {
        it.kf_id: it.prompt
        for it in KeyframeComposer.plan_missing_scene_keyframes(bible, manifest, pdir)
    }
    assert "white pilot shirt with gold epaulets" in planned[s4["keyframe_key"]]
    assert "dark charcoal courtroom suit" in planned[s5["keyframe_key"]]
    assert "low-angle" in planned[s3["keyframe_key"]].lower()


def test_cinematography_pyramid_staging_and_coverage_lint_catches_monotony():
    # 12-beat scene staged through ScriptIngestor must keep MCU+CU <= 50%, 0 jump-cuts, and 0 warnings
    raw_beats = [
        {"beat_id": f"B{i:02d}", "chapter_id": "CH01", "location": "LOC_1",
         "speaker": "Marcus" if i % 2 == 1 else "Reyes",
         "characters_present": ["CHAR_MARCUS", "CHAR_REYES"],
         "dialogue": f"Line number {i} in tense precinct dialogue." if i > 1 else None,
         "action_summary": "Characters face each other across the counter."}
        for i in range(1, 13)
    ]
    bible, beats_doc = ScriptIngestor.sanitize_and_stage({
        "project_title": "Pyramid Staging",
        "characters": [
            {"id": "CHAR_MARCUS", "name": "Marcus", "look_verbatim": "65yo dignified Black veteran in olive jacket", "anchor_image": "m.png"},
            {"id": "CHAR_REYES", "name": "Reyes", "look_verbatim": "32yo precinct officer in dark navy uniform", "anchor_image": "r.png"},
        ],
        "locations": [{"id": "LOC_1", "name": "Precinct", "look_verbatim": "precinct front desk at night", "set_facts": ["counter center"]}],
        "beats": raw_beats,
    })
    manifest = ScreenplayCompiler.compile_shots(bible, beats_doc["beats"])
    assert manifest["coverage_warnings"] == []
    shots = manifest["shots"]
    assert shots[0]["allow_camera_motion"] is True
    cu_ratio = sum(1 for s in shots if "close" in s["framing"].lower()) / len(shots)
    assert cu_ratio <= 0.40

    # Bad manual manifest with 3 consecutive Close-ups + identical single framing jump-cut -> flagged!
    bad_shots = [
        {"shot_id": "S1", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C1", "framing": "Wide Shot", "is_multi_person": True},
        {"shot_id": "S2", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C1", "framing": "Close-up", "is_multi_person": False},
        {"shot_id": "S3", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C1", "framing": "Close-up", "is_multi_person": False},
        {"shot_id": "S4", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C2", "framing": "Close-up", "is_multi_person": False},
        {"shot_id": "S5", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C1", "framing": "Close-up", "is_multi_person": False},
        {"shot_id": "S6", "chapter_id": "CH01", "location": "LOC_1", "primary_character_id": "C2", "framing": "Close-up", "is_multi_person": False},
    ]
    warns = ScreenplayCompiler.audit_coverage(bad_shots)
    assert any("Quá 2 shot cận cảnh đặc tả" in w for w in warns)
    assert any("JUMP_CUT_30_DEG_WARNING" in w for w in warns)
    assert any("CLOSEUP_BUDGET_EXCEEDED" in w for w in warns)


def test_qc_moving_camera_fair_scoring_and_virtual_camera_rig(tmp_path: Path):
    # 1. Moving-camera QC score does not penalize intentional camera drift
    moving_qc = {
        "verdict": "PASS",
        "allow_camera_motion": True,
        "warnings": [],
        "metrics": {
            "spatial_continuity": {"span_grid_corr": 0.42, "has_internal_cut": False},
            "optical_flow": {"camera_drift_px": 58.0, "nod_range_pct": 8.0, "shake_range_pct": 6.0},
        },
    }
    score = FilmQCEngine.compute_take_quality_score(moving_qc)
    assert score >= 95.0

    # 2. Virtual Camera Rig renders drift_right, pull_out, handheld_subtle, push_in & pre-flashback fade-out cleanly
    import subprocess
    clips = {}
    for idx in range(1, 5):
        cp = tmp_path / f"raw_{idx}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=2.4",
                "-f", "lavfi", "-i", "sine=frequency=320:sample_rate=48000:duration=2.4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                "-c:a", "aac", "-ac", "2", "-shortest", str(cp),
            ],
            check=True,
            capture_output=True,
        )
        clips[f"SH0{idx}"] = cp

    manifest = {
        "project_title": "Virtual Camera Rig Test",
        "shots": [
            {"shot_id": "SH01", "chapter_id": "CH01", "location": "LOC_1", "post_camera_motion": "drift_right", "audio_mode": "SILENT_ACTION"},
            {"shot_id": "SH02", "chapter_id": "CH01", "location": "LOC_1", "post_camera_motion": "handheld_subtle", "audio_mode": "SILENT_ACTION"},
            {"shot_id": "SH03", "chapter_id": "CH02", "location": "LOC_1", "is_flashback": True, "post_camera_motion": "pull_out", "audio_mode": "SILENT_ACTION"},
            {"shot_id": "SH04", "chapter_id": "CH03", "location": "LOC_1", "post_camera_motion": "push_in", "audio_mode": "SILENT_ACTION"},
        ],
    }
    out_mp4 = tmp_path / "master_rig.mp4"
    rep = MasterAssembler.assemble_project(
        shots_manifest=manifest,
        clip_paths_by_shot=clips,
        output_mp4=out_mp4,
        export_stems=False,
    )
    assert rep["success"] is True
    ok_dec, msg = FilmQCEngine.verify_full_decode(out_mp4)
    assert ok_dec is True, msg


def test_security_zipslip_slot_kf_mapping_adaptive_batches_and_timestamp_rollover(tmp_path: Path):
    # 1. ZipSlip protection
    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../../escaped.txt", b"boom")
    unpacked_evil = BatchPackager.unpack_batch_result(evil_zip, tmp_path / "safe_out")
    assert unpacked_evil["verified"] is False
    assert any("ZipSlip" in e for e in unpacked_evil["errors"])
    assert not (tmp_path / "escaped.txt").exists()

    # 2. Keyframe slot_id (`kf_01.png`) -> `kf_id` mapping via kf_manifest.json
    kf_out = tmp_path / "kf_batch"
    BatchPackager.create_keyframe_handoff(
        "KFB01",
        [KeyframeItem(kf_id="LOC_CABIN__wide__CHAR_A__default", prompt="16:9 wide still")],
        kf_out,
    )
    sample_png = _make_16_9_png(tmp_path / "sample.png")
    kf_res_zip = kf_out / "KFB01_kf_result.zip"
    with zipfile.ZipFile(kf_res_zip, "w") as zf:
        zf.writestr("kf_01.png", sample_png.read_bytes())

    kf_unpacked = BatchPackager.unpack_keyframe_result(
        kf_res_zip,
        kf_out / "extracted",
        expected_kf_ids=["LOC_CABIN__wide__CHAR_A__default"],
        handoff_manifest_path=kf_out / "KFB01_kf_manifest.json",
    )
    assert kf_unpacked["verified"] is True
    assert "LOC_CABIN__wide__CHAR_A__default" in kf_unpacked["keyframes"]

    # 3. Adaptive batch sizing: 36 shots on 3 accounts -> 6; 8 retry shots on 4 accounts -> 2
    assert ParallelPoolEngine._compute_balanced_batch_size(36, 3, 6) == 6
    assert ParallelPoolEngine._compute_balanced_batch_size(12, 2, 6) == 6
    assert ParallelPoolEngine._compute_balanced_batch_size(8, 4, 6) == 2
    assert ParallelPoolEngine._compute_balanced_batch_size(3, 4, 6) == 1

    # 4. Filename & export stem sanitization + Animatic timestamp 59.9999s rollover
    assert _safe_filename("../../etc/passwd") == "passwd"
    assert ":" not in _safe_export_stem("Flight 214: The Final Stand?", "proj_1")
    assert AnimaticBuilder._format_srt_timestamp(59.9999) == "00:01:00,000"
    assert AnimaticBuilder._format_srt_timestamp(3599.9999) == "01:00:00,000"
