import json
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.screenplay_compiler import ScreenplayCompiler
from muse_studio.core.script_ingestor import ScriptIngestor


def _make_clean_16_9_png(path: Path, bg=(42, 68, 98), fg=(185, 145, 112)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1280, 720), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([110, 120, 530, 610], fill=fg)
    d.ellipse([730, 170, 1090, 530], fill=(95, 132, 178))
    img.save(path, format="PNG")
    return path


def test_ingestor_parses_screenplay_into_valid_bible_and_staged_beats(tmp_path: Path):
    script_text = """TITLE: THE FOUR-STAR PIN

INT. PRECINCT COUNTER LOBBY - NIGHT

Officer Reyes sits behind the scratched wooden desk holding a silver four-star pin under the fluorescent lamp. Marcus stands calmly across the counter.

REYES
This real, or you buy this online?

MARCUS
That belonged to my wife. She earned every star.

REYES
Wait right here while I run the serial number.

EXT. PRECINCT PARKING LOT - DAWN

Rain glistens on the asphalt outside the station doors. Marcus steps onto the walkway, fastening his olive canvas coat.

MARCUS
Time to go home.
"""
    script_file = tmp_path / "four_star_pin.txt"
    script_file.write_text(script_text, encoding="utf-8")
    proj_dir = tmp_path / "proj_screenplay"

    res = ScriptIngestor.ingest_file(
        input_path=script_file,
        project_dir=proj_dir,
        preset="drama_35mm",
        use_llm=False,
    )

    bible_path = proj_dir / "story_bible.json"
    beats_path = proj_dir / "beats.json"
    assert bible_path.exists()
    assert beats_path.exists()
    assert res["coverage"]["missing_dialogues"] == []

    bible = json.loads(bible_path.read_text(encoding="utf-8"))
    beats_payload = json.loads(beats_path.read_text(encoding="utf-8"))
    beats = beats_payload["beats"]

    char_names = {c["name"].upper() for c in bible["characters"]}
    assert "REYES" in char_names or any("REYES" in n for n in char_names)
    assert "MARCUS" in char_names or any("MARCUS" in n for n in char_names)

    anchor_names = [c["anchor_image"] for c in bible["characters"]]
    assert len(anchor_names) == len(set(anchor_names)), "Each character must get a unique anchor_image"

    # Seed clean anchor PNGs to verify full downstream ScreenplayCompiler + FilmQCEngine preflight compatibility
    anchors_dir = proj_dir / "assets" / "anchors"
    for idx, ch in enumerate(bible["characters"]):
        _make_clean_16_9_png(anchors_dir / ch["anchor_image"], bg=(40 + idx * 25, 65, 95))

    _, _, manifest = ScreenplayCompiler.compile_project_dir(proj_dir, audio_mode="native_drama")
    assert manifest["bible_warnings"] == []
    assert manifest["coverage_warnings"] == []

    ok_pre, findings = FilmQCEngine.validate_manifest_preflight(manifest)
    assert ok_pre is True, f"Expected 0 preflight errors, got: {findings}"

    spoken = [b.get("dialogue") for b in beats if b.get("dialogue")]
    assert "This real, or you buy this online?" in spoken
    assert "That belonged to my wife. She earned every star." in spoken
    assert "Time to go home." in spoken


