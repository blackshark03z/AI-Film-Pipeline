"""FLOW-PERFORMANCE-MOTION-CANARY-017 (Phases 14-15): the Owner
side-by-side motion comparison reel + the Owner decision template.

The reel presents F2C BASELINE -> B (motion-only) -> C (combined), then
G3C BASELINE -> D (combined), trimmed to each shot's editorial range,
with minimal segment labels only (no worker verdicts anywhere). The
candidate A is absent (provider-side failure, no output). The canonical
master is not touched. No candidate is promoted by anything here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D17 = ROOT / "projects/flow_performance_motion_canary_017"
REEL = D17 / "OWNER_MOTION_COMPARE_REEL_017.mp4"
FONT = "C\\:/Windows/Fonts/arial.ttf"

SEGMENTS = [
    {"label": "F2C BASELINE", "video": ROOT /
     "projects/flow_upload_contract_requal_009/reproof/"
     "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
     "c1a69047933565230870ad22.mp4",
     "asset_sha256": "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c3989"
                     "8254890a767",
     "trim": (0.0, 5.6), "candidate": "F2C-BASELINE (canonical)",
     "job_id": "job_9b52476a10e4284086ea604967ed43c75d454642f6b4b4a5a99450"
               "a0c5f1ade5"},
    {"label": "B MOTION-ONLY", "video": D17 /
     "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_B/videos/"
     "9dde513caff34ed5979bef13.mp4", "trim": (0.0, 5.6),
     "candidate": "F2C-P017-B", "job_id": "job_ed72ee8d1ad373b9"},
    {"label": "C COMBINED", "video": D17 /
     "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C/videos/"
     "b104f61c4424cf3e0e564323.mp4", "trim": (0.0, 5.6),
     "candidate": "F2C-P017-C", "job_id": "job_579be6d43ed40c99"},
    {"label": "G3C BASELINE", "video": ROOT /
     "projects/flow_upload_contract_requal_009/reproof/"
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
     "6013b45645fdffa4fa702278.mp4",
     "asset_sha256": "ffe42e7e9af47e599faa6996807ca1cfea6324343c5abcb9063"
                     "81589bf89a528",
     "trim": (0.0, 3.2), "candidate": "G3C-BASELINE (canonical)",
     "job_id": "job_fa40f8bf5cdad57b3d4fbb7b00af3a0f3d0ddfbc432e3b50c4c57"
               "d0c3bf93208"},
    {"label": "D COMBINED", "video": D17 /
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D/videos/"
     "23eadf3f247614c52d4cb5a6.mp4", "trim": (0.0, 3.2),
     "candidate": "G3C-P017-D", "job_id": "job_529aaad9f011d718"},
]


def full_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    # resolve full job ids for B/C/D from their frozen intents
    for seg in SEGMENTS:
        if len(seg["job_id"]) < 40:
            shot_dir = seg["video"].parent.parent
            intent = json.loads((shot_dir / "frozen_intent.json")
                                .read_text(encoding="utf-8"))
            seg["job_id"] = intent["provider_job_id"]
        if "asset_sha256" not in seg:
            seg["asset_sha256"] = full_sha(seg["video"])

    inputs, filters = [], []
    for i, seg in enumerate(SEGMENTS):
        inputs += ["-i", str(seg["video"])]
        start, end = seg["trim"]
        filters.append(
            f"[{i}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,"
            f"drawtext=fontfile='{FONT}':text='{seg['label']}':"
            f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.55:"
            f"boxborderw=12:x=24:y=24[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(SEGMENTS)))
    filters.append(f"{concat}concat=n={len(SEGMENTS)}:v=1:a=0[vout]")
    REEL.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "24", str(REEL)], check=True)

    reel_sha = full_sha(REEL)
    segments, t = [], 0.0
    for seg in SEGMENTS:
        dur = round(seg["trim"][1] - seg["trim"][0], 3)
        packet_dir = None
        manifest_row = {
            "reel_start_s": round(t, 3), "reel_end_s": round(t + dur, 3),
            "label": seg["label"], "candidate_id": seg["candidate"],
            "asset_sha256": seg["asset_sha256"],
            "provider_job_id": seg["job_id"],
            "trim": {"source_in_s": seg["trim"][0],
                     "source_out_s": seg["trim"][1]}}
        segments.append(manifest_row)
        t += dur

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,avg_frame_rate", "-show_entries",
         "format=duration", "-of", "json", str(REEL)],
        capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(REEL), "-f", "null", "-"],
        capture_output=True, text=True)
    manifest = {
        "version": "owner-motion-compare-manifest-017-v1",
        "reel": {"path": "OWNER_MOTION_COMPARE_REEL_017.mp4",
                 "sha256": reel_sha, "width": info["streams"][0]["width"],
                 "height": info["streams"][0]["height"],
                 "fps": info["streams"][0]["avg_frame_rate"],
                 "duration_s": duration, "audio": "none",
                 "full_decode": decode.returncode == 0 and
                 not decode.stderr.strip()},
        "labels": "minimal segment labels only; no worker verdicts "
                  "displayed; the worker classification lives in "
                  "performance_control_experiment_017.json",
        "absent": {"F2C-P017-A": "provider render failure (not charged); "
                                 "no output exists"},
        "segments": segments,
        "source_rule": "canonical baseline assets + Package-017 candidate "
                       "assets, editorial-range trims, no canonical "
                       "master involvement",
    }
    (D17 / "owner_motion_compare_manifest_017.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"reel_sha256": reel_sha, "duration_s": duration,
                      "segments": len(segments),
                      "full_decode": manifest["reel"]["full_decode"]}))


if __name__ == "__main__":
    main()
