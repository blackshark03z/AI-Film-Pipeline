import json
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from muse_studio.cli import main as cli_main
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.batch_packager import BatchPackager, KeyframeItem, ShotItem, compute_sha256
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.master_assembler import MasterAssembler
from muse_studio.core.screenplay_compiler import ScreenplayCompiler, StoryBibleError
from muse_studio.core.tempmail_client import TempMailClient


def _make_clean_16_9_png(path: Path, bg=(40, 65, 95), fg=(180, 140, 110)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1280, 720), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 520, 600], fill=fg)
    d.ellipse([740, 180, 1080, 520], fill=(95, 130, 175))
    img.save(path, format="PNG")
    return path


def _make_dynamic_720p_clip(path: Path, duration_s: float = 4.0, freq: int = 440) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=24:duration={duration_s}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={duration_s}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-ac", "2", "-b:a", "192k",
        str(path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return path


def test_batch_packager_catches_missing_shot_04(tmp_path: Path):
    img = _make_clean_16_9_png(tmp_path / "anchor.png")
    shots = [
        ShotItem(shot_id=f"SHOT_00{i}", prompt="16:9 locked-off static tripod", first_frame_path=img)
        for i in range(1, 7)
    ]
    handoff_zip, _ = BatchPackager.create_batch_handoff("B06", shots, tmp_path / "handoff")

    # Tạo result zip thiếu shot_04 giống lỗi thực tế ở BATCH_06
    res_zip = tmp_path / "B06_result.zip"
    receipt_shots = []
    with zipfile.ZipFile(res_zip, "w") as zf:
        for i in [1, 2, 3, 5, 6]:
            payload = b"MP4_DATA_" + (b"x" * 120000)
            zf.writestr(f"shot_{i:02d}.mp4", payload)
            receipt_shots.append({
                "slot_id": f"shot_{i:02d}",
                "output_file": f"shot_{i:02d}.mp4",
                "sha256": compute_sha256(payload),
                "status": "ok",
            })
        zf.writestr(
            "batch_receipt.json",
            json.dumps({
                "batch_id": "B06",
                "shots": receipt_shots,
                "failed_shots": [{"shot_id": "shot_04", "status": "not_generated"}],
            }),
        )

    res = BatchPackager.unpack_batch_result(
        res_zip,
        tmp_path / "extracted",
        handoff_manifest_path=handoff_zip,
    )
    assert res["verified"] is False
    assert "SHOT_004" in res["missing_shots"]
    assert len(res["failed_shots"]) == 1
    assert len(res["verified_shots"]) == 5

    # Kiểm tra đóng gói retry từ danh sách thiếu
    retry_batches = BatchPackager.build_retry_batches(shots + [shots[0]], "B06", tmp_path / "retry")
    assert len(retry_batches) == 2
    assert len(retry_batches[0][3]) == 6
    assert len(retry_batches[1][3]) == 1


def test_screenplay_compiler_catches_duplicate_anchor_and_preserves_fields(tmp_path: Path):
    anchors = tmp_path / "assets" / "anchors"
    _make_clean_16_9_png(anchors / "brianna.png")
    _make_clean_16_9_png(anchors / "craig.png", bg=(60, 40, 40))

    bad_bible = {
        "project_title": "Test",
        "characters": [
            {"id": "CHAR_A", "name": "A", "look_verbatim": "Adult A", "anchor_image": "craig.png", "axis_gaze": "looking screen-right"},
            {"id": "CHAR_B", "name": "B", "look_verbatim": "Adult B", "anchor_image": "craig.png", "axis_gaze": "looking screen-left"},
        ],
        "locations": [{"id": "LOC_1", "name": "Jetbridge", "look_verbatim": "enclosed steel corridor", "set_facts": ["narrow 2m walkway"]}],
    }
    with pytest.raises(StoryBibleError, match="DUPLICATE_CHARACTER_ANCHOR"):
        ScreenplayCompiler.compile_shots(bad_bible, [], anchors_dir=anchors)

    good_bible = {
        "project_title": "Test",
        "characters": [
            {"id": "CHAR_A", "name": "Brianna", "look_verbatim": "40yo Black female pilot in crisp white uniform", "anchor_image": "brianna.png", "axis_gaze": "looking screen-right"},
            {"id": "CHAR_B", "name": "Craig", "look_verbatim": "48yo airport police officer in navy uniform", "anchor_image": "craig.png", "axis_gaze": "looking screen-left"},
        ],
        "locations": [
            {"id": "LOC_1", "name": "Jetbridge B14", "look_verbatim": "corrugated steel jetbridge tunnel at dawn", "set_facts": ["aircraft door at far right"]}
        ],
    }
    beats = [
        {
            "beat_id": "B001", "chapter_id": "CH01", "speaker": None,
            "characters_present": ["CHAR_A"], "location": "LOC_1",
            "framing": "Wide Shot", "action_summary": "Brianna walks steadily toward aircraft door.",
            "dialogue": None, "narration": "At 6:45 AM, Charlotte airport was tense.",
        },
        {
            "beat_id": "B002", "chapter_id": "CH01", "speaker": "Brianna",
            "characters_present": ["CHAR_A", "CHAR_B"], "location": "LOC_1",
            "framing": "Two-Shot", "action_summary": "Brianna taps screen on phone and holds badge firmly.",
            "dialogue": "I am Captain Johnson.", "narration": None,
        },
    ]

    manifest_native = ScreenplayCompiler.compile_shots(good_bible, beats, audio_mode="native_drama", anchors_dir=anchors)
    s1, s2 = manifest_native["shots"]
    assert "corrugated steel jetbridge tunnel at dawn" in s1["compiled_prompt"]
    assert s1["duration_s"] == 5.0
    assert s1["scene_card_overlay"] == "JETBRIDGE B14"
    assert "Lips remain completely closed" in s1["compiled_prompt"]

    # Two-shot không bị ép "Only this character in frame" và động tác "tap screen" được làm sạch
    assert "Only this character in frame" not in s2["compiled_prompt"]
    assert "tap screen" not in s2["compiled_prompt"].lower()
    assert "five distinct fingers" in s2["compiled_prompt"].lower()

    manifest_hybrid = ScreenplayCompiler.compile_shots(good_bible, beats, audio_mode="hybrid_narrated", anchors_dir=anchors)
    assert manifest_hybrid["shots"][0]["audio_mode"] == "HYBRID_VO"
    assert "Charlotte airport" in manifest_hybrid["shots"][0]["voiceover_text"]


def test_keyframe_composer_verify_and_contact_sheet(tmp_path: Path):
    good = _make_clean_16_9_png(tmp_path / "good.png")
    ok, errs, _ = KeyframeComposer.verify_keyframe_image(good)
    assert ok is True, errs

    flat = tmp_path / "flat.png"
    Image.new("RGB", (1280, 720), (120, 120, 120)).save(flat)
    ok_flat, errs_flat, _ = KeyframeComposer.verify_keyframe_image(flat)
    assert ok_flat is False
    assert any("FLAT_IMAGE" in e for e in errs_flat)

    bad_ar = tmp_path / "square.png"
    Image.new("RGB", (800, 800), (80, 100, 120)).save(bad_ar)
    ok_ar, errs_ar, _ = KeyframeComposer.verify_keyframe_image(bad_ar)
    assert ok_ar is False
    assert any("BAD_ASPECT_RATIO" in e for e in errs_ar)

    sheet = KeyframeComposer.build_contact_sheet([good, flat], tmp_path / "sheet.jpg", cols=2)
    assert sheet is not None and sheet.exists() and sheet.stat().st_size > 1000


def test_film_qc_engine_flicker_freeze_and_axis_preflight(tmp_path: Path):
    # 1. Preflight axis jump check
    manifest = {
        "shots": [
            {
                "shot_id": "S1", "order": 1, "chapter_id": "CH01", "location": "LOC_1",
                "primary_character_id": "CHAR_A", "gaze": "looking screen-right",
                "dialogue": "Hello.",
                "compiled_prompt": "16:9 locked-off static tripod shot. Says in English: Hello.",
            },
            {
                "shot_id": "S2", "order": 2, "chapter_id": "CH01", "location": "LOC_1",
                "primary_character_id": "CHAR_A", "gaze": "looking screen-left",
                "dialogue": "Wait.",
                "compiled_prompt": "16:9 locked-off static tripod shot. Says in English: Wait.",
            },
        ]
    }
    ok_pre, findings = FilmQCEngine.validate_manifest_preflight(manifest)
    assert ok_pre is False
    assert any("AXIS_JUMP_180" in f["error"] for f in findings)

    # 2. Gate 3 flicker / jump-cut (black -> bright white transition)
    flicker_clip = tmp_path / "flicker.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1.5:r=24",
        "-f", "lavfi", "-i", "color=c=white:s=1280x720:d=1.5:r=24",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=3.0",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        str(flicker_clip),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    res_flicker = FilmQCEngine.evaluate_generated_clip(flicker_clip, {"id": "FLK"}, min_duration_s=2.0)
    assert res_flicker["verdict"] == "REJECT"
    assert any("DEFECT_FLICKER_OR_JUMPCUT" in d for d in res_flicker["defects"])


def test_master_assembler_1080p_ebur128_and_single_tag(tmp_path: Path):
    c1 = _make_dynamic_720p_clip(tmp_path / "c1.mp4", duration_s=4.0, freq=440)
    c2 = _make_dynamic_720p_clip(tmp_path / "c2.mp4", duration_s=4.0, freq=520)

    bible = {
        "project_title": "Assemble Test",
        "characters": [
            {"id": "CHAR_BRIANNA", "name": "Brianna Johnson", "role": "Airline Captain", "axis_gaze": "looking screen-right"}
        ],
    }
    manifest = {
        "shots": [
            {
                "shot_id": "SH01", "chapter_id": "CH01", "location": "LOC_1",
                "primary_character_id": "CHAR_BRIANNA", "gaze": "looking screen-right",
                "speaker": "Brianna", "dialogue": "Welcome aboard.", "action_summary": "Brianna checks badge on counter.",
                "is_climax_closeup": False, "audio_mode": "NATIVE_DIALOGUE",
            },
            {
                "shot_id": "SH02", "chapter_id": "CH01", "location": "LOC_1",
                "primary_character_id": "CHAR_BRIANNA", "gaze": "looking screen-right",
                "speaker": "Brianna", "dialogue": "Ready for departure.", "action_summary": "Brianna speaks calmly.",
                "is_climax_closeup": True, "audio_mode": "NATIVE_DIALOGUE",
            },
        ]
    }

    out_mp4 = tmp_path / "out" / "master_1080p.mp4"
    rep = MasterAssembler.assemble_project(
        shots_manifest=manifest,
        clip_paths_by_shot={"SH01": c1, "SH02": c2},
        output_mp4=out_mp4,
        story_bible=bible,
        capcut_draft=True,
    )
    assert rep["success"] is True
    assert out_mp4.exists()
    assert Path(rep["sidecar_srt"]).exists()
    assert Path(rep["capcut_manifest"]).exists()
    assert rep["tagged_characters"] == ["CHAR_BRIANNA"]

    # Verify video/audio streams & loudness
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out_mp4)
    ], text=True))
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert int(v["width"]) == 1920 and int(v["height"]) == 1080
    assert v["r_frame_rate"] == "24/1"
    assert a["sample_rate"] == "48000"
    assert int(a["channels"]) == 2

    lufs = rep["ebur128"]["integrated_lufs"]
    assert lufs is not None and -17.0 <= lufs <= -15.0
    ok_dec, dec_msg = FilmQCEngine.verify_full_decode(out_mp4)
    assert ok_dec is True, dec_msg