def test_ingestor_parses_prose_and_srt_without_dropping_events(tmp_path: Path):
    prose_text = (
        "Inside the quiet cockpit at dawn, Captain Brianna checked the overhead panel. "
        "\"Fuel balance verified and beacon active,\" Brianna said calmly. "
        "First Officer Craig glanced at the dispatch tablet beside the throttle. "
        "\"Tower cleared us for Runway Two-Seven,\" Craig replied."
    )
    prose_file = tmp_path / "story.md"
    prose_file.write_text(prose_text, encoding="utf-8")
    prose_proj = tmp_path / "proj_prose"

    prose_res = ScriptIngestor.ingest_file(prose_file, prose_proj, use_llm=False)
    assert prose_res["coverage"]["missing_dialogues"] == []
    prose_beats = json.loads((prose_proj / "beats.json").read_text(encoding="utf-8"))["beats"]
    dialogues = " ".join(b.get("dialogue") or "" for b in prose_beats)
    assert "Fuel balance verified and beacon active" in dialogues
    assert "Tower cleared us for Runway Two-Seven" in dialogues

    srt_text = (
        "1\n00:00:01,000 --> 00:00:04,500\nBRI: Step away from the aircraft door right now.\n\n"
        "2\n00:00:05,000 --> 00:00:08,800\nCRAIG: Check my credentials before Touching the radio.\n"
    )
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(srt_text, encoding="utf-8")
    srt_proj = tmp_path / "proj_srt"

    srt_res = ScriptIngestor.ingest_file(srt_file, srt_proj, use_llm=False)
    assert srt_res["total_beats"] >= 2
    srt_bible = json.loads((srt_proj / "story_bible.json").read_text(encoding="utf-8"))
    assert ScreenplayCompiler.validate_story_bible(srt_bible, strict_files=False) == []


def test_ingestor_sanitizes_flawed_llm_json_for_axis_and_unique_anchors(tmp_path: Path):
    script_file = tmp_path / "mini.txt"
    script_file.write_text("ALICE\nHello Bob.\n\nBOB\nHello Alice.\n", encoding="utf-8")

    def flawed_llm(_prompt: str):
        return {
            "project_title": "Flawed LLM Output",
            "characters": [
                {"id": "CHAR_ALICE", "name": "Alice", "look_verbatim": "30yo woman in red blazer", "anchor_image": "same.png"},
                {"id": "CHAR_BOB", "name": "Bob", "look_verbatim": "35yo man in gray suit", "anchor_image": "same.png"},
            ],
            "locations": [
                {"id": "LOC_ROOM", "name": "Meeting Room", "look_verbatim": "glass conference room", "set_facts": ["table center"]}
            ],
            "beats": [
                {"beat_id": "B001", "chapter_id": "CH01", "location": "LOC_ROOM", "speaker": "Alice", "characters_present": ["CHAR_ALICE", "CHAR_BOB"], "framing": "Close-up", "gaze": "looking screen-right", "dialogue": "Hello Bob."},
                {"beat_id": "B002", "chapter_id": "CH01", "location": "LOC_ROOM", "speaker": "Alice", "characters_present": ["CHAR_ALICE", "CHAR_BOB"], "framing": "Close-up", "gaze": "looking screen-left", "dialogue": "Are you listening?"},
                {"beat_id": "B003", "chapter_id": "CH01", "location": "LOC_ROOM", "speaker": "Bob", "characters_present": ["CHAR_BOB", "CHAR_ALICE"], "framing": "Close-up", "dialogue": "Hello Alice."},
            ],
        }

    proj = tmp_path / "proj_llm"
    ScriptIngestor.ingest_file(script_file, proj, use_llm=True, llm_callable=flawed_llm)
    anchors_dir = proj / "assets" / "anchors"
    bible = json.loads((proj / "story_bible.json").read_text(encoding="utf-8"))
    for idx, ch in enumerate(bible["characters"]):
        _make_clean_16_9_png(anchors_dir / ch["anchor_image"], bg=(50 + idx * 30, 70, 90))

    _, _, manifest = ScreenplayCompiler.compile_project_dir(proj)
    assert manifest["bible_warnings"] == []
    assert manifest["coverage_warnings"] == []
    ok_pre, findings = FilmQCEngine.validate_manifest_preflight(manifest)
    assert ok_pre is True, f"Sanitizer must fix duplicate anchors, missing Wide shot, and 180-axis flip: {findings}"


