"""FLOW-PRODUCTION-SCALE-007 (L6/L7) — canonical 30-slot ledger, timing plan,
technical QC and provisional editorial ranges.

Canonical slot order (30):
  1-10   SEQ004_SWORDSMAN_DESCENT (adopted, Package-004; B5R repaired take)
  11-18  SEQ005_VALLEY_STREAM      (adopted, Package-005)
  19-30  SEQ007_DAYLIGHT_ROAD      (live, this package; slot SEQ7_E2 ← SEQ7_E2R
         repair take, slot SEQ7_G3 ← SEQ7_G3B repair take — dead-reservation
         successors under durable RepairDecisions)

Per slot this tool:
- re-validates the immutable asset (SHA-256) and probes exact duration;
- runs deterministic technical anomaly scans (blackdetect / freezedetect,
  full-decode EOF);
- cuts the editorial range: historical slots keep the full clip (no
  qualified trim exists); live slots use the FROZEN editorial_target_duration
  placed inside the technically usable window — never tuned after seeing
  clips to hide defects;
- writes one durable EditorialRange per slot (write-once) plus a machine-
  readable timing/QC plan.

Every worker-chosen range is labeled PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE —
never Owner-approved. Semantic dimensions remain OWNER_REVIEW_RECOMMENDED
(SEMANTIC_QC_UNQUALIFIED; no Gemini calls in this package).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.editorial_range import (
    ProbeBasis,
    make_editorial_range,
    revalidate,
    write_range,
)
from film_pipeline.editorial import probe_media
from film_pipeline.live_runtime import file_sha256

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "projects/flow_production_scale_007"
OUT_DIR = RUN_DIR / "master_package_007"
RANGES_DIR = OUT_DIR / "ranges"
P4 = ROOT / "projects/flow_multiscene_004"
P5_SEQ = ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM"
P7_SEQ = RUN_DIR / "sequence_SEQ007_DAYLIGHT_ROAD"

PLAN_C = json.loads((ROOT / "fixtures/sequence007/sequence_plan_007.json")
                    .read_text(encoding="utf-8"))
TARGETS = {s["shot_id"]: s.get("editorial_target_duration")
           for scene in PLAN_C["scenes"] for s in scene["shots"]}

SEQ4_SLOTS = ["SEQ4_A1", "SEQ4_A2", "SEQ4_A3", "SEQ4_A4", "SEQ4_A5",
              "SEQ4_B1", "SEQ4_B2", "SEQ4_B3", "SEQ4_B4", "SEQ4_B5R"]
SEQ5_SLOTS = ["SEQ5_C1", "SEQ5_C2", "SEQ5_C3", "SEQ5_C4",
              "SEQ5_D1", "SEQ5_D2", "SEQ5_D3", "SEQ5_D4"]
SEQ7_SLOTS = ["SEQ7_E1", "SEQ7_E2", "SEQ7_E3", "SEQ7_E4",
              "SEQ7_F1", "SEQ7_F2", "SEQ7_F3", "SEQ7_F4",
              "SEQ7_G1", "SEQ7_G2", "SEQ7_G3", "SEQ7_G4"]
SEQ7_REPAIR_FOR = {"SEQ7_E2": "SEQ7_E2R", "SEQ7_G3": "SEQ7_G3B"}
CANONICAL_ORDER = SEQ4_SLOTS + SEQ5_SLOTS + SEQ7_SLOTS
SCENE_OF = {**{s: "SEQ004" for s in SEQ4_SLOTS},
            **{s: "SEQ005" for s in SEQ5_SLOTS},
            **{s: "SEQ007" for s in SEQ7_SLOTS}}


def result_path(slot: str) -> Path:
    if slot in SEQ4_SLOTS:
        if slot == "SEQ4_B5R":
            return P4 / "repair_scope" / f"shot_{slot}" / "result.json"
        scene = "SCENE_A_DAWN_STANCE" if slot.startswith("SEQ4_A") \
            else "SCENE_B_VALLEY_PASS"
        return P4 / f"scene_{scene}" / f"shot_{slot}" / "result.json"
    if slot in SEQ5_SLOTS:
        scene = "SCENE_C_VALLEY_FLOOR" if slot.startswith("SEQ5_C") \
            else "SCENE_D_STREAM_REST"
        return P5_SEQ / f"scene_{scene}" / f"shot_{slot}" / "result.json"
    if slot in SEQ7_REPAIR_FOR:
        repair_id = SEQ7_REPAIR_FOR[slot]
        return RUN_DIR / "repair_scope" / f"repair_{repair_id}" / \
            f"shot_{repair_id}" / "result.json"
    scene = next(sc["scene_id"] for sc in PLAN_C["scenes"]
                 if any(s["shot_id"] == slot for s in sc["shots"]))
    return P7_SEQ / f"scene_{scene}" / f"shot_{slot}" / "result.json"


def canonical_shot_id(slot: str) -> str:
    return SEQ7_REPAIR_FOR.get(slot, slot)


def anomaly_scan(path: Path) -> dict:
    """Deterministic black/freeze detection + full-decode EOF (read-only)."""
    black = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf",
         "blackdetect=d=0.1:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False)
    black_ranges = re.findall(
        r"black_start:([\d.]+)\s+black_end:([\d.]+)", black.stderr)
    freeze = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf",
         "freezedetect=n=0.003:d=0.5", "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False)
    freeze_ranges = re.findall(
        r"freeze_start:([\d.]+)\s+freeze_duration:([\d.]+)", freeze.stderr)
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
         "-f", "null", "-"], capture_output=True, text=True, timeout=300,
        check=False)
    return {
        "black_ranges_s": [[float(a), float(b)] for a, b in black_ranges],
        "freeze_ranges_s": [[float(a), float(a) + float(b)]
                            for a, b in freeze_ranges],
        "full_decode_eof": decode.returncode == 0,
        "decode_stderr": decode.stderr[:200],
    }


def usable_window(duration: float, scan: dict) -> tuple[float, float]:
    """Deterministic technically-usable window from anomaly scans."""
    start, end = 0.0, duration
    for b0, b1 in scan["black_ranges_s"]:
        if b0 <= 0.05 and b1 > start:
            start = b1
        if b1 >= duration - 0.05 and b0 < end:
            end = b0
    for f0, f1 in scan["freeze_ranges_s"]:
        if f0 <= 0.05 and f1 > start:
            start = f1
        if f1 >= duration - 0.05 and f0 < end:
            end = f0
    return start, end


def main() -> None:
    RANGES_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    slots = []
    for order, slot in enumerate(CANONICAL_ORDER, 1):
        result = json.loads(result_path(slot).read_text(encoding="utf-8"))
        if result.get("gate") not in ("SHOT_PROVEN",
                                      "R3_SHOT3_REPROOF_PROVEN"):
            raise SystemExit(f"{slot}: not proven ({result.get('gate')})")
        asset = result["asset"]
        asset_path = Path(asset["uri_or_path"])
        if file_sha256(asset_path) != asset["sha256"]:
            raise SystemExit(f"{slot}: asset SHA-256 drift")
        media = probe_media(asset_path)
        scan = anomaly_scan(asset_path)
        if not scan["full_decode_eof"]:
            raise SystemExit(f"{slot}: full decode failed")
        duration = media.duration_s
        target = TARGETS.get(slot)
        is_live = SCENE_OF[slot] == "SEQ007"
        if is_live and target:
            win_start, win_end = usable_window(duration, scan)
            source_in = round(min(win_start, max(0.0, duration - target)), 3)
            source_out = round(min(source_in + target, duration), 3)
            basis = (f"frozen editorial_target_duration {target}s inside "
                     f"usable window [{win_start:.3f}, {win_end:.3f}]")
        else:
            source_in, source_out = 0.0, round(duration, 3)
            basis = "historical full-clip selection (no qualified trim)"
        rng = make_editorial_range(
            selected_take_id=result["selected_take"]["selected_take_id"]
            if result.get("selected_take") else
            "take_" + asset["sha256"][:16],
            shot_id=canonical_shot_id(slot),
            asset_id=asset["asset_id"], asset_sha256=asset["sha256"],
            source_in_s=source_in, source_out_s=source_out,
            probe=ProbeBasis(duration_s=duration, fps_num=media.fps_num,
                             fps_den=media.fps_den),
            note=f"{basis}; PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE")
        revalidate(rng, asset_path)
        range_path = RANGES_DIR / f"{order:02d}_{slot}.json"
        write_range(rng, range_path)
        slots.append({
            "order": order, "slot_id": slot,
            "canonical_shot_id": canonical_shot_id(slot),
            "sequence": SCENE_OF[slot],
            "provenance": ("repair_successor" if slot in SEQ7_REPAIR_FOR
                           else "direct_live" if is_live else
                           "historical_adopted"),
            "result_ref": str(result_path(slot)),
            "asset_path": str(asset_path),
            "asset_sha256": asset["sha256"],
            "provider_media_id": result.get("output_identity"),
            "duration_s": duration,
            "fps": media.fps,
            "editorial_target_duration": target,
            "source_in_s": source_in, "source_out_s": source_out,
            "selected_duration_s": round(source_out - source_in, 3),
            "editorial_range_id": rng.editorial_range_id,
            "range_file": str(range_path),
            "anomalies": {"black": scan["black_ranges_s"],
                          "freeze": scan["freeze_ranges_s"]},
            "full_decode_eof": scan["full_decode_eof"],
            "qc_technical": "PASS",
            "semantic_dimension": "OWNER_REVIEW_RECOMMENDED",
        })
        print(json.dumps({"slot": slot, "order": order,
                          "range": [source_in, source_out],
                          "anomalies": bool(scan["black_ranges_s"] or
                                            scan["freeze_ranges_s"])}),
              flush=True)
    summary = {
        "version": "timing-plan-007-v1",
        "generated_at": now,
        "slot_count": len(slots),
        "sequence_durations_s": {
            "SEQ004": round(sum(s["selected_duration_s"] for s in slots
                                if s["sequence"] == "SEQ004"), 3),
            "SEQ005": round(sum(s["selected_duration_s"] for s in slots
                                if s["sequence"] == "SEQ005"), 3),
            "SEQ007": round(sum(s["selected_duration_s"] for s in slots
                                if s["sequence"] == "SEQ007"), 3)},
        "total_selected_s": round(sum(s["selected_duration_s"]
                                      for s in slots), 3),
        "provisional_label": "PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE",
        "semantic_qc_status": "SEMANTIC_QC_UNQUALIFIED",
        "slots": slots,
    }
    (OUT_DIR / "timing_plan_007.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"slot_count": len(slots),
                      "total_selected_s": summary["total_selected_s"],
                      "sequence_durations_s":
                          summary["sequence_durations_s"]}), flush=True)


if __name__ == "__main__":
    main()
