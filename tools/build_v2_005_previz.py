"""AI-FILM-QUALITY-V2-005 — Phase 7: deterministic decomposition previz.

Renders the frozen F2A/F2B plans into planning evidence:
  F2A_BLOCKING_TOPDOWN.png / F2B_BLOCKING_TOPDOWN.png
  F2A_START_END_SCHEMATIC.png / F2B_START_END_SCHEMATIC.png
  F2_DECOMPOSITION_PREVIZ.mp4   (BEFORE_GATE -> CUT -> BEYOND_GATE)
Planning evidence only; no generation.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image, ImageDraw, ImageFont

from build_v2_003_previz import render_schematic, render_topdown

PKG = ROOT / "projects/quality_v2_005_f2_decomposition"
FONT = "C:/Windows/Fonts/arial.ttf"


def cut_card(out: Path) -> None:
    img = Image.new("RGB", (1280, 720), "black")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 64)
    s = ImageFont.truetype(FONT, 28)
    d.text((640, 280), "THE CUT", font=f, fill="white", anchor="mm")
    d.text((640, 380),
           "F2A ends committed AT the threshold",
           font=s, fill="#adb5bd", anchor="mm")
    d.text((640, 430),
           "F2B opens already crossing / just beyond it",
           font=s, fill="#adb5bd", anchor="mm")
    d.text((640, 500), "The audience infers: he crossed.",
           font=s, fill="#ffd166", anchor="mm")
    img.save(out)


def combine(start_png: Path, end_png: Path, out: Path, label: str) -> None:
    a, b = Image.open(start_png), Image.open(end_png)
    canvas = Image.new("RGB", (a.width + b.width + 20, a.height),
                       "#101418")
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width + 20, 0))
    d = ImageDraw.Draw(canvas)
    d.text((canvas.width // 2, 12), label, font=ImageFont.truetype(
        FONT, 30), fill="white", anchor="mm")
    canvas.save(out)


def main() -> int:
    plan = json.loads((PKG / "f2_decomposition_plan_v2_005.json")
                      .read_text(encoding="utf-8"))
    shots = {"F2A": plan["f2a_commit_to_cross"]["blocking"],
             "F2B": plan["f2b_emerge_far_side"]["blocking"]}
    tmp = PKG / "previz_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    produced = {}
    for tag, blocking in shots.items():
        spec_path = tmp / f"{tag}_blocking.json"
        spec_path.write_text(json.dumps(blocking, indent=1),
                             encoding="utf-8")
        subprocess.run(
            [sys.executable, str(ROOT / "tools/build_v2_003_previz.py"),
             str(spec_path), str(tmp),
             f"{tag} BLOCKING PREVIZ (frozen decomposition, V2-005)",
             f"{tag}_"], check=True)
        produced[f"{tag}_BLOCKING_TOPDOWN.png"] = \
            tmp / f"{tag}_BLOCKING_TOPDOWN.png"
        combine(tmp / f"{tag}_START_FRAME_SCHEMATIC.png",
                tmp / f"{tag}_END_FRAME_SCHEMATIC.png",
                tmp / f"{tag}_START_END_SCHEMATIC.png",
                f"{tag}: START (left) -> END (right)")
        produced[f"{tag}_START_END_SCHEMATIC.png"] = \
            tmp / f"{tag}_START_END_SCHEMATIC.png"
    # required names in the package dir
    required = {
        "F2A_BLOCKING_TOPDOWN.png": produced["F2A_BLOCKING_TOPDOWN.png"],
        "F2B_BLOCKING_TOPDOWN.png": produced["F2B_BLOCKING_TOPDOWN.png"],
        "F2A_START_END_SCHEMATIC.png":
            produced["F2A_START_END_SCHEMATIC.png"],
        "F2B_START_END_SCHEMATIC.png":
            produced["F2B_START_END_SCHEMATIC.png"]}
    import hashlib
    shas = {}
    for name, src in required.items():
        dst = PKG / name
        dst.write_bytes(src.read_bytes())
        shas[name] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # decomposition previz: F2A topdown -> CUT -> F2B topdown
    card = PKG / "previz_tmp" / "CUT_CARD.png"
    cut_card(card)
    mp4 = PKG / "F2_DECOMPOSITION_PREVIZ.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-loop", "1", "-t", "4", "-i", str(required[
             "F2A_BLOCKING_TOPDOWN.png"]),
         "-loop", "1", "-t", "4", "-i", str(card),
         "-loop", "1", "-t", "4", "-i", str(required[
             "F2B_BLOCKING_TOPDOWN.png"]),
         "-filter_complex",
         "[0:v]scale=1280:720,setsar=1[a];[1:v]scale=1280:720,setsar=1[b];"
         "[2:v]scale=1280:720,setsar=1[c];[a][b][c]concat=n=3:v=1:a=0"
         "[vout]",
         "-map", "[vout]", "-an", "-c:v", "libx264", "-preset",
         "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "24",
         str(mp4)], check=True)
    shas["F2_DECOMPOSITION_PREVIZ.mp4"] = hashlib.sha256(
        mp4.read_bytes()).hexdigest()
    (PKG / "previz_manifest_v2_005.json").write_text(
        json.dumps({"version": "f2-decomposition-previz-manifest-v1",
                    "artifacts": {k: str((PKG / k).relative_to(ROOT))
                                  for k in shas},
                    "sha256": shas,
                    "sequence": ["BEFORE_GATE (F2A)", "CUT",
                                 "BEYOND_GATE (F2B)"]}, indent=1),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2005_P7_PREVIZ_READY",
                      "artifacts": list(shas)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
