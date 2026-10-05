"""AI-FILM-QUALITY-V2-006 — Phase 9 technical evidence: per-shot strips,
identity 3-way grid (canonical F2 / F2A / F2B), and the PAIR join
(F2A 2.8s + F2B 2.8s) used by P12 and the review surface."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_006_f2_decomposed_live"
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")
F2A_VIDEO = PKG / ("scene_SCENE_F_STORM_GATE/shot_SEQ7_F2A_V2_006/"
                   "videos")
F2B_VIDEO = PKG / ("scene_SCENE_F_FAR_SIDE/shot_SEQ7_F2B_V2_006/videos")


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def only_mp4(d: Path) -> Path:
    return sorted(d.glob("*.mp4"))[0]


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
    f2a, f2b = only_mp4(F2A_VIDEO), only_mp4(F2B_VIDEO)
    report = {"version": "v2-006-technical-evidence-v1",
              "checkpoint": "V2006_P9_TECH_QC", "shots": {}}
    for cid, video in (("F2A", f2a), ("F2B", f2b)):
        probe = ffprobe(video)
        times = [round(0.2 + 0.4 * i, 1) for i in range(8)]
        s = ev / f"strip_{cid}.png"
        strip(video, times, s, 4)
        report["shots"][cid] = {
            "video": str(video.relative_to(ROOT)),
            "sha256": file_sha(video),
            "ffprobe": probe,
            "full_decode": full_decode(video),
            "usable_window_s": [0.0, 2.8],
            "strip_times_s": times, "strip": s.name}
    # identity 3-way grid: canonical / F2A / F2B at matched beats
    inputs, filters = [], []
    rows = []
    labels = [("BASELINE", BASELINE_F2), ("F2A", f2a), ("F2B", f2b)]
    times = [0.2, 1.4, 2.4]
    idx = 0
    for label, video in labels:
        for t in times:
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
    sheet = ev / "identity_grid_v2_006.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters) + ";" + grid + layout,
         "-map", "[out]", "-update", "1", str(sheet)], check=True)
    report["identity_grid"] = sheet.name
    # PAIR join (P12 basis + review artifact): 2.8s + 2.8s with a CUT
    pair = PKG / "NEW_F2_PAIR.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-i", str(f2a), "-i", str(f2b),
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
    (PKG / "technical_qc_v2_006.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2006_P9_TECH_QC",
                      "shots": {c: {"decode":
                                    report["shots"][c]["full_decode"],
                                    "dur":
                                    report["shots"][c]["ffprobe"][
                                        "duration_s"]}
                                for c in report["shots"]},
                      "pair_sha": report["pair_join"]["sha256"][:16]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
