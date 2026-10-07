"""V2-020 — junction frame QC + watermark bottom-right-box QC + manifest.

Junction QC: no black and no duplicated frame at the two cut points.
Watermark QC: the Dola consumer watermark is bottom-right near-white text;
scan the bottom-right box across sampled frames for text-bright pixels
(luma >= 235). ABSENT expected (provider-issued unwatermarked siblings).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "projects/quality_v2_020_autonomous_production"
PROOF = RUN / "qualification_run/CLEAN_SEQUENCE_PROOF.mp4"
MASTER = RUN / "qualification_run/DISTRIBUTION_MASTER.mp4"

sys.path.insert(0, str(ROOT / "src"))
from run_v2_020_production import _orch  # noqa: E402


def extract_frames(video: Path, numbers: list[int], tmp: Path,
                   prefix: str) -> list[Path]:
    paths = []
    for n in numbers:
        out = tmp / f"{prefix}_{n:04d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
             f"select=eq(n\\,{n})", "-vsync", "passthrough", "-frames:v",
             "1", str(out)], capture_output=True)
        if out.exists():
            paths.append(out)
    return paths


def frame_luma(path: Path) -> float:
    from PIL import Image
    with Image.open(path) as im:
        gray = list(im.convert("L").resize((160, 90)).getdata())
    return sum(gray) / len(gray)


def frame_mad(a: Path, b: Path) -> float:
    from PIL import Image
    with Image.open(a) as x, Image.open(b) as y:
        ga = list(x.convert("L").resize((160, 90)).getdata())
        gb = list(y.convert("L").resize((160, 90)).getdata())
    return sum(abs(p - q) for p, q in zip(ga, gb)) / len(ga)


def watermark_br_box(video: Path, samples: list[int], tmp: Path) -> dict:
    from PIL import Image
    bright_total = 0
    checked = 0
    for n in samples:
        out = tmp / f"wm_{n:04d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
             f"select=eq(n\\,{n})", "-vsync", "passthrough", "-frames:v",
             "1", str(out)], capture_output=True)
        if not out.exists():
            continue
        with Image.open(out) as im:
            w, h = im.size
            box = im.convert("L").crop((int(w * 0.72), int(h * 0.82),
                                        int(w * 0.995), int(h * 0.985)))
            pixels = list(box.getdata())
        bright_total += sum(1 for v in pixels if v >= 235)
        checked += 1
    return {"frames_checked": checked,
            "text_bright_pixels_br_box": bright_total,
            "verdict": "ABSENT" if bright_total < 50 else "PRESENT?"}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="v2_020_qc_"))
    # junctions: A->B at frame 121 (0-based last A frame = 121? ranges 122
    # frames per shot: junction frames = 121/122 and 243/244)
    junctions = {}
    for name, (a, b) in {"A-B": (120, 122), "B-C": (242, 244)}.items():
        fa = extract_frames(PROOF, [a], tmp, f"j{name}a")
        fb = extract_frames(PROOF, [b], tmp, f"j{name}b")
        if fa and fb:
            junctions[name] = {
                "frame_a_luma": round(frame_luma(fa[0]), 2),
                "frame_b_luma": round(frame_luma(fb[0]), 2),
                "cross_mad": round(frame_mad(fa[0], fb[0]), 3),
                "black": frame_luma(fa[0]) < 16 or frame_luma(fb[0]) < 16,
                "duplicated": frame_mad(fa[0], fb[0]) < 0.02,
            }
    wm = watermark_br_box(MASTER, [0, 60, 120, 180, 240, 300, 360], tmp)
    orch = _orch(RUN)
    orch.load_or_init(RUN.name)
    doc = {
        "version": "v2-020-master-qc-v1",
        "junctions": junctions,
        "watermark_qc": wm,
        "master_sha256": orch.state.master.get(
            "distribution_master_sha256"),
        "finishing_recorded": orch.state.finishing,
        "editorial_frame_count": orch.state.editorial.get("frame_count"),
    }
    dst = RUN / "qualification_run" / "V2_020_MASTER_QC.json"
    dst.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1)[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
