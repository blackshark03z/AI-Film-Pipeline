import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw

from muse_studio.cli import main as cli_main
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.delivery_packager import DeliveryPackager
from muse_studio.core.film_qc_engine import FilmQCEngine


def _make_textured_png(path: Path, bg=(42, 68, 96), fg=(190, 150, 110)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(17)
    arr = rng.integers(30, 80, size=(720, 1280, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([120, 110, 540, 620], fill=bg)
    d.ellipse([740, 160, 1100, 540], fill=fg)
    img.save(path, format="PNG")
    return path


def _make_take_clip(path: Path, drift_px: int = 0, duration_s: float = 2.6, freq: int = 380) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fps = 24
    n_frames = int(round(duration_s * fps))
    rng = np.random.default_rng(23)
    canvas = np.full((720, 1400, 3), (48, 58, 76), dtype=np.uint8)
    for _ in range(70):
        x = int(rng.integers(12, 1320))
        y = int(rng.integers(12, 650))
        cv2.rectangle(canvas, (x, y), (x + 36, y + 28), (110, 150, 195), -1)

    frames = []
    for i in range(n_frames):
        shift = int(round((drift_px * i) / max(1, n_frames - 1)))
        frm = canvas[:, shift : shift + 1280].copy()
        dx = int(round(14 * np.sin(2 * np.pi * i / 14.0)))
        cv2.rectangle(frm, (520 + dx, 410), (760 + dx, 680), (185, 145, 110), -1)
        frames.append(frm)

    raw = b"".join(f.tobytes() for f in frames)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1280x720", "-r", str(fps), "-i", "-",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={duration_s}",
        "-t", str(duration_s),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "12",
        "-c:a", "aac", "-ac", "2", "-b:a", "192k", "-shortest",
        str(path),
    ]
    subprocess.run(cmd, input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return path


def test_face_boxes_x_norm_bridge_between_qc_and_delivery():
    # Worker 2 produces x_norm/y_norm/w_norm/h_norm dicts inside metrics["actor_consistency"]["face_boxes"]
    qc_face_boxes = [{"x_norm": 0.65, "y_norm": 0.18, "w_norm": 0.20, "h_norm": 0.32}]
    # Face is on right half (center ~0.75) -> tag must choose left side (180) even if gaze says screen-right
    tag_x = DeliveryPackager.choose_face_aware_tag_x(qc_face_boxes, ref_width=1920, default_gaze="looking screen-right")
    assert tag_x == 180

    qc_left_face = [{"x_norm": 0.12, "y_norm": 0.18, "w_norm": 0.20, "h_norm": 0.32}]
    tag_x_right = DeliveryPackager.choose_face_aware_tag_x(qc_left_face, ref_width=1920, default_gaze="looking screen-left")
    assert tag_x_right == 1220


def test_cli_v4_end_to_end_animatic_multitake_qc_titles_stems_and_deliver(tmp_path: Path):
    pdir = tmp_path / "proj_v4_e2e"
    anchors = pdir / "assets" / "anchors"
    _make_textured_png(anchors / "brianna.png")

    bible = {
        "project_title": "Flight 1128 V4",
        "subtitle": "Based on Verified Events",
        "characters": [
            {
                "id": "CHAR_BRIANNA",
                "name": "Brianna Johnson",
                "role": "Airline Captain",
                "look_verbatim": "40yo Black female airline captain",
                "anchor_image": "brianna.png",
                "axis_gaze": "looking screen-right",
                "wardrobe_by_chapter": {
                    "CH01": "crisp white pilot uniform shirt with four gold bars",
                },
            }
        ],
        "locations": [
            {
                "id": "LOC_JETBRIDGE",
                "name": "Jetbridge B14",
                "look_verbatim": "enclosed corrugated steel airport jetbridge",
                "set_facts": ["aircraft boarding door at right"],
            }
        ],
        "props_ledger": [
            {
                "id": "prop_gold_wings_pin",
                "name": "Captain Wings Pin",
                "description": "polished gold captain wings lapel pin",
                "keywords": ["wings pin"],
            }
        ],
    }
    (pdir / "story_bible.json").write_text(json.dumps(bible), encoding="utf-8")

    beats = [
        {
            "beat_id": "B01",
            "chapter_id": "CH01",
            "speaker": None,
            "characters_present": ["CHAR_BRIANNA"],
            "location": "LOC_JETBRIDGE",
            "framing": "Wide Shot",
            "action_summary": "Brianna walks down the jetbridge wearing her wings pin.",
            "dialogue": None,
            "narration": "Six forty-five at Gate B14.",
        }
    ]
    (pdir / "beats.json").write_text(json.dumps(beats), encoding="utf-8")

    temp_mgr = AccountManager(storage_file=tmp_path / "accs.json", profiles_dir=tmp_path / "profiles")
    imp = temp_mgr.bulk_import_accounts("SimAcc|||session=abc|")
    temp_mgr.update_account(imp["accounts"][0]["id"], status="READY")

    with patch("muse_studio.cli.AccountManager", return_value=temp_mgr):
        # 1. Compile + Keyframes with --include-setups + Re-compile + Preflight
        assert cli_main(["compile", str(pdir)]) == 0
        assert cli_main(["keyframes", str(pdir), "--simulate", "--include-setups"]) == 0
        assert (pdir / "assets" / "setups" / "LOC_JETBRIDGE__master_plate.png").exists()
        assert cli_main(["compile", str(pdir)]) == 0
        assert cli_main(["preflight", str(pdir)]) == 0

        # 2. New CLI command: animatic
        anim_mp4 = pdir / "ANIMATIC" / "preview_v4.mp4"
        assert cli_main(["animatic", str(pdir), "--output", str(anim_mp4), "--fps", "12"]) == 0
        assert anim_mp4.exists() and anim_mp4.stat().st_size > 2000
        assert anim_mp4.with_suffix(".srt").exists()

        # 3. Multi-take qc-audit selects highest quality_score take (0px drift over 20px drift)
        b1 = pdir / "BATCHES_V2" / "B_DRIFT" / "verified_clips"
        b2 = pdir / "BATCHES_V2" / "B_STEADY" / "verified_clips"
        take_drift = _make_take_clip(b1 / "SHOT_001_CH01.mp4", drift_px=20, duration_s=2.7)
        take_steady = _make_take_clip(b2 / "SHOT_001_CH01.mp4", drift_px=0, duration_s=2.7)

        assert cli_main(["qc-audit", str(pdir), "--strips"]) == 0
        audit = json.loads((pdir / "qc_audit_report.json").read_text(encoding="utf-8"))
        assert audit["passed_count"] == 1
        shot_qc = audit["per_shot_qc"]["SHOT_001_CH01"]
        assert shot_qc["metrics"]["optical_flow"]["camera_drift_px"] < 5.0
        assert shot_qc["metrics"]["quality_score"] > 70.0

        # 4. Assemble with V4 flags (--with-titles --capcut-draft --color-mood cold_thriller)
        out_master = pdir / "MASTER_OUTPUT" / "v4_master.mp4"
        assert cli_main([
            "assemble", str(pdir),
            "--output", str(out_master),
            "--with-titles",
            "--capcut-draft",
            "--color-mood", "cold_thriller",
        ]) == 0
        assert out_master.exists()
        assert out_master.with_name("v4_master.me_stem.m4a").exists()
        assert out_master.with_name("v4_master.dialogue_stem.m4a").exists()
        assert out_master.with_name("v4_master.chapters.txt").exists()
        assert out_master.with_name("v4_master.i18n_template.json").exists()
        assert (pdir / "MASTER_OUTPUT" / "capcut_draft_v4_master" / "draft_content.json").exists()
        # With opening (2.5s) + shot (~2.7s) + credits (3.0s), duration must be >= 7.5s
        dur_out = float(FilmQCEngine.probe_clip(out_master)[0]["duration"])
        assert dur_out >= 7.5

        # 5. Standalone CLI command: deliver (builds Trailer + 9:16 Vertical Shorts + Poster)
        assert cli_main(["deliver", str(pdir), "--master", str(out_master)]) == 0
        kit_dir = out_master.parent / "DELIVERY_KIT"
        assert (kit_dir / "trailer_1080p.mp4").exists()
        assert (kit_dir / "shorts_vertical_9x16.mp4").exists()
        assert (kit_dir / "poster_1080p.png").exists()


def test_pool_runner_include_setups_and_prompt_repair_v4_defects(tmp_path: Path):
    from muse_studio.core.prompt_repair_agent import PromptRepairAgent
    from muse_studio.pool_runner import main as pool_main

    # 1. PromptRepairAgent handles v4 defects (LIPSYNC_FROZEN_MOUTH / SILENT_DIALOGUE_TRACK / VISUAL_IDENTITY_DRIFT)
    #    and preserves allow_camera_motion without forcing static tripod on motion-allowed shots
    shot_vent = {
        "shot_id": "SH_V4_REP",
        "framing": "Medium Shot",
        "dialogue": "Check the flight plan.",
        "compiled_prompt": "Locked-off static tripod shot in 16:9 aspect ratio. Brianna says: Check the flight plan.",
    }
    rep_vent = PromptRepairAgent.repair_shot(
        shot_vent,
        ["DEFECT_LIPSYNC_FROZEN_MOUTH", "DEFECT_SILENT_DIALOGUE_TRACK", "DEFECT_VISUAL_IDENTITY_DRIFT"],
    )
    assert "CLARIFY_ASR_LIPSYNC" in rep_vent["repair_history"][-1]["fixes"]
    assert "REINFORCE_REFERENCE_IDENTITY" in rep_vent["repair_history"][-1]["fixes"]
    assert "exact facial structure and wardrobe from image 1" in rep_vent["compiled_prompt"].lower()

    motion_shot = {
        "shot_id": "SH_DOLLY",
        "allow_camera_motion": True,
        "compiled_prompt": "Smooth slow dolly-in shot in 16:9 aspect ratio.",
    }
    rep_motion = PromptRepairAgent.repair_shot(motion_shot, ["DEFECT_FROZEN_VIDEO"])
    assert "locked-off static tripod" not in rep_motion["compiled_prompt"].lower()

    # 2. pool_runner keyframes --include-setups generates Master Location Plates in parallel
    pdir = tmp_path / "proj_pool_setups"
    pdir.mkdir(parents=True, exist_ok=True)
    _make_textured_png(pdir / "assets" / "anchors" / "lead.png")
    (pdir / "story_bible.json").write_text(
        json.dumps({
            "project_title": "Pool Setups",
            "characters": [{"id": "CHAR_1", "name": "Lead", "look_verbatim": "40yo pilot", "anchor_image": "lead.png"}],
            "locations": [{"id": "LOC_HANGAR", "name": "Hangar", "look_verbatim": "wide steel aircraft hangar"}],
        }),
        encoding="utf-8",
    )
    (pdir / "shots_manifest.json").write_text(json.dumps({"shots": []}), encoding="utf-8")

    accs_f = tmp_path / "pool_accs.json"
    accs_f.write_text("[]", encoding="utf-8")
    rc = pool_main([
        "keyframes", str(pdir),
        "--include-setups",
        "--simulate",
        "-n", "2",
        "--no-ui-sync",
        "--accounts-file", str(accs_f),
        "--profiles-dir", str(tmp_path / "pool_profiles"),
    ])
    assert rc == 0
    assert (pdir / "assets" / "setups" / "LOC_HANGAR__master_plate.png").exists()

