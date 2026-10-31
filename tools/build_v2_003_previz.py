"""AI-FILM-QUALITY-V2-003 — Phase 9: deterministic spatial previz.

Renders a BlockingSpec (JSON) into planning evidence with NO external
AI and NO video generation:

  <out>/BLOCKING_TOPDOWN.png      2D blocking map (zones, path, crossing)
  <out>/START_FRAME_SCHEMATIC.png start spatial state
  <out>/END_FRAME_SCHEMATIC.png   end spatial state
  <out>/BLOCKING_PREVIZ.mp4       the three cards assembled (if ffmpeg)

Usage:
  python tools/build_v2_003_previz.py <blocking_spec.json> <out_dir> <title>

This is planning evidence only — never canonical media. The F2 previz
artifacts require the F2 Director plan (BLOCKED_ON_DIRECTOR_MODEL);
tests prove the renderer on a clearly-labeled synthetic fixture.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT = "C:/Windows/Fonts/arial.ttf"


def _font(size):
    # Windows workstation font first (keeps existing pinned renders stable);
    # portable fallbacks so the renderer also works on Linux/CI.
    for candidate in (FONT, "DejaVuSans.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _zone_x(waypoint_zones, zone):
    """Deterministic left-to-right slot by first waypoint occurrence."""
    ordered = []
    for z in waypoint_zones:
        top = z.split(":")[0]
        if top not in ordered:
            ordered.append(top)
    return ordered.index(zone.split(":")[0]) / max(len(ordered) - 1, 1)


def render_topdown(blocking: dict, out: Path, title: str) -> Path:
    img = Image.new("RGB", (W, H), "#101418")
    d = ImageDraw.Draw(img)
    wp = [w["zone"] for w in blocking["travel_path"]["ordered_waypoints"]]
    lane_y = H // 2
    xs = {}
    ordered_tops = []
    for z in wp:
        top = z.split(":")[0]
        if top not in ordered_tops:
            ordered_tops.append(top)
    n = max(len(ordered_tops) - 1, 1)
    for i, top in enumerate(ordered_tops):
        xs[top] = 120 + int((W - 240) * i / n)
    # zones
    for top, x in xs.items():
        color = "#3d5a80" if top == blocking["start_zone"] else (
            "#40916c" if top == blocking["end_zone"].split(":")[0]
            else "#6c757d")
        d.rounded_rectangle([x - 110, lane_y - 70, x + 110, lane_y + 70],
                            radius=14, outline=color, width=4)
        d.text((x, lane_y - 88), top, font=_font(22), fill="white",
               anchor="mm")
    # forbidden zones strip
    fz = blocking.get("forbidden_zones") or []
    if fz:
        d.text((W // 2, lane_y + 130),
               "FORBIDDEN ZONES: " + ", ".join(fz), font=_font(20),
               fill="#e63946", anchor="mm")
    # travel path
    points = [(xs[z.split(":")[0]], lane_y) for z in wp]
    d.line(points, fill="#ffd166", width=6)
    for (x, y) in points:
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill="#ffd166")
    # crossing threshold
    crossing = blocking["travel_path"]["required_crossing"]
    crossing_wp = next((w for w in
                        blocking["travel_path"]["ordered_waypoints"]
                        if w.get("is_crossing")), None)
    if crossing_wp:
        cx = xs[crossing_wp["zone"].split(":")[0]]
        for y in range(lane_y - 200, lane_y + 200, 18):
            d.line([(cx, y), (cx, y + 9)], fill="#f4a261", width=4)
        d.text((cx, lane_y - 230),
               f"THRESHOLD: {crossing}", font=_font(22), fill="#f4a261",
               anchor="mm")
    # direction arrow
    if len(points) >= 2:
        (x0, _), (x1, _) = points[0], points[-1]
        mid = lane_y - 150
        d.line([(x0, mid), (x1 - (14 if x1 > x0 else -14), mid)],
               fill="#ffd166", width=4)
        d.polygon([(x1, mid), (x1 - 18, mid - 10), (x1 - 18, mid + 10)]
                  if x1 > x0 else
                  [(x1, mid), (x1 + 18, mid - 10), (x1 + 18, mid + 10)],
                  fill="#ffd166")
    d.text((W // 2, 44), title, font=_font(30), fill="white", anchor="mm")
    d.text((W // 2, 86),
           f"path={blocking['travel_path']['path_type']}  "
           f"reversal_forbidden={blocking.get('forbidden_reversal')}",
           font=_font(20), fill="#adb5bd", anchor="mm")
    d.text((W // 2, H - 36),
           "PLANNING EVIDENCE ONLY - NOT CANONICAL MEDIA "
           "(QUALITY-V2-003 previz)",
           font=_font(18), fill="#adb5bd", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def render_schematic(blocking: dict, out: Path, title: str,
                     side: str) -> Path:
    img = Image.new("RGB", (W, H), "#1b263b")
    d = ImageDraw.Draw(img)
    d.text((W // 2, 40), title, font=_font(28), fill="white", anchor="mm")
    # gate posts
    d.rectangle([W // 2 - 40, 160, W // 2 - 10, 560], fill="#495057")
    d.rectangle([W // 2 + 10, 160, W // 2 + 40, 560], fill="#495057")
    d.text((W // 2, 140), "GATE", font=_font(20), fill="#adb5bd",
           anchor="mm")
    # subject
    subject_x = 240 if side == "START" else W - 240
    d.ellipse([subject_x - 26, 330, subject_x + 26, 382], fill="#e9c46a")
    d.rectangle([subject_x - 16, 382, subject_x + 16, 500],
                fill="#e9c46a")
    d.text((subject_x, 540), "SUBJECT", font=_font(18), fill="#e9c46a",
           anchor="mm")
    label = blocking["start_zone"] if side == "START" \
        else blocking["end_zone"]
    d.text((subject_x, 300), label, font=_font(22), fill="white",
           anchor="mm")
    # travel direction arrow across the gate
    arrow_y = 430
    x0, x1 = (300, W - 300)
    d.line([(x0, arrow_y), (x1 - 16, arrow_y)], fill="#ffd166", width=6)
    d.polygon([(x1, arrow_y), (x1 - 20, arrow_y - 12),
               (x1 - 20, arrow_y + 12)], fill="#ffd166")
    d.text((W // 2, arrow_y - 40),
           blocking["travel_path"]["required_crossing"], font=_font(20),
           fill="#f4a261", anchor="mm")
    d.text((W // 2, H - 60),
           f"screen_direction: {blocking['screen_direction']}",
           font=_font(20), fill="#adb5bd", anchor="mm")
    d.text((W // 2, H - 28),
           "PLANNING EVIDENCE ONLY - NOT CANONICAL MEDIA",
           font=_font(18), fill="#adb5bd", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def main() -> int:
    spec_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) > 3 else "BLOCKING PREVIZ"
    prefix = sys.argv[4] if len(sys.argv) > 4 else ""
    blocking = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    topdown = render_topdown(blocking,
                             out_dir / f"{prefix}BLOCKING_TOPDOWN.png",
                             title)
    start = render_schematic(
        blocking, out_dir / f"{prefix}START_FRAME_SCHEMATIC.png", title,
        "START")
    end = render_schematic(
        blocking, out_dir / f"{prefix}END_FRAME_SCHEMATIC.png", title,
        "END")
    mp4 = out_dir / f"{prefix}BLOCKING_PREVIZ.mp4"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-loop", "1", "-t", "3", "-i", str(start),
             "-loop", "1", "-t", "3", "-i", str(topdown),
             "-loop", "1", "-t", "3", "-i", str(end),
             "-filter_complex",
             "[0:v]scale=1280:720,setsar=1[a];[1:v]scale=1280:720,"
             "setsar=1[b];[2:v]scale=1280:720,setsar=1[c];"
             "[a][b][c]concat=n=3:v=1:a=0[vout]",
             "-map", "[vout]", "-an", "-c:v", "libx264", "-preset",
             "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "24",
             str(mp4)], check=True)
    except (subprocess.CalledProcessError, OSError):
        mp4 = None
    produced = {"topdown": str(topdown), "start": str(start),
                "end": str(end), "mp4": str(mp4) if mp4 else None}
    print(json.dumps({"produced": produced}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
