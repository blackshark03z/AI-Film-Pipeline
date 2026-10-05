"""AI-FILM-QUALITY-V2-008 — Phase 9 evidence: technical probe, strips,
identity grid, and the PAIR join (2.8s + 2.8s)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,avg_frame_rate",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True)
    data = json.loads(out.stdout)
    s = next(x for x in data["streams"] if "width" in x)
    return {"duration_s": float(data["format"]["duration"]),
            "width": s["width"], "height": s["height"],
            "fps": s["avg_frame_rate"]}


def full_decode(path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
         "-map", "0:v:0", "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def strip(video, times, out, cols):
    select = "+".join(f"eq(n\\,{int(t * 24)})" for t in times)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
         f"select='{select}',scale=426:-1,tile={cols}x"
         f"{max(len(times) // cols, 1)}", "-frames:v", "1", "-update", "1",
         str(out)], check=True)


def main() -> int:
    ev = PKG / "qc_evidence"
    ev.mkdir(parents=True, exist_ok=True)
    report = {"version": "v2-008-technical-evidence-v1",
              "checkpoint": "V2008_P9_TECH_QC", "shots": {}}
    vids = {}
    for cid, scene, shot in (
            ("F2A", "scene_SCENE_F_STORM_GATE", "SEQ7_F2A_V2_008"),
            ("F2B", "scene_SCENE_F_FAR_SIDE", "SEQ7_F2B_V2_008")):
        r = json.loads((PKG / scene / f"shot_{shot}/result.json")
                       .read_text(encoding="utf-8"))
        video = Path(r["asset"]["uri_or_path"])
        vids[cid] = video
        probe = ffprobe(video)
        times = [round(0.15 + 0.35 * i, 2) for i in range(8)]
        s = ev / f"strip_{cid}.png"
        strip(video, times, s, 4)
        report["shots"][cid] = {
            "video": str(video.relative_to(ROOT)),
            "sha256": file_sha(video),
            "provider_job_id": r["provider_job_id"],
            "output_identity": r["output_identity"],
            "ffprobe": probe, "full_decode": full_decode(video),
            "usable_window_s": [0.0, 2.8],
            "strip_times_s": times, "strip": s.name}
    inputs, filters = [], []
    idx = 0
    rows = []
    for label, video in (("BASELINE", BASELINE_F2), ("F2A", vids["F2A"]),
                         ("F2B", vids["F2B"])):
        for t in (0.2, 1.4, 2.4):
            inputs += ["-ss", f"{t:.3f}", "-i", str(video)]
            filters.append(
                f"[{idx}:v]scale=426:240,setsar=1,drawtext=fontfile="
                f"'C\\:/Windows/Fonts/arial.ttf':text='{label} t={t}s':"
                f"fontcolor=white:fontsize=22:box=1:boxcolor=black@0.55:"
                f"boxborderw=8[v{idx}]")
            rows.append(idx)
            idx += 1
    grid = "".join(f"[v{i}]" for i in rows)
    layout = ("xstack=inputs=9:layout=0_0|426_0|852_0|0_240|426_240|"
              "852_240|0_480|426_480|852_480[out]")
    sheet = ev / "identity_grid_v2_008.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters) + ";" + grid + layout,
         "-map", "[out]", "-update", "1", str(sheet)], check=True)
    report["identity_grid"] = sheet.name
    pair = PKG / "NEW_F2_PAIR.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(vids["F2A"]),
         "-i", str(vids["F2B"]),
         "-filter_complex",
         "[0:v]trim=start=0:end=2.8,setpts=PTS-STARTPTS,fps=24,"
         "scale=1280:720,setsar=1[a];[1:v]trim=start=0:end=2.8,"
         "setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1[b];"
         "[a][b]concat=n=2:v=1:a=0[vout]",
         "-map", "[vout]", "-an", "-c:v", "libx264", "-preset",
         "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24",
         str(pair)], check=True)
    report["pair_join"] = {"path": str(pair.relative_to(ROOT)),
                           "sha256": file_sha(pair),
                           "probe": ffprobe(pair)}
    (PKG / "technical_qc_v2_008.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P9_TECH_QC",
                      "shots": {c: {
                          "decode": report["shots"][c]["full_decode"],
                          "sha": report["shots"][c]["sha256"][:12]}
                          for c in report["shots"]},
                      "pair_sha": report["pair_join"]["sha256"][:16]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
