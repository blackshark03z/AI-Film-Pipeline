import asyncio
import json
import subprocess
import threading
import wave
from pathlib import Path
from time import perf_counter
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np
import pytest

from muse_studio import autoprod, cli, pool_runner
from muse_studio.core.account_manager import AccountManager
from muse_studio.core.cinema_audio_engine import CinemaAudioEngine
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.headless_muse_client import HeadlessMuseClient
from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.master_assembler import MasterAssembler
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine
from muse_studio.core.script_ingestor import ScriptIngestor


def _encode_clip(path: Path, source: str, duration: float) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", source, "-t", str(duration),
            "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", str(path),
        ],
        check=True,
    )
    return path


def test_v50_qc_engine_speed_and_in_memory_parity(tmp_path, monkeypatch):
    moving = _encode_clip(tmp_path / "moving.mp4", "testsrc2=size=1280x720:rate=24", 8)
    static = _encode_clip(tmp_path / "static.mp4", "color=c=gray:s=640x360:r=24", 8)

    def no_subprocess(*args, **kwargs):
        pytest.fail("The motion and flow gates must decode in memory")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    start = perf_counter()
    motion = FilmQCEngine.analyze_temporal_motion_and_freeze(moving)
    flow = FilmQCEngine.analyze_optical_flow(moving)
    elapsed = perf_counter() - start
    assert elapsed < 1.2, f"8-second 720p QC took {elapsed:.3f}s"
    assert motion["total_frames_sampled"] == 32
    assert motion["max_motion_energy"] >= motion["avg_motion_energy"] > 0.4
    assert not motion["is_frozen"] and not motion["has_flicker"] and not motion["has_black_out"]
    assert {"min_hist_corr", "hand_spike_time_s", "early_transition_cut_s"} <= motion.keys()
    assert flow["valid"] and flow["frames"] >= 32
    assert {"camera_drift_px", "nod_range_pct", "shake_range_pct"} <= flow.keys()
    assert FilmQCEngine.analyze_temporal_motion_and_freeze(static)["is_frozen"]


def test_v50_master_assembler_parallel_norm_and_color_stats(tmp_path, monkeypatch):
    red = _encode_clip(tmp_path / "red.mp4", "color=c=red:s=320x180:r=24", 1.0)
    blue = _encode_clip(tmp_path / "blue.mp4", "color=c=blue:s=320x180:r=24", 1.5)
    real_run = subprocess.run
    norm_barrier = threading.Barrier(2, timeout=15)
    second_finished = threading.Event()
    norm_completion = []

    def observe_ffmpeg(cmd, *args, **kwargs):
        if cmd[0] != "ffmpeg":
            return real_run(cmd, *args, **kwargs)
        if "-vframes" in cmd:
            pytest.fail("DI color measurement unexpectedly used the PNG fallback")
        output_name = Path(cmd[-1]).name
        if output_name not in {"norm_RED.mp4", "norm_BLUE.mp4"}:
            return real_run(cmd, *args, **kwargs)
        assert cmd[cmd.index("-threads") + 1] == "2"
        norm_barrier.wait()
        result = real_run(cmd, *args, **kwargs)
        if output_name == "norm_RED.mp4":
            assert second_finished.wait(timeout=15)
        norm_completion.append(output_name)
        if output_name == "norm_BLUE.mp4":
            second_finished.set()
        return result

    monkeypatch.setattr(subprocess, "run", observe_ffmpeg)
    y, r, g, b = MasterAssembler._measure_clip_color_stats(red)
    assert r > 245 and g < 10 and b < 10
    assert y == pytest.approx(0.299 * r + 0.587 * g + 0.114 * b)

    shots = [
        {"shot_id": "RED", "chapter_id": "CH01", "audio_mode": "SILENT_ACTION"},
        {"shot_id": "BLUE", "chapter_id": "CH02", "audio_mode": "SILENT_ACTION"},
    ]
    master = tmp_path / "master.mp4"
    report = MasterAssembler.assemble_project(
        {"shots": shots}, {"RED": red, "BLUE": blue}, master,
        enable_film_grain=False, enable_voice_timbre_lock=False, export_stems=False,
    )
    assert report["success"] and report["duration_s"] == pytest.approx(2.5, abs=0.15)
    assert norm_completion == ["norm_BLUE.mp4", "norm_RED.mp4"]
    cap = cv2.VideoCapture(str(master))
    try:
        for time_ms, expected_channel in [(250, 2), (1750, 0)]:
            cap.set(cv2.CAP_PROP_POS_MSEC, time_ms)
            ok, frame = cap.read()
            assert ok and np.argmax(frame.mean(axis=(0, 1))) == expected_channel
    finally:
        cap.release()