def test_prompt_repair_hides_hands_on_hand_mutation_while_passing_preflight(tmp_path: Path):
    from muse_studio.core.prompt_repair_agent import PromptRepairAgent

    anchor = _make_clean_16_9_png(tmp_path / "anchor.png")
    shot = {
        "shot_id": "SHOT_001_CH01",
        "order": 1,
        "chapter_id": "CH01",
        "location": "LOC_DESK",
        "primary_character_id": "CHAR_REYES",
        "framing": "Medium Shot",
        "gaze": "looking screen-left",
        "dialogue": "Check this badge number.",
        "action_summary": "Officer Reyes holds the smartphone and badge in his hand.",
        "first_frame_path": str(anchor),
        "compiled_prompt": (
            "Image 1 is the exact first frame of the shot, Medium Shot, looking screen-left. "
            "Locked-off static tripod shot of exactly 10 seconds, in exactly 16:9 aspect ratio: "
            "the camera does not move, pan, tilt or zoom. "
            "[0.5-9s] Speaking directly in English, the character says verbatim: \"Check this badge number.\" "
            "Officer Reyes holds the smartphone and badge in his hand. "
            "Both hands clearly visible with five distinct fingers each, no extra fingers, no fused digits."
        ),
    }

    repaired = PromptRepairAgent.repair_shot(
        shot,
        defects=["DEFECT_ANATOMICAL_HAND_MUTATION: Phát hiện dị tật ngón tay."],
    )
    assert "chest-up" in repaired["framing"].lower()
    assert "out of frame" in repaired["compiled_prompt"].lower() or "below frame" in repaired["compiled_prompt"].lower()
    assert repaired["repair_attempts"] == 1

    ok, errs = FilmQCEngine.validate_shot_preflight(repaired)
    assert ok is True, f"Repaired shot must still pass preflight, got: {errs}"


def test_prompt_repair_cleans_stage_directions_and_heals_asr_and_freeze(tmp_path: Path):
    from muse_studio.core.prompt_repair_agent import PromptRepairAgent

    anchor = _make_clean_16_9_png(tmp_path / "anchor2.png")
    shot = {
        "shot_id": "SHOT_002_CH01",
        "order": 2,
        "chapter_id": "CH01",
        "location": "LOC_DESK",
        "primary_character_id": "CHAR_MARCUS",
        "framing": "Medium Close-up",
        "gaze": "looking screen-right",
        "dialogue": "(brief pause) That belonged to my wife. [sighs] She earned it.",
        "action_summary": "Marcus paces across the room turning sharply.",
        "first_frame_path": str(anchor),
        "compiled_prompt": (
            "Image 1 is the exact first frame of the shot, Medium Close-up, looking screen-right. "
            "Locked-off static tripod shot of exactly 10 seconds, in exactly 16:9 aspect ratio. "
            "[0.5-9s] Speaking directly in English, the character says verbatim: "
            "\"(brief pause) That belonged to my wife. [sighs] She earned it.\" "
            "Marcus paces across the room turning sharply. Hands stay naturally out of frame."
        ),
    }

    repaired = PromptRepairAgent.repair_shot(
        shot,
        defects=[
            "DEFECT_SPOKEN_STAGE_DIRECTION: AI đọc thành tiếng chỉ dẫn sân khấu ('brief pause').",
            "DEFECT_DIALOGUE_MISMATCH: WER 35% > 15%.",
            "DEFECT_PARTIAL_FREEZE: Nhân vật đơ cứng trong cửa sổ thoại.",
            "DEFECT_CAMERA_DRIFT: Camera tự lia 34px > 28px.",
        ],
    )
    assert "brief pause" not in repaired["dialogue"].lower()
    assert "[sighs]" not in repaired["dialogue"].lower()
    assert "brief pause" not in repaired["compiled_prompt"].lower()
    assert "that belonged to my wife. she earned it." in repaired["dialogue"].lower()
    assert "articulating every english word clearly" in repaired["compiled_prompt"].lower()
    assert "natural expressive facial" in repaired["compiled_prompt"].lower()
    assert "zero background translation" in repaired["compiled_prompt"].lower()

    ok, errs = FilmQCEngine.validate_shot_preflight(repaired)
    assert ok is True, f"Repaired ASR/freeze shot must pass preflight: {errs}"