def test_cli_pipeline_simulate_e2e(tmp_path: Path):
    pdir = tmp_path / "proj_sim"
    anchors = pdir / "assets" / "anchors"
    _make_clean_16_9_png(anchors / "brianna.png")

    (pdir / "story_bible.json").write_text(json.dumps({
        "project_title": "Sim Movie",
        "characters": [{
            "id": "CHAR_BRIANNA", "name": "Brianna", "role": "Captain",
            "look_verbatim": "40yo Black female pilot", "anchor_image": "brianna.png", "axis_gaze": "looking screen-right",
        }],
        "locations": [{
            "id": "LOC_CABIN", "name": "Forward Galley",
            "look_verbatim": "commercial airliner galley interior", "set_facts": ["cockpit door left"],
        }],
    }), encoding="utf-8")

    (pdir / "beats.json").write_text(json.dumps([
        {
            "beat_id": "B01", "chapter_id": "CH01", "speaker": None,
            "characters_present": ["CHAR_BRIANNA"], "location": "LOC_CABIN",
            "framing": "Wide Shot", "action_summary": "Brianna steps into galley.", "dialogue": None, "narration": "Morning flight.",
        }
    ]), encoding="utf-8")

    assert cli_main(["compile", str(pdir)]) == 0
    assert cli_main(["keyframes", str(pdir), "--simulate"]) == 0
    assert cli_main(["compile", str(pdir)]) == 0
    assert cli_main(["preflight", str(pdir)]) == 0
    assert cli_main(["run-pool", str(pdir), "--simulate"]) == 0
    out_master = pdir / "final_sim.mp4"
    assert cli_main(["assemble", str(pdir), "--output", str(out_master)]) == 0
    assert out_master.exists() and out_master.stat().st_size > 10000


