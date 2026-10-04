"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phase 7): immutable baseline
motion evidence for the canonical F2C and G3C takes.

Dense deterministic frame packets (10 fps over the relevant action
window) extracted read-only from the exact canonical assets. Baseline
worker motion observations are advisory only. No retrospective prompt
changes; the canonical takes stay untouched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.motion_qc import (build_motion_packet,
                                     record_motion_observations)

D17 = ROOT / "projects/flow_performance_motion_canary_017"
PACKETS = D17 / "motion_packets"

BASELINES = [
    {
        "packet_id": "MOT-Q017-BASE-F2C",
        "subject_label": "canonical SEQ7_F2 (F2C) baseline",
        "video": ROOT / "projects/flow_upload_contract_requal_009/reproof/"
                 "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
                 "c1a69047933565230870ad22.mp4",
        "asset_sha256": "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8"
                        "c39898254890a767",
        "trim": (0.4, 4.4),
    },
    {
        "packet_id": "MOT-Q017-BASE-G3C",
        "subject_label": "canonical SEQ7_G3 (G3C) baseline",
        "video": ROOT / "projects/flow_upload_contract_requal_009/reproof/"
                 "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
                 "6013b45645fdffa4fa702278.mp4",
        "asset_sha256": "ffe42e7e9af47e599faa6996807ca1cfea6324343c5abcb90"
                        "6381589bf89a528",
        "trim": (0.0, 3.2),
    },
]


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for baseline in BASELINES:
        video = baseline["video"]
        import hashlib
        actual = hashlib.sha256(video.read_bytes()).hexdigest()
        if actual != baseline["asset_sha256"]:
            raise SystemExit(f"baseline asset hash drift: {video}")
        packet = build_motion_packet(
            packet_id=baseline["packet_id"],
            subject_label=baseline["subject_label"],
            video_path=video, out_base=PACKETS,
            trim_start_s=baseline["trim"][0],
            trim_end_s=baseline["trim"][1], fps=10, created_at=now)
        records.append(packet)
        print(json.dumps({"packet": packet.packet_id,
                          "frames": len(packet.frame_files),
                          "sha": packet.source_asset_sha256[:16]}))
    (D17 / "baseline_motion_packets_017.json").write_text(
        json.dumps({"version": "baseline-motion-packets-017-v1",
                    "packets": [json.loads(
                        Path(p.frame_dir, "packet.json").read_text(
                            encoding="utf-8")) for p in records]},
                   indent=1), encoding="utf-8")
    print("baseline packets frozen:", [p.packet_id for p in records])


if __name__ == "__main__":
    main()
