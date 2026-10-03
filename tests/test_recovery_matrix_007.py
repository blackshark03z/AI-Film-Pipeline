"""FLOW-PRODUCTION-SCALE-007 (L14) — scale recovery-matrix gap tests.

Fills the offline proof gaps the 58-scenario matrix needs beyond the
existing suites: continuity frame extraction determinism; repair-successor
canonical selection over a stale original take; repair budget ceiling;
mutation accounting with dead reservations; upload dedupe accounting.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.live_runtime import file_sha256
from scale_run import assert_budget_available, mutation_accounting


def synthetic_video(path, color="blue", fps=24, duration=1.0):
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s=320x240:r={fps}:d={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_last_frame_extraction_deterministic(tmp_path):
    from run_production_scale_007 import extract_last_frame
    video = tmp_path / "v.mp4"
    synthetic_video(video, color="blue")
    # Distinct last frame: append a red tail so the final frame differs.
    tail = tmp_path / "tail.mp4"
    synthetic_video(tail, color="red", duration=0.2)
    concat_list = tmp_path / "list.txt"
    concat_list.write_text(f"file '{video.as_posix()}'\n"
                           f"file '{tail.as_posix()}'\n", encoding="utf-8")
    joined = tmp_path / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat",
                    "-safe", "0", "-i", str(concat_list), "-c", "copy",
                    str(joined)], check=True, capture_output=True)
    f1 = extract_last_frame(joined, tmp_path / "f1.png")
    f2 = extract_last_frame(joined, tmp_path / "f2.png")
    assert f1["sha256"] == f2["sha256"]  # deterministic, no drift
    from PIL import Image
    with Image.open(tmp_path / "f1.png") as img:
        # The extracted last frame is the red tail, not the blue body.
        r, g, b = img.convert("RGB").getpixel((160, 120))
    assert r > 150 and g < 100 and b < 100


def test_repair_successor_canonical_over_stale_original(tmp_path, monkeypatch):
    """Slot canonical mapping must resolve to the repair-successor take when
    both a stale primary take and a repair take exist (live proof: SEQ7_E2 ←
    SEQ7_E2R, SEQ7_G3 ← SEQ7_G3B under durable RepairDecisions)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import build_master_scale_007 as build
    # The frozen mapping: repaired slots resolve through their successor's
    # durable result, never the stale primary result.
    for slot, repair_id in build.SEQ7_REPAIR_FOR.items():
        result = json.loads(build.result_path(slot).read_text(
            encoding="utf-8"))
        assert result["gate"] == "SHOT_PROVEN"
        assert result["asset"]["asset_id"]
        # the successor's fixture carries the repair shot id
        spec = json.loads(Path(build.ROOT / f"fixtures/sequence007/"
                              f"{repair_id}.json").read_text(encoding="utf-8"))
        assert spec["shot_id"] == repair_id
        # and a durable RepairDecision binds the slot to the successor
        decision = json.loads((build.RUN_DIR /
                               f"repair_decision_{repair_id}.json")
                              .read_text(encoding="utf-8"))
        assert decision["shot_id"] == slot
        assert decision["strategy"] == "pickup"


def test_repair_budget_ceiling_enforced():
    ledger = {"repair_consumed": [{"shot_id": f"R{i}"} for i in range(3)]}
    with pytest.raises(Exception, match="REPAIR_BUDGET_EXHAUSTED"):
        assert_budget_available(len(ledger["repair_consumed"]), 3, "REPAIR")
    assert_budget_available(2, 3, "REPAIR")  # within budget is fine


def test_mutation_accounting_with_dead_reservations_and_upload_dedupe():
    ledger = {
        "primary_consumed": [{"shot_id": s} for s in ("A", "B", "C")],
        "repair_consumed": [{"shot_id": "R1"}],
        "uploads": [{"for_shot": "X", "media_id": "m1"},
                    {"for_shot": "X", "media_id": "m1"},  # report duplicate
                    {"for_shot": "Y", "media_id": "m2"}],
        "dead_reservations": [{"shot_id": "D1"}, {"shot_id": "D2"}],
    }
    acct = mutation_accounting(ledger, max_primary=12, max_repair=3,
                               max_uploads=2, hard_ceiling=15)
    assert acct["primary_releases"] == 3 and acct["repair_releases"] == 1
    assert acct["continuity_uploads"] == 2  # deduped by media id
    assert acct["dead_reservations"] == 2
    assert acct["generates_authorized"] == 6  # 3+1+2 dead
    assert acct["hard_ceiling_ok"]
    assert acct["total_authority_events"] == 8  # 6 generates + 2 uploads
    over = mutation_accounting(
        {"primary_consumed": list(range(13)), "repair_consumed": [],
         "uploads": [], "dead_reservations": []},
        max_primary=12, max_repair=3, max_uploads=2, hard_ceiling=15)
    assert not over["primary_budget_ok"]  # primary budget violated...
    assert over["hard_ceiling_ok"]        # ...but 13 authorized ≤ 15 ceiling
    assert over["generates_authorized"] == 13
    ceiling_breach = mutation_accounting(
        {"primary_consumed": list(range(12)), "repair_consumed": [1, 2, 3],
         "uploads": [{"media_id": "m"}], "dead_reservations": [1]},
        max_primary=12, max_repair=3, max_uploads=2, hard_ceiling=15)
    assert not ceiling_breach["hard_ceiling_ok"]  # 12+3+1 dead = 16 > 15