def test_tempmail_snapshot_preserves_new_otp():
    # Mail arrives right after snapshot_seen_ids() before wait_for_otp_code() runs
    with patch.object(TempMailClient, "get_inbox") as mock_inbox:
        mock_inbox.side_effect = [
            {"mail_list": [{"mail_id": "100", "subject": "Old mail"}]},
            {"mail_list": [{"mail_id": "101", "subject": "Muse code 918273"}, {"mail_id": "100", "subject": "Old mail"}]},
        ]
        seen = TempMailClient.snapshot_seen_ids("a@merepost.com")
        otp = TempMailClient.wait_for_otp_code("a@merepost.com", timeout_seconds=5, check_interval=0.01, initial_seen_ids=seen)
        assert otp == "918273"


def test_asr_text_normalization_equivalences():
    import jiwer
    n = FilmQCEngine._normalize_asr_text
    assert n("Good morning, Mom. Gate B fourteen.") == n("Good morning mum. Gate B14.")
    assert n("One hundred forty-two passengers at six hundred hours.") == n("142 passengers at 600 hours.")
    assert n("Pre-flight walkaround on OCC crew portal.") == n("Preflight walk around on occrew portal.")
    assert n("Section 46,504.") == n("Section forty-six thousand five hundred and four.")
    d_ref = FilmQCEngine._to_digit_stream("Dispatch, verify FAA ATP certificate number seven-eight-one-niner-four, Captain Brianna Johnson.")
    d_hyp = FilmQCEngine._to_digit_stream("Dispatch, verify FAA ATP certificate number 781-904, Captain Brianna Johnson.")
    assert jiwer.wer(d_ref, d_hyp) <= 0.15


