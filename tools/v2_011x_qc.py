"""V2-011X Phases 3-5 — per-creation technical QC, same-generation
equivalence, and watermark pixel QC. Deterministic; pixels are authority.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
P11R = ROOT / "projects/quality_v2_011r_targeted_repair"
P12 = ROOT / "projects/quality_v2_012_f3r_policy_repair"
PKG = ROOT / "projects/quality_v2_011x_clean_rebind"
FR = PKG / "qc_frames"

PAIRS = [
    {"label": "F1R", "wm": P11D / "assets/f1r.mp4",
     "clean": PKG / "assets/clean/f1r.mp4"},
    {"label": "F2A-R", "wm": P11R / "assets/f2a_r.mp4",
     "clean": PKG / "assets/clean/f2a_r.mp4"},
    {"label": "F2B-R", "wm": P11R / "assets/f2b_r.mp4",
     "clean": PKG / "assets/clean/f2b_r.mp4"},
    {"label": "F3R_012", "wm": P12 / "assets/f3r_012.mp4",
     "clean": PKG / "assets/clean/f3r_012.mp4"},
]
POSITIONS = [0, 10, 25, 50, 75, 90, 100]


def ffprobe_json(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    return json.loads(r.stdout)


def grab(video: Path, t: float, out: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i",
         str(video), "-frames:v", "1", str(out)], capture_output=True)
    return out.exists()


def probe_full(video: Path) -> dict:
    dur = float(ffprobe_json(video)["format"]["duration"])
    st = ffprobe_json(video)["streams"][0]
    dec = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i",
                          str(video), "-f", "null", "-"],
                         capture_output=True).returncode == 0
    pts = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "frame=pts_time", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True)
    ts = [float(x) for x in pts.stdout.replace(",", "").split() if x.strip()]
    fps = eval(st["r_frame_rate"], {"__builtins__": {}}) if "/" in st["r_frame_rate"] else float(st["r_frame_rate"])
    gaps = [i for i in range(1, len(ts))
            if abs(ts[i] - ts[i - 1] - 1 / fps) > 1e-6] if ts else []
    blk = subprocess.run(["ffmpeg", "-i", str(video), "-vf",
                          "blackdetect=d=0.04:pix_th=0.10", "-an", "-f",
                          "null", "-"], capture_output=True, text=True)
    frz = subprocess.run(["ffmpeg", "-i", str(video), "-vf",
                          "freezedetect=n=0.001:d=0.3", "-an", "-f", "null",
                          "-"], capture_output=True, text=True)
    return {"duration_s": dur, "fps": st["r_frame_rate"],
            "frames": int(st["nb_frames"]), "resolution":
                f'{st["width"]}x{st["height"]}', "codec": st["codec_name"],
            "decode_pass": dec, "timestamp_discontinuities": len(gaps),
            "black_frames": "blackdetect" in blk.stderr,
            "frozen_frames": "freeze_start" in frz.stderr}


def mad_excluding_watermark(a: Path, b: Path) -> float:
    """Mean absolute difference over the frame EXCLUDING the bottom-right
    watermark region (x>0.70w, y>0.86h). PIL-only (no numpy in this env)."""
    from PIL import Image, ImageChops
    ia = Image.open(a).convert("L")
    ib = Image.open(b).convert("L")
    if ia.size != ib.size:
        return 255.0
    w, h = ia.size
    diff = ImageChops.difference(ia, ib)
    # keep everything except the bottom-right watermark box: split into
    # three strips that avoid (x>0.70w AND y>0.86h)
    top = diff.crop((0, 0, w, int(h * 0.86)))
    bl = diff.crop((0, int(h * 0.86), int(w * 0.70), h))
    data = list(top.getdata()) + list(bl.getdata())
    return sum(data) / max(1, len(data))


def watermark_region_luma(path: Path) -> float:
    """95th-percentile luma of the bottom-right watermark box (bright text
    => elevated). PIL-only."""
    from PIL import Image
    im = Image.open(path).convert("L")
    w, h = im.size
    crop = im.crop((int(w * 0.72), int(h * 0.86), int(w * 0.97), int(h * 0.99)))
    data = sorted(crop.getdata())
    return float(data[int(len(data) * 0.95)])


def main() -> int:
    FR.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    report = {"version": "v2-011x-qc-v1", "pairs": []}
    for pair in PAIRS:
        label = pair["label"]
        wm, clean = pair["wm"], pair["clean"]
        entry = {"label": label}
        entry["technical_watermarked"] = probe_full(wm)
        entry["technical_clean"] = probe_full(clean)
        tw, tc = entry["technical_watermarked"], entry["technical_clean"]
        entry["technical_compatible"] = (
            tw["duration_s"] == tc["duration_s"] and
            tw["frames"] == tc["frames"] and
            tw["resolution"] == tc["resolution"] and
            tw["fps"] == tc["fps"])
        # equivalence frames
        dur = tc["duration_s"]
        mads = []
        wm_lumas, clean_lumas = [], []
        for p in POSITIONS:
            t = 0.0 if p == 0 else min(dur - 0.125, dur * p / 100)
            fw = FR / f"{label.replace('-','')}_wm_{p:03d}.png"
            fc = FR / f"{label.replace('-','')}_cl_{p:03d}.png"
            grab(wm, t, fw)
            grab(clean, t, fc)
            if fw.exists() and fc.exists():
                mads.append(round(mad_excluding_watermark(fw, fc), 3))
                wm_lumas.append(round(watermark_region_luma(fw), 1))
                clean_lumas.append(round(watermark_region_luma(fc), 1))
        entry["equivalence_mad_excluding_watermark_region"] = mads
        entry["equivalence_mad_max"] = max(mads) if mads else None
        entry["watermark_region_p95_luma_watermarked"] = wm_lumas
        entry["watermark_region_p95_luma_clean"] = clean_lumas
        # the mark is bright text: wm p95 clearly elevated vs clean background
        delta = [round(w - c, 1) for w, c in zip(wm_lumas, clean_lumas)]
        entry["watermark_region_p95_delta"] = delta
        entry["WATERMARK_VERDICT_clean"] = (
            "WATERMARK_ABSENT" if all(d > 25 for d in delta) else
            "WATERMARK_AMBIGUOUS")
        entry["SAME_GENERATION_EQUIVALENCE"] = (
            "PROVEN" if entry["equivalence_mad_max"] is not None and
            entry["equivalence_mad_max"] < 8 and entry["technical_compatible"]
            else "REVIEW")
        report["pairs"].append(entry)
        print(label, "| MAD max:", entry["equivalence_mad_max"],
              "| wm-delta:", delta, "|",
              entry["SAME_GENERATION_EQUIVALENCE"],
              entry["WATERMARK_VERDICT_clean"])
    (PKG / "V2_011X_QC_RESULTS.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote V2_011X_QC_RESULTS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
