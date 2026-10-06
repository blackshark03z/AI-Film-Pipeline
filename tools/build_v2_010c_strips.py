"""010C: extract frame strips from F2 assets for the owner review packet."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
ASSETS = PKG / "assets"
REVIEW = PKG / "owner_review"
REVIEW.mkdir(exist_ok=True)


def strip_for(video: Path, shot: str, times=(0.5, 2.5, 5.0, 7.5, 9.5)) -> list:
    rows = []
    for i, t in enumerate(times, 1):
        out = REVIEW / f"{shot}_t{str(t).replace('.', '_')}.png"
        result = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(video),
             "-frames:v", "1", str(out)], capture_output=True)
        if result.returncode == 0 and out.exists():
            rows.append({"t_s": t, "file": out.name})
    return rows


def main() -> int:
    manifest = {"version": "v2-010c-owner-review-strips-v1", "shots": {}}
    for shot in ("f2a", "f2b"):
        videos = sorted(ASSETS.glob(f"{shot}_*.mp4"))
        if not videos:
            continue
        manifest["shots"][shot] = {
            "video": videos[-1].name,
            "frames": strip_for(videos[-1], shot.upper())}
    (REVIEW / "strips_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010C_STRIPS_BUILT",
                      "shots": {k: len(v.get("frames", []))
                                for k, v in manifest["shots"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