def test_internal_scene_cut_detected_by_histogram(tmp_path: Path):
    # Hai cảnh cùng độ sáng trung bình ~128 nhưng khác màu hoàn toàn (đỏ thuần -> xanh lam thuần)
    cut_clip = tmp_path / "internal_cut.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=#cc3333:s=1280x720:d=1.8:r=24",
        "-f", "lavfi", "-i", "color=c=#2277cc:s=1280x720:d=1.8:r=24",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=3.6",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        str(cut_clip),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    res = FilmQCEngine.evaluate_generated_clip(cut_clip, {"id": "CUT_TEST"}, min_duration_s=2.0)
    assert res["verdict"] == "REJECT"
    assert any("DEFECT_INTERNAL_SCENE_CUT" in d for d in res["defects"])


def test_account_usage_quota_parsing_and_api(tmp_path: Path):
    exhausted_txt = (
        "Settings\nGeneral\nUsage\nFree plan\n"
        "Weekly limit resets on Nov 22\n100% used\n"
        "Additional tokens\nNever expires\n100% used (0 tokens left)\nUpgrade\nLanguage"
    )
    q_ex = AccountManager.parse_usage_from_settings_text(exhausted_txt)
    assert q_ex is not None
    assert q_ex["is_exhausted"] is True
    assert q_ex["weekly_used_pct"] == 100.0
    assert q_ex["weekly_remaining_pct"] == 0.0
    assert q_ex["bonus_tokens_left"] == 0
    assert "Nov 22" in q_ex["reset_text"]

    active_txt = (
        "Usage\nPro plan\nWeekly limit resets on Nov 24\n35% used\n"
        "Additional tokens\nNever expires\n20% used (400 tokens left)\nUpgrade"
    )
    q_ok = AccountManager.parse_usage_from_settings_text(active_txt)
    assert q_ok is not None
    assert q_ok["is_exhausted"] is False
    assert q_ok["weekly_used_pct"] == 35.0
    assert q_ok["weekly_remaining_pct"] == 65.0
    assert q_ok["bonus_tokens_left"] == 400
    assert q_ok["plan"] == "Pro plan"

    bonus_1b_txt = (
        "Usage\nFree plan\nWeekly limit resets on Nov 25\n100% used\n"
        "Additional tokens\nNever expires\n0% used (1B tokens left)\nUpgrade"
    )
    q_1b = AccountManager.parse_usage_from_settings_text(bonus_1b_txt)
    assert q_1b is not None
    assert q_1b["is_exhausted"] is False
    assert q_1b["weekly_used_pct"] == 100.0
    assert q_1b["bonus_used_pct"] == 0.0
    assert q_1b["bonus_remaining_pct"] == 100.0
    assert q_1b["bonus_tokens_left"] == 1_000_000_000

    bonus_comma_txt = (
        "Usage\nFree plan\nWeekly limit resets on Nov 25\n100% used\n"
        "Additional tokens\nNever expires\n5% used (950,000,000 tokens left)\nUpgrade"
    )
    q_comma = AccountManager.parse_usage_from_settings_text(bonus_comma_txt)
    assert q_comma is not None
    assert q_comma["is_exhausted"] is False
    assert q_comma["bonus_tokens_left"] == 950_000_000
    assert q_comma["bonus_remaining_pct"] == 95.0

    mgr = AccountManager(storage_file=tmp_path / "accs.json", profiles_dir=tmp_path / "profiles")
    imp = mgr.bulk_import_accounts("CookiePool01|||session=xyz123|")
    assert imp["imported_count"] == 1
    acc = imp["accounts"][0]
    mgr.update_account(acc["id"], status="READY", usage_info=q_ok)
    reloaded = mgr.get_account(acc["id"])
    assert reloaded["usage_info"]["weekly_remaining_pct"] == 65.0
    assert reloaded["usage_info"]["bonus_tokens_left"] == 400

    vlock = mgr._get_verify_lock(acc["id"])
    assert vlock.acquire(blocking=False) is True
    try:
        dup_res = mgr.auto_login_and_verify(acc["id"])
        assert dup_res["status"] == "CHECKING"
    finally:
        vlock.release()