def test_v50_cinema_audio_deesser_and_jl_cut_window(tmp_path):
    assert "equalizer=f=6800:t=q:w=2.0:g=-2.2" in CinemaAudioEngine.build_dialogue_cleanup_af()
    sr = 48000
    source = tmp_path / "source.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setparams((2, 2, sr, 0, "NONE", "not compressed"))
        wav.writeframes(np.full((sr, 2), 10000, dtype="<i2").tobytes())

    stem = CinemaAudioEngine.build_dialogue_stem_with_jl_cuts(
        [{"wav_path": source, "pre_lap_wav": source, "post_lap_wav": source, "start_s": 1, "duration_s": 1}],
        3, tmp_path / "stem.wav", sr=sr,
    )
    with wave.open(str(stem), "rb") as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").reshape(-1, 2)[:, 0]
    pre_start, post_end = round(0.74 * sr), round(2.26 * sr)
    assert not np.any(samples[:pre_start]) and not np.any(samples[post_end:])
    assert samples[pre_start + round(0.03 * sr)] > 0
    assert samples[post_end - round(0.03 * sr)] > 0
    assert samples[sr - 1] == pytest.approx(4500, abs=3)
    assert samples[2 * sr] == pytest.approx(4500, abs=3)


def test_v50_warm_session_pool_lifecycle_and_adaptive_timeout(tmp_path):
    assert [HeadlessMuseClient.compute_adaptive_timeout(n) for n in (0, 1, 6, 100)] == [185, 185, 510, 600]
    assert [HeadlessMuseClient.compute_adaptive_timeout(n, False) for n in (0, 1, 4, 100)] == [125, 125, 230, 320]
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    external, active = [mgr.add_account(name=name)["id"] for name in ("external", "worker")]
    for aid in (external, active):
        mgr.update_account(aid, status="READY")
        mgr.get_profile_dir(aid).mkdir(parents=True, exist_ok=True)
    (mgr.get_profile_dir(external) / "SingletonLock").touch()

    clip = tmp_path / "result.mp4"
    clip.write_bytes(b"fake clip used by the injected QC evaluator")
    (tmp_path / "shots_manifest.json").write_text(json.dumps({"shots": [{
        "shot_id": "SHOT_001_CH01", "compiled_prompt": "test", "first_frame_path": str(clip),
    }]}), encoding="utf-8")

    pw, context = AsyncMock(), AsyncMock()
    page = Mock()
    page.is_closed.return_value = False
    dispatches = []

    class ProbeClient(HeadlessMuseClient):
        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480, simulate=False):
            assert self._keep_warm
            assert account_id == active and timeout_seconds == 185
            dispatches.append(account_id)
            flag = mgr.get_profile_dir(account_id) / "SingletonLock"
            if len(dispatches) == 1:
                flag.touch()
                self._warm_sessions[account_id] = (pw, context, page)
            else:
                assert account_id in self.warm_account_ids and flag.exists()
            return {"verified_shots": {shots[0].shot_id: {"path": str(clip)}}}

    client = ProbeClient(mgr)
    engine = ParallelPoolEngine(
        mgr, client_factory=lambda _: client, sync_ui=False,
        qc_evaluator=lambda *args, **kwargs: {"verdict": "PASS" if len(dispatches) == 2 else "REJECT"},
    )
    report = engine.run_videos(project_dir=tmp_path, max_accounts=1, auto_repair=False, max_rounds=2)
    assert report["status"] == "COMPLETED" and dispatches == [active, active]
    assert not client.warm_account_ids and not (tmp_path / ".autoprod.lock").exists()
    assert (mgr.get_profile_dir(external) / "SingletonLock").exists()
    context.close.assert_awaited_once()
    pw.stop.assert_awaited_once()

    events = []

    class FailingKeyframes:
        def enable_warm_pool(self, enabled):
            assert enabled
            self.sibling_started = asyncio.Event()

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240, simulate=False):
            if keyframes[0].kf_id == "first":
                await self.sibling_started.wait()
                raise RuntimeError("dispatch failed")
            self.sibling_started.set()
            try:
                await asyncio.Future()
            finally:
                events.append("sibling cancelled")

        async def close_all_sessions(self):
            events.append("pool closed")

    (tmp_path / "story_bible.json").write_text(json.dumps({"characters": [
        {"anchor_image": "first.png"}, {"anchor_image": "second.png"},
    ]}), encoding="utf-8")
    failing_engine = ParallelPoolEngine(mgr, client_factory=lambda _: FailingKeyframes(), sync_ui=False)
    with pytest.raises(RuntimeError, match="dispatch failed"):
        failing_engine.run_keyframes(project_dir=tmp_path, simulate=True, max_accounts=2)
    assert events == ["sibling cancelled", "pool closed"]
    assert not (tmp_path / ".autoprod.lock").exists()


