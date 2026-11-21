import asyncio
import inspect
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from muse_studio.core.account_manager import AccountManager
from muse_studio.core.headless_muse_client import HeadlessMuseClient
from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.screenplay_compiler import ScreenplayCompiler


def _make_textured_16_9_png(path: Path, bg=(38, 62, 92), fg=(185, 145, 105)) -> Path:
    """Create a clean >5KB 16:9 PNG passing KeyframeComposer.verify_keyframe_image."""
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    noise = rng.integers(25, 75, size=(720, 1280, 3), dtype=np.uint8)
    img = Image.fromarray(noise, mode="RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([100, 120, 540, 610], fill=bg)
    d.ellipse([720, 160, 1100, 540], fill=fg)
    img.save(path, format="PNG")
    return path


def test_dynamic_props_ledger_keywords_tokens_and_state_tracking(tmp_path: Path):
    anchors = tmp_path / "assets" / "anchors"
    _make_textured_16_9_png(anchors / "lead.png")

    bible = {
        "project_title": "Dynamic Props V4",
        "characters": [
            {
                "id": "CHAR_MARCUS",
                "name": "Marcus",
                "look_verbatim": "45yo investigator in charcoal trenchcoat",
                "anchor_image": "lead.png",
                "axis_gaze": "looking screen-right",
            }
        ],
        "locations": [
            {
                "id": "LOC_OFFICE",
                "name": "Archive Office",
                "look_verbatim": "wood-paneled archive office with brass desk lamp",
                "set_facts": ["mahogany desk center"],
            }
        ],
        "props_ledger": [
            {
                "id": "prop_brass_compass",
                "name": "Antique Brass Compass",
                "description": "heavy antique brass pocket compass",
                "keywords": ["compass", "lodestar"],
                "state_tracking": {
                    "CH01-CH02": "glass crystal intact",
                    "CH03": "cracked glass face",
                },
            },
            {
                "id": "prop_evidence_dossier",
                "name": "Classified Dossier",
                "description": "manila classified dossier with red wax seal",
            },
            {
                "id": "prop_court_gavel",
                "name": "Walnut Gavel",
                "description": "polished walnut ceremonial gavel",
                "state_tracking": {
                    "B003": "resting beside brass soundblock",
                },
            },
            {
                "id": "prop_badge",
                "name": "Federal Badge",
                "description": "gold shield federal investigator badge",
            },
        ],
    }

    beats = [
        {
            "beat_id": "B001",
            "chapter_id": "CH01",
            "speaker": None,
            "characters_present": ["CHAR_MARCUS"],
            "location": "LOC_OFFICE",
            "framing": "Medium Close-up",
            "action_summary": "Marcus inspects the lodestar under the desk lamp.",
            "dialogue": None,
            "narration": None,
        },
        {
            "beat_id": "B002",
            "chapter_id": "CH02",
            "speaker": "Marcus",
            "characters_present": ["CHAR_MARCUS"],
            "location": "LOC_OFFICE",
            "framing": "Medium Shot",
            "action_summary": "Marcus stands beside the cabinet.",
            "dialogue": "Every page inside that dossier proves the timeline.",
            "narration": None,
        },
        {
            "beat_id": "B003",
            "chapter_id": "CH04",
            "speaker": None,
            "characters_present": ["CHAR_MARCUS"],
            "location": "LOC_OFFICE",
            "framing": "Wide Shot",
            "action_summary": "Marcus pauses quietly near the window.",
            "dialogue": None,
            "narration": None,
        },
        {
            "beat_id": "B004",
            "chapter_id": "CH04",
            "speaker": None,
            "characters_present": ["CHAR_MARCUS"],
            "location": "LOC_OFFICE",
            "framing": "Close-up",
            "action_summary": "Marcus waits calmly.",
            "dialogue": None,
            "narration": "His federal credential gleamed in the hallway light.",
        },
        {
            "beat_id": "B005",
            "chapter_id": "CH05",
            "speaker": None,
            "characters_present": ["CHAR_MARCUS"],
            "location": "LOC_OFFICE",
            "framing": "Wide Shot",
            "action_summary": "Marcus exhales slowly.",
            "dialogue": None,
            "narration": None,
        },
    ]

    manifest = ScreenplayCompiler.compile_shots(bible, beats, anchors_dir=anchors)
    s1, s2, s3, s4, s5 = manifest["shots"]

    assert s1["keyframe_key"].endswith("__brass_compass")
    assert "glass crystal intact" in s1["compiled_prompt"]

    assert s2["keyframe_key"].endswith("__evidence_dossier")
    assert "manila classified dossier with red wax seal" in s2["compiled_prompt"]

    assert s3["keyframe_key"].endswith("__court_gavel")
    assert "resting beside brass soundblock" in s3["compiled_prompt"]

    assert s4["keyframe_key"].endswith("__badge")
    assert "gold shield federal investigator badge" in s4["compiled_prompt"]

    assert s5["keyframe_key"].endswith("__default")


def test_wardrobe_progression_by_chapter_and_override(tmp_path: Path):
    anchors = tmp_path / "assets" / "anchors"
    _make_textured_16_9_png(anchors / "brianna.png")

    verbatim = "40yo Black female pilot with neat shoulder-length braids"
    bible = {
        "project_title": "Wardrobe Progression",
        "characters": [
            {
                "id": "CHAR_BRIANNA",
                "name": "Brianna",
                "look_verbatim": verbatim,
                "anchor_image": "brianna.png",
                "axis_gaze": "looking screen-right",
                "wardrobe_by_chapter": {
                    "CH01": "crisp white captain shirt with four gold stripes",
                    "CH02": "tailored navy courtroom suit",
                },
            }
        ],
        "locations": [
            {
                "id": "LOC_1",
                "name": "Hallway",
                "look_verbatim": "modern marble corridor",
                "set_facts": [],
            }
        ],
    }

    beats = [
        {
            "beat_id": "B01",
            "chapter_id": "CH01",
            "characters_present": ["CHAR_BRIANNA"],
            "location": "LOC_1",
            "framing": "Wide Shot",
            "action_summary": "Brianna walks forward.",
        },
        {
            "beat_id": "B02",
            "chapter_id": "CH02",
            "characters_present": ["CHAR_BRIANNA"],
            "location": "LOC_1",
            "framing": "Medium Close-up",
            "action_summary": "Brianna stands composed.",
        },
        {
            "beat_id": "B03",
            "chapter_id": "CH02",
            "characters_present": ["CHAR_BRIANNA"],
            "location": "LOC_1",
            "framing": "Medium Shot",
            "wardrobe_override": "charcoal wool overcoat",
            "action_summary": "Brianna steps outside.",
        },
    ]

    manifest = ScreenplayCompiler.compile_shots(bible, beats, anchors_dir=anchors)
    s1, s2, s3 = manifest["shots"]

    assert verbatim in s1["compiled_prompt"]
    assert "Current scene wardrobe: crisp white captain shirt with four gold stripes." in s1["compiled_prompt"]

    assert verbatim in s2["compiled_prompt"]
    assert "Current scene wardrobe: tailored navy courtroom suit." in s2["compiled_prompt"]

    assert verbatim in s3["compiled_prompt"]
    assert "Current scene wardrobe: charcoal wool overcoat." in s3["compiled_prompt"]
    assert "tailored navy courtroom suit" not in s3["compiled_prompt"]


def test_camera_lens_lighting_and_flashback_metadata(tmp_path: Path):
    anchors = tmp_path / "assets" / "anchors"
    _make_textured_16_9_png(anchors / "lead.png")

    bible = {
        "project_title": "Cinematography & Flashback",
        "characters": [
            {
                "id": "CHAR_1",
                "name": "Elena",
                "look_verbatim": "34yo architect with silver-rimmed glasses",
                "anchor_image": "lead.png",
                "axis_gaze": "looking screen-right",
            }
        ],
        "locations": [
            {
                "id": "LOC_STUDIO",
                "name": "Design Studio",
                "look_verbatim": "industrial loft studio with concrete columns",
                "color_mood": "cool_daylight",
            }
        ],
    }

    beats = [
        {
            "beat_id": "B01",
            "chapter_id": "CH01",
            "characters_present": ["CHAR_1"],
            "location": "LOC_STUDIO",
            "framing": "Wide Shot",
            "action_summary": "Elena stands beside the drafting table.",
        },
        {
            "beat_id": "B02",
            "chapter_id": "CH02",
            "chapter_title": "CH02 - Early Flashback",
            "characters_present": ["CHAR_1"],
            "location": "LOC_STUDIO",
            "framing": "Medium Shot",
            "lens_mm": 85,
            "camera_angle": "low-angle",
            "lighting_mood": "moody chiaroscuro lighting",
            "camera_motion": "slow dolly-in",
            "action_summary": "Elena gazes at the miniature bridge model.",
        },
        {
            "beat_id": "B03",
            "chapter_id": "CH03",
            "characters_present": ["CHAR_1"],
            "location": "LOC_STUDIO",
            "framing": "Medium Close-up",
            "speaker": "Elena",
            "dialogue": "We rebuild the span from steel.",
            "camera_motion": "slow dolly-in",
            "action_summary": "Elena speaks with quiet resolve.",
        },
    ]

    manifest = ScreenplayCompiler.compile_shots(bible, beats, anchors_dir=anchors)
    s1, s2, s3 = manifest["shots"]

    # S1: Default static shot 1
    assert "Locked-off static tripod shot" in s1["compiled_prompt"]
    assert s1["allow_camera_motion"] is False
    assert s1["is_flashback"] is False
    assert s1["color_mood"] == "cool_daylight"
    assert s1["transition_in"] == "fade_in"

    # S2: Non-dialogue controlled camera motion + lens/angle/lighting + flashback
    assert s2["allow_camera_motion"] is True
    assert "slow dolly-in" in s2["compiled_prompt"].lower()
    assert "the camera does not move" not in s2["compiled_prompt"].lower()
    assert "85mm" in s2["compiled_prompt"].lower()
    assert "low-angle" in s2["compiled_prompt"].lower()
    assert "moody chiaroscuro lighting" in s2["compiled_prompt"].lower()
    assert s2["is_flashback"] is True
    assert s2["color_mood"] == "warm_flashback"
    assert s2["transition_in"] == "dissolve"

    # S3: Dialogue shot forces static lock, cut transition
    assert s3["allow_camera_motion"] is False
    assert "Locked-off static tripod shot" in s3["compiled_prompt"]
    assert s3["is_flashback"] is False
    assert s3["color_mood"] == "cool_daylight"
    assert s3["transition_in"] == "cut"


def test_directing_audit_d2_pingpong_and_d6_must_show():
    shots = [
        {
            "shot_id": "S01",
            "chapter_id": "CH01",
            "framing": "Wide Shot",
            "is_multi_person": False,
            "speaker": None,
            "dialogue": None,
            "action_summary": "Brianna enters the briefing room holding FAA certificate 781904.",
            "compiled_prompt": "Wide shot of Brianna with FAA certificate 781904.",
        },
        {
            "shot_id": "S02",
            "chapter_id": "CH01",
            "framing": "Medium Close-up",
            "is_multi_person": False,
            "speaker": "Brianna",
            "dialogue": "Good morning Officer.",
            "action_summary": "Brianna speaks.",
            "compiled_prompt": "MCU Brianna speaking.",
        },
        {
            "shot_id": "S03",
            "chapter_id": "CH01",
            "framing": "Medium Close-up",
            "is_multi_person": False,
            "speaker": "Craig",
            "dialogue": "Step aside please.",
            "action_summary": "Craig responds.",
            "compiled_prompt": "MCU Craig speaking.",
        },
        {
            "shot_id": "S04",
            "chapter_id": "CH01",
            "framing": "Close-up",
            "is_multi_person": False,
            "speaker": "Brianna",
            "dialogue": "Check the flight deck manifest.",
            "action_summary": "Brianna replies.",
            "compiled_prompt": "CU Brianna speaking.",
        },
    ]

    # Backward-compatible 1-arg call
    w_no_bible = ScreenplayCompiler.audit_coverage(shots)
    assert any(
        w.startswith("CH01: Cảnh hội thoại đa nhân vật thiếu góc chung (Two-Shot/OTS)")
        for w in w_no_bible
    )

    bible = {
        "must_show": [
            {"what": "FAA certificate 781904", "chapter_id": "CH01", "keywords": ["certificate", "781904"]},
            {"what": "Bodycam red recording light", "chapter_id": "CH01", "keywords": ["bodycam", "recording light"]},
            {"what": "Walnut gavel on soundblock"},
        ]
    }
    w_with_bible = ScreenplayCompiler.audit_coverage(shots, bible=bible)
    assert not any("FAA certificate 781904" in w for w in w_with_bible)
    assert "MUST_SHOW_UNCOVERED (CH01): Chưa có shot hiển thị chi tiết 'Bodycam red recording light'." in w_with_bible
    assert "MUST_SHOW_UNCOVERED (GLOBAL): Chưa có shot hiển thị chi tiết 'Walnut gavel on soundblock'." in w_with_bible


def test_keyframe_composer_location_plates_and_turnaround_refs(tmp_path: Path):
    pdir = tmp_path / "proj_kf_v4"
    dirs = KeyframeComposer.ensure_asset_dirs(pdir)

    p_default = _make_textured_16_9_png(dirs["anchors"] / "brianna.png", bg=(30, 50, 80))
    p_profile = _make_textured_16_9_png(dirs["anchors"] / "brianna_profile.png", bg=(50, 70, 90))
    p_3q = _make_textured_16_9_png(dirs["anchors"] / "brianna_3q.png", bg=(60, 80, 100))
    p_full = _make_textured_16_9_png(dirs["anchors"] / "brianna_full.png", bg=(70, 90, 110))
    _make_textured_16_9_png(dirs["anchors"] / "craig.png", bg=(80, 50, 50))

    bible = {
        "project_title": "Location Plates & Turnaround",
        "characters": [
            {
                "id": "CHAR_BRIANNA",
                "name": "Brianna",
                "look_verbatim": "40yo Black female airline captain",
                "anchor_image": "brianna.png",
                "turnaround_images": {
                    "profile": "brianna_profile.png",
                    "three_quarter": "brianna_3q.png",
                    "full_body": "brianna_full.png",
                },
                "axis_gaze": "looking screen-right",
            },
            {
                "id": "CHAR_CRAIG",
                "name": "Craig",
                "look_verbatim": "48yo airport officer",
                "anchor_image": "craig.png",
                "axis_gaze": "looking screen-left",
            },
        ],
        "locations": [
            {
                "id": "LOC_JETBRIDGE",
                "name": "Jetbridge B14",
                "look_verbatim": "corrugated steel jetbridge walkway",
                "set_facts": ["aircraft boarding door at right"],
            },
            {
                "id": "LOC_COCKPIT",
                "name": "Boeing 737 Cockpit",
                "look_verbatim": "modern Boeing 737 glass cockpit",
                "set_facts": ["dual yoke controls", "overhead panel"],
            },
        ],
    }

    # Pre-populate LOC_COCKPIT master plate so only LOC_JETBRIDGE is planned
    existing_cockpit_plate = _make_textured_16_9_png(dirs["setups"] / "LOC_COCKPIT__master_plate.png", bg=(25, 45, 65))
    missing_plates = KeyframeComposer.plan_missing_location_plates(bible, dirs["setups"])
    assert len(missing_plates) == 1
    assert missing_plates[0].kf_id == "LOC_JETBRIDGE__master_plate"
    assert "16:9 widescreen architectural master location plate, empty set with zero people, no characters in frame" in missing_plates[0].prompt
    assert "corrugated steel jetbridge walkway" in missing_plates[0].prompt
    assert "aircraft boarding door at right" in missing_plates[0].prompt

    manifest = {
        "shots": [
            {
                "shot_id": "S1",
                "keyframe_key": "LOC_COCKPIT__profile_shot__CHAR_BRIANNA__default",
                "location": "LOC_COCKPIT",
                "framing": "Profile Shot",
                "primary_character_id": "CHAR_BRIANNA",
                "characters_present": ["CHAR_BRIANNA"],
                "action_summary": "Brianna checks instrument panel.",
            },
            {
                "shot_id": "S2",
                "keyframe_key": "LOC_COCKPIT__ots_shot__CHAR_BRIANNA__default",
                "location": "LOC_COCKPIT",
                "framing": "Over-the-Shoulder OTS",
                "is_multi_person": True,
                "primary_character_id": "CHAR_BRIANNA",
                "characters_present": ["CHAR_BRIANNA", "CHAR_CRAIG"],
                "action_summary": "Brianna speaks across cockpit doorway.",
            },
            {
                "shot_id": "S3",
                "keyframe_key": "LOC_JETBRIDGE__wide_shot__CHAR_BRIANNA__default",
                "location": "LOC_JETBRIDGE",
                "framing": "Wide Shot",
                "primary_character_id": "CHAR_BRIANNA",
                "characters_present": ["CHAR_BRIANNA"],
                "action_summary": "Brianna walks down jetbridge.",
            },
            {
                "shot_id": "S4",
                "keyframe_key": "LOC_JETBRIDGE__mcu__CHAR_BRIANNA__default",
                "location": "LOC_JETBRIDGE",
                "framing": "Medium Close-up",
                "primary_character_id": "CHAR_BRIANNA",
                "characters_present": ["CHAR_BRIANNA"],
                "action_summary": "Brianna pauses calmly.",
            },
        ]
    }

    planned_kfs = {
        item.kf_id: item
        for item in KeyframeComposer.plan_missing_scene_keyframes(bible, manifest, pdir)
    }

    # S1: Profile turnaround + existing cockpit master plate
    assert p_profile in planned_kfs["LOC_COCKPIT__profile_shot__CHAR_BRIANNA__default"].reference_images
    assert existing_cockpit_plate in planned_kfs["LOC_COCKPIT__profile_shot__CHAR_BRIANNA__default"].reference_images

    # S2: OTS -> three_quarter turnaround + craig anchor + existing cockpit master plate
    assert p_3q in planned_kfs["LOC_COCKPIT__ots_shot__CHAR_BRIANNA__default"].reference_images
    assert existing_cockpit_plate in planned_kfs["LOC_COCKPIT__ots_shot__CHAR_BRIANNA__default"].reference_images

    # S3: Wide -> full_body turnaround (LOC_JETBRIDGE plate does not exist yet)
    assert p_full in planned_kfs["LOC_JETBRIDGE__wide_shot__CHAR_BRIANNA__default"].reference_images
    assert len(planned_kfs["LOC_JETBRIDGE__wide_shot__CHAR_BRIANNA__default"].reference_images) == 1

    # S4: MCU -> falls back to anchor_image
    assert p_default in planned_kfs["LOC_JETBRIDGE__mcu__CHAR_BRIANNA__default"].reference_images

    # Test end-to-end simulated generation with include_setups=True using isolated temp AccountManager
    (pdir / "story_bible.json").write_text(json.dumps(bible), encoding="utf-8")
    (pdir / "shots_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    mgr = AccountManager(storage_file=tmp_path / "temp_accs.json", profiles_dir=tmp_path / "temp_profiles")
    imp = mgr.bulk_import_accounts("SimAcc01|||session=sim123|")
    aid = imp["accounts"][0]["id"]
    mgr.update_account(aid, status="READY")
    client = HeadlessMuseClient(account_manager=mgr)

    rep = asyncio.run(
        KeyframeComposer.generate_and_verify_keyframes(
            project_dir=pdir,
            account_ids=[aid],
            client=client,
            simulate=True,
            include_setups=True,
        )
    )
    jetbridge_plate = dirs["setups"] / "LOC_JETBRIDGE__master_plate.png"
    assert jetbridge_plate.exists()
    assert str(jetbridge_plate) in rep["setups_generated"]
    assert (dirs["setups"] / "setups_contact_sheet.jpg").exists()


def test_animatic_builder_renders_hud_slate_srt_and_valid_mp4(tmp_path: Path):
    from muse_studio.core import animatic_builder
    from muse_studio.core.animatic_builder import AnimaticBuilder

    # Verify zero FFmpeg drawtext filter usage in AnimaticBuilder implementation
    src = inspect.getsource(animatic_builder)
    assert "drawtext" not in src

    pdir = tmp_path / "proj_animatic"
    pdir.mkdir(parents=True, exist_ok=True)
    frame1 = _make_textured_16_9_png(pdir / "assets" / "keyframes" / "shot1.png")

    (pdir / "story_bible.json").write_text(
        json.dumps({"project_title": "Animatic Test"}),
        encoding="utf-8",
    )
    manifest = {
        "project_title": "Animatic Test",
        "shots": [
            {
                "shot_id": "SHOT_001_CH01",
                "chapter_id": "CH01",
                "location_name": "Jetbridge B14",
                "framing": "Medium Close-up",
                "gaze": "looking screen-right",
                "speaker": "Brianna",
                "dialogue": "Check the flight manifest now.",
                "action_summary": "Brianna holds her ID badge steadily.",
                "duration_s": 1.4,
                "target_trim_duration_s": None,
                "first_frame_path": str(frame1),
            },
            {
                "shot_id": "SHOT_002_CH01",
                "chapter_id": "CH01",
                "location_name": "Forward Galley",
                "framing": "Wide Shot",
                "gaze": "looking screen-left",
                "speaker": None,
                "dialogue": None,
                "action_summary": "Craig steps back into the forward galley.",
                "duration_s": 5.0,
                "target_trim_duration_s": 1.2,
                "first_frame_path": str(pdir / "assets" / "keyframes" / "missing_slate.png"),
            },
        ],
    }
    (pdir / "shots_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    res = AnimaticBuilder.build_animatic(project_dir=pdir, fps=12)
    assert res["success"] is True
    assert res["shots_count"] == 2
    assert 2.3 <= float(res["duration_s"]) <= 3.0

    mp4_path = Path(res["animatic_mp4"])
    srt_path = Path(res["animatic_srt"])
    assert mp4_path == pdir / "ANIMATIC" / "animatic_preview.mp4"
    assert mp4_path.exists() and mp4_path.stat().st_size > 2000
    assert srt_path.exists()
    srt_text = srt_path.read_text(encoding="utf-8")
    assert "Check the flight manifest now." in srt_text

    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4_path)],
            text=True,
        )
    )
    v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert int(v_stream["width"]) == 1280
    assert int(v_stream["height"]) == 720
    assert v_stream["pix_fmt"] == "yuv420p"
    assert v_stream["r_frame_rate"] == "12/1"
    assert a_stream["sample_rate"] == "48000"
    assert int(a_stream["channels"]) == 2
