"""V2-011A Phase 1 — deterministic owner review pack.

Frames at t=0..100% (11 per shot) + event frames + contact sheets +
F2A_end/F2B_start side-by-side. Faithful extraction only: no
beautification, no interpolation, no generative modification.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011a_f2_creative_acceptance"
REVIEW = PKG / "owner_review"
ASSETS = {
    "F2A": ROOT / "projects/quality_v2_010c_dola_fullstack/assets/f2a_20261006T014607.mp4",
    "F2B": ROOT / "projects/quality_v2_010e_final_f2b/assets/f2b_010e_reconciled.mp4",
}
DURATIONS = {"F2A": 10.08, "F2B": 5.088}


def ff_frame(video: Path, t: float, out: Path) -> bool:
    # ffmpeg exits 0 WITHOUT writing when the seek lands past the last
    # decodable frame (container duration > real last PTS) — walk back
    for delta in (0.0, 0.04, 0.08, 0.16, 0.24, 0.4):
        attempt = max(0.0, t - delta)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{attempt:.3f}",
             "-i", str(video), "-frames:v", "1", str(out)],
            capture_output=True)
        if out.exists():
            return True
    return False


def montage(paths: list[Path], cols: int, out: Path, label_h: int = 0) -> bool:
    """Simple PIL grid montage (faithful, no filtering)."""
    from PIL import Image, ImageDraw
    imgs = [Image.open(p) for p in paths if p.exists()]
    if not imgs:
        return False
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for i, im in enumerate(imgs):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(70, 70, 70))
        if label_h:
            draw.text((x + 8, y + 4), Path(paths[i]).stem, fill=(255, 255, 80))
    sheet.save(out)
    return True


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    manifest = {"version": "v2-011a-owner-review-pack-v1",
                "built_at": datetime.now(timezone.utc).isoformat(),
                "method": "faithful ffmpeg extraction; PIL montage; no "
                          "beautification/interpolation/generation",
                "shots": {}}
    for shot, video in ASSETS.items():
        frames_dir = REVIEW / f"{shot}_frames"
        frames_dir.mkdir(exist_ok=True)
        duration = DURATIONS[shot]
        entries = []
        for pct in range(0, 101, 10):
            t = duration * pct / 100
            t = min(t, duration - 0.04)  # inside the last frame
            out = frames_dir / f"{shot}_t{pct:03d}.png"
            ok = ff_frame(video, t, out)
            entries.append({"t_s": round(t, 3), "pct": pct,
                            "file": out.name if ok else None})
        manifest["shots"][shot] = {"duration_s": duration,
                                   "frames": entries}
    # side-by-side: F2A end-state vs F2B start-state (the cut junction)
    a_end = REVIEW / "F2A_frames/F2A_t100.png"
    b_start = REVIEW / "F2B_frames/F2B_t000.png"
    from PIL import Image, ImageDraw
    a_im, b_im = Image.open(a_end), Image.open(b_start)
    w, h = a_im.size
    sheet = Image.new("RGB", (w * 2 + 8, h + 28), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    sheet.paste(a_im, (0, 28))
    sheet.paste(b_im, (w + 8, 28))
    draw.text((8, 6), "F2A end (t=10.04s)", fill=(255, 255, 80))
    draw.text((w + 16, 6), "F2B start (t=0.00s)", fill=(120, 255, 120))
    sheet.save(REVIEW / "F2A_F2B_side_by_side.png")

    for shot in ASSETS:
        frames = sorted((REVIEW / f"{shot}_frames").glob("*.png"))
        montage(frames, 4, REVIEW / f"{shot}_contact_sheet.png",
                label_h=1)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    (PKG / "V2_011A_REVIEW_PACK_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {s: len(list((REVIEW / f"{s}_frames").glob("*.png")))
              for s in ASSETS}
    print(json.dumps({"checkpoint": "V2011A_P1_REVIEW_PACK",
                      "frames": counts,
                      "side_by_side": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