def test_v50_turnarounds_and_cinematic_cutaways(tmp_path, monkeypatch):
    script = tmp_path / "script.json"
    cast = [
        {"id": "CHAR_MARA", "name": "Mara", "look_verbatim": "Mara has warm brown skin and wears a navy coat."},
        {"id": "CHAR_JULES", "name": "Jules", "look_verbatim": "Jules wears a linen jacket."},
    ]
    dialogue = {
        3: "Tomorrow, we decide whether to hand it over.",
        6: "The badge stays here.",
    }
    source_action = "The badge is face down on the table. Mara lifts the badge and puts it inside the drawer."
    directions = {
        3: {
            "kind": "reaction", "purpose": "Show Mara receiving the decision to wait.",
            "source_field": "dialogue", "source_excerpt": dialogue[3], "character_id": "CHAR_MARA",
        },
        6: {
            "kind": "state_insert", "purpose": "Establish where the badge remains before it is stored.",
            "source_field": "dialogue", "source_excerpt": dialogue[6], "prop_id": "PROP_BADGE",
        },
        8: {
            "kind": "source_action", "purpose": "Show the badge being put away once.",
            "source_field": "action_summary", "source_excerpt": source_action,
            "prop_id": "PROP_BADGE", "character_id": "CHAR_MARA",
            "before_state": "face down on the table", "after_state": "inside the drawer",
        },
    }
    script.write_text(json.dumps({
        "characters": cast,
        "locations": [{"id": "LOC_OFFICE", "name": "Office", "look_verbatim": "A dim office."}],
        "props_ledger": [{"id": "PROP_BADGE", "name": "badge", "state_tracking": {"B006": "face down on the table"}}],
        "beats": [
            {
                "beat_id": f"B{index:03d}", "speaker": cast[index % 2]["name"] if index != 8 else None,
                "location": "LOC_OFFICE", "characters_present": [char["id"] for char in cast],
                "dialogue": dialogue.get(index, f"This is dialogue line {index}.") if index != 8 else None,
                "source_start_s": index * 2.0, "source_end_s": index * 2.0 + 1.0,
                "staging": directions.get(index), "action_summary": source_action if index == 8 else None,
            }
            for index in range(1, 11)
        ],
    }), encoding="utf-8")
    project = tmp_path / "project"
    original = ScriptIngestor.ingest_file(script, project, use_llm=False)
    beats_path = Path(original["beats_path"])
    original_beats = beats_path.read_bytes()
    assert original["total_beats"] == 10
    assert cli.main(["compile", str(project), "--cinematic-cutaways"]) == 0
    assert beats_path.read_bytes() == original_beats
    manifest_path = project / "shots_manifest.json"
    initial_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shots = initial_manifest["shots"]
    cuts = [shot for shot in shots if shot.get("cutaway_type")]
    assert [(cut["staging"]["kind"], cut["lens_mm"], cut["target_trim_duration_s"]) for cut in cuts] == [
        ("reaction", 85, 2.5), ("state_insert", 100, 2.0), ("source_action", 100, 5.0),
    ]
    assert [shot["order"] for shot in shots] == list(range(1, 13))
    assert [shot["shot_id"] for shot in shots if shot["dialogue"]] == [
        beat["shot_id"] for beat in json.loads(original_beats)["beats"] if beat["dialogue"]
    ]
    assert cuts[0]["primary_character_id"] == "CHAR_MARA"
    assert "Keep hands out of frame for this reaction." in cuts[0]["compiled_prompt"]
    assert all(cut["audio_mode"] == "SILENT_ACTION" and not cut["dialogue"] for cut in cuts)
    assert "face down on the table" in cuts[1]["compiled_prompt"]
    assert "Keep all people, hands and faces out of frame." in cuts[1]["compiled_prompt"]
    assert "hovering" not in cuts[1]["compiled_prompt"]
    assert cuts[1]["primary_character_id"] is None
    assert cuts[2]["compiled_prompt"].count(source_action) == 1
    assert "Closing state: inside the drawer." in cuts[2]["compiled_prompt"]
    assert sum(shot["beat_id"] == "B008" for shot in shots) == 1
    assert cuts[2]["staging"]["source_beat_id"] == "B008"

    isolated_args = ["--accounts-file", str(tmp_path / "accounts.json"), "--profiles-dir", str(tmp_path / "profiles")]
    seen = {}
    generate = HeadlessMuseClient.generate_keyframes_batch

    async def capture_refs(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=None, simulate=False):
        for item in keyframes:
            seen[item.kf_id] = item
        return await generate(self, account_id, keyframes, batch_id, output_dir, timeout_seconds, simulate)

    monkeypatch.setattr(HeadlessMuseClient, "generate_keyframes_batch", capture_refs)
    command = ["keyframes", str(project), "--include-turnarounds", "--simulate", "--no-ui-sync", "-n", "2"]
    assert pool_runner.main(command + isolated_args) == 0
    bible_path = project / "story_bible.json"
    bible = json.loads(bible_path.read_text(encoding="utf-8"))
    anchors_dir = project / "assets" / "anchors"
    for char in bible["characters"]:
        anchor = anchors_dir / char["anchor_image"]
        assert char["turnaround_images"] == {
            angle: f"{anchor.stem}__{angle}.png" for angle in ("three_quarter", "full_body")
        }
        for angle, filename in char["turnaround_images"].items():
            assert (anchors_dir / filename).is_file()
            item = seen[Path(filename).stem]
            assert item.reference_images == [anchor]
            assert ("45-degree" if angle == "three_quarter" else "head to toe") in item.prompt
    wide_shot = next(shot for shot in shots if "wide" in shot["framing"].lower())
    assert any(path.name.endswith("__full_body.png") for path in seen[wide_shot["keyframe_key"]].reference_images)
    ots_shot = next(shot for shot in shots if "over-the-shoulder" in shot["framing"].lower())
    assert any(path.name.endswith("__three_quarter.png") for path in seen[ots_shot["keyframe_key"]].reference_images)
    state_frame = seen[cuts[1]["keyframe_key"]]
    assert not state_frame.reference_images
    assert "face down on the table" in state_frame.prompt
    assert "hover" not in state_frame.prompt
    macro_frame = seen[cuts[2]["keyframe_key"]]
    assert "All faces stay out of frame" in macro_frame.prompt
    assert "face down on the table" in macro_frame.prompt
    assert "warm brown skin" in macro_frame.prompt
    assert "Use Image 1 only to match the hand's skin tone and the sleeve" in macro_frame.prompt
    assert "Opening state: face down on the table" in macro_frame.prompt
    assert "inside the drawer" not in macro_frame.prompt
    mara = next(char for char in bible["characters"] if char["id"] == "CHAR_MARA")
    assert macro_frame.reference_images == [anchors_dir / mara["anchor_image"]]
    assert not KeyframeComposer.plan_missing_character_turnarounds(bible, anchors_dir)
    seen.clear()
    assert pool_runner.main(command + isolated_args) == 0
    assert not seen
    assert cli.main(["compile", str(project), "--cinematic-cutaways"]) == 0
    assert cli.main(["preflight", str(project)]) == 0

    resumed_project = tmp_path / "autoprod"
    autoprod_args = [
        str(script), "--project-dir", str(resumed_project), "--cinematic-cutaways", "--simulate",
        "--no-llm", "--no-ui-sync", "--stop-after-casting",
    ] + isolated_args
    assert autoprod.main(autoprod_args) == 0
    staged = json.loads((resumed_project / "beats.json").read_text(encoding="utf-8"))
    assert staged["total_beats"] == 12
    assert ScriptIngestor.inject_cinematic_cutaways(bible, staged["beats"]) == staged["beats"]
    assert autoprod.main(autoprod_args) == 0
    assert json.loads((resumed_project / "shots_manifest.json").read_text(encoding="utf-8"))["total_shots"] == 12
