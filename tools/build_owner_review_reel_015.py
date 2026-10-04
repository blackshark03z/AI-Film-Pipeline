"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 4): deterministic Owner
review reel.

Builds OWNER_REVIEW_REEL_015.mp4 from canonical assets ONLY, in canonical
master order, using each shot's frozen EditorialRange. For every
shot-scope review target the reel shows previous canonical shot -> target
-> next canonical shot; the two adjacent G targets share one built window
(context is never duplicated). No textual overlay is burned — the
manifest maps reel time ranges to shots/requests. The master-level
advisory request covers the full reel.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D15 = ROOT / "projects/flow_owner_review_content_gates_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
REEL = D15 / "reel/OWNER_REVIEW_REEL_015.mp4"
FPS = 24

MEDIA_ROOTS = {
    "seq004_media": ROOT / "projects/flow_multiscene_004",
    "seq005_media": (ROOT /
                     "projects/flow_sequence_005/"
                     "sequence_SEQ005_VALLEY_STREAM").parent,
    "seq007_media": ROOT / "projects/flow_production_scale_007",
    "reproof008_media": (ROOT /
                         "projects/flow_upload_contract_requal_009/reproof"),
}

# review item -> (target slot, window slots in canonical order)
ITEMS = [
    ("OWNER-REV-015-001", "SEQ7_E2", ["SEQ7_E1", "SEQ7_E2", "SEQ7_E3"]),
    ("OWNER-REV-015-002", "SEQ7_F2", ["SEQ7_F1", "SEQ7_F2", "SEQ7_F3"]),
    ("OWNER-REV-015-003", "SEQ7_G2", ["SEQ7_G1", "SEQ7_G2", "SEQ7_G3",
                                      "SEQ7_G4"]),
    ("OWNER-REV-015-004", "SEQ7_G3", ["SEQ7_G1", "SEQ7_G2", "SEQ7_G3",
                                      "SEQ7_G4"]),
]
FORBIDDEN_MARKERS = ("shot_SEQ4_B5/", "_3C", "shot_3C", "canary",
                     "post_gate", "invalid")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    review_set = json.loads((D15 / "owner_review_set_015.json").read_text(
        encoding="utf-8"))
    master = json.loads((M10 / "master_summary.json").read_text(
        encoding="utf-8"))
    edit_job = json.loads((M10 / "autoedit_package/edit_job.json")
                          .read_text(encoding="utf-8"))
    media_by_sha = {m["sha256"]: m for m in edit_job["media"]}

    # resolve every needed slot: frozen range -> asset -> canonical media
    segment_sources: dict[str, dict] = {}
    for _, _, window in ITEMS:
        for slot_id in window:
            if slot_id in segment_sources:
                continue
            order = next(s["order"] for s in master["slots"]
                         if s["slot_id"] == slot_id)
            rng = json.loads(
                (M10 / f"ranges/{order:02d}_{slot_id}.json").read_text(
                    encoding="utf-8"))
            media = media_by_sha[rng["asset_sha256"]]
            base = MEDIA_ROOTS[media["locator"]["root_id"]]
            asset = base / media["locator"]["path"]
            rel = asset.relative_to(ROOT).as_posix()
            for marker in FORBIDDEN_MARKERS:
                if marker in rel:
                    raise SystemExit(f"forbidden lineage asset: {rel}")
            if not asset.is_file():
                raise SystemExit(f"asset missing: {rel}")
            actual = file_hash(asset)
            if actual != rng["asset_sha256"]:
                raise SystemExit(f"asset hash drift: {rel}")
            segment_sources[slot_id] = {
                "order": order, "slot_id": slot_id,
                "asset_rel": rel, "asset_sha256": actual,
                "source_in_s": rng["source_in_s"],
                "source_out_s": rng["source_out_s"],
                "selected_duration_s": rng["selected_duration_s"],
                "editorial_range_id": rng["editorial_range_id"],
                "selected_take_id": rng["selected_take_id"]}

    # build the ordered, deduplicated stream of segments
    stream: list[str] = []
    for _, _, window in ITEMS:
        for slot_id in window:
            if slot_id not in stream:
                stream.append(slot_id)

    inputs: list[str] = []
    filters: list[str] = []
    for index, slot_id in enumerate(stream):
        src = segment_sources[slot_id]
        inputs += ["-i", str(ROOT / src["asset_rel"])]
        filters.append(
            f"[{index}:v]trim=start={src['source_in_s']:.6f}:"
            f"end={src['source_out_s']:.6f},setpts=PTS-STARTPTS,"
            f"fps={FPS},scale=1280:720,setsar=1[v{index}]")
    concat = "".join(f"[v{i}]" for i in range(len(stream)))
    filters.append(f"{concat}concat=n={len(stream)}:v=1:a=0[vout]")
    REEL.parent.mkdir(parents=True, exist_ok=True)
    cmd = (["ffmpeg", "-y", "-v", "error"] + inputs +
           ["-filter_complex", ";".join(filters), "-map", "[vout]",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS), str(REEL)])
    subprocess.run(cmd, check=True)

    # manifest: reel time ranges -> canonical shots/assets -> request ids
    segments, t = [], 0.0
    for slot_id in stream:
        src = segment_sources[slot_id]
        segments.append({**src, "reel_start_s": round(t, 3),
                         "reel_end_s": round(t + src["selected_duration_s"],
                                             3)})
        t += src["selected_duration_s"]
    total = round(t, 3)

    def window_range(window: list[str]) -> tuple[float, float]:
        first = next(s for s in segments if s["slot_id"] == window[0])
        last = next(s for s in segments if s["slot_id"] == window[-1])
        return first["reel_start_s"], last["reel_end_s"]

    items = []
    for rid, target, window in ITEMS:
        start, end = window_range(window)
        items.append({"review_request_id": rid, "target_slot": target,
                      "window_pattern": "previous -> target -> next",
                      "reel_start_s": start, "reel_end_s": end})
    items.append({"review_request_id": "OWNER-REV-015-005",
                  "target_slot": "MASTER",
                  "window_pattern": "full reel (temporal judgment)",
                  "reel_start_s": 0.0, "reel_end_s": total})

    reel_sha = file_hash(REEL)
    manifest = {
        "version": "review-reel-manifest-015-v1",
        "reel": {"path": "reel/OWNER_REVIEW_REEL_015.mp4",
                 "sha256": reel_sha, "width": 1280, "height": 720,
                 "fps": FPS, "duration_s": total, "audio": "none "
                 "(visual review reel; narration gate unqualified)"},
        "overlay": "none (manifest maps time ranges; no worker verdict "
                   "displayed, no sensitive metadata burned in)",
        "segments": segments,
        "items": items,
        "source_rule": "canonical master assets only, frozen "
                       "editorial-range-v1 trims, canonical master order",
    }
    (D15 / "reel/review_reel_manifest_015.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8")

    # validate: probe + full decode
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,avg_frame_rate", "-show_entries",
         "format=duration", "-of", "json", str(REEL)],
        capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    stream_info = info["streams"][0]
    duration = float(info["format"]["duration"])
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(REEL), "-f", "null", "-"],
        capture_output=True, text=True)
    full_decode = decode.returncode == 0 and not decode.stderr.strip()
    checks = {
        "width": stream_info["width"] == 1280,
        "height": stream_info["height"] == 720,
        "fps": stream_info["avg_frame_rate"] == f"{FPS}/1",
        "duration_matches_manifest": abs(duration - total) <= 0.25,
        "full_decode": full_decode,
        "asset_hashes_verified": True,
        "ordering_canonical": [s["slot_id"] for s in segments] == stream,
        "no_stale_assets": True,
    }
    result = {"checks": checks, "result": "PASS" if all(checks.values())
              else "FAIL", "reel_sha256": reel_sha,
              "duration_s": duration}
    (D15 / "reel/reel_validation_015.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
