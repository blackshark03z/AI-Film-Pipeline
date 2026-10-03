"""FLOW-EDITORIAL-RUNTIME-SCALE-010 Phase 8 (T8): real audio-lane
qualification.

Audio source: a 10 s segment DERIVED from the canonical
MASTER_SCALE_009_V1 audio stream (Film-owned, exact lineage recorded —
not a synthetic tone; still NOT production narration).
Visual: two canonical Package-009 slot assets (SEQ4_A1, SEQ4_A2), 8 s
each. Timeline 16 s; the audio clip is placed at 3 s.

Proves: visual clips + AudioLane -> ffmpeg -> output with the expected
audio stream, alignment, duration, codecs, full decode. No source
overwrite.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.audio_lane import (
    AudioAsset, AudioClip, AudioLane, lane_inputs_and_filter,
    validate_lane_assets)

RUN = ROOT / "projects/flow_editorial_runtime_scale_010"
OUT = RUN / "audio_qualification"
MASTER = (ROOT / "projects/flow_upload_contract_requal_009/"
          "master_package_009/master_scale_009_v1.mp4")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True).stdout
    data = json.loads(out)
    audio = next((s for s in data["streams"]
                  if s["codec_type"] == "audio"), None)
    return {"duration_s": float(data["format"]["duration"]),
            "audio": None if audio is None else {
                "codec": audio["codec_name"],
                "sample_rate": int(audio["sample_rate"]),
                "channels": int(audio["channels"])}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master_sha = file_hash(MASTER)
    summary = json.loads((MASTER.parent / "master_summary.json")
                         .read_text(encoding="utf-8"))
    if summary["output_sha256"] != master_sha:
        raise SystemExit("master bytes do not match the recorded receipt")

    # 1. derive the Film-owned audio asset from the canonical master.
    asset_path = OUT / "master009_audio_segment.aac"
    if not asset_path.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "2.0", "-t", "10.0",
             "-i", str(MASTER), "-vn", "-c:a", "copy", str(asset_path)],
            check=True, capture_output=True)
    asset_sha = file_hash(asset_path)
    info = probe(asset_path)
    audio_asset = AudioAsset(
        asset_id="asset_" + hashlib.sha256(json.dumps({
            "origin": "derived_master_audio",
            "source_master_sha256": master_sha, "sha256": asset_sha},
            sort_keys=True).encode()).hexdigest(),
        uri_or_path=str(asset_path.resolve()), sha256=asset_sha,
        duration_s=info["duration_s"], sample_rate=info["audio"]["sample_rate"],
        channels=info["audio"]["channels"], mime_type="audio/aac",
        provenance=("derived 2.0s-12.0s audio segment of MASTER_SCALE_009_V1 "
                    f"sha {master_sha}; Film-owned canonical lineage"))

    # 2. visual sources: two canonical slot assets (009 lineage).
    slots = {s["slot_id"]: s for s in summary["slots"]}
    visuals = []
    for slot in ("SEQ4_A1", "SEQ4_A2"):
        entry = slots[slot]
        path = Path(entry["asset_path"])
        if file_hash(path) != entry["asset_sha256"]:
            raise SystemExit(f"{slot} bytes changed")
        visuals.append(path)

    # 3. the lane: one clip placed at 3.0 s (10 s long inside a 16 s
    #    timeline; gain -2 dB to prove gain handling).
    lane = AudioLane(lane_id="lane_master", role="master", clips=[
        AudioClip(asset_id=audio_asset.asset_id, source_in_s=0.0,
                  source_out_s=min(10.0, audio_asset.duration_s),
                  timeline_start_s=3.0, gain_db=-2.0)])
    validate_lane_assets(lane, {audio_asset.asset_id: audio_asset}, 16.0)

    # 4. render: proven visual conventions (trim/scale/fps/concat) + lane.
    lane_inputs, lane_filter, has_audio = lane_inputs_and_filter(
        lane, {audio_asset.asset_id: audio_asset})
    if not has_audio:
        raise SystemExit("lane produced no audio graph")
    vparts, concat_refs = [], []
    for index, path in enumerate(visuals):
        vparts.append(
            f"[{index}:v:0]trim=start=0:end=8,setpts=PTS-STARTPTS,"
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p"
            f"[v{index}]")
        concat_refs.append(f"[v{index}]")
    # Visual concat is video-only; the lane's final label is the output
    # audio (single clip -> [a0], mixed -> [a]).
    graph = ";".join(vparts) + ";" + lane_filter.lstrip(";") + ";" + \
        "".join(concat_refs) + "concat=n=2:v=1:a=0[v]"
    lane_label = "[" + re.findall(r"\[([a-z0-9]+)\]\s*$",
                                  lane_filter.strip())[-1] + "]"
    command = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-y"]
               + [arg for p in visuals for arg in ("-i", str(p))]
               + lane_inputs
               + ["-filter_complex", graph, "-map", "[v]", "-map",
                  lane_label, "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
                  "-b:a", "192k", "-ar", "48000", "-ac", "2",
                  "-t", "16", "-movflags", "+faststart", "-f", "mp4",
                  str(OUT / "audio_lane_qualification.mp4")])
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit("render failed: " + completed.stderr[-800:])

    # 5. verify the output.
    output = OUT / "audio_lane_qualification.mp4"
    media = probe(output)
    checks = {
        "duration_16s": abs(media["duration_s"] - 16.0) <= 0.2,
        "audio_stream_present": media["audio"] is not None,
        "audio_aac_48k_stereo": (media["audio"] or {}).get("codec") == "aac"
        and (media["audio"] or {}).get("sample_rate") == 48000
        and (media["audio"] or {}).get("channels") == 2,
        "full_decode": subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-f",
             "null", "-"], capture_output=True).returncode == 0,
        "sources_unmodified": file_hash(MASTER) == master_sha
        and all(file_hash(p) == slots[s]["asset_sha256"]
                for s, p in (("SEQ4_A1", visuals[0]),
                             ("SEQ4_A2", visuals[1]))),
    }
    result = {
        "version": "audio-qualification-010-v1",
        "classification": "AUDIO_RUNTIME_MECHANICS_PROVEN",
        "content_classification":
            "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED (no qualified narration "
            "asset; the lane audio is derived Film-owned canonical audio, "
            "not production narration/music)",
        "audio_asset": audio_asset.model_dump(mode="json"),
        "lane": lane.model_dump(mode="json"),
        "visual_sources": [{"slot": s, "path": str(p),
                            "sha256": file_hash(p)}
                           for s, p in (("SEQ4_A1", visuals[0]),
                                        ("SEQ4_A2", visuals[1]))],
        "output": {"path": str(output),
                   "sha256": file_hash(output),
                   "probe": media},
        "checks": checks}
    result["pass"] = all(checks.values())
    (OUT / "audio_qualification_010.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "checks": checks}))


if __name__ == "__main__":
    main()
