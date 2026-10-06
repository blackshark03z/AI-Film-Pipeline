"""V2-011D RESUME — F3R evidence production (technical probe + sheets).

Usage: v2_011d_f3r_evidence.py <acquired:yes>

Builds the F3R contact sheet, the F2->F3R junction sheet, and the full-res
base-junction pair. Palette numbers are measured for the hard QC. Creative
verdicts are recorded by the QC writer after visual inspection.
"""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
C011C = ROOT / "projects/quality_v2_011c_full_sequence_context"
ASSET = PKG / "assets" / "f3r.mp4"
FRAMES = PKG / "frames_f3r"
TARGET = {"luma": 99.10, "u": 141.53, "v": 112.97}  # locked F2 end region


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def measure(video: Path) -> dict:
    out = {}
    for key, sig in (("luma", "YAVG"), ("u", "UAVG"), ("v", "VAVG")):
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video), "-vf",
             f"signalstats,metadata=print:key=lavfi.signalstats.{sig}:file=-",
             "-an", "-f", "null", "-"], capture_output=True, text=True)
        vals = [float(m) for m in re.findall(rf"{sig}=([\d.]+)", r.stdout)]
        out[key] = round(sum(vals) / len(vals), 2) if vals else None
    return out


def sheet(tiles, title, out_path, cols=8):
    TW, TH, LH = 320, 180, 26
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    W = cols * (TW + 4) + 4
    H = 40 + len(rows) * (TH + LH + 4)
    img = Image.new("RGB", (W, H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    d.text((8, 8), title, fill=(255, 220, 120))
    y = 36
    for row in rows:
        for j, (path, label, sub) in enumerate(row):
            im = Image.open(path).convert("RGB").resize((TW, TH), Image.LANCZOS)
            c = Image.new("RGB", (TW, TH + LH), (16, 16, 20))
            c.paste(im, (0, 0))
            dd = ImageDraw.Draw(c)
            dd.text((6, TH + 2), label, fill=(240, 240, 240))
            dd.text((6, TH + 13), sub, fill=(160, 200, 255))
            img.paste(c, (4 + j * (TW + 4), y))
        y += TH + LH + 4
    img.save(out_path)
    print("wrote", out_path)


def main() -> int:
    if not ASSET.exists():
        print("f3r.mp4 not acquired yet")
        return 1
    sha = hashlib.sha256(ASSET.read_bytes()).hexdigest()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration",
         "-of", "json", str(ASSET)], capture_output=True, text=True)
    st = json.loads(probe.stdout)["streams"][0]
    n_frames = int(st["nb_frames"])
    palette = measure(ASSET)
    print(json.dumps({"sha": sha, "probe": st, "palette": palette,
                      "target": TARGET}, indent=1))

    # frames
    FRAMES.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ASSET),
                    "-fps_mode", "passthrough", "-start_number", "0",
                    str(FRAMES / "F3R_%04d.png")], capture_output=True)
    got = len(list(FRAMES.glob("F3R_*.png")))
    print("frames extracted:", got)

    # F3R contact sheet (12 tiles)
    step = max(1, (n_frames - 1) // 11)
    idxs = list(range(0, n_frames, step))[:12]
    if idxs[-1] != n_frames - 1:
        idxs.append(n_frames - 1)
    tiles = [(str(FRAMES / f"F3R_{n:04d}.png"), f"F3R n={n}", f"t={n/24:.2f}s")
             for n in idxs]
    sheet(tiles, "V2-011D F3R (SEQ7_F3_R) contact sheet — sha " + sha[:12] + "…",
          PKG / "owner_review_011d" / "F3R_contact_sheet.png", cols=6)

    # F2->F3R junction sheet: F2 locked end (102-133) vs F3R start (0-23)
    f2_tiles = [(str(C011C / "frames" / f"F2_last_n{n:03d}.png"),
                 f"F2 lock n={n}", f"t={n/24:.2f}s") for n in range(102, 134, 2)]
    f3_tiles = [(str(FRAMES / f"F3R_{n:04d}.png"), f"F3R n={n}", f"t={n/24:.2f}s")
                for n in range(0, 24, 2)]
    sheet(f2_tiles + f3_tiles,
          "F2 end (LOCKED, immutable) frames 102-132 | F3R start frames 0-22 | junction target | F3R IN trim window 0..12",
          PKG / "owner_review_011d" / "F2_F3R_JUNCTION.png", cols=8)

    # full-res base pair: F2 n=133 -> F3R n=0
    a = Image.open(C011C / "frames" / "F2_last_n133.png")
    b = Image.open(FRAMES / "F3R_0000.png")
    cv = Image.new("RGB", (a.width + b.width + 12, 720), (0, 0, 0))
    cv.paste(a, (0, 0))
    cv.paste(b, (a.width + 12, 0))
    cv.save(PKG / "frames" / "PAIR_F2_n133_F3R_n0.png")
    print("wrote frames/PAIR_F2_n133_F3R_n0.png")

    record = {
        "version": "v2-011d-f3r-asset-evidence-v1",
        "recorded_at": utcnow(),
        "asset_sha256": sha,
        "probe": st,
        "frames_extracted": got,
        "palette_measured": palette,
        "palette_target_f2_end_region": TARGET,
        "sheets": ["owner_review_011d/F3R_contact_sheet.png",
                   "owner_review_011d/F2_F3R_JUNCTION.png"],
        "base_pair": "frames/PAIR_F2_n133_F3R_n0.png",
    }
    (PKG / "V2_011D_F3R_ASSET_EVIDENCE.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote V2_011D_F3R_ASSET_EVIDENCE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