def test_srt_normalizer_and_coverage_gate(tmp_path: Path):
    from muse_studio.core.srt_normalizer import SRTNormalizer
    from muse_studio.core.keyframe_composer import KeyframeComposer
    from PIL import Image

    # Tạo SRT tổng dài 15 phút (900s) gồm 3 chương và câu CTA lẫn ở cuối
    cues_txt = [
        "1\n00:00:02,000 --> 00:00:08,000\n[clears throat] Opening confrontation on the aircraft jetbridge.\n",
        "2\n00:04:50,000 --> 00:04:58,000\nCaptain Brianna refuses to yield to false authority at Gate B14.\n",
        "3\n00:05:10,000 --> 00:05:18,000\nOfficer Craig inspects FAA credentials in the forward galley.\n",
        "4\n00:09:50,000 --> 00:09:58,000\nPassengers applaud as Flight 1128 prepares for departure.\n",
        "5\n00:10:20,000 --> 00:10:28,000\nViral video sparks FAA federal investigation under 49 USC 46504.\n",
        "6\n00:14:40,000 --> 00:14:52,000\nFederal Judge Katherine Moore sentences Pamela Davis cleanly.\n",
        "7\n00:14:52,000 --> 00:15:00,000\nLike, share, and subscribe. Remember, the people who refuse to see you today will hear your name tomorrow.\n",
        "8\n00:15:02,000 --> 00:15:08,000\nHit that like button and drop your answer below!\n",
    ]
    srt_p = tmp_path / "story.srt"
    srt_p.write_text("\n".join(cues_txt), encoding="utf-8")

    ch_p = tmp_path / "chapters.txt"
    ch_p.write_text(
        "00:00 - Confrontation\n05:00 - Escalation\n10:00 - Fallout & Sentencing\n",
        encoding="utf-8",
    )

    skel = SRTNormalizer.normalize_srt_to_beats_skeleton(srt_p, chapters_path=ch_p, window_s=22.0)
    joined_raw = " ".join(b["raw_text"] for b in skel["beats"]).lower()
    assert "[clears throat]" not in joined_raw
    assert "hit that like button" not in joined_raw
    assert "like, share, and subscribe" not in joined_raw
    assert "people who refuse to see you today" in joined_raw
    assert 895.0 <= skel["story_end_s"] <= 901.0

    # (a) Bản cắt cụt ở 09:58 thiếu Chapter 3 + tail + thời lượng -> FAIL HARD
    trunc_beats = [
        {"beat_id": f"B{i:03d}", "duration_s": 10.0, "source_start_s": i * 35.0, "source_end_s": (i + 1) * 35.0}
        for i in range(16)
    ]
    bad_cov = SRTNormalizer.audit_srt_coverage(srt_p, trunc_beats, chapters_path=ch_p)
    assert bad_cov["passed"] is False
    assert any("UNCOVERED_SRT_TAIL" in e for e in bad_cov["errors"])
    assert any("UNCOVERED_SRT_CHAPTER" in e for e in bad_cov["errors"])

    # (b) Bản phủ đủ 00:00 -> 15:00 qua đủ 3 chương (~265s >= 252s) -> PASS
    full_beats = [
        {"beat_id": f"B{i:03d}", "duration_s": 10.0, "source_start_s": i * 24.5, "source_end_s": min(900.0, (i + 1) * 24.5)}
        for i in range(37)
    ]
    good_cov = SRTNormalizer.audit_srt_coverage(srt_p, full_beats, chapters_path=ch_p)
    assert good_cov["passed"] is True, good_cov["errors"]
    assert all(ch["covered"] for ch in good_cov["chapter_coverage"])

    # (c) Kiểm tra KeyframeComposer.plan_missing_scene_keyframes tôn trọng keyframes_index.json
    kf_dir = tmp_path / "assets" / "keyframes"
    kf_dir.mkdir(parents=True, exist_ok=True)
    reusable = kf_dir / "kf_custom.png"
    Image.new("RGB", (640, 360), (40, 80, 120)).save(reusable)
    # Bảo đảm vượt MIN_IMAGE_BYTES (5KB)
    reusable.write_bytes(reusable.read_bytes() + b"\x00" * 6000)
    (kf_dir / "keyframes_index.json").write_text(
        json.dumps({"LOC_TEST__wide_shot__CHAR_A__default": str(reusable)}),
        encoding="utf-8",
    )
    planned = KeyframeComposer.plan_missing_scene_keyframes(
        bible={"characters": [{"id": "CHAR_A"}], "locations": [{"id": "LOC_TEST", "look_verbatim": "test"}]},
        manifest={
            "shots": [
                {
                    "shot_id": "S01",
                    "keyframe_key": "LOC_TEST__wide_shot__CHAR_A__default",
                    "location": "LOC_TEST",
                    "primary_character_id": "CHAR_A",
                    "characters_present": ["CHAR_A"],
                }
            ]
        },
        project_dir=tmp_path,
    )
    assert planned == []



