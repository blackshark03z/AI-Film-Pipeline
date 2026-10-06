"""V2-011B — Phase 2/3: frame-accurate trims + hard-cut proof assembly.

Frame resolution at 24 fps (nearest-frame rule, recorded honestly):
    F2A-R  requested 1.2→4.0   → frames 29→96  (1.208333→4.000000)
    F2B-R  requested 0.4→3.2   → frames 10→77  (0.416667→3.208333)
Hard cut, no dissolve/crossfade/speed-ramp/interpolation. High-quality
re-encode (the only way to cut hevc sources at arbitrary frames); audio
trimmed in sync.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011b_editorial_assembly"
OUT = PKG / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
R11 = ROOT / "projects/quality_v2_011r_targeted_repair/assets"
FPS = 24

CLIPS = {
    "F2A_R_SELECTED.mp4": {
        "source": R11 / "f2a_r.mp4",
        "source_sha256": "50a133c891aaa0060bc1f7d9d6c48c77a3fab1e802bc5f7a4fc43e112404d99b",
        "requested_in": 1.2, "requested_out": 4.0,
        "start_frame": 29, "end_frame": 96,
    },
    "F2B_R_SELECTED.mp4": {
        "source": R11 / "f2b_r.mp4",
        "source_sha256": "8679709b00860a2e3af45354b2166eae2b6d6b365731a278f21809a42babbbff",
        "requested_in": 0.4, "requested_out": 3.2,
        "start_frame": 10, "end_frame": 77,
    },
}

ENC_V = ["-c:v", "libx264", "-crf", "14", "-preset", "slow",
         "-pix_fmt", "yuv420p", "-r", "24"]
ENC_A = ["-c:a", "aac", "-b:a", "192k"]


def run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,"
             "r_frame_rate,nb_frames", "-of", "json", str(path)])
    data = json.loads(r.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {"duration": data.get("format", {}).get("duration"),
            "video_codec": video.get("codec_name"),
            "width": video.get("width"), "height": video.get("height"),
            "fps": video.get("r_frame_rate"),
            "nb_frames": video.get("nb_frames"),
            "audio": [s.get("codec_name") for s in streams
                      if s.get("codec_type") == "audio"]}


def main() -> int:
    records = {}
    for out_name, spec in CLIPS.items():
        out = OUT / out_name
        start_s = spec["start_frame"] / FPS
        dur_frames = spec["end_frame"] - spec["start_frame"]
        dur_s = dur_frames / FPS
        # frame-accurate trim: decode from 0, drop first N frames —
        # -ss before -i is keyframe-imprecise; use the trim filter
        vf = (f"trim=start_frame={spec['start_frame']}:"
              f"end_frame={spec['end_frame']},setpts=PTS-STARTPTS")
        af = (f"atrim=start={start_s:.6f}:duration={dur_s:.6f},"
              f"asetpts=PTS-STARTPTS")
        r = run(["ffmpeg", "-y", "-v", "error", "-i", str(spec["source"]),
                 "-vf", vf, "-af", af, *ENC_V, *ENC_A, str(out)])
        if r.returncode != 0:
            print(json.dumps({"status": "TRIM_FAILED", "shot": out_name,
                              "stderr": r.stderr[-300:]}))
            return 1
        pr = probe(out)
        records[out_name] = {
            "source": str(spec["source"]),
            "source_sha256": spec["source_sha256"],
            "requested_in": spec["requested_in"],
            "requested_out": spec["requested_out"],
            "resolved_start_frame": spec["start_frame"],
            "resolved_end_frame": spec["end_frame"],
            "resolved_in_s": round(start_s, 6),
            "resolved_out_s": round((spec["end_frame"]) / FPS, 6),
            "frames_used": dur_frames,
            "actual_trim_duration_s": round(dur_s, 6),
            "output": str(out), "probe": pr,
            "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        print(json.dumps({"trimmed": out_name, "probe": pr}))

    # ---- hard-cut assembly ------------------------------------------------
    concat_list = OUT / "concat_list.txt"
    concat_list.write_text(
        "file '" + str(OUT / "F2A_R_SELECTED.mp4").replace("'", "'\\''") +
        "'\nfile '" + str(OUT / "F2B_R_SELECTED.mp4").replace("'", "'\\''") +
        "'\n", encoding="utf-8")
    proof = OUT / "F2_SEQUENCE_EDITORIAL_PROOF.mp4"
    r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c:v", "libx264", "-crf", "14",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-r", "24",
             "-c:a", "aac", "-b:a", "192k", str(proof)])
    if r.returncode != 0:
        print(json.dumps({"status": "ASSEMBLY_FAILED",
                          "stderr": r.stderr[-300:]}))
        return 1
    pr = probe(proof)
    proof_sha = hashlib.sha256(proof.read_bytes()).hexdigest()
    manifest = {
        "version": "v2-011b-assembly-v1",
        "checkpoint": "V2011B_P2_P3_TRIM_ASSEMBLY",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "fps_rule": "24 fps nearest-frame boundary resolution",
        "clips": records,
        "proof": {"path": str(proof), "sha256": proof_sha, "probe": pr,
                  "expected_frames": 134,
                  "expected_duration_s": round(134 / FPS, 6),
                  "cut_type": "HARD_CUT"},
    }
    (PKG / "V2_011B_ASSEMBLY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2011B_ASSEMBLED",
                      "proof_sha256": proof_sha[:16],
                      "proof_frames": pr.get("nb_frames"),
                      "proof_duration": pr.get("duration")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
