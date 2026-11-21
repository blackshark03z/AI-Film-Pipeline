import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from muse_studio.core.account_manager import AccountManager
from muse_studio.core.headless_muse_client import QuotaExceededException
from muse_studio.core.video_processor import VideoProcessor
from muse_studio.pool_runner import main as pool_runner_main
from muse_studio.core.parallel_pool_engine import ParallelPoolEngine


def _make_clean_16_9_png(path: Path, bg=(42, 68, 98), fg=(185, 145, 112)) -> Path:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    noise = rng.integers(25, 70, size=(720, 1280, 3), dtype=np.uint8)
    img = Image.fromarray(noise, mode="RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([110, 120, 530, 610], fill=fg)
    d.ellipse([730, 170, 1090, 530], fill=bg)
    img.save(path, format="PNG")
    return path


def _seed_manifest_project(proj_dir: Path, num_shots: int) -> Path:
    proj_dir.mkdir(parents=True, exist_ok=True)
    anchor = _make_clean_16_9_png(proj_dir / "assets" / "anchors" / "lead.png")
    bible = {
        "project_title": "Parallel Nx6 Test",
        "characters": [
            {
                "id": "CHAR_LEAD",
                "name": "Lead",
                "look_verbatim": "A 40-year-old realistic lead character in dark coat",
                "anchor_image": "lead.png",
                "axis_gaze": "looking screen-right",
            }
        ],
        "locations": [
            {
                "id": "LOC_HQ",
                "name": "Command Room",
                "look_verbatim": "dimly lit operations room at night",
                "set_facts": ["console desk in center"],
            }
        ],
    }
    (proj_dir / "story_bible.json").write_text(json.dumps(bible, indent=2), encoding="utf-8")

    shots = []
    for i in range(1, num_shots + 1):
        shots.append({
            "shot_id": f"SHOT_{i:03d}_CH01",
            "order": i,
            "chapter_id": "CH01",
            "location": "LOC_HQ",
            "primary_character_id": "CHAR_LEAD",
            "duration_s": 5.0,
            "framing": "Wide Establishing Shot" if i == 1 else "Medium Shot",
            "gaze": "looking screen-right",
            "speaker": None,
            "dialogue": None,
            "audio_mode": "SILENT_ACTION",
            "action_summary": "Character observes the screen calmly.",
            "first_frame_path": str(anchor),
            "compiled_prompt": (
                "Image 1 is the exact first frame, Medium Shot, looking screen-right. "
                "Locked-off static tripod shot of exactly 5 seconds, in exactly 16:9 aspect ratio. "
                "Hands stay naturally out of frame."
            ),
        })
    manifest = {"project_title": "Parallel Nx6 Test", "total_shots": num_shots, "shots": shots}
    (proj_dir / "shots_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return proj_dir


def test_pool_runner_enforces_exact_n_accounts_times_6_concurrent_throughput(tmp_path: Path):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    locked_acc = mgr.add_account(name="BusySessionAcc")
    mgr.update_account(locked_acc["id"], status="READY")
    locked_dir = tmp_path / "profiles" / locked_acc["id"]
    locked_dir.mkdir(parents=True, exist_ok=True)

    free_ids = []
    for idx in range(6):
        a = mgr.add_account(name=f"Worker_{idx + 1}")
        mgr.update_account(a["id"], status="READY")
        free_ids.append(a["id"])

    proj_dir = _seed_manifest_project(tmp_path / "proj_36", num_shots=36)
    seed_mp4 = tmp_path / "seed.mp4"
    VideoProcessor.create_synthetic_test_clip(seed_mp4, duration_s=3.5, text="OK")
    seed_bytes = seed_mp4.read_bytes()

    telemetry = {
        "in_flight_batches": 0,
        "peak_batches": 0,
        "in_flight_shots": 0,
        "peak_shots": 0,
        "accounts_used": set(),
        "batch_sizes": [],
    }

    class ConcurrencyProbeClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480, simulate=False):
            telemetry["in_flight_batches"] += 1
            telemetry["in_flight_shots"] += len(shots)
            telemetry["peak_batches"] = max(telemetry["peak_batches"], telemetry["in_flight_batches"])
            telemetry["peak_shots"] = max(telemetry["peak_shots"], telemetry["in_flight_shots"])
            telemetry["accounts_used"].add(account_id)
            telemetry["batch_sizes"].append(len(shots))
            await asyncio.sleep(0.08)
            telemetry["in_flight_batches"] -= 1
            telemetry["in_flight_shots"] -= len(shots)

            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(seed_bytes)
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    def fast_pass_qc(clip_path, shot_spec, min_duration_s=3.0, strip_output_path=None):
        return {"verdict": "PASS", "shot_id": shot_spec["shot_id"], "defects": [], "warnings": [], "metrics": {}}

    # Hold OS lock on locked_acc/lockfile just like another live Chrome session
    with open(locked_dir / "lockfile", "wb") as held:
        engine = ParallelPoolEngine(
            account_manager=mgr,
            client_factory=ConcurrencyProbeClient,
            qc_evaluator=fast_pass_qc,
            sync_ui=False,
        )
        res = engine.run_videos(project_dir=proj_dir, max_accounts=3, max_rounds=2, simulate=False)
        _ = held

    assert res["status"] == "COMPLETED"
    assert res["passed_count"] == 36
    assert locked_acc["id"] not in telemetry["accounts_used"], "OS-locked profile from other session must never be touched"
    assert telemetry["peak_batches"] == 3, f"Expected 3 accounts running concurrently, got {telemetry['peak_batches']}"
    assert telemetry["peak_shots"] == 18, f"Expected 3 accounts x 6 shots = 18 shots simultaneously, got {telemetry['peak_shots']}"
    assert len(telemetry["accounts_used"]) == 3, "Must cap concurrency strictly at granted max_accounts=3"
    assert all(sz == 6 for sz in telemetry["batch_sizes"])


def test_dynamic_queue_hot_swaps_standby_account_when_worker_hits_quota(tmp_path: Path):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    accs = []
    for idx in range(4):
        a = mgr.add_account(name=f"Acc_{idx + 1}")
        mgr.update_account(a["id"], status="READY")
        accs.append(a["id"])

    proj_dir = _seed_manifest_project(tmp_path / "proj_failover", num_shots=18)
    seed_mp4 = tmp_path / "seed2.mp4"
    VideoProcessor.create_synthetic_test_clip(seed_mp4, duration_s=3.5, text="OK")
    seed_bytes = seed_mp4.read_bytes()
    failing_acc = accs[0]
    used_accounts = set()

    class QuotaFailoverClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_videos_batch(self, account_id, shots, batch_id, output_dir, timeout_seconds=480, simulate=False):
            used_accounts.add(account_id)
            if account_id == failing_acc:
                self.account_manager.update_account(account_id, status="COOLDOWN")
                raise QuotaExceededException(f"{account_id} out of credits")
            await asyncio.sleep(0.04)
            out = Path(output_dir) / "verified_clips"
            out.mkdir(parents=True, exist_ok=True)
            verified = {}
            for idx, s in enumerate(shots, start=1):
                p = out / f"shot_{idx:02d}.mp4"
                p.write_bytes(seed_bytes)
                verified[s.shot_id] = {"path": str(p), "bytes": p.stat().st_size}
            return {"verified": True, "verified_shots": verified, "missing_shots": [], "failed_shots": []}

    engine = ParallelPoolEngine(
        account_manager=mgr,
        client_factory=QuotaFailoverClient,
        qc_evaluator=lambda cp, ss, **kw: {"verdict": "PASS", "shot_id": ss["shot_id"], "defects": [], "metrics": {}},
        sync_ui=False,
    )
    res = engine.run_videos(project_dir=proj_dir, max_accounts=2, max_rounds=1, simulate=False)

    assert res["status"] == "COMPLETED", "Standby account must hot-swap in and complete all 18 shots in Round 1"
    assert res["passed_count"] == 18
    assert len(used_accounts) == 3, "1 failed active + 1 healthy active + 1 hot-swapped standby = 3 accounts touched"


def test_keyframes_parallel_dispatches_n_accounts_times_4_images_simultaneously(tmp_path: Path):
    mgr = AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")
    for idx in range(4):
        a = mgr.add_account(name=f"KF_Worker_{idx + 1}")
        mgr.update_account(a["id"], status="READY")

    proj_dir = tmp_path / "proj_kf_12"
    proj_dir.mkdir(parents=True, exist_ok=True)
    bible = {
        "project_title": "12 Anchors Parallel",
        "characters": [
            {
                "id": f"CHAR_{i:02d}",
                "name": f"Char {i}",
                "look_verbatim": f"A {30 + i}-year-old realistic person in distinct jacket #{i}",
                "anchor_image": f"char_{i:02d}.png",
                "axis_gaze": "looking screen-right" if i % 2 == 0 else "looking screen-left",
            }
            for i in range(1, 13)
        ],
        "locations": [{"id": "LOC_1", "name": "Room", "look_verbatim": "realistic room", "set_facts": ["desk center"]}],
    }
    (proj_dir / "story_bible.json").write_text(json.dumps(bible, indent=2), encoding="utf-8")
    (proj_dir / "shots_manifest.json").write_text(json.dumps({"shots": []}), encoding="utf-8")

    kf_telemetry = {"in_flight": 0, "peak_in_flight": 0}

    class ParallelKFProbeClient:
        def __init__(self, account_manager):
            self.account_manager = account_manager

        async def generate_keyframes_batch(self, account_id, keyframes, batch_id, output_dir, timeout_seconds=240, simulate=False):
            from muse_studio.core.headless_muse_client import HeadlessMuseClient

            kf_telemetry["in_flight"] += 1
            kf_telemetry["peak_in_flight"] = max(kf_telemetry["peak_in_flight"], kf_telemetry["in_flight"])
            await asyncio.sleep(0.08)
            kf_telemetry["in_flight"] -= 1
            return await HeadlessMuseClient(self.account_manager).generate_keyframes_batch(
                account_id=account_id, keyframes=keyframes, batch_id=batch_id, output_dir=output_dir, simulate=True
            )

    engine = ParallelPoolEngine(account_manager=mgr, client_factory=ParallelKFProbeClient, sync_ui=False)
    rep = engine.run_keyframes(project_dir=proj_dir, max_accounts=3, simulate=False)

    assert kf_telemetry["peak_in_flight"] == 3, f"Expected 3 accounts x 4 images simultaneously, got {kf_telemetry['peak_in_flight']}"
    assert len(rep["anchors_generated"]) == 12
    assert rep["rejected"] == []


def test_pool_runner_cli_capacity_and_videos_commands(tmp_path: Path, capsys):
    acc_file = tmp_path / "cli_accounts.json"
    prof_dir = tmp_path / "cli_profiles"
    mgr = AccountManager(storage_file=acc_file, profiles_dir=prof_dir)
    for idx in range(3):
        a = mgr.add_account(name=f"CLI_Acc_{idx + 1}")
        mgr.update_account(a["id"], status="READY")

    rc_cap = pool_runner_main([
        "capacity",
        "--max-accounts", "2",
        "--accounts-file", str(acc_file),
        "--profiles-dir", str(prof_dir),
    ])
    assert rc_cap == 0
    cap_out = json.loads(capsys.readouterr().out)
    assert cap_out["granted_accounts"] == 2
    assert cap_out["parallel_video_shots_per_wave"] == 12
    assert len(cap_out["standby_account_ids"]) == 1

    proj_dir = _seed_manifest_project(tmp_path / "proj_cli_vid", num_shots=12)
    rc_vid = pool_runner_main([
        "videos",
        str(proj_dir),
        "--max-accounts", "2",
        "--simulate",
        "--no-ui-sync",
        "--accounts-file", str(acc_file),
        "--profiles-dir", str(prof_dir),
    ])
    assert rc_vid == 0
    audit = json.loads((proj_dir / "qc_audit_report.json").read_text(encoding="utf-8"))
    assert audit["passed_count"] == 12