def test_session_lock_blocks_live_concurrent_owner_and_recovers_stale_pid(tmp_path: Path):
    from muse_studio.core.autoprod_orchestrator import SessionConflictError, SessionLock

    proj_dir = tmp_path / "locked_proj"
    lock1 = SessionLock(proj_dir, session_tag="worker_A")
    lock1.acquire()
    try:
        lock2 = SessionLock(proj_dir, session_tag="worker_B")
        with pytest.raises(SessionConflictError, match="worker_A"):
            lock2.acquire()
    finally:
        lock1.release()

    # Simulate stale lock left behind by a crashed/non-existent process
    proj_dir.mkdir(parents=True, exist_ok=True)
    stale_file = proj_dir / ".autoprod.lock"
    stale_file.write_text(
        json.dumps({"pid": 99999991, "session_tag": "dead_worker", "started_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    lock3 = SessionLock(proj_dir, session_tag="recovered_worker")
    lock3.acquire()
    try:
        meta = json.loads(stale_file.read_text(encoding="utf-8"))
        assert meta["pid"] == os.getpid()
        assert meta["session_tag"] == "recovered_worker"
    finally:
        lock3.release()
    assert not stale_file.exists()


def test_busy_account_detector_skips_os_locked_and_busy_status_accounts(tmp_path: Path):
    from muse_studio.core.account_manager import AccountManager
    from muse_studio.core.autoprod_orchestrator import BusyAccountDetector

    profiles_dir = tmp_path / "profiles"
    storage_file = tmp_path / "accounts.json"
    mgr = AccountManager(storage_file=storage_file, profiles_dir=profiles_dir)

    a_locked = mgr.add_account(name="LockedByOtherPlaywright")
    a_busy_flag = mgr.add_account(name="MarkedBusyInJson")
    a_free = mgr.add_account(name="FreeReadyAcc")

    mgr.update_account(a_locked["id"], status="READY")
    mgr.update_account(a_busy_flag["id"], status="BUSY")
    mgr.update_account(a_free["id"], status="READY")

    locked_prof = profiles_dir / a_locked["id"]
    locked_prof.mkdir(parents=True, exist_ok=True)
    free_prof = profiles_dir / a_free["id"]
    free_prof.mkdir(parents=True, exist_ok=True)
    (free_prof / "lockfile").write_bytes(b"")  # Unlocked stale 0-byte lockfile (like closed Chrome)

    # Hold a real OS-level file handle open on a_locked/lockfile (matching live Chrome behavior)
    live_lock_path = locked_prof / "lockfile"
    with open(live_lock_path, "wb") as held_handle:
        avail, skipped = BusyAccountDetector.select_uncontended_ready_accounts(mgr)
        assert avail == [a_free["id"]]
        assert a_locked["id"] in skipped
        assert a_busy_flag["id"] in skipped
        _ = held_handle


def test_autoprod_end_to_end_from_raw_script_and_closed_loop_self_heal(tmp_path: Path):
    from muse_studio.autoprod import main as autoprod_main
    from muse_studio.core.account_manager import AccountManager
    from muse_studio.core.autoprod_orchestrator import AutoprodOrchestrator
    from muse_studio.core.video_processor import VideoProcessor

    # Part A: Full CLI Zero-Talk Script -> 1080p MP4 Master + SRT
    script_path = tmp_path / "night_shift.txt"
    script_path.write_text(
        "TITLE: NIGHT SHIFT\n\n"
        "INT. CONTROL TOWER - NIGHT\n\n"
        "Controller Elena watches the radar sweep across the glass console.\n\n"
        "ELENA\n"
        "Runway lights are green. Hold short of Bravo.\n\n"
        "PILOT DAN\n"
        "Holding short of Bravo, tower.\n",
        encoding="utf-8",
    )
    proj_dir = tmp_path / "night_shift_out"
    iso_accounts = tmp_path / "iso_accounts.json"
    iso_profiles = tmp_path / "iso_profiles"

    rc = autoprod_main([
        str(script_path),
        "--project-dir", str(proj_dir),
        "--preset", "drama_35mm",
        "--simulate",
        "--no-llm",
        "--no-ui-sync",
        "--accounts-file", str(iso_accounts),
        "--profiles-dir", str(iso_profiles),
    ])
    assert rc == 0

    master_mp4 = proj_dir / "MASTER_OUTPUT" / "final_master_1080p.mp4"
    master_srt = proj_dir / "MASTER_OUTPUT" / "final_master_1080p.srt"
    state_json = proj_dir / "autoprod_state.json"
    assert master_mp4.exists() and master_mp4.stat().st_size > 10000
    assert master_srt.exists()
    state = json.loads(state_json.read_text(encoding="utf-8"))
    assert state["status"] == "COMPLETED"

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(master_mp4),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    vstream = json.loads(probe.stdout)["streams"][0]
    assert int(vstream["width"]) == 1920
    assert int(vstream["height"]) == 1080

    # Part B: Closed-loop self-healing retry (Round 1 QC_REJECT -> PromptRepairAgent rewrites -> Round 2 PASS)
    heal_script = tmp_path / "heal.txt"
    heal_script.write_text(
        "INT. OFFICE - NIGHT\n\nMARCUS\n(brief pause) Check the silver badge.\n",
        encoding="utf-8",
    )
    heal_proj = tmp_path / "heal_proj"
    mgr = AccountManager(storage_file=tmp_path / "heal_acc.json", profiles_dir=tmp_path / "heal_prof")
    acc = mgr.add_account(name="Worker1")
    mgr.update_account(acc["id"], status="READY")

    prompts_seen_by_round = []

    class FakeSelfHealClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240, simulate=False):
            from muse_studio.core.headless_muse_client import HeadlessMuseClient
            return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True
            )

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480, simulate=False):
            prompts_seen_by_round.append([s.prompt for s in shots])
            output_dir = Path(output_dir)
            extract_dir = output_dir / "verified_clips"
            extract_dir.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, sh in enumerate(shots, start=1):
                mp4_p = extract_dir / f"shot_{idx:02d}.mp4"
                VideoProcessor.create_synthetic_test_clip(mp4_p, duration_s=4.0, text=sh.shot_id)
                verified[sh.shot_id] = {"path": str(mp4_p), "bytes": mp4_p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    eval_calls = {"count": 0}

    def fake_qc_eval(clip_path, shot_spec, min_duration_s=3.0, strip_output_path=None):
        eval_calls["count"] += 1
        if eval_calls["count"] == 1:
            return {
                "verdict": "REJECT",
                "shot_id": shot_spec["shot_id"],
                "defects_count": 2,
                "defects": [
                    "DEFECT_SPOKEN_STAGE_DIRECTION: AI đọc nhầm 'brief pause'.",
                    "DEFECT_ANATOMICAL_HAND_MUTATION: Lỗi ngón tay.",
                ],
                "warnings": [],
                "metrics": {},
            }
        return {
            "verdict": "PASS",
            "shot_id": shot_spec["shot_id"],
            "defects_count": 0,
            "defects": [],
            "warnings": [],
            "metrics": {"trim_window": {"trim_in_s": 0.0, "trim_out_s": 3.5, "trimmed_duration_s": 3.5}},
        }

    orch = AutoprodOrchestrator(
        account_manager=mgr,
        client_factory=FakeSelfHealClient,
        qc_evaluator=fake_qc_eval,
        sync_ui=False,
    )
    heal_res = orch.run(
        input_path=heal_script,
        project_dir=heal_proj,
        preset="drama_35mm",
        max_rounds=2,
        simulate=False,
        use_llm=False,
    )
    # Round 15: autoprod never sends for real (one production send path: pool_runner, whose closed-loop repair is
    # covered by the pool tests). Stages 1-2 run, then it refuses before touching any account or client.
    assert heal_res["status"] == "REFUSED_USE_POOL_RUNNER"
    assert "pool_runner keyframes" in heal_res["message"] and "pool_runner videos" in heal_res["message"]
    assert prompts_seen_by_round == [] and eval_calls["count"] == 0
    assert (heal_proj / "shots_manifest.json").exists()
